"""
Configuration settings for the application
"""
from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Assistant Juridique Marocain"
    
    # CORS Settings
    ALLOWED_HOSTS: List[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    
    # Ollama Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"  # Faster model than llama2
    EMBEDDING_MODEL: str = "nomic-embed-text:latest"
    OLLAMA_TIMEOUT: float = 600.0  # 10 minutes for LLM requests
    OLLAMA_MAX_RETRIES: int = 3
    OLLAMA_RETRY_DELAY: float = 1.0
    EMBEDDING_MAX_CONCURRENT: int = 5
    
    # Gemini Settings
    GEMINI_API_KEY: str = ""
    USE_GEMINI_VALIDATION: bool = True
    
    # ChromaDB Settings
    CHROMA_DB_PATH: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "legal_documents"
    
    # Data Settings
    CSV_DATA_PATH: str = "../data"
    
    # Performance Settings
    MAX_SOURCES: int = 3  # Reduced from 5 to 3 for faster responses
    SIMILARITY_THRESHOLD: float = 0.002  # Adjusted for new similarity calculation
    
    # Development Settings
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()