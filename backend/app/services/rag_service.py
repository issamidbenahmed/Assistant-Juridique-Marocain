"""
RAG Pipeline Service - Orchestrates the complete Retrieval-Augmented Generation workflow
"""
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RAGServiceError(Exception):
    """Custom exception for RAG service errors"""
    pass


class RAGService:
    """Service for orchestrating the complete RAG pipeline"""
    
    def __init__(self, 
                 embedding_service=None,
                 llm_service=None,
                 data_service=None,
                 text_processor=None,
                 fast_mode=False):
        """Initialize RAG service with all required components"""
        # Import here to avoid circular imports
        from .embedding_service import EmbeddingService
        from .llm_service import LLMService
        from .data_service import DataService
        from ..utils.text_processor import TextProcessor
        from ..core.config import settings
        
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()
        self.data_service = data_service or DataService()
        self.text_processor = text_processor or TextProcessor()
        
        # Configuration from settings
        self.max_sources = settings.MAX_SOURCES
        self.fast_mode = fast_mode
        if fast_mode:
            self.max_sources = min(self.max_sources, 2)  # Limit to 2 sources in fast mode
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD
        
        # Performance tracking
        self._performance_metrics = {
            "total_queries": 0,
            "avg_response_time": 0.0,
            "avg_embedding_time": 0.0,
            "avg_search_time": 0.0,
            "avg_generation_time": 0.0,
            "avg_validation_time": 0.0
        }
    
    async def get_pipeline_info(self) -> Dict[str, Any]:
        """Get information about the RAG pipeline configuration"""
        return {
            "pipeline_version": "1.0.0",
            "configuration": {
                "max_sources": self.max_sources,
                "similarity_threshold": self.similarity_threshold
            },
            "performance_metrics": self._performance_metrics.copy()
        }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all RAG pipeline components"""
        return {
            "healthy": True,
            "timestamp": datetime.now().isoformat()
        }
    
    async def process_question(self, 
                              question: str,
                              max_sources: Optional[int] = None,
                              similarity_threshold: Optional[float] = None,
                              validate_response: Optional[bool] = None) -> Dict[str, Any]:
        """
        Process a question through the complete RAG pipeline
        
        Args:
            question: The user's question
            max_sources: Maximum number of sources to retrieve
            similarity_threshold: Minimum similarity threshold for sources
            validate_response: Whether to validate the response
            
        Returns:
            Dict containing response, sources, metadata, and performance metrics
        """
        start_time = time.time()
        
        try:
            logger.info(f"Processing question: {question[:100]}...")
            
            # Step 1: Generate question embedding
            embedding_start = time.time()
            question_embedding = await self.embedding_service.embed_text(question)
            embedding_time = time.time() - embedding_start
            logger.info(f"Generated question embedding in {embedding_time:.2f}s")
            
            # Step 2: Search for relevant documents
            search_start = time.time()
            search_results = await self.data_service.search_documents(
                query_vector=question_embedding,
                limit=max_sources or self.max_sources,
                similarity_threshold=similarity_threshold or self.similarity_threshold
            )
            search_time = time.time() - search_start
            logger.info(f"Found {len(search_results)} relevant documents in {search_time:.2f}s")
            
            # Step 3: Prepare context from search results
            context = self._prepare_context(search_results)
            logger.debug(f"Prepared context with {len(context)} characters")
            
            # Step 4: Generate response using LLM
            generation_start = time.time()
            response = await self.llm_service.generate_with_ollama(
                question=question,
                context=context
            )
            generation_time = time.time() - generation_start
            logger.info(f"Generated response in {generation_time:.2f}s")
            
            # Step 5: Prepare sources for response
            sources = self._prepare_sources(search_results)
            
            # Step 6: Calculate confidence score
            confidence = self._calculate_confidence(search_results, response)
            
            # Step 7: Prepare metadata
            total_time = time.time() - start_time
            metadata = {
                "question": question,
                "sources_found": len(sources),
                "confidence": confidence,
                "validated": False,
                "validation_score": None,
                "timestamp": datetime.now().isoformat(),
                "processing_time": total_time,
                "model_used": self.llm_service.ollama_model if hasattr(self.llm_service, 'ollama_model') else "unknown",
                "total_documents_searched": len(search_results)
            }
            
            # Performance metrics
            performance = {
                "total_time": total_time,
                "embedding_time": embedding_time,
                "search_time": search_time,
                "generation_time": generation_time,
                "validation_time": 0.0
            }
            
            # Update performance metrics
            self._update_performance_metrics(performance)
            
            logger.info(f"RAG pipeline completed successfully in {total_time:.2f}s")
            
            return {
                "response": response,
                "sources": sources,
                "metadata": metadata,
                "performance": performance
            }
            
        except Exception as e:
            logger.error(f"RAG pipeline failed: {str(e)}", exc_info=True)
            raise RAGServiceError(f"Failed to process question: {str(e)}")
    
    def _prepare_context(self, search_results: List[Dict[str, Any]]) -> str:
        """Prepare context string from search results"""
        if not search_results:
            return ""
        
        context_parts = []
        # Adjust context length based on mode
        max_context_length = 800 if getattr(self, 'fast_mode', False) else 1500
        current_length = 0
        
        for i, result in enumerate(search_results[:self.max_sources], 1):
            metadata = result.get("metadata", {})
            content = result.get("content", "")
            
            # Truncate content based on mode
            max_content_length = 200 if getattr(self, 'fast_mode', False) else 300
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."
            
            # Format context entry (shorter format)
            context_entry = f"""Source {i}: {metadata.get('document_name', 'Unknown')} - {metadata.get('article', 'N/A')}
{content}
"""
            
            # Check if adding this would exceed limit
            if current_length + len(context_entry) > max_context_length:
                break
                
            context_parts.append(context_entry)
            current_length += len(context_entry)
        
        return "\n".join(context_parts)
    
    def _prepare_sources(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare sources list from search results"""
        sources = []
        
        for i, result in enumerate(search_results, 1):
            metadata = result.get("metadata", {})
            
            source = {
                "document_name": metadata.get("document_name", ""),
                "article": metadata.get("article", ""),
                "chapter": metadata.get("chapter", ""),
                "section": metadata.get("section", ""),
                "pages": metadata.get("pages", ""),
                "content": result.get("content", ""),
                "relevance_score": result.get("relevance_score", 0.0),
                "rank": i
            }
            sources.append(source)
        
        return sources
    
    def _calculate_confidence(self, search_results: List[Dict[str, Any]], response: str) -> float:
        """Calculate confidence score based on search results and response quality"""
        if not search_results:
            return 0.0
        
        # Base confidence on average similarity of top results
        similarities = []
        for result in search_results[:3]:  # Top 3 results
            # Use the relevance_score that was already calculated correctly
            similarity = result.get("relevance_score", 0.0)
            similarities.append(similarity)
        
        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            # Scale to 0-100 and apply some adjustments
            confidence = min(100.0, avg_similarity * 100 * 1.2)  # Slight boost
            return round(confidence, 1)
        
        return 50.0  # Default confidence
    
    def _update_performance_metrics(self, performance: Dict[str, float]):
        """Update running performance metrics"""
        self._performance_metrics["total_queries"] += 1
        
        # Update averages
        total_queries = self._performance_metrics["total_queries"]
        
        for metric in ["avg_response_time", "avg_embedding_time", "avg_search_time", "avg_generation_time"]:
            current_avg = self._performance_metrics[metric]
            new_value = performance.get(metric.replace("avg_", ""), 0.0)
            
            # Calculate running average
            self._performance_metrics[metric] = (
                (current_avg * (total_queries - 1) + new_value) / total_queries
            )

    async def close(self):
        """Close all service connections"""
        pass