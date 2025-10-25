"""
Data management endpoints
"""
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


class ReloadDataRequest(BaseModel):
    """Request model for data reload endpoint"""
    reset_collection: Optional[bool] = Field(default=False, description="Whether to reset the collection before reloading")
    data_directory: Optional[str] = Field(default=None, description="Custom data directory path")
    incremental: Optional[bool] = Field(default=False, description="Whether to perform incremental update")


class ReloadDataResponse(BaseModel):
    """Response model for data reload endpoint"""
    status: str = Field(..., description="Status of the reload operation")
    message: str = Field(..., description="Human-readable message")
    statistics: Dict[str, Any] = Field(default={}, description="Reload statistics")
    task_id: Optional[str] = Field(default=None, description="Background task ID for tracking")


class IndexingStatusResponse(BaseModel):
    """Response model for indexing status"""
    status: str = Field(..., description="Current indexing status")
    progress: Dict[str, Any] = Field(default={}, description="Indexing progress information")
    statistics: Dict[str, Any] = Field(default={}, description="Current statistics")


def get_indexing_service(request: Request):
    """Dependency to get indexing service from app state"""
    if not hasattr(request.app.state, 'services'):
        raise HTTPException(
            status_code=503,
            detail="Services not initialized. Please try again later."
        )
    
    services = request.app.state.services
    indexing_service = services.get("indexing")
    
    if not indexing_service:
        raise HTTPException(
            status_code=503,
            detail="Indexing service not available. Please try again later."
        )
    
    return indexing_service


@router.post("/reload-data", response_model=ReloadDataResponse)
async def reload_data(
    request_data: ReloadDataRequest,
    background_tasks: BackgroundTasks,
    indexing_service = Depends(get_indexing_service)
) -> ReloadDataResponse:
    """
    Reload and reindex CSV data
    
    This endpoint triggers the document indexing pipeline to reload legal documents:
    1. Loads CSV files from the data directory
    2. Processes and cleans document content
    3. Generates embeddings for all documents
    4. Indexes documents in ChromaDB
    
    Args:
        request_data: Reload configuration options
        background_tasks: FastAPI background tasks for async processing
        
    Returns:
        ReloadDataResponse: Status and statistics of the reload operation
        
    Raises:
        HTTPException: If the reload operation fails
    """
    try:
        logger.info(f"Starting data reload. Reset: {request_data.reset_collection}, Incremental: {request_data.incremental}")
        
        # Generate task ID for tracking
        task_id = f"reload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Define progress callback for tracking
        progress_updates = []
        
        async def progress_callback(progress: Dict[str, Any]):
            """Callback to track indexing progress"""
            progress_updates.append({
                "timestamp": datetime.now().isoformat(),
                "progress": progress.copy()
            })
            logger.info(f"Indexing progress: {progress['processed_documents']}/{progress['total_documents']} documents")
        
        try:
            # Choose indexing method based on request
            if request_data.incremental:
                logger.info("Performing incremental data update...")
                result = await indexing_service.incremental_update(
                    data_directory=request_data.data_directory,
                    progress_callback=progress_callback
                )
            else:
                logger.info("Performing full data reload...")
                result = await indexing_service.index_all_documents(
                    data_directory=request_data.data_directory,
                    reset_collection=request_data.reset_collection,
                    progress_callback=progress_callback
                )
            
            # Determine response based on result
            if result["status"] == "completed":
                status = "success"
                message = f"Data reload completed successfully. {result['summary']}"
            elif result["status"] == "failed":
                status = "error"
                message = f"Data reload failed. {result.get('summary', 'Unknown error')}"
            else:
                status = "partial"
                message = f"Data reload completed with issues. {result['summary']}"
            
            response = ReloadDataResponse(
                status=status,
                message=message,
                statistics=result.get("statistics", {}),
                task_id=task_id
            )
            
            logger.info(f"Data reload completed: {message}")
            return response
            
        except Exception as e:
            logger.error(f"Data reload failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Data reload failed: {str(e)}"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in reload-data endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during data reload"
        )


