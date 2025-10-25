"""
FastAPI main application for Assistant Juridique Marocain
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.endpoints import ask, data, history

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global services (will be initialized on startup)
services = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Assistant Juridique Marocain API...")
    
    try:
        # Initialize services
        from app.services.embedding_service import EmbeddingService
        from app.services.llm_service import LLMService
        from app.services.data_service import DataService
        from app.services.indexing_service import IndexingService
        
        # Create service instances
        services["embedding"] = EmbeddingService()
        services["llm"] = LLMService()
        services["data"] = DataService()
        services["indexing"] = IndexingService(
            data_service=services["data"],
            embedding_service=services["embedding"]
        )
        
        # Initialize services
        await services["data"].initialize()
        await services["indexing"].initialize()
        
        # Create optimized RAG service instance
        from app.services.rag_service import RAGService
        services["rag"] = RAGService(
            embedding_service=services["embedding"],
            llm_service=services["llm"],
            data_service=services["data"],
            text_processor=None,
            fast_mode=False  # Use normal optimized mode
        )
        
        logger.info("✓ All services initialized successfully")
        
        # Store services in app state for access in endpoints
        app.state.services = services
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise
    
    # Shutdown
    logger.info("Shutting down Assistant Juridique Marocain API...")
    
    try:
        # Close services
        if "embedding" in services:
            await services["embedding"].close()
        if "llm" in services:
            await services["llm"].close()
        if "indexing" in services:
            await services["indexing"].close()
        # RAG service doesn't need explicit closing as it uses other services
        
        logger.info("✓ All services closed successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# Create FastAPI application
app = FastAPI(
    title="Assistant Juridique Marocain API",
    description="API pour l'assistant juridique basé sur RAG (Retrieval-Augmented Generation)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost"]
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "Une erreur interne s'est produite. Veuillez réessayer plus tard.",
            "details": str(exc) if settings.DEBUG else None
        }
    )

# Include API routers with versioning
app.include_router(
    ask.router,
    prefix=settings.API_V1_STR,
    tags=["Questions"]
)

app.include_router(
    data.router,
    prefix=settings.API_V1_STR,
    tags=["Data Management"]
)

app.include_router(
    history.router,
    prefix=settings.API_V1_STR,
    tags=["History"]
)

# Root endpoints
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Assistant Juridique Marocain API",
        "version": "1.0.0",
        "description": "API pour l'assistant juridique basé sur RAG",
        "docs": "/docs",
        "redoc": "/redoc",
        "api_v1": settings.API_V1_STR
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check if services are available
        if not hasattr(app.state, 'services'):
            return {
                "status": "starting",
                "message": "Services are initializing"
            }
        
        services = app.state.services
        
        # Basic health check
        health_status = {
            "status": "healthy",
            "timestamp": "2025-10-24T00:00:00Z",
            "services": {
                "embedding": "unknown",
                "llm": "unknown", 
                "data": "unknown"
            }
        }
        
        # Check individual services if available
        if "embedding" in services:
            try:
                embedding_health = await services["embedding"].check_health()
                health_status["services"]["embedding"] = "healthy" if embedding_health["healthy"] else "unhealthy"
            except Exception:
                health_status["services"]["embedding"] = "error"
        
        if "llm" in services:
            try:
                llm_health = await services["llm"].check_ollama_health()
                health_status["services"]["llm"] = "healthy" if llm_health["healthy"] else "unhealthy"
            except Exception:
                health_status["services"]["llm"] = "error"
        
        if "data" in services:
            try:
                data_health = await services["data"].health_check()
                health_status["services"]["data"] = "healthy" if data_health["status"] == "healthy" else "unhealthy"
            except Exception:
                health_status["services"]["data"] = "error"
        
        # Determine overall status
        service_statuses = list(health_status["services"].values())
        if "error" in service_statuses or "unhealthy" in service_statuses:
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/info")
async def get_api_info():
    """Get detailed API information and service status"""
    try:
        if not hasattr(app.state, 'services'):
            return {
                "api": {
                    "title": app.title,
                    "version": app.version,
                    "description": app.description
                },
                "services": "initializing"
            }
        
        services = app.state.services
        
        info = {
            "api": {
                "title": app.title,
                "version": app.version,
                "description": app.description,
                "endpoints": {
                    "ask": f"{settings.API_V1_STR}/ask",
                    "reload_data": f"{settings.API_V1_STR}/reload-data",
                    "history": f"{settings.API_V1_STR}/history"
                }
            },
            "configuration": {
                "max_sources": settings.MAX_SOURCES,
                "similarity_threshold": settings.SIMILARITY_THRESHOLD,
                "ollama_model": settings.OLLAMA_MODEL,
                "embedding_model": settings.EMBEDDING_MODEL
            },
            "services": {}
        }
        
        # Get service information
        if "embedding" in services:
            try:
                info["services"]["embedding"] = services["embedding"].get_model_info()
            except Exception as e:
                info["services"]["embedding"] = {"error": str(e)}
        
        if "llm" in services:
            try:
                info["services"]["llm"] = services["llm"].get_service_info()
            except Exception as e:
                info["services"]["llm"] = {"error": str(e)}
        
        if "data" in services:
            try:
                stats = await services["data"].get_collection_stats()
                info["services"]["data"] = {
                    "collection_name": services["data"].collection_name,
                    "total_documents": stats.get("total_documents", 0)
                }
            except Exception as e:
                info["services"]["data"] = {"error": str(e)}
        
        return info
        
    except Exception as e:
        logger.error(f"Failed to get API info: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get API information")