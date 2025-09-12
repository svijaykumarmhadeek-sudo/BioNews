from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import requests
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage
from newsapi import NewsApiClient
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import re
import feedparser
import yfinance as yf
import pandas as pd

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Biotech News & Stock API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Initialize LLM chat for summarization
llm_key = os.environ.get('EMERGENT_LLM_KEY')
chat = LlmChat(
    api_key=llm_key,
    session_id="biotech-news-summarizer",
    system_message="You are an expert biotech news writer for Inshorts-style app. Create: 1) A concise headline (50-60 characters) and 2) A flowing, natural summary (300-400 characters) that reads like professional journalism. Include key biotech/pharma facts, drug names, companies, clinical phases, and outcomes. Ensure the summary flows naturally, conveys main points clearly, and ends with a complete thought - never cut off abruptly. Write in Inshorts' conversational yet informative style."
).with_model("openai", "gpt-4o")

# News API client
news_api_key = os.environ.get('NEWS_API_KEY')
newsapi = NewsApiClient(api_key=news_api_key) if news_api_key else None

# Categories for biotech news
CATEGORIES = [
    "Academic Research",
    "Industry Updates", 
    "Early Discovery",
    "Clinical Trials",
    "Drug Modalities",
    "Healthcare & Policy"
]

# Real-time RSS feeds for biotech news
RSS_FEEDS = [
    {
        'name': 'FierceBiotech',
        'url': 'https://www.fiercebiotech.com/rss/xml',
        'category': 'Industry Updates'
    },
    {
        'name': 'BioPharma Dive',
        'url': 'https://www.biopharmadive.com/feeds/news/',
        'category': 'Industry Updates'
    },
    {
        'name': 'GenomeWeb',
        'url': 'https://www.genomeweb.com/rss-feeds/all',
        'category': 'Academic Research'
    },
    {
        'name': 'BioWorld',
        'url': 'https://www.bioworld.com/rss/news.xml',
        'category': 'Industry Updates'
    },
    {
        'name': 'Nature Biotechnology',
        'url': 'https://feeds.nature.com/nbt/rss/current',
        'category': 'Academic Research'
    },
    {
        'name': 'BioCentury',
        'url': 'https://www.biocentury.com/rss',
        'category': 'Industry Updates'
    }
]

# Top biotech and pharma stock symbols
BIOTECH_STOCKS = [
    # Large Cap Biotech/Pharma
    'JNJ', 'PFE', 'ABBV', 'MRK', 'BMY', 'LLY', 'TMO', 'ABT', 'AMGN', 'DHR',
    'GILD', 'VRTX', 'REGN', 'BIIB', 'ILMN', 'ISRG', 'ZTS', 'MRNA', 'BNTX',
    
    # Mid Cap Biotech
    'ALNY', 'SGEN', 'INCY', 'EXAS', 'TECH', 'BMRN', 'SRPT', 'RARE', 'BLUE', 'FOLD',
    'ARCT', 'CRSP', 'EDIT', 'NTLA', 'BEAM', 'PRIME', 'VCYT', 'PACB', 'NVTA', 'CDNA',
    
    # Emerging Biotech
    'SANA', 'RPTX', 'VERV', 'CGEM', 'RLAY', 'JANX', 'IRON', 'RAIN', 'FATE', 'XENE',
    'PGEN', 'APLS', 'RGNX', 'MRUS', 'KROS', 'ASND', 'ALLO', 'CHRS', 'RCUS', 'ADPT'
]

# Category mapping for different news sources
CATEGORY_MAPPING = {
    'clinical trial': 'Clinical Trials',
    'fda approval': 'Drug Modalities',
    'biotech': 'Industry Updates',
    'pharmaceutical': 'Industry Updates',
    'drug discovery': 'Early Discovery',
    'research': 'Academic Research',
    'healthcare policy': 'Healthcare & Policy',
    'gene therapy': 'Drug Modalities',
    'cancer treatment': 'Clinical Trials',
    'vaccine': 'Drug Modalities'
}

# Global variable to track last update
last_news_update = datetime.now(timezone.utc)
last_stock_update = datetime.now(timezone.utc)

