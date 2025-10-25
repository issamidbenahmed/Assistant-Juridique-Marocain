"""
Response models for API endpoints
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class Source(BaseModel):
    """Source information for legal documents"""
    content: str
    document: str
    article: Optional[str] = None
    chapter: Optional[str] = None
    pages: Optional[str] = None
    relevance_score: float

class ResponseMetadata(BaseModel):
    """Metadata for RAG responses"""
    question: str
    sources_found: int
    confidence: float
    validated: bool
    validation_score: Optional[float] = None
    timestamp: str
    processing_time: float
    model_used: str
    total_documents_searched: int

class RAGResponse(BaseModel):
    """Response model for RAG pipeline"""
    response: str
    sources: List[Source]
    metadata: ResponseMetadata
    processing_time: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "Une société anonyme est...",
                "sources": [
                    {
                        "content": "La société anonyme est constituée...",
                        "document": "Loi n° 17-95",
                        "article": "Article 2",
                        "chapter": "TITRE PREMIER",
                        "pages": "[5]",
                        "relevance_score": 0.95
                    }
                ],
                "metadata": {
                    "model_used": "llama2",
                    "validated": True,
                    "total_documents_searched": 150,
                    "timestamp": "2024-01-01T00:00:00Z"
                },
                "processing_time": 2.5
            }
        }