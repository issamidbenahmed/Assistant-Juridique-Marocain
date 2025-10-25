"""
LLM Service for text generation and validation using Ollama and Gemini
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
import httpx
import google.generativeai as genai
from ..core.config import settings

logger = logging.getLogger(__name__)

class LLMServiceError(Exception):
    """Custom exception for LLM service errors"""
    pass

class LLMService:
    """Service for LLM operations with Ollama and Gemini"""
    
    def __init__(self, ollama_base_url: Optional[str] = None, ollama_model: Optional[str] = None):
        self.ollama_base_url = ollama_base_url or settings.OLLAMA_BASE_URL
        self.ollama_model = ollama_model or settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
        self.max_retries = settings.OLLAMA_MAX_RETRIES
        self.retry_delay = settings.OLLAMA_RETRY_DELAY
        self._ollama_client: Optional[httpx.AsyncClient] = None
        self._ollama_model_verified = False
        
        # Initialize Gemini if API key is provided
        self.use_gemini = bool(settings.GEMINI_API_KEY)
        if self.use_gemini:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-pro')
        else:
            self.gemini_model = None
    
    async def _get_ollama_client(self) -> httpx.AsyncClient:
        """Get or create Ollama HTTP client"""
        if self._ollama_client is None:
            self._ollama_client = httpx.AsyncClient(
                timeout=httpx.Timeout(600.0, connect=30.0, read=600.0),  # 10 minute timeout
                limits=httpx.Limits(max_connections=3, max_keepalive_connections=1)
            )
        return self._ollama_client
    
    async def _verify_ollama_model(self) -> None:
        """Verify that the Ollama model is available"""
        if self._ollama_model_verified:
            return
        
        client = await self._get_ollama_client()
        
        try:
            response = await client.get(f"{self.ollama_base_url}/api/tags")
            response.raise_for_status()
            
            models_data = response.json()
            available_models = [model["name"] for model in models_data.get("models", [])]
            
            if self.ollama_model not in available_models:
                logger.error(f"Ollama model '{self.ollama_model}' not found. Available models: {available_models}")
                raise LLMServiceError(
                    f"Ollama model '{self.ollama_model}' not available. "
                    f"Available models: {', '.join(available_models) if available_models else 'None'}"
                )
            
            self._ollama_model_verified = True
            logger.info(f"Ollama model '{self.ollama_model}' verified and available")
            
        except httpx.RequestError as e:
            raise LLMServiceError(f"Cannot connect to Ollama at {self.ollama_base_url}: {str(e)}")
        except httpx.HTTPStatusError as e:
            raise LLMServiceError(f"Ollama API error during model verification: {e.response.status_code}")
    
    def _create_legal_prompt(self, question: str, context: str) -> str:
        """Create a concise prompt for faster legal question answering"""
        prompt_template = """Assistant juridique marocain. Réponds en français basé sur ces sources:

{context}

Question: {question}