# Define Models
class Article(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    headline: Optional[str] = None  # Concise 50-60 char headline
    summary: str  # Natural flowing 300-400 char summary
    content: str
    category: str
    source: str
    url: str
    image_url: Optional[str] = None
    published_at: datetime
    keywords: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StockData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    name: str
    current_price: float
    price_change: float
    percent_change: float
    volume: int
    market_cap: Optional[float] = None
    sector: str = "Biotechnology/Pharmaceuticals"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserPreferences(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    preferred_categories: List[str] = []
    watchlist_stocks: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SearchQuery(BaseModel):
    query: str
    category: Optional[str] = None
    limit: int = 20

class SystemStatus(BaseModel):
    last_news_update: datetime
    last_stock_update: datetime
    total_articles: int
    total_stocks: int
    articles_by_category: Dict[str, int]
    top_gainers: List[Dict[str, Any]]
    top_losers: List[Dict[str, Any]]
    next_scheduled_update: Optional[datetime] = None

# News aggregation functions
def categorize_article(title: str, content: str) -> str:
    """Automatically categorize articles based on content"""
    text = (title + " " + content).lower()
    
    # Check for specific keywords
    for keyword, category in CATEGORY_MAPPING.items():
        if keyword in text:
            return category
    
    # Default categorization based on broader keywords
    if any(word in text for word in ['clinical', 'trial', 'patient', 'treatment']):
        return 'Clinical Trials'
    elif any(word in text for word in ['discovery', 'compound', 'molecule']):
        return 'Early Discovery'
    elif any(word in text for word in ['fda', 'approval', 'drug', 'therapy']):
        return 'Drug Modalities'
    elif any(word in text for word in ['policy', 'regulation', 'healthcare']):
        return 'Healthcare & Policy'
    elif any(word in text for word in ['research', 'study', 'university']):
        return 'Academic Research'
    else:
        return 'Industry Updates'

def extract_keywords(title: str, content: str) -> List[str]:
    """Extract relevant keywords from article content"""
    text = (title + " " + content).lower()
    
    # Biotech/pharma specific keywords
    biotech_keywords = [
        'crispr', 'gene therapy', 'car-t', 'immunotherapy', 'mrna', 'vaccine',
        'clinical trial', 'fda approval', 'biomarker', 'precision medicine',
        'antibody', 'protein', 'small molecule', 'biologics', 'biosimilar',
        'oncology', 'neurology', 'cardiology', 'rare disease', 'orphan drug'
    ]
    
    found_keywords = []
    for keyword in biotech_keywords:
        if keyword in text:
            found_keywords.append(keyword)
    
    # Extract additional keywords using regex
    drug_pattern = r'\b[A-Z]{2,}-\d+\b|\b[A-Z][a-z]+\d+\b'
    drug_matches = re.findall(drug_pattern, title + " " + content)
    found_keywords.extend(drug_matches[:3])  # Limit to 3 drug names
    
    return found_keywords[:5]  # Return max 5 keywords

async def fetch_rss_feeds() -> List[Dict]:
    """Fetch real-time news from RSS feeds"""
    articles = []
    
    for feed_info in RSS_FEEDS:
        try:
            logging.info(f"Fetching RSS feed: {feed_info['name']}")
            
            # Parse RSS feed
            feed = feedparser.parse(feed_info['url'])
            
            if feed.bozo:
                logging.warning(f"Feed parsing issues for {feed_info['name']}: {feed.bozo_exception}")
                continue
                
            # Process feed entries
            for entry in feed.entries[:5]:  # Limit to 5 articles per feed
                try:
                    # Extract content
                    content = ""
                    if hasattr(entry, 'summary'):
                        content = entry.summary
                    elif hasattr(entry, 'description'):
                        content = entry.description
                    elif hasattr(entry, 'content') and entry.content:
                        content = entry.content[0].value if isinstance(entry.content, list) else entry.content
                    
                    # Clean HTML tags
                    if content:
                        soup = BeautifulSoup(content, 'html.parser')
                        content = soup.get_text().strip()
                    
                    # Parse publication date
                    pub_date = datetime.now(timezone.utc)
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                    
                    # Skip articles older than 7 days
                    if (datetime.now(timezone.utc) - pub_date).days > 7:
                        continue
                    
                    articles.append({
                        'title': entry.title,
                        'content': content[:1000],  # Limit content length
                        'category': feed_info.get('category', categorize_article(entry.title, content)),
                        'source': feed_info['name'],
                        'url': entry.link,
                        'image_url': get_feed_image(entry),
                        'published_at': pub_date,
                        'keywords': extract_keywords(entry.title, content)
                    })
                    
                except Exception as e:
                    logging.warning(f"Error processing RSS entry from {feed_info['name']}: {e}")
                    continue
                    
            await asyncio.sleep(1)  # Rate limiting between feeds
            
        except Exception as e:
            logging.error(f"Error fetching RSS feed {feed_info['name']}: {e}")
            continue
    
    logging.info(f"Fetched {len(articles)} articles from RSS feeds")
    return articles

def get_feed_image(entry) -> str:
    """Extract image from RSS entry"""
    default_images = [
        "https://images.unsplash.com/photo-1581594549595-35f6edc7b762?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzh8MHwxfHNlYXJjaHwxfHxiaW90ZWNofGVufDB8fHx8MTc1NzY5Nzg2Mnww&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1578496480240-32d3e0c04525?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzh8MHwxfHNlYXJjaHw0fHxiaW90ZWNofGVufDB8fHx8MTc1NzY5Nzg2Mnww&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1576671081837-49000212a370?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDN8MHwxfHNlYXJjaHwyfHxwaGFybWFjZXV0aWNhbHxlbnwwfHx8fDE3NTc2OTc4Njd8MA&ixlib=rb-4.1.0&q=85"
    ]
    
    # Try to extract image from entry
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0]['url']
    elif hasattr(entry, 'enclosures') and entry.enclosures:
        for enclosure in entry.enclosures:
            if enclosure.type.startswith('image/'):
                return enclosure.href
    
    # Return random default image
    import random
    return random.choice(default_images)

async def fetch_stock_data() -> List[Dict]:
    """Fetch biotech/pharma stock data"""
    stock_data = []
    
    try:
        logging.info("Fetching biotech/pharma stock data...")
        
        # Fetch data in batches to avoid API limits
        batch_size = 10
        for i in range(0, len(BIOTECH_STOCKS), batch_size):
            batch = BIOTECH_STOCKS[i:i + batch_size]
            
            try:
                # Download stock data
                tickers = yf.Tickers(' '.join(batch))
                
                for symbol in batch:
                    try:
                        ticker = tickers.tickers[symbol]
                        
                        # Get current info
                        info = ticker.info
                        hist = ticker.history(period="2d")
                        
                        if hist.empty or len(hist) < 2:
                            continue
                        
                        current_price = hist['Close'][-1]
                        previous_price = hist['Close'][-2]
                        price_change = current_price - previous_price
                        percent_change = (price_change / previous_price) * 100
                        
                        stock_data.append({
                            'symbol': symbol,
                            'name': info.get('longName', symbol),
                            'current_price': round(float(current_price), 2),
                            'price_change': round(float(price_change), 2),
                            'percent_change': round(float(percent_change), 2),
                            'volume': int(hist['Volume'][-1]) if not pd.isna(hist['Volume'][-1]) else 0,
                            'market_cap': info.get('marketCap'),
                            'sector': 'Biotechnology/Pharmaceuticals'
                        })
                        
                    except Exception as e:
                        logging.warning(f"Error fetching data for {symbol}: {e}")
                        continue
                
                await asyncio.sleep(1)  # Rate limiting between batches
                
            except Exception as e:
                logging.error(f"Error fetching batch {batch}: {e}")
                continue
        
        logging.info(f"Fetched data for {len(stock_data)} stocks")
        return stock_data
        
    except Exception as e:
        logging.error(f"Error in fetch_stock_data: {e}")
        return []

async def fetch_pubmed_articles(max_articles: int = 8) -> List[Dict]:
    """Fetch latest biotech articles from PubMed"""
    articles = []
    
    try:
        # PubMed search terms for biotech/pharma
        search_terms = [
            "biotechnology[Title/Abstract] AND 2024[Date - Publication]",
            "pharmaceutical[Title/Abstract] AND clinical trial[Title/Abstract] AND 2024[Date - Publication]"
        ]
        
        for search_term in search_terms:
            # Search PubMed
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': search_term,
                'retmax': max_articles // 2,
                'retmode': 'xml'
            }
            
            search_response = requests.get(search_url, params=search_params, timeout=10)
            if search_response.status_code != 200:
                continue
                
            # Parse search results
            search_root = ET.fromstring(search_response.content)
            pmids = [id_elem.text for id_elem in search_root.findall('.//Id')]
            
            if not pmids:
                continue
                
            # Fetch article details
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids[:3]),  # Limit to 3 articles per search
                'retmode': 'xml'
            }
            
            fetch_response = requests.get(fetch_url, params=fetch_params, timeout=15)
            if fetch_response.status_code != 200:
                continue
                
            # Parse article details
            root = ET.fromstring(fetch_response.content)
            
            for article_elem in root.findall('.//PubmedArticle'):
                try:
                    title_elem = article_elem.find('.//ArticleTitle')
                    abstract_elem = article_elem.find('.//AbstractText')
                    journal_elem = article_elem.find('.//Journal/Title')
                    date_elem = article_elem.find('.//PubDate')
                    pmid_elem = article_elem.find('.//PMID')
                    
                    if title_elem is not None and abstract_elem is not None:
                        title = title_elem.text or "No title available"
                        abstract = abstract_elem.text or "No abstract available"
                        journal = journal_elem.text if journal_elem is not None else "PubMed Journal"
                        pmid = pmid_elem.text if pmid_elem is not None else "unknown"
                        
                        # Parse publication date
                        pub_date = datetime.now(timezone.utc)
                        if date_elem is not None:
                            year_elem = date_elem.find('Year')
                            month_elem = date_elem.find('Month')
                            day_elem = date_elem.find('Day')
                            
                            if year_elem is not None:
                                year = int(year_elem.text)
                                month = int(month_elem.text) if month_elem is not None else 1
                                day = int(day_elem.text) if day_elem is not None else 1
                                pub_date = datetime(year, month, day, tzinfo=timezone.utc)
                        
                        articles.append({
                            'title': title,
                            'content': abstract,
                            'category': categorize_article(title, abstract),
                            'source': journal,
                            'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                            'image_url': "https://images.unsplash.com/photo-1578496480240-32d3e0c04525?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzh8MHwxfHNlYXJjaHw0fHxiaW90ZWNofGVufDB8fHx8MTc1NzY5Nzg2Mnww&ixlib=rb-4.1.0&q=85",
                            'published_at': pub_date,
                            'keywords': extract_keywords(title, abstract)
                        })
                        
                except Exception as e:
                    logging.warning(f"Error parsing PubMed article: {e}")
                    continue
                    
            await asyncio.sleep(1)  # Rate limiting
            
    except Exception as e:
        logging.error(f"Error fetching PubMed articles: {e}")
    
    return articles