@router.get("/reload-data/status", response_model=IndexingStatusResponse)
async def get_reload_status(
    indexing_service = Depends(get_indexing_service)
) -> IndexingStatusResponse:
    """
    Get current status of data indexing operation
    
    Returns:
        IndexingStatusResponse: Current indexing status and progress
    """
    try:
        status = await indexing_service.get_indexing_status()
        
        return IndexingStatusResponse(
            status=status.get("status", "unknown"),
            progress=status,
            statistics=status.get("statistics", {})
        )
        
    except Exception as e:
        logger.error(f"Failed to get reload status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get indexing status"
        )


@router.get("/collection/stats")
async def get_collection_stats(request: Request):
    """
    Get statistics about the document collection
    
    Returns:
        Dict: Collection statistics and information
    """
    try:
        if not hasattr(request.app.state, 'services'):
            raise HTTPException(
                status_code=503,
                detail="Services not initialized"
            )
        
        services = request.app.state.services
        data_service = services.get("data")
        
        if not data_service:
            raise HTTPException(
                status_code=503,
                detail="Data service not available"
            )
        
        # Get collection statistics
        stats = await data_service.get_collection_stats()
        info = await data_service.get_collection_info()
        
        return {
            "collection_stats": stats,
            "collection_info": info,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get collection statistics"
        )


@router.get("/collection/health")
async def get_collection_health(request: Request):
    """
    Get health status of the document collection and data services
    
    Returns:
        Dict: Health status of data-related services
    """
    try:
        if not hasattr(request.app.state, 'services'):
            return {
                "status": "unavailable",
                "message": "Services not initialized"
            }
        
        services = request.app.state.services
        
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Check data service
        if "data" in services:
            try:
                data_health = await services["data"].health_check()
                health_status["components"]["data_service"] = data_health
            except Exception as e:
                health_status["components"]["data_service"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Check indexing service
        if "indexing" in services:
            try:
                indexing_status = await services["indexing"].get_indexing_status()
                health_status["components"]["indexing_service"] = {
                    "status": indexing_status.get("status", "unknown"),
                    "last_indexing": indexing_status.get("timestamps", {})
                }
            except Exception as e:
                health_status["components"]["indexing_service"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Determine overall health
        component_statuses = []
        for component, status in health_status["components"].items():
            if "data_service" in component:
                component_statuses.append(status.get("status") == "healthy")
            else:
                component_statuses.append(status.get("status") not in ["error", "failed"])
        
        if not all(component_statuses):
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Collection health check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/collection/backup")
async def backup_collection(
    backup_path: Optional[str] = None,
    indexing_service = Depends(get_indexing_service)
):
    """
    Create a backup of the document collection
    
    Args:
        backup_path: Optional custom backup path
        
    Returns:
        Dict: Backup operation result
    """
    try:
        # Generate backup path if not provided
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"./backups/collection_backup_{timestamp}.json"
        
        logger.info(f"Creating collection backup at {backup_path}")
        
        success = await indexing_service.backup_index(backup_path)
        
        if success:
            return {
                "status": "success",
                "message": "Collection backup created successfully",
                "backup_path": backup_path,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Backup operation failed"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Backup operation failed: {str(e)}"
        )


@router.get("/collection/info")
async def get_collection_info(request: Request):
    """
    Get detailed information about the document collection
    
    Returns:
        Dict: Comprehensive collection information
    """
    try:
        if not hasattr(request.app.state, 'services'):
            raise HTTPException(
                status_code=503,
                detail="Services not initialized"
            )
        
        services = request.app.state.services
        indexing_service = services.get("indexing")
        
        if not indexing_service:
            raise HTTPException(
                status_code=503,
                detail="Indexing service not available"
            )
        
        # Get comprehensive index statistics
        info = await indexing_service.get_index_statistics()
        
        return {
            "collection_info": info,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get collection information"
        )