Réponds de façon concise avec citations d'articles."""
        
        return prompt_template.format(context=context, question=question)
    
    async def _make_ollama_request(self, prompt: str, retry_count: int = 0) -> str:
        """Make a request to Ollama with retry logic"""
        if not prompt or not prompt.strip():
            raise LLMServiceError("Prompt cannot be empty")
        
        # Ensure model is verified before making requests
        if not self._ollama_model_verified:
            await self._verify_ollama_model()
        
        client = await self._get_ollama_client()
        
        try:
            start_time = time.time()
            response = await client.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt.strip(),
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent legal responses
                        "top_p": 0.9,
                        "top_k": 40,
                        "num_predict": 512  # Reduced from 2048 to 512 for faster responses
                    }
                }
            )
            response.raise_for_status()
            
            data = response.json()
            if "response" not in data:
                raise LLMServiceError("Invalid response format from Ollama")
            
            generated_text = data["response"].strip()
            if not generated_text:
                raise LLMServiceError("Empty response from Ollama")
            
            # Log performance metrics
            duration = time.time() - start_time
            logger.info(f"Ollama response generated in {duration:.2f}s, length: {len(generated_text)}")
            
            return generated_text
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error from Ollama: {e.response.status_code}"
            if e.response.status_code == 404:
                error_msg += f" - Model '{self.ollama_model}' not found"
            elif e.response.status_code == 500:
                error_msg += " - Internal server error in Ollama"
            
            logger.error(f"{error_msg} - {e.response.text}")
            
            # Retry on server errors
            if e.response.status_code >= 500 and retry_count < self.max_retries:
                logger.info(f"Retrying Ollama request (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay * (retry_count + 1))
                return await self._make_ollama_request(prompt, retry_count + 1)
            
            raise LLMServiceError(error_msg)
            
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to Ollama at {self.ollama_base_url}: {str(e)}"
            logger.error(error_msg)
            
            # Retry on connection errors
            if retry_count < self.max_retries:
                logger.info(f"Retrying Ollama request (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay * (retry_count + 1))
                return await self._make_ollama_request(prompt, retry_count + 1)
            
            raise LLMServiceError(error_msg)
            
        except Exception as e:
            logger.error(f"Unexpected error in Ollama request: {str(e)}")
            raise LLMServiceError(f"Text generation failed: {str(e)}")
    
    async def generate_with_ollama(self, question: str, context: str) -> str:
        """Generate response using Ollama with legal prompt template"""
        logger.info(f"Generating response for question of length {len(question)}")
        
        try:
            # Create structured legal prompt
            prompt = self._create_legal_prompt(question, context)
            
            # Generate response
            response = await self._make_ollama_request(prompt)
            
            logger.info(f"Successfully generated response with length {len(response)}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate response with Ollama: {str(e)}")
            raise
    
    def _create_validation_prompt(self, original_question: str, response: str, context: str) -> str:
        """Create a prompt for validating the response with Gemini"""
        validation_template = """Évalue la qualité et la précision de cette réponse juridique:

QUESTION ORIGINALE:
{question}

CONTEXTE JURIDIQUE FOURNI:
{context}

RÉPONSE À ÉVALUER:
{response}

CRITÈRES D'ÉVALUATION:
1. La réponse est-elle basée sur les sources fournies?
2. Les références juridiques sont-elles correctes?
3. La réponse est-elle complète et précise?
4. Le langage juridique est-il approprié?
5. Y a-t-il des erreurs factuelles ou des omissions importantes?

Fournis une évaluation concise (maximum 200 mots) avec:
- Note sur 10
- Points forts
- Points à améliorer (si applicable)
- Recommandations pour améliorer la réponse

ÉVALUATION:"""
        
        return validation_template.format(
            question=original_question,
            context=context,
            response=response
        )
    
    async def validate_with_gemini(self, original_question: str, response: str, context: str) -> Dict[str, Any]:
        """Validate response using Gemini API"""
        if not self.use_gemini or not self.gemini_model:
            logger.warning("Gemini validation requested but not configured")
            return {
                "validated": False,
                "score": None,
                "feedback": "Gemini validation not available",
                "error": "Gemini API key not configured"
            }
        
        try:
            logger.info("Validating response with Gemini")
            start_time = time.time()
            
            # Create validation prompt
            validation_prompt = self._create_validation_prompt(original_question, response, context)
            
            # Generate validation response
            gemini_response = await asyncio.to_thread(
                self.gemini_model.generate_content, validation_prompt
            )
            
            validation_text = gemini_response.text.strip()
            
            # Parse score from validation (simple regex approach)
            import re
            score_match = re.search(r'(?:note|score).*?(\d+(?:[.,]\d+)?)\s*/\s*10', validation_text, re.IGNORECASE)
            score = float(score_match.group(1).replace(',', '.')) if score_match else None
            
            duration = time.time() - start_time
            logger.info(f"Gemini validation completed in {duration:.2f}s, score: {score}")
            
            return {
                "validated": True,
                "score": score,
                "feedback": validation_text,
                "validation_time": duration,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Gemini validation failed: {str(e)}")
            return {
                "validated": False,
                "score": None,
                "feedback": None,
                "error": str(e)
            }
    
    async def check_ollama_health(self) -> Dict[str, Any]:
        """Check if Ollama service is healthy and model is available"""
        health_status = {
            "healthy": False,
            "ollama_running": False,
            "model_available": False,
            "generation_test": False,
            "error": None,
            "model_info": None,
            "response_time": None
        }
        
        client = await self._get_ollama_client()
        start_time = time.time()
        
        try:
            # Check if Ollama is running
            response = await client.get(f"{self.ollama_base_url}/api/tags")
            response.raise_for_status()
            health_status["ollama_running"] = True
            
            # Check if model is available
            models_data = response.json()
            available_models = [model["name"] for model in models_data.get("models", [])]
            
            if self.ollama_model in available_models:
                health_status["model_available"] = True
                # Get model details
                model_details = next((m for m in models_data.get("models", []) if m["name"] == self.ollama_model), None)
                if model_details:
                    health_status["model_info"] = {
                        "name": model_details["name"],
                        "size": model_details.get("size", "unknown"),
                        "modified_at": model_details.get("modified_at", "unknown")
                    }
            else:
                health_status["error"] = f"Model '{self.ollama_model}' not found. Available: {', '.join(available_models)}"
                return health_status
            
            # Test text generation with a simple prompt
            try:
                test_response = await self._make_ollama_request("Test de santé du service LLM")
                if test_response and len(test_response) > 0:
                    health_status["generation_test"] = True
                else:
                    health_status["error"] = "Generation test returned empty result"
                    return health_status
            except Exception as e:
                health_status["error"] = f"Generation test failed: {str(e)}"
                return health_status
            
            # All checks passed
            health_status["healthy"] = True
            health_status["response_time"] = round(time.time() - start_time, 3)
            
            logger.info(f"Ollama LLM service is healthy. Model: {self.ollama_model}, "
                       f"Response time: {health_status['response_time']}s")
            
        except httpx.RequestError as e:
            health_status["error"] = f"Cannot connect to Ollama at {self.ollama_base_url}: {str(e)}"
            logger.error(health_status["error"])
        except httpx.HTTPStatusError as e:
            health_status["error"] = f"Ollama API error: {e.response.status_code}"
            logger.error(health_status["error"])
        except Exception as e:
            health_status["error"] = f"Unexpected error during health check: {str(e)}"
            logger.error(health_status["error"])
        
        return health_status
    
    async def check_gemini_health(self) -> Dict[str, Any]:
        """Check if Gemini API is available and working"""
        health_status = {
            "healthy": False,
            "configured": self.use_gemini,
            "generation_test": False,
            "error": None,
            "response_time": None
        }
        
        if not self.use_gemini:
            health_status["error"] = "Gemini API key not configured"
            return health_status
        
        try:
            start_time = time.time()
            
            # Test with a simple prompt
            test_response = await asyncio.to_thread(
                self.gemini_model.generate_content, 
                "Test de santé de l'API Gemini. Réponds simplement 'OK'."
            )
            
            if test_response and test_response.text:
                health_status["generation_test"] = True
                health_status["healthy"] = True
                health_status["response_time"] = round(time.time() - start_time, 3)
                logger.info(f"Gemini API is healthy. Response time: {health_status['response_time']}s")
            else:
                health_status["error"] = "Gemini test returned empty response"
                
        except Exception as e:
            health_status["error"] = f"Gemini API error: {str(e)}"
            logger.error(health_status["error"])
        
        return health_status
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the LLM service configuration"""
        return {
            "ollama": {
                "base_url": self.ollama_base_url,
                "model": self.ollama_model,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
                "model_verified": self._ollama_model_verified
            },
            "gemini": {
                "configured": self.use_gemini,
                "model": "gemini-pro" if self.use_gemini else None,
                "validation_enabled": settings.USE_GEMINI_VALIDATION
            },
            "endpoints": {
                "ollama_generate": f"{self.ollama_base_url}/api/generate",
                "ollama_models": f"{self.ollama_base_url}/api/tags"
            }
        }
    
    async def get_available_ollama_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from Ollama"""
        client = await self._get_ollama_client()
        
        try:
            response = await client.get(f"{self.ollama_base_url}/api/tags")
            response.raise_for_status()
            
            models_data = response.json()
            return models_data.get("models", [])
            
        except Exception as e:
            logger.error(f"Failed to get available Ollama models: {str(e)}")
            raise LLMServiceError(f"Failed to get available models: {str(e)}")
    
    async def switch_ollama_model(self, new_model: str) -> bool:
        """Switch to a different Ollama model"""
        old_model = self.ollama_model
        self.ollama_model = new_model
        self._ollama_model_verified = False
        
        try:
            await self._verify_ollama_model()
            logger.info(f"Successfully switched Ollama model from '{old_model}' to '{new_model}'")
            return True
        except Exception as e:
            # Revert to old model on failure
            self.ollama_model = old_model
            self._ollama_model_verified = False
            logger.error(f"Failed to switch to model '{new_model}': {str(e)}")
            raise LLMServiceError(f"Failed to switch to model '{new_model}': {str(e)}")
    
    async def close(self):
        """Close the HTTP client"""
        if self._ollama_client:
            await self._ollama_client.aclose()
            self._ollama_client = None