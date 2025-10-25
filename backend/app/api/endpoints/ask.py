"""
Ask endpoint for processing legal questions
"""
import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.models.request import QuestionRequest
from app.models.response import RAGResponse, Source, ResponseMetadata

logger = logging.getLogger(__name__)
router = APIRouter()


class AskRequest(BaseModel):
    """Request model for ask endpoint"""
    question: str = Field(..., min_length=1, max_length=1000, description="The legal question to ask")
    max_sources: Optional[int] = Field(default=None, ge=1, le=20, description="Maximum number of sources to return")
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum similarity threshold")
    validate_response: Optional[bool] = Field(default=None, description="Whether to validate response with Gemini")


class AskResponse(BaseModel):
    """Response model for ask endpoint"""
    response: str = Field(..., description="The generated response to the question")
    sources: List[Source] = Field(default=[], description="List of relevant legal sources")
    metadata: ResponseMetadata = Field(..., description="Response metadata and statistics")
    performance: Dict[str, float] = Field(default={}, description="Performance metrics")


def get_rag_service(request: Request):
    """Dependency to get RAG service from app state"""
    if not hasattr(request.app.state, 'services'):
        raise HTTPException(
            status_code=503,
            detail="Services not initialized. Please try again later."
        )
    
    services = request.app.state.services
    
    # Get pre-created optimized RAG service
    if "rag" not in services:
        raise HTTPException(
            status_code=503,
            detail="RAG service not initialized. Please try again later."
        )
    
    return services["rag"]


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request_data: AskRequest,
    rag_service = Depends(get_rag_service)
) -> AskResponse:
    """
    Process a legal question and return RAG response
    
    This endpoint processes legal questions using the RAG (Retrieval-Augmented Generation) pipeline:
    1. Generates embeddings for the question
    2. Searches for relevant legal documents
    3. Generates a response using the LLM with context
    4. Optionally validates the response with Gemini
    
    Args:
        request_data: The question request with optional parameters
        
    Returns:
        AskResponse: The generated response with sources and metadata
        
    Raises:
        HTTPException: If the question processing fails
    """
    try:
        logger.info(f"Processing question: {request_data.question[:100]}...")
        
        # Validate question
        if not request_data.question or not request_data.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        # Process question through RAG pipeline
        try:
            result = await rag_service.process_question(
                question=request_data.question.strip(),
                max_sources=request_data.max_sources,
                similarity_threshold=request_data.similarity_threshold,
                validate_response=request_data.validate_response
            )
            
        except Exception as e:
            logger.error(f"RAG pipeline failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process question: {str(e)}"
            )
        
        # Convert result to response format
        try:
            # Convert sources to Source models
            sources = []
            for source_data in result.get("sources", []):
                source = Source(
                    document=source_data.get("document_name", ""),
                    article=source_data.get("article", ""),
                    chapter=source_data.get("chapter", ""),
                    pages=source_data.get("pages", ""),
                    content=source_data.get("content", ""),
                    relevance_score=source_data.get("relevance_score", 0.0)
                )
                sources.append(source)
            
            # Create metadata
            metadata_dict = result.get("metadata", {})
            metadata = ResponseMetadata(
                question=metadata_dict.get("question", request_data.question),
                sources_found=metadata_dict.get("sources_found", len(sources)),
                confidence=metadata_dict.get("confidence", 0.0),
                validated=metadata_dict.get("validated", False),
                validation_score=metadata_dict.get("validation_score"),
                timestamp=metadata_dict.get("timestamp", "2025-10-25T00:00:00Z"),
                processing_time=result.get("performance", {}).get("total_time", 0.0),
                model_used=metadata_dict.get("model_used", "llama2:latest"),
                total_documents_searched=metadata_dict.get("total_documents_searched", 750)
            )
            
            # Create response
            response = AskResponse(
                response=result.get("response", ""),
                sources=sources,
                metadata=metadata,
                performance=result.get("performance", {})
            )
            
            logger.info(f"Question processed successfully. Sources: {len(sources)}, Confidence: {metadata.confidence}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to format response: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to format response"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in ask endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your question"
        )


@router.get("/ask/health")
async def ask_health_check(request: Request):
    """
    Health check for the ask endpoint and RAG pipeline
    
    Returns:
        Dict: Health status of all RAG pipeline components
    """
    try:
        if not hasattr(request.app.state, 'services'):
            return {
                "status": "unavailable",
                "message": "Services not initialized"
            }
        
        services = request.app.state.services
        
        # Check individual service health
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": "2025-10-24T00:00:00Z"
        }
        
        # Check embedding service
        if "embedding" in services:
            try:
                embedding_health = await services["embedding"].check_health()
                health_status["components"]["embedding"] = embedding_health
            except Exception as e:
                health_status["components"]["embedding"] = {"healthy": False, "error": str(e)}
        
        # Check LLM service
        if "llm" in services:
            try:
                llm_health = await services["llm"].check_ollama_health()
                health_status["components"]["llm"] = llm_health
            except Exception as e:
                health_status["components"]["llm"] = {"healthy": False, "error": str(e)}
        
        # Check data service
        if "data" in services:
            try:
                data_health = await services["data"].health_check()
                health_status["components"]["data"] = data_health
            except Exception as e:
                health_status["components"]["data"] = {"status": "unhealthy", "error": str(e)}
        
        # Determine overall health
        component_health = []
        for component, status in health_status["components"].items():
            if component == "data":
                component_health.append(status.get("status") == "healthy")
            else:
                component_health.append(status.get("healthy", False))
        
        if not all(component_health):
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/ask/info")
async def ask_info(request: Request):
    """
    Get information about the ask endpoint and RAG pipeline configuration
    
    Returns:
        Dict: Configuration and capability information
    """
    try:
        if not hasattr(request.app.state, 'services'):
            return {
                "status": "unavailable",
                "message": "Services not initialized"
            }
        
        services = request.app.state.services
        
        info = {
            "endpoint": "/ask",
            "description": "Process legal questions using RAG pipeline",
            "capabilities": [
                "Legal document search",
                "Context-aware response generation",
                "Source citation",
                "Response validation (optional)"
            ],
            "parameters": {
                "question": "Required string (1-1000 characters)",
                "max_sources": "Optional integer (1-20, default from config)",
                "similarity_threshold": "Optional float (0.0-1.0, default from config)",
                "validate_response": "Optional boolean (default from config)"
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
                    "total_documents": stats.get("total_documents", 0),
                    "document_sources": stats.get("document_sources", {})
                }
            except Exception as e:
                info["services"]["data"] = {"error": str(e)}
        
        return info
        
    except Exception as e:
        logger.error(f"Failed to get ask info: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get endpoint information")