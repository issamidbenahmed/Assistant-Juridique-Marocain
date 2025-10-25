"""
Embedding Service for text vectorization using Ollama
"""
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
import httpx
from ..core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingServiceError(Exception):
    """Custom exception for embedding service errors"""
    pass

class EmbeddingService:
    """Service for handling text embeddings with Ollama integration"""
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.EMBEDDING_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
        self.max_retries = settings.OLLAMA_MAX_RETRIES
        self.retry_delay = settings.OLLAMA_RETRY_DELAY
        self.max_concurrent = settings.EMBEDDING_MAX_CONCURRENT
        self._client: Optional[httpx.AsyncClient] = None
        self._model_verified = False
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )
        return self._client
    
    async def _make_embedding_request(self, text: str, retry_count: int = 0) -> List[float]:
        """Make a single embedding request to Ollama with retry logic"""
        if not text or not text.strip():
            raise EmbeddingServiceError("Text cannot be empty")
        
        # Ensure model is verified before making requests
        if not self._model_verified:
            await self._verify_model()
        
        client = await self._get_client()
        
        try:
            start_time = time.time()
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text.strip()
                }
            )
            response.raise_for_status()
            
            data = response.json()
            if "embedding" not in data:
                raise EmbeddingServiceError("Invalid response format from Ollama")
            
            embedding = data["embedding"]
            if not isinstance(embedding, list) or not embedding:
                raise EmbeddingServiceError("Invalid embedding format")
            
            # Log performance metrics
            duration = time.time() - start_time
            logger.debug(f"Embedding generated in {duration:.2f}s, dimension: {len(embedding)}")
            
            return embedding
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error from Ollama: {e.response.status_code}"
            if e.response.status_code == 404:
                error_msg += f" - Model '{self.model}' not found"
            elif e.response.status_code == 500:
                error_msg += " - Internal server error in Ollama"
            
            logger.error(f"{error_msg} - {e.response.text}")
            
            # Retry on server errors
            if e.response.status_code >= 500 and retry_count < self.max_retries:
                logger.info(f"Retrying embedding request (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay * (retry_count + 1))
                return await self._make_embedding_request(text, retry_count + 1)
            
            raise EmbeddingServiceError(error_msg)
            
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to Ollama at {self.base_url}: {str(e)}"
            logger.error(error_msg)
            
            # Retry on connection errors
            if retry_count < self.max_retries:
                logger.info(f"Retrying embedding request (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay * (retry_count + 1))
                return await self._make_embedding_request(text, retry_count + 1)
            
            raise EmbeddingServiceError(error_msg)
            
        except Exception as e:
            logger.error(f"Unexpected error in embedding request: {str(e)}")
            raise EmbeddingServiceError(f"Embedding generation failed: {str(e)}")
    
    async def _verify_model(self) -> None:
        """Verify that the embedding model is available in Ollama"""
        if self._model_verified:
            return
        
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            models_data = response.json()
            available_models = [model["name"] for model in models_data.get("models", [])]
            
            if self.model not in available_models:
                logger.error(f"Embedding model '{self.model}' not found. Available models: {available_models}")
                raise EmbeddingServiceError(
                    f"Embedding model '{self.model}' not available. "
                    f"Available models: {', '.join(available_models) if available_models else 'None'}"
                )
            
            self._model_verified = True
            logger.info(f"Embedding model '{self.model}' verified and available")
            
        except httpx.RequestError as e:
            raise EmbeddingServiceError(f"Cannot connect to Ollama at {self.base_url}: {str(e)}")
        except httpx.HTTPStatusError as e:
            raise EmbeddingServiceError(f"Ollama API error during model verification: {e.response.status_code}")
    
    def _truncate_text(self, text: str, max_tokens: int = 512) -> str:
        """Truncate text to fit within model context length"""
        if not text:
            return text
        
        # Rough estimation: 1 token ≈ 4 characters for most languages
        # For safety, we use 3 characters per token
        max_chars = max_tokens * 3
        
        if len(text) <= max_chars:
            return text
        
        # Truncate and add ellipsis
        truncated = text[:max_chars-3] + "..."
        logger.warning(f"Text truncated from {len(text)} to {len(truncated)} characters")
        return truncated

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        logger.info(f"Generating embedding for text of length {len(text)}")
        
        try:
            # Truncate text if too long
            truncated_text = self._truncate_text(text)
            embedding = await self._make_embedding_request(truncated_text)
            logger.info(f"Successfully generated embedding with dimension {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"Failed to embed text: {str(e)}")
            raise
    
    async def embed_batch(self, texts: List[str], max_concurrent: Optional[int] = None) -> List[List[float]]:
        """Generate embeddings for multiple texts with configurable concurrency"""
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for batch of {len(texts)} texts")
        start_time = time.time()
        
        # Filter out empty texts and maintain original indices
        valid_texts = [(i, text) for i, text in enumerate(texts) if text and text.strip()]
        
        if not valid_texts:
            raise EmbeddingServiceError("No valid texts provided for embedding")
        
        # Create semaphore to limit concurrent requests
        max_concurrent = max_concurrent or self.max_concurrent
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def embed_with_semaphore(index_text_pair):
            async with semaphore:
                index, text = index_text_pair
                try:
                    # Truncate text if too long
                    truncated_text = self._truncate_text(text)
                    embedding = await self._make_embedding_request(truncated_text)
                    return index, embedding, None
                except Exception as e:
                    logger.error(f"Failed to embed text at index {index}: {str(e)}")
                    return index, None, str(e)
        
        try:
            # Execute all embedding requests concurrently
            results = await asyncio.gather(
                *[embed_with_semaphore(pair) for pair in valid_texts],
                return_exceptions=True
            )
            
            # Process results and handle errors
            embeddings = []
            errors = []
            
            for result in results:
                if isinstance(result, Exception):
                    errors.append(str(result))
                    continue
                
                index, embedding, error = result
                if error:
                    errors.append(f"Index {index}: {error}")
                else:
                    embeddings.append((index, embedding))
            
            if errors:
                error_summary = f"Failed to embed {len(errors)} texts: {'; '.join(errors[:3])}"
                if len(errors) > 3:
                    error_summary += f" and {len(errors) - 3} more"
                raise EmbeddingServiceError(error_summary)
            
            # Sort results by original index and extract embeddings
            embeddings.sort(key=lambda x: x[0])
            final_embeddings = [emb[1] for emb in embeddings]
            
            duration = time.time() - start_time
            logger.info(f"Successfully generated {len(final_embeddings)} embeddings in {duration:.2f}s")
            return final_embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding failed: {str(e)}")
            raise
    
    async def check_health(self) -> Dict[str, Any]:
        """Check if Ollama service is healthy and model is available"""
        health_status = {
            "healthy": False,
            "ollama_running": False,
            "model_available": False,
            "embedding_test": False,
            "error": None,
            "model_info": None,
            "response_time": None
        }
        
        client = await self._get_client()
        start_time = time.time()
        
        try:
            # Check if Ollama is running
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            health_status["ollama_running"] = True
            
            # Check if embedding model is available
            models_data = response.json()
            available_models = [model["name"] for model in models_data.get("models", [])]
            
            if self.model in available_models:
                health_status["model_available"] = True
                # Get model details
                model_details = next((m for m in models_data.get("models", []) if m["name"] == self.model), None)
                if model_details:
                    health_status["model_info"] = {
                        "name": model_details["name"],
                        "size": model_details.get("size", "unknown"),
                        "modified_at": model_details.get("modified_at", "unknown")
                    }
            else:
                health_status["error"] = f"Model '{self.model}' not found. Available: {', '.join(available_models)}"
                return health_status
            
            # Test embedding generation with a simple text
            try:
                test_embedding = await self._make_embedding_request("health check test")
                if test_embedding and len(test_embedding) > 0:
                    health_status["embedding_test"] = True
                    health_status["model_info"]["embedding_dimension"] = len(test_embedding)
                else:
                    health_status["error"] = "Embedding test returned empty result"
                    return health_status
            except Exception as e:
                health_status["error"] = f"Embedding test failed: {str(e)}"
                return health_status
            
            # All checks passed
            health_status["healthy"] = True
            health_status["response_time"] = round(time.time() - start_time, 3)
            
            logger.info(f"Ollama embedding service is healthy. Model: {self.model}, "
                       f"Dimension: {health_status['model_info']['embedding_dimension']}, "
                       f"Response time: {health_status['response_time']}s")
            
        except httpx.RequestError as e:
            health_status["error"] = f"Cannot connect to Ollama at {self.base_url}: {str(e)}"
            logger.error(health_status["error"])
        except httpx.HTTPStatusError as e:
            health_status["error"] = f"Ollama API error: {e.response.status_code}"
            logger.error(health_status["error"])
        except Exception as e:
            health_status["error"] = f"Unexpected error during health check: {str(e)}"
            logger.error(health_status["error"])
        
        return health_status
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model and service configuration"""
        return {
            "model_name": self.model,
            "base_url": self.base_url,
            "service": "ollama",
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "model_verified": self._model_verified,
            "endpoints": {
                "embeddings": f"{self.base_url}/api/embeddings",
                "models": f"{self.base_url}/api/tags"
            }
        }
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from Ollama"""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            models_data = response.json()
            return models_data.get("models", [])
            
        except Exception as e:
            logger.error(f"Failed to get available models: {str(e)}")
            raise EmbeddingServiceError(f"Failed to get available models: {str(e)}")
    
    async def switch_model(self, new_model: str) -> bool:
        """Switch to a different embedding model"""
        old_model = self.model
        self.model = new_model
        self._model_verified = False
        
        try:
            await self._verify_model()
            logger.info(f"Successfully switched embedding model from '{old_model}' to '{new_model}'")
            return True
        except Exception as e:
            # Revert to old model on failure
            self.model = old_model
            self._model_verified = False
            logger.error(f"Failed to switch to model '{new_model}': {str(e)}")
            raise EmbeddingServiceError(f"Failed to switch to model '{new_model}': {str(e)}")
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None