async def fetch_real_biotech_news() -> List[Dict]:
    """Fetch news from all sources including real-time RSS"""
    all_articles = []
    
    try:
        logging.info("Fetching real biotech news from multiple sources...")
        
        # Fetch from all sources concurrently
        tasks = [
            fetch_rss_feeds(),  # Real-time RSS feeds
            fetch_pubmed_articles(6),  # Reduced to make room for RSS
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
            elif isinstance(result, Exception):
                logging.error(f"Error in news fetching task: {result}")
        
        # Remove duplicates based on title similarity
        unique_articles = []
        seen_titles = set()
        
        for article in all_articles:
            title_key = article['title'].lower()[:50]  # First 50 chars for similarity check
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_articles.append(article)
        
        logging.info(f"Fetched {len(unique_articles)} unique articles from all sources")
        return unique_articles[:30]  # Limit to 30 most recent
        
    except Exception as e:
        logging.error(f"Error in fetch_real_biotech_news: {e}")
        return []

async def summarize_article(content: str, title: str) -> tuple:
    """Use LLM to create Inshorts-style headline and summary"""
    try:
        user_message = UserMessage(text=f"Create Inshorts-style content for this biotech article:\n\nTitle: {title}\nContent: {content}\n\nGenerate:\n1. Concise headline (50-60 characters)\n2. Natural, flowing summary (300-400 characters)\n\nFor the summary: Write like a professional journalist. Include key details (drug names, companies, clinical phases, outcomes) but ensure it flows naturally and ends with a complete thought. No abrupt cut-offs. Make it conversational yet informative, exactly like Inshorts style.\n\nFormat: HEADLINE: [headline]\nSUMMARY: [summary]")
        response = await chat.send_message(user_message)
        
        # Parse the response
        lines = response.strip().split('\n')
        headline = title[:60]  # Fallback
        summary = content[:400] + "..."  # Fallback
        
        for line in lines:
            if line.startswith('HEADLINE:'):
                headline = line.replace('HEADLINE:', '').strip()[:60]
            elif line.startswith('SUMMARY:'):
                summary = line.replace('SUMMARY:', '').strip()[:400]
        
        return headline, summary
        
    except Exception as e:
        logging.error(f"Error creating Inshorts content: {e}")
        # Fallback to truncated versions
        headline = title[:60]
        summary = content[:400] + "..."
        return headline, summary

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Biotech News & Stock API", "version": "3.0.0", "features": ["Real-time RSS Feeds", "Stock Data", "Auto Updates", "Timestamps"]}

@api_router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get system status with last update info and stock data"""
    total_articles = await db.articles.count_documents({})
    total_stocks = await db.stocks.count_documents({})
    
    # Count articles by category
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}
    ]
    category_counts = {}
    async for result in db.articles.aggregate(pipeline):
        category_counts[result["_id"]] = result["count"]
    
    # Get top gainers and losers
    top_gainers_cursor = db.stocks.find().sort("percent_change", -1).limit(5)
    top_losers_cursor = db.stocks.find().sort("percent_change", 1).limit(5)
    
    top_gainers = []
    async for stock in top_gainers_cursor:
        top_gainers.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "percent_change": stock["percent_change"],
            "current_price": stock["current_price"]
        })
    
    top_losers = []
    async for stock in top_losers_cursor:
        top_losers.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "percent_change": stock["percent_change"],
            "current_price": stock["current_price"]
        })
    
    return SystemStatus(
        last_news_update=last_news_update,
        last_stock_update=last_stock_update,
        total_articles=total_articles,
        total_stocks=total_stocks,
        articles_by_category=category_counts,
        top_gainers=top_gainers,
        top_losers=top_losers,
        next_scheduled_update=None
    )

@api_router.get("/stocks", response_model=List[StockData])
async def get_stocks(
    sort_by: str = Query("percent_change", description="Sort by: percent_change, volume, market_cap"),
    order: str = Query("desc", description="Order: asc or desc"),
    limit: int = Query(50, ge=1, le=100, description="Number of stocks to return")
):
    """Get biotech/pharma stock data"""
    sort_order = -1 if order == "desc" else 1
    
    # Validate sort field
    valid_sorts = ["percent_change", "volume", "market_cap", "current_price"]
    if sort_by not in valid_sorts:
        sort_by = "percent_change"
    
    stocks = await db.stocks.find().sort(sort_by, sort_order).limit(limit).to_list(length=None)
    return [StockData(**stock) for stock in stocks]

@api_router.get("/stocks/gainers", response_model=List[StockData])
async def get_top_gainers(limit: int = Query(25, ge=1, le=50)):
    """Get top gaining biotech/pharma stocks"""
    stocks = await db.stocks.find().sort("percent_change", -1).limit(limit).to_list(length=None)
    return [StockData(**stock) for stock in stocks]

@api_router.get("/stocks/losers", response_model=List[StockData])
async def get_top_losers(limit: int = Query(25, ge=1, le=50)):
    """Get top losing biotech/pharma stocks"""
    stocks = await db.stocks.find().sort("percent_change", 1).limit(limit).to_list(length=None)
    return [StockData(**stock) for stock in stocks]

@api_router.get("/categories")
async def get_categories():
    """Get all available news categories"""
    return {"categories": CATEGORIES}

@api_router.get("/articles", response_model=List[Article])
async def get_articles(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100, description="Number of articles to return")
):
    """Get news articles with optional category filter"""
    query = {}
    if category and category in CATEGORIES:
        query["category"] = category
    
    articles = await db.articles.find(query).sort("published_at", -1).limit(limit).to_list(length=None)
    return [Article(**article) for article in articles]

@api_router.get("/articles/{article_id}", response_model=Article)
async def get_article(article_id: str):
    """Get a specific article by ID"""
    article = await db.articles.find_one({"id": article_id})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return Article(**article)

@api_router.post("/articles/migrate")
async def migrate_articles():
    """Migrate existing articles to Inshorts format"""
    try:
        logging.info("Starting article migration to Inshorts format...")
        
        # Find articles without headlines
        articles_to_migrate = await db.articles.find({"headline": {"$exists": False}}).to_list(length=None)
        migrated_count = 0
        
        for article_data in articles_to_migrate:
            try:
                # Generate headline and update summary
                headline, summary = await summarize_article(article_data["content"], article_data["title"])
                
                # Update the article
                await db.articles.update_one(
                    {"_id": article_data["_id"]},
                    {
                        "$set": {
                            "headline": headline,
                            "summary": summary
                        }
                    }
                )
                migrated_count += 1
                
            except Exception as e:
                logging.error(f"Error migrating article {article_data.get('id', 'unknown')}: {e}")
                continue
        
        logging.info(f"Migration completed: {migrated_count} articles migrated")
        return {
            "message": f"Migrated {migrated_count} articles to Inshorts format",
            "migrated_count": migrated_count
        }
        
    except Exception as e:
        logging.error(f"Error during migration: {e}")
        raise HTTPException(status_code=500, detail=f"Error during migration: {str(e)}")

@api_router.post("/articles/update-summaries")
async def update_all_summaries():
    """Update all existing articles with longer summaries (350-400 chars)"""
    try:
        logging.info("Starting summary update to longer format...")
        
        # Find all articles
        articles_to_update = await db.articles.find({}).to_list(length=None)
        updated_count = 0
        
        for article_data in articles_to_update:
            try:
                # Generate new headline and longer summary
                headline, summary = await summarize_article(article_data["content"], article_data["title"])
                
                # Update the article
                await db.articles.update_one(
                    {"_id": article_data["_id"]},
                    {
                        "$set": {
                            "headline": headline,
                            "summary": summary
                        }
                    }
                )
                updated_count += 1
                
            except Exception as e:
                logging.error(f"Error updating article {article_data.get('id', 'unknown')}: {e}")
                continue
        
        logging.info(f"Summary update completed: {updated_count} articles updated")
        return {
            "message": f"Updated {updated_count} articles with longer summaries",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logging.error(f"Error during summary update: {e}")
        raise HTTPException(status_code=500, detail=f"Error during summary update: {str(e)}")

@api_router.post("/articles/refresh")
async def refresh_articles():
    """Fetch and store new articles from real sources"""
    global last_news_update
    
    try:
        logging.info("Starting manual article refresh...")
        new_articles = await fetch_real_biotech_news()
        stored_count = 0
        
        for article_data in new_articles:
            # Check if article already exists (by URL or title similarity)
            existing = await db.articles.find_one({
                "$or": [
                    {"url": article_data["url"]},
                    {"title": {"$regex": f"^{re.escape(article_data['title'][:50])}", "$options": "i"}}
                ]
            })
            
            if existing:
                continue
                
            # Create Inshorts-style headline and summary
            headline, summary = await summarize_article(article_data["content"], article_data["title"])
            
            article = Article(
                **article_data,
                headline=headline,
                summary=summary
            )
            
            await db.articles.insert_one(article.model_dump())
            stored_count += 1
        
        last_news_update = datetime.now(timezone.utc)
        logging.info(f"Manual refresh completed: {stored_count} new articles stored")
        
        return {
            "message": f"Refreshed {stored_count} new articles", 
            "total_fetched": len(new_articles),
            "last_update": last_news_update
        }
        
    except Exception as e:
        logging.error(f"Error refreshing articles: {e}")
        raise HTTPException(status_code=500, detail=f"Error refreshing articles: {str(e)}")

@api_router.post("/stocks/refresh")
async def refresh_stocks():
    """Fetch and store latest stock data"""
    global last_stock_update
    
    try:
        logging.info("Starting manual stock refresh...")
        stock_data = await fetch_stock_data()
        stored_count = 0
        
        for stock_info in stock_data:
            # Upsert stock data
            await db.stocks.replace_one(
                {"symbol": stock_info["symbol"]},
                StockData(**stock_info).model_dump(),
                upsert=True
            )
            stored_count += 1
        
        last_stock_update = datetime.now(timezone.utc)
        logging.info(f"Manual stock refresh completed: {stored_count} stocks updated")
        
        return {
            "message": f"Refreshed {stored_count} stocks", 
            "last_update": last_stock_update
        }
        
    except Exception as e:
        logging.error(f"Error refreshing stocks: {e}")
        raise HTTPException(status_code=500, detail=f"Error refreshing stocks: {str(e)}")

@api_router.post("/search", response_model=List[Article])
async def search_articles(search_query: SearchQuery):
    """Search articles by keywords"""
    query = {
        "$or": [
            {"title": {"$regex": search_query.query, "$options": "i"}},
            {"summary": {"$regex": search_query.query, "$options": "i"}},
            {"content": {"$regex": search_query.query, "$options": "i"}},
            {"keywords": {"$in": [search_query.query.lower()]}}
        ]
    }
    
    if search_query.category and search_query.category in CATEGORIES:
        query["category"] = search_query.category
    
    articles = await db.articles.find(query).sort("published_at", -1).limit(search_query.limit).to_list(length=None)
    return [Article(**article) for article in articles]

@api_router.post("/preferences", response_model=UserPreferences)
async def save_user_preferences(user_id: str, categories: List[str], stocks: List[str] = []):
    """Save user's preferred categories and stock watchlist"""
    # Validate categories
    valid_categories = [cat for cat in categories if cat in CATEGORIES]
    valid_stocks = [stock for stock in stocks if stock in BIOTECH_STOCKS]
    
    preferences = UserPreferences(
        user_id=user_id,
        preferred_categories=valid_categories,
        watchlist_stocks=valid_stocks
    )
    
    # Upsert preferences
    await db.preferences.replace_one(
        {"user_id": user_id},
        preferences.model_dump(),
        upsert=True
    )
    
    return preferences

@api_router.get("/preferences/{user_id}", response_model=UserPreferences)
async def get_user_preferences(user_id: str):
    """Get user's preferred categories and stock watchlist"""
    prefs = await db.preferences.find_one({"user_id": user_id})
    if not prefs:
        # Return default preferences
        return UserPreferences(user_id=user_id, preferred_categories=CATEGORIES)
    return UserPreferences(**prefs)

# Auto-update scheduler
scheduler = AsyncIOScheduler()

async def scheduled_news_update():
    """Scheduled task to update news every 12 hours"""
    global last_news_update
    
    try:
        logging.info("Starting scheduled news update...")
        new_articles = await fetch_real_biotech_news()
        stored_count = 0
        
        for article_data in new_articles:
            # Check if article already exists
            existing = await db.articles.find_one({
                "$or": [
                    {"url": article_data["url"]},
                    {"title": {"$regex": f"^{re.escape(article_data['title'][:50])}", "$options": "i"}}
                ]
            })
            
            if existing:
                continue
                
            # Create Inshorts-style headline and summary
            headline, summary = await summarize_article(article_data["content"], article_data["title"])
            
            article = Article(
                **article_data,
                headline=headline,
                summary=summary
            )
            
            await db.articles.insert_one(article.model_dump())
            stored_count += 1
        
        last_news_update = datetime.now(timezone.utc)
        logging.info(f"Scheduled news update completed: {stored_count} new articles stored")
        
    except Exception as e:
        logging.error(f"Error in scheduled news update: {e}")

async def scheduled_stock_update():
    """Scheduled task to update stock data daily"""
    global last_stock_update
    
    try:
        logging.info("Starting scheduled stock update...")
        stock_data = await fetch_stock_data()
        stored_count = 0
        
        for stock_info in stock_data:
            await db.stocks.replace_one(
                {"symbol": stock_info["symbol"]},
                StockData(**stock_info).model_dump(),
                upsert=True
            )
            stored_count += 1
        
        last_stock_update = datetime.now(timezone.utc)
        logging.info(f"Scheduled stock update completed: {stored_count} stocks updated")
        
    except Exception as e:
        logging.error(f"Error in scheduled stock update: {e}")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Initialize the database and start scheduler"""
    global last_news_update, last_stock_update
    
    try:
        # Check if we already have articles
        article_count = await db.articles.count_documents({})
        stock_count = await db.stocks.count_documents({})
        
        if article_count < 5:  # If less than 5 articles, fetch initial set
            logger.info("Initializing database with real biotech news...")
            await refresh_articles()
        else:
            logger.info(f"Database already has {article_count} articles")
        
        if stock_count < 10:  # If less than 10 stocks, fetch initial set
            logger.info("Initializing database with biotech stock data...")
            await refresh_stocks()
        else:
            logger.info(f"Database already has {stock_count} stocks")
        
        # Start the scheduler for auto-updates
        if not scheduler.running:
            # News updates every 6 hours (more frequent for real-time feeds)
            scheduler.add_job(
                scheduled_news_update,
                'interval',
                hours=6,
                id='news_update',
                next_run_time=None
            )
            
            # Stock updates daily at market close (6 PM EST)
            scheduler.add_job(
                scheduled_stock_update,
                'cron',
                hour=18,  # 6 PM EST
                minute=0,
                id='stock_update'
            )
            
            scheduler.start()
            logger.info("Auto-update scheduler started - news every 6 hours, stocks daily")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if scheduler.running:
        scheduler.shutdown()
    client.close()