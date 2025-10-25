"""
Document models for legal content
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class LegalDocument(BaseModel):
    """Model for legal documents"""
    id: str
    content: str
    document_name: str
    article: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    pages: Optional[str] = None
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "doc_001",
                "content": "La société anonyme est constituée par une ou plusieurs personnes...",
                "document_name": "Loi n° 17-95",
                "article": "Article 2",
                "chapter": "TITRE PREMIER",
                "pages": "[5]",
                "metadata": {
                    "content_length": 150,
                    "indexed_at": "2024-01-01T00:00:00Z"
                },
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }