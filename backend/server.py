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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Biotech News API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Initialize LLM chat for summarization
llm_key = os.environ.get('EMERGENT_LLM_KEY')
chat = LlmChat(
    api_key=llm_key,
    session_id="biotech-news-summarizer",
    system_message="You are an expert biotech and pharmaceutical research summarizer. Summarize articles in 2-3 concise sentences highlighting key findings, mechanisms, clinical phases, or policy changes. Focus on compound names, outcomes, and significance."
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

# Define Models
class Article(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    summary: str
    content: str
    category: str
    source: str
    url: str
    image_url: Optional[str] = None
    published_at: datetime
    keywords: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ArticleCreate(BaseModel):
    title: str
    content: str
    category: str
    source: str
    url: str
    image_url: Optional[str] = None
    published_at: datetime
    keywords: List[str] = []

class UserPreferences(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    preferred_categories: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SearchQuery(BaseModel):
    query: str
    category: Optional[str] = None
    limit: int = 20

class SystemStatus(BaseModel):
    last_update: datetime
    total_articles: int
    articles_by_category: Dict[str, int]
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

async def fetch_pubmed_articles(max_articles: int = 10) -> List[Dict]:
    """Fetch latest biotech articles from PubMed"""
    articles = []
    
    try:
        # PubMed search terms for biotech/pharma
        search_terms = [
            "biotechnology[Title/Abstract] AND 2024[Date - Publication]",
            "pharmaceutical[Title/Abstract] AND clinical trial[Title/Abstract] AND 2024[Date - Publication]",
            "gene therapy[Title/Abstract] AND 2024[Date - Publication]",
            "immunotherapy[Title/Abstract] AND cancer[Title/Abstract] AND 2024[Date - Publication]"
        ]
        
        for search_term in search_terms[:2]:  # Limit to 2 searches to avoid rate limits
            # Search PubMed
            search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
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
                'id': ','.join(pmids[:5]),  # Limit to 5 articles per search
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
    
    return articles[:max_articles]

async def fetch_newsapi_articles(max_articles: int = 10) -> List[Dict]:
    """Fetch biotech news from NewsAPI"""
    articles = []
    
    if not newsapi:
        return articles
        
    try:
        # Search for biotech/pharma news
        keywords = [
            "biotechnology", "pharmaceutical", "clinical trial", 
            "FDA approval", "gene therapy", "immunotherapy"
        ]
        
        for keyword in keywords[:3]:  # Limit searches
            try:
                response = newsapi.get_everything(
                    q=keyword,
                    language='en',
                    sort_by='publishedAt',
                    page_size=max_articles // 3,
                    domains='biopharmadive.com,fiercebiotech.com,biospace.com,endpoints.com'
                )
                
                if response.get('status') == 'ok' and response.get('articles'):
                    for article in response['articles']:
                        if article.get('title') and article.get('description'):
                            # Use description as content since full content might be limited
                            content = article.get('content') or article.get('description', '')
                            
                            articles.append({
                                'title': article['title'],
                                'content': content,
                                'category': categorize_article(article['title'], content),
                                'source': article.get('source', {}).get('name', 'NewsAPI'),
                                'url': article.get('url', ''),
                                'image_url': article.get('urlToImage') or "https://images.unsplash.com/photo-1576671081837-49000212a370?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDN8MHwxfHNlYXJjaHwyfHxwaGFybWFjZXV0aWNhbHxlbnwwfHx8fDE3NTc2OTc4Njd8MA&ixlib=rb-4.1.0&q=85",
                                'published_at': datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00')),
                                'keywords': extract_keywords(article['title'], content)
                            })
                            
            except Exception as e:
                logging.warning(f"Error fetching NewsAPI articles for {keyword}: {e}")
                continue
                
            await asyncio.sleep(1)  # Rate limiting
            
    except Exception as e:
        logging.error(f"Error with NewsAPI: {e}")
    
    return articles[:max_articles]

async def fetch_clinical_trials(max_articles: int = 5) -> List[Dict]:
    """Fetch recent clinical trials from ClinicalTrials.gov"""
    articles = []
    
    try:
        # Search for recent biotech clinical trials
        url = "https://clinicaltrials.gov/api/query/study_fields"
        params = {
            'expr': 'biotechnology OR "gene therapy" OR immunotherapy OR "CAR-T"',
            'fields': 'NCTId,BriefTitle,BriefSummary,Condition,InterventionName,StudyFirstPostDate,LeadSponsorName',
            'min_rnk': 1,
            'max_rnk': max_articles,
            'fmt': 'json'
        }
        
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            
            if 'StudyFieldsResponse' in data and 'StudyFields' in data['StudyFieldsResponse']:
                for study in data['StudyFieldsResponse']['StudyFields']:
                    try:
                        nct_id = study.get('NCTId', [''])[0]
                        title = study.get('BriefTitle', [''])[0]
                        summary = study.get('BriefSummary', [''])[0]
                        condition = ', '.join(study.get('Condition', []))
                        intervention = ', '.join(study.get('InterventionName', []))
                        sponsor = study.get('LeadSponsorName', [''])[0]
                        post_date = study.get('StudyFirstPostDate', [''])[0]
                        
                        if title and summary:
                            # Parse date
                            pub_date = datetime.now(timezone.utc)
                            if post_date:
                                try:
                                    pub_date = datetime.strptime(post_date, '%B %d, %Y').replace(tzinfo=timezone.utc)
                                except:
                                    pass
                            
                            content = f"{summary}\n\nCondition: {condition}\nIntervention: {intervention}\nSponsor: {sponsor}"
                            
                            articles.append({
                                'title': f"Clinical Trial: {title}",
                                'content': content,
                                'category': 'Clinical Trials',
                                'source': 'ClinicalTrials.gov',
                                'url': f"https://clinicaltrials.gov/study/{nct_id}",
                                'image_url': "https://images.unsplash.com/photo-1581594549595-35f6edc7b762?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzh8MHwxfHNlYXJjaHwxfHxiaW90ZWNofGVufDB8fHx8MTc1NzY5Nzg2Mnww&ixlib=rb-4.1.0&q=85",
                                'published_at': pub_date,
                                'keywords': extract_keywords(title, content)
                            })
                            
                    except Exception as e:
                        logging.warning(f"Error parsing clinical trial: {e}")
                        continue
                        
    except Exception as e:
        logging.error(f"Error fetching clinical trials: {e}")
    
    return articles

async def fetch_real_biotech_news() -> List[Dict]:
    """Fetch news from all sources"""
    all_articles = []
    
    try:
        logging.info("Fetching real biotech news from multiple sources...")
        
        # Fetch from all sources concurrently
        tasks = [
            fetch_pubmed_articles(8),
            fetch_newsapi_articles(8),
            fetch_clinical_trials(4)
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
        
        logging.info(f"Fetched {len(unique_articles)} unique articles from real sources")
        return unique_articles[:20]  # Limit to 20 most recent
        
    except Exception as e:
        logging.error(f"Error in fetch_real_biotech_news: {e}")
        return []

async def summarize_article(content: str) -> str:
    """Use LLM to summarize article content"""
    try:
        user_message = UserMessage(text=f"Summarize this biotech/pharma article in 2-3 sentences: {content}")
        response = await chat.send_message(user_message)
        return response.strip()
    except Exception as e:
        logging.error(f"Error summarizing article: {e}")
        # Fallback to first 200 characters
        return content[:200] + "..." if len(content) > 200 else content

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Biotech News API", "version": "2.0.0", "features": ["Real News Integration", "Auto Updates", "Timestamps"]}

@api_router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get system status with last update info"""
    total_articles = await db.articles.count_documents({})
    
    # Count articles by category
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}
    ]
    category_counts = {}
    async for result in db.articles.aggregate(pipeline):
        category_counts[result["_id"]] = result["count"]
    
    return SystemStatus(
        last_update=last_news_update,
        total_articles=total_articles,
        articles_by_category=category_counts,
        next_scheduled_update=None  # Will be updated when scheduler is running
    )

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
                
            # Summarize the article content
            summary = await summarize_article(article_data["content"])
            
            article = Article(
                **article_data,
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
async def save_user_preferences(user_id: str, categories: List[str]):
    """Save user's preferred categories"""
    # Validate categories
    valid_categories = [cat for cat in categories if cat in CATEGORIES]
    
    preferences = UserPreferences(
        user_id=user_id,
        preferred_categories=valid_categories
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
    """Get user's preferred categories"""
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
                
            # Summarize the article content
            summary = await summarize_article(article_data["content"])
            
            article = Article(
                **article_data,
                summary=summary
            )
            
            await db.articles.insert_one(article.model_dump())
            stored_count += 1
        
        last_news_update = datetime.now(timezone.utc)
        logging.info(f"Scheduled update completed: {stored_count} new articles stored")
        
    except Exception as e:
        logging.error(f"Error in scheduled news update: {e}")

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
    global last_news_update
    
    try:
        # Check if we already have articles
        article_count = await db.articles.count_documents({})
        
        if article_count < 5:  # If less than 5 articles, fetch initial set
            logger.info("Initializing database with real biotech news...")
            await refresh_articles()
        else:
            logger.info(f"Database already has {article_count} articles")
        
        # Start the scheduler for auto-updates every 12 hours
        if not scheduler.running:
            scheduler.add_job(
                scheduled_news_update,
                'interval',
                hours=12,
                id='news_update',
                next_run_time=None  # Start immediately for first run, then every 12 hours
            )
            scheduler.start()
            logger.info("Auto-update scheduler started - updates every 12 hours")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if scheduler.running:
        scheduler.shutdown()
    client.close()