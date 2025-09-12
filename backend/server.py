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

# Categories for biotech news
CATEGORIES = [
    "Academic Research",
    "Industry Updates", 
    "Early Discovery",
    "Clinical Trials",
    "Drug Modalities",
    "Healthcare & Policy"
]

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

# News aggregation functions
async def fetch_biotech_news():
    """Fetch news from various biotech sources"""
    articles = []
    
    # Sample biotech/pharma news data (in production, you'd fetch from real APIs)
    sample_articles = [
        {
            "title": "Novel CAR-T Cell Therapy Shows Promise in Phase II Clinical Trial",
            "content": "A breakthrough CAR-T cell therapy targeting CD19 antigen has demonstrated remarkable efficacy in treating relapsed B-cell lymphomas. The Phase II clinical trial enrolled 156 patients and achieved a 78% complete response rate. The treatment, developed by BioPharma Innovations, uses a novel third-generation CAR construct with enhanced persistence. Patients showed durable responses at 12-month follow-up with manageable cytokine release syndrome. The FDA has granted breakthrough therapy designation for this innovative immunotherapy approach.",
            "category": "Clinical Trials",
            "source": "BioPharma Journal",
            "url": "https://example.com/car-t-therapy",
            "image_url": "https://images.unsplash.com/photo-1581594549595-35f6edc7b762?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzh8MHwxfHNlYXJjaHwxfHxiaW90ZWNofGVufDB8fHx8MTc1NzY5Nzg2Mnww&ixlib=rb-4.1.0&q=85",
            "keywords": ["CAR-T", "immunotherapy", "lymphoma", "clinical trial"],
            "published_at": datetime.now(timezone.utc)
        },
        {
            "title": "CRISPR Gene Editing Platform Receives FDA Approval for Sickle Cell Disease",
            "content": "The FDA has approved the first CRISPR-based gene therapy for sickle cell disease, marking a historic milestone in precision medicine. The treatment, called CTX001, was developed collaboratively by CRISPR Therapeutics and Vertex Pharmaceuticals. Clinical trials showed that 95% of patients achieved transfusion independence with no vaso-occlusive crises. The therapy works by editing the BCL11A gene to reactivate fetal hemoglobin production. This approval paves the way for broader applications of gene editing in treating genetic disorders.",
            "category": "Drug Modalities",
            "source": "Nature Biotechnology",
            "url": "https://example.com/crispr-approval",
            "image_url": "https://images.unsplash.com/photo-1578496480240-32d3e0c04525?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzh8MHwxfHNlYXJjaHw0fHxiaW90ZWNofGVufDB8fHx8MTc1NzY5Nzg2Mnww&ixlib=rb-4.1.0&q=85",
            "keywords": ["CRISPR", "gene therapy", "sickle cell", "FDA approval"],
            "published_at": datetime.now(timezone.utc)
        },
        {
            "title": "Breakthrough mRNA Vaccine Platform for Cancer Immunotherapy",
            "content": "Researchers at MIT have developed a revolutionary mRNA vaccine platform that can be rapidly customized for different cancer types. The platform uses lipid nanoparticles to deliver tumor-specific antigens and immune adjuvants directly to dendritic cells. Preclinical studies in melanoma and colorectal cancer models showed 85% tumor regression rates. The technology allows for personalized cancer vaccines to be manufactured within 48 hours of tumor sequencing. Phase I human trials are expected to begin next quarter with partnerships from major pharmaceutical companies.",
            "category": "Academic Research",
            "source": "Cell Medicine",
            "url": "https://example.com/mrna-cancer-vaccine",
            "image_url": "https://images.unsplash.com/photo-1648792940059-3b782a7b8b20?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzh8MHwxfHNlYXJjaHwzfHxiaW90ZWNofGVufDB8fHx8MTc1NzY5Nzg2Mnww&ixlib=rb-4.1.0&q=85",
            "keywords": ["mRNA", "cancer vaccine", "immunotherapy", "personalized medicine"],
            "published_at": datetime.now(timezone.utc)
        },
        {
            "title": "AI-Powered Drug Discovery Identifies Novel Alzheimer's Treatment",
            "content": "DeepMind's AlphaFold AI has identified a promising small molecule compound for treating Alzheimer's disease by targeting amyloid-beta aggregation. The compound, designated DM-2847, shows high selectivity for pathological protein conformations while sparing normal cellular functions. In vitro studies demonstrated 92% reduction in amyloid plaque formation with excellent blood-brain barrier penetration. The discovery process took only 6 months compared to traditional 3-5 year timelines. Pharmaceutical giant Roche has licensed the compound for IND-enabling studies and Phase I trials.",
            "category": "Early Discovery",
            "source": "Science Translational Medicine",
            "url": "https://example.com/ai-alzheimers-drug",
            "image_url": "https://images.unsplash.com/photo-1576671081837-49000212a370?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDN8MHwxfHNlYXJjaHwyfHxwaGFybWFjZXV0aWNhbHxlbnwwfHx8fDE3NTc2OTc4Njd8MA&ixlib=rb-4.1.0&q=85",
            "keywords": ["AI", "drug discovery", "Alzheimer's", "small molecule"],
            "published_at": datetime.now(timezone.utc)
        },
        {
            "title": "Biosimilar Market Expansion Drives Healthcare Cost Reduction",
            "content": "The global biosimilar market has reached $25 billion with significant impact on healthcare costs. New FDA guidelines have streamlined approval processes for complex biosimilar products including monoclonal antibodies and protein therapeutics. Cost savings of 20-40% compared to reference biologics have improved patient access to life-saving treatments. European markets lead adoption with 75% biosimilar penetration in oncology indications. Regulatory harmonization between FDA and EMA is accelerating global development timelines for biosimilar manufacturers.",
            "category": "Healthcare & Policy",
            "source": "Pharmaceutical Executive",
            "url": "https://example.com/biosimilar-market",
            "image_url": "https://images.pexels.com/photos/3938022/pexels-photo-3938022.jpeg",
            "keywords": ["biosimilars", "healthcare policy", "cost reduction", "FDA"],
            "published_at": datetime.now(timezone.utc)
        },
        {
            "title": "Moderna Partners with Gates Foundation for Global mRNA Manufacturing",
            "content": "Moderna has announced a strategic partnership with the Bill & Melinda Gates Foundation to establish mRNA manufacturing facilities in Africa and Asia. The initiative aims to produce vaccines for pandemic preparedness and endemic diseases like malaria and tuberculosis. Investment of $500 million will fund technology transfer and local workforce training programs. The facilities will use Moderna's proprietary lipid nanoparticle formulation technology for enhanced vaccine stability in tropical climates. Production capacity is expected to reach 1 billion doses annually by 2027.",
            "category": "Industry Updates",
            "source": "BioPharma Dive",
            "url": "https://example.com/moderna-gates-partnership",
            "image_url": "https://images.unsplash.com/photo-1707944746058-4da338d0f827?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDF8MHwxfHNlYXJjaHwyfHxsYWJvcmF0b3J5JTIwcmVzZWFyY2h8ZW58MHx8fHwxNzU3Njk3ODcyfDA&ixlib=rb-4.1.0&q=85",
            "keywords": ["Moderna", "mRNA", "global health", "manufacturing"],
            "published_at": datetime.now(timezone.utc)
        }
    ]
    
    return sample_articles

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
    return {"message": "Biotech News API", "version": "1.0.0"}

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
    """Fetch and store new articles"""
    try:
        new_articles = await fetch_biotech_news()
        stored_count = 0
        
        for article_data in new_articles:
            # Check if article already exists
            existing = await db.articles.find_one({"url": article_data["url"]})
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
        
        return {"message": f"Refreshed {stored_count} articles", "total_fetched": len(new_articles)}
    except Exception as e:
        logging.error(f"Error refreshing articles: {e}")
        raise HTTPException(status_code=500, detail="Error refreshing articles")

@api_router.post("/search", response_model=List[Article])
async def search_articles(search_query: SearchQuery):
    """Search articles by keywords"""
    query = {
        "$or": [
            {"title": {"$regex": search_query.query, "$options": "i"}},
            {"summary": {"$regex": search_query.query, "$options": "i"}},
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
    """Initialize the database with sample data"""
    try:
        # Check if we already have articles
        article_count = await db.articles.count_documents({})
        if article_count == 0:
            logger.info("Initializing database with sample articles...")
            await refresh_articles()
    except Exception as e:
        logger.error(f"Error during startup: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()