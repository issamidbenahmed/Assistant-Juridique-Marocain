"""
Request models for API endpoints
"""
from pydantic import BaseModel
from typing import Optional

class QuestionRequest(BaseModel):
    """Request model for asking questions"""
    question: str
    include_validation: bool = True
    max_sources: int = 3
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Qu'est-ce qu'une société anonyme selon la loi marocaine?",
                "include_validation": True,
                "max_sources": 3
            }
        }