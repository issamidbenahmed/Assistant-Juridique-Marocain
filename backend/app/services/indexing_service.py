"""
Document Indexing Pipeline Service
Handles the complete process of loading, processing, and indexing legal documents
"""
import asyncio
import logging
import time
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from .data_service import DataService
from .embedding_service import EmbeddingService, EmbeddingServiceError
from ..utils.text_processor import TextProcessor
from ..core.config import settings

logger = logging.getLogger(__name__)


class IndexingServiceError(Exception):
    """Custom exception for indexing service errors"""
    pass


class IndexingService:
    """Service for document indexing pipeline"""
    
    def __init__(self, 
                 data_service: Optional[DataService] = None,
                 embedding_service: Optional[EmbeddingService] = None,
                 text_processor: Optional[TextProcessor] = None):
        """Initialize indexing service with required components"""
        self.data_service = data_service or DataService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.text_processor = text_processor or TextProcessor()
        
        # Configuration
        self.data_directory = settings.CSV_DATA_PATH
        self.batch_size = 50  # Process documents in batches
        
        # Progress tracking
        self.indexing_progress = {
            "status": "idle",
            "total_files": 0,
            "processed_files": 0,
            "total_documents": 0,
            "processed_documents": 0,
            "indexed_documents": 0,
            "failed_documents": 0,
            "start_time": None,
            "end_time": None,
            "errors": []
        }
    
    async def initialize(self):
        """Initialize all required services"""
        try:
            logger.info("Initializing indexing pipeline services...")
            
            # Initialize data service (ChromaDB)
            await self.data_service.initialize()
            logger.info("✓ Data service initialized")
            
            # Verify embedding service
            health = await self.embedding_service.check_health()
            if not health["healthy"]:
                raise IndexingServiceError(f"Embedding service not healthy: {health['error']}")
            logger.info("✓ Embedding service verified")
            
            logger.info("Indexing pipeline initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize indexing pipeline: {str(e)}")
            raise IndexingServiceError(f"Indexing pipeline initialization failed: {str(e)}")
    
    async def index_all_documents(self, 
                                data_directory: Optional[str] = None,
                                reset_collection: bool = False,
                                progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Index all documents from CSV files in the data directory
        
        Args:
            data_directory: Directory containing CSV files (default from settings)
            reset_collection: Whether to reset the collection before indexing
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dict containing indexing results and statistics
        """
        data_directory = data_directory or self.data_directory
        
        # Reset progress tracking
        self.indexing_progress = {
            "status": "running",
            "total_files": 0,
            "processed_files": 0,
            "total_documents": 0,
            "processed_documents": 0,
            "indexed_documents": 0,
            "failed_documents": 0,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "errors": []
        }
        
        try:
            logger.info(f"Starting document indexing from directory: {data_directory}")
            
            # Reset collection if requested
            if reset_collection:
                logger.info("Resetting document collection...")
                await self.data_service.reset_collection()
                logger.info("✓ Collection reset")
            
            # Step 1: Load all CSV files and documents
            logger.info("Loading documents from CSV files...")
            documents = await self._load_all_documents(data_directory, progress_callback)
            
            if not documents:
                logger.warning("No documents found to index")
                self.indexing_progress["status"] = "completed"
                self.indexing_progress["end_time"] = datetime.now().isoformat()
                return self._get_indexing_results()
            
            self.indexing_progress["total_documents"] = len(documents)
            logger.info(f"Loaded {len(documents)} documents for indexing")
            
            # Step 2: Process and index documents in batches
            logger.info("Starting document processing and indexing...")
            await self._process_and_index_documents(documents, progress_callback)
            
            # Step 3: Finalize indexing
            self.indexing_progress["status"] = "completed"
            self.indexing_progress["end_time"] = datetime.now().isoformat()
            
            results = self._get_indexing_results()
            logger.info(f"Indexing completed: {results['summary']}")
            
            return results
            
        except Exception as e:
            self.indexing_progress["status"] = "failed"
            self.indexing_progress["end_time"] = datetime.now().isoformat()
            self.indexing_progress["errors"].append(str(e))
            logger.error(f"Document indexing failed: {str(e)}")
            raise IndexingServiceError(f"Document indexing failed: {str(e)}")
    
    async def _load_all_documents(self, 
                                data_directory: str, 
                                progress_callback: Optional[callable] = None) -> List:
        """Load all documents from CSV files"""
        if not os.path.exists(data_directory):
            raise IndexingServiceError(f"Data directory does not exist: {data_directory}")
        
        # Get all CSV files
        csv_files = [f for f in os.listdir(data_directory) if f.endswith('.csv')]
        if not csv_files:
            logger.warning(f"No CSV files found in directory: {data_directory}")
            return []
        
        self.indexing_progress["total_files"] = len(csv_files)
        logger.info(f"Found {len(csv_files)} CSV files to process")
        
        all_documents = []
        
        for csv_file in csv_files:
            try:
                file_path = os.path.join(data_directory, csv_file)
                logger.info(f"Loading documents from {csv_file}...")
                
                # Load documents from CSV file
                documents = await self.data_service.load_csv_files(os.path.dirname(file_path))
                
                # Filter documents from this specific file
                file_documents = [doc for doc in documents if csv_file in str(doc.metadata.get('source_file', ''))]
                
                if not file_documents:
                    # If no source_file metadata, assume all documents are from this file
                    file_documents = documents
                
                all_documents.extend(file_documents)
                self.indexing_progress["processed_files"] += 1
                
                logger.info(f"Loaded {len(file_documents)} documents from {csv_file}")
                
                # Call progress callback if provided
                if progress_callback:
                    await progress_callback(self.indexing_progress.copy())
                
            except Exception as e:
                error_msg = f"Failed to load {csv_file}: {str(e)}"
                logger.error(error_msg)
                self.indexing_progress["errors"].append(error_msg)
                continue
        
        return all_documents
    
    async def _process_and_index_documents(self, 
                                         documents: List, 
                                         progress_callback: Optional[callable] = None):
        """Process and index documents in batches"""
        total_documents = len(documents)
        
        # Process documents in batches
        for i in range(0, total_documents, self.batch_size):
            batch_end = min(i + self.batch_size, total_documents)
            batch_documents = documents[i:batch_end]
            
            logger.info(f"Processing batch {i//self.batch_size + 1}: documents {i+1}-{batch_end}")
            
            try:
                # Step 1: Clean and preprocess document content
                processed_documents = []
                for doc in batch_documents:
                    try:
                        # Clean the document content
                        cleaned_content = self.text_processor.clean_text(doc.content)
                        
                        # Update document with cleaned content
                        doc.content = cleaned_content
                        processed_documents.append(doc)
                        
                        self.indexing_progress["processed_documents"] += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to process document {doc.id}: {str(e)}"
                        logger.error(error_msg)
                        self.indexing_progress["errors"].append(error_msg)
                        self.indexing_progress["failed_documents"] += 1
                        continue
                
                if not processed_documents:
                    logger.warning(f"No documents successfully processed in batch {i//self.batch_size + 1}")
                    continue
                
                # Step 2: Generate embeddings for the batch
                logger.info(f"Generating embeddings for {len(processed_documents)} documents...")
                
                try:
                    # Extract text content for embedding
                    texts = [doc.content for doc in processed_documents]
                    
                    # Generate embeddings in batch
                    embeddings = await self.embedding_service.embed_batch(texts)
                    
                    logger.info(f"Generated {len(embeddings)} embeddings")
                    
                except EmbeddingServiceError as e:
                    error_msg = f"Failed to generate embeddings for batch: {str(e)}"
                    logger.error(error_msg)
                    self.indexing_progress["errors"].append(error_msg)
                    self.indexing_progress["failed_documents"] += len(processed_documents)
                    continue
                
                # Step 3: Index documents with embeddings
                logger.info(f"Indexing {len(processed_documents)} documents...")
                
                try:
                    success = await self.data_service.index_documents(processed_documents, embeddings)
                    
                    if success:
                        self.indexing_progress["indexed_documents"] += len(processed_documents)
                        logger.info(f"Successfully indexed {len(processed_documents)} documents")
                    else:
                        error_msg = f"Failed to index batch {i//self.batch_size + 1}"
                        logger.error(error_msg)
                        self.indexing_progress["errors"].append(error_msg)
                        self.indexing_progress["failed_documents"] += len(processed_documents)
                
                except Exception as e:
                    error_msg = f"Failed to index batch {i//self.batch_size + 1}: {str(e)}"
                    logger.error(error_msg)
                    self.indexing_progress["errors"].append(error_msg)
                    self.indexing_progress["failed_documents"] += len(processed_documents)
                
                # Call progress callback if provided
                if progress_callback:
                    await progress_callback(self.indexing_progress.copy())
                
                # Small delay between batches to avoid overwhelming the system
                await asyncio.sleep(0.1)
                
            except Exception as e:
                error_msg = f"Failed to process batch {i//self.batch_size + 1}: {str(e)}"
                logger.error(error_msg)
                self.indexing_progress["errors"].append(error_msg)
                self.indexing_progress["failed_documents"] += len(batch_documents)
                continue
    
    def _get_indexing_results(self) -> Dict[str, Any]:
        """Get comprehensive indexing results"""
        progress = self.indexing_progress.copy()
        
        # Calculate duration
        duration = None
        if progress["start_time"] and progress["end_time"]:
            start = datetime.fromisoformat(progress["start_time"])
            end = datetime.fromisoformat(progress["end_time"])
            duration = (end - start).total_seconds()
        
        # Calculate success rate
        success_rate = 0.0
        if progress["total_documents"] > 0:
            success_rate = (progress["indexed_documents"] / progress["total_documents"]) * 100
        
        # Create summary
        summary = f"Indexed {progress['indexed_documents']}/{progress['total_documents']} documents " \
                 f"({success_rate:.1f}% success rate)"
        
        if progress["failed_documents"] > 0:
            summary += f", {progress['failed_documents']} failed"
        
        return {
            "status": progress["status"],
            "summary": summary,
            "statistics": {
                "total_files": progress["total_files"],
                "processed_files": progress["processed_files"],
                "total_documents": progress["total_documents"],
                "processed_documents": progress["processed_documents"],
                "indexed_documents": progress["indexed_documents"],
                "failed_documents": progress["failed_documents"],
                "success_rate": round(success_rate, 2),
                "duration_seconds": duration
            },
            "timestamps": {
                "start_time": progress["start_time"],
                "end_time": progress["end_time"]
            },
            "errors": progress["errors"][:10]  # Limit to first 10 errors
        }
    
    async def get_indexing_status(self) -> Dict[str, Any]:
        """Get current indexing status and progress"""
        return self._get_indexing_results()
    
    async def incremental_update(self, 
                               data_directory: Optional[str] = None,
                               progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Perform incremental update of the document index
        Only processes new or modified files
        """
        # For now, this is a simplified implementation
        # In a production system, you would track file modification times
        # and only process changed files
        
        logger.info("Performing incremental index update...")
        
        # Get current collection stats
        current_stats = await self.data_service.get_collection_stats()
        current_count = current_stats.get("total_documents", 0)
        
        # Perform full reindex (in a real implementation, this would be smarter)
        results = await self.index_all_documents(
            data_directory=data_directory,
            reset_collection=False,
            progress_callback=progress_callback
        )
        
        # Calculate what was added
        new_stats = await self.data_service.get_collection_stats()
        new_count = new_stats.get("total_documents", 0)
        added_documents = new_count - current_count
        
        results["incremental_update"] = {
            "documents_before": current_count,
            "documents_after": new_count,
            "documents_added": added_documents
        }
        
        return results
    
    async def backup_index(self, backup_path: str) -> bool:
        """Create a backup of the current document index"""
        try:
            logger.info(f"Creating index backup at {backup_path}")
            success = await self.data_service.backup_collection(backup_path)
            
            if success:
                logger.info("Index backup completed successfully")
            else:
                logger.error("Index backup failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Index backup failed: {str(e)}")
            return False
    
    async def get_index_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the document index"""
        try:
            # Get collection stats
            collection_stats = await self.data_service.get_collection_stats()
            
            # Get collection info
            collection_info = await self.data_service.get_collection_info()
            
            # Get health status
            health_status = await self.data_service.health_check()
            
            return {
                "collection_stats": collection_stats,
                "collection_info": collection_info,
                "health_status": health_status,
                "indexing_service": {
                    "batch_size": self.batch_size,
                    "data_directory": self.data_directory,
                    "last_indexing": self.indexing_progress
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get index statistics: {str(e)}")
            return {"error": str(e)}
    
    async def close(self):
        """Close all service connections"""
        try:
            await self.embedding_service.close()
            logger.info("Indexing service closed")
        except Exception as e:
            logger.error(f"Error closing indexing service: {str(e)}")