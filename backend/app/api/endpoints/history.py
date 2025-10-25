"""
History management endpoints
"""
import logging
import json
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()


class ConversationEntry(BaseModel):
    """Model for a conversation entry"""
    id: str = Field(..., description="Unique conversation ID")
    question: str = Field(..., description="The user's question")
    response: str = Field(..., description="The assistant's response")
    sources_count: int = Field(default=0, description="Number of sources used")
    confidence: float = Field(default=0.0, description="Response confidence score")
    timestamp: str = Field(..., description="ISO timestamp of the conversation")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")


class ConversationHistory(BaseModel):
    """Model for conversation history response"""
    conversations: List[ConversationEntry] = Field(default=[], description="List of conversations")
    total_count: int = Field(default=0, description="Total number of conversations")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Number of items per page")
    has_more: bool = Field(default=False, description="Whether there are more pages")


class SaveConversationRequest(BaseModel):
    """Request model for saving a conversation"""
    question: str = Field(..., description="The user's question")
    response: str = Field(..., description="The assistant's response")
    sources_count: Optional[int] = Field(default=0, description="Number of sources used")
    confidence: Optional[float] = Field(default=0.0, description="Response confidence score")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class HistoryService:
    """Simple file-based history service"""
    
    def __init__(self, history_file: str = "./data/conversation_history.json"):
        self.history_file = history_file
        self.ensure_history_file()
    
    def ensure_history_file(self):
        """Ensure the history file and directory exist"""
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    def load_history(self) -> List[Dict[str, Any]]:
        """Load conversation history from file"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def save_history(self, history: List[Dict[str, Any]]):
        """Save conversation history to file"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def add_conversation(self, conversation: Dict[str, Any]) -> str:
        """Add a new conversation to history"""
        history = self.load_history()
        
        # Generate unique ID
        conversation_id = str(uuid.uuid4())
        conversation["id"] = conversation_id
        conversation["timestamp"] = datetime.now().isoformat()
        
        # Add to beginning of list (most recent first)
        history.insert(0, conversation)
        
        # Keep only last 1000 conversations to prevent file from growing too large
        if len(history) > 1000:
            history = history[:1000]
        
        self.save_history(history)
        return conversation_id
    
    def get_conversations(self, 
                         page: int = 1, 
                         page_size: int = 50,
                         search_query: Optional[str] = None,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get paginated conversation history with optional filtering"""
        history = self.load_history()
        
        # Apply filters
        filtered_history = []
        for conv in history:
            # Date filter
            if start_date or end_date:
                try:
                    conv_date = datetime.fromisoformat(conv.get("timestamp", ""))
                    if start_date and conv_date < start_date:
                        continue
                    if end_date and conv_date > end_date:
                        continue
                except ValueError:
                    continue
            
            # Search filter
            if search_query:
                search_lower = search_query.lower()
                question = conv.get("question", "").lower()
                response = conv.get("response", "").lower()
                if search_lower not in question and search_lower not in response:
                    continue
            
            filtered_history.append(conv)
        
        # Pagination
        total_count = len(filtered_history)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_conversations = filtered_history[start_idx:end_idx]
        
        return {
            "conversations": page_conversations,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": end_idx < total_count
        }
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a specific conversation"""
        history = self.load_history()
        original_length = len(history)
        
        history = [conv for conv in history if conv.get("id") != conversation_id]
        
        if len(history) < original_length:
            self.save_history(history)
            return True
        return False
    
    def clear_history(self, before_date: Optional[datetime] = None) -> int:
        """Clear conversation history, optionally before a specific date"""
        history = self.load_history()
        original_count = len(history)
        
        if before_date:
            # Keep conversations after the specified date
            filtered_history = []
            for conv in history:
                try:
                    conv_date = datetime.fromisoformat(conv.get("timestamp", ""))
                    if conv_date >= before_date:
                        filtered_history.append(conv)
                except ValueError:
                    # Keep conversations with invalid timestamps
                    filtered_history.append(conv)
            history = filtered_history
        else:
            # Clear all history
            history = []
        
        self.save_history(history)
        return original_count - len(history)


# Global history service instance
history_service = HistoryService()


@router.get("/history", response_model=ConversationHistory)
async def get_history(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    search: Optional[str] = Query(default=None, description="Search query for questions and responses"),
    start_date: Optional[str] = Query(default=None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(default=None, description="End date filter (ISO format)")
) -> ConversationHistory:
    """
    Get conversation history with pagination and filtering
    
    Args:
        page: Page number (1-based)
        page_size: Number of conversations per page (1-100)
        search: Optional search query to filter conversations
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)
        
    Returns:
        ConversationHistory: Paginated conversation history
        
    Raises:
        HTTPException: If date parsing fails
    """
    try:
        # Parse date filters if provided
        start_dt = None
        end_dt = None
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid start_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )
        
        # Get conversations
        result = history_service.get_conversations(
            page=page,
            page_size=page_size,
            search_query=search,
            start_date=start_dt,
            end_date=end_dt
        )
        
        # Convert to response model
        conversations = []
        for conv in result["conversations"]:
            entry = ConversationEntry(
                id=conv.get("id", ""),
                question=conv.get("question", ""),
                response=conv.get("response", ""),
                sources_count=conv.get("sources_count", 0),
                confidence=conv.get("confidence", 0.0),
                timestamp=conv.get("timestamp", ""),
                metadata=conv.get("metadata", {})
            )
            conversations.append(entry)
        
        return ConversationHistory(
            conversations=conversations,
            total_count=result["total_count"],
            page=result["page"],
            page_size=result["page_size"],
            has_more=result["has_more"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve conversation history"
        )


@router.post("/history")
async def save_conversation(request_data: SaveConversationRequest):
    """
    Save a new conversation to history
    
    Args:
        request_data: Conversation data to save
        
    Returns:
        Dict: Success response with conversation ID
        
    Raises:
        HTTPException: If saving fails
    """
    try:
        conversation = {
            "question": request_data.question,
            "response": request_data.response,
            "sources_count": request_data.sources_count,
            "confidence": request_data.confidence,
            "metadata": request_data.metadata
        }
        
        conversation_id = history_service.add_conversation(conversation)
        
        logger.info(f"Saved conversation {conversation_id}")
        
        return {
            "status": "success",
            "message": "Conversation saved successfully",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to save conversation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to save conversation"
        )


@router.delete("/history/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a specific conversation from history
    
    Args:
        conversation_id: ID of the conversation to delete
        
    Returns:
        Dict: Success or error response
        
    Raises:
        HTTPException: If conversation not found or deletion fails
    """
    try:
        success = history_service.delete_conversation(conversation_id)
        
        if success:
            logger.info(f"Deleted conversation {conversation_id}")
            return {
                "status": "success",
                "message": "Conversation deleted successfully",
                "conversation_id": conversation_id
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete conversation"
        )


@router.delete("/history")
async def clear_history(
    before_date: Optional[str] = Query(default=None, description="Clear conversations before this date (ISO format)")
):
    """
    Clear conversation history
    
    Args:
        before_date: Optional date to clear conversations before (ISO format)
        
    Returns:
        Dict: Success response with count of deleted conversations
        
    Raises:
        HTTPException: If date parsing or clearing fails
    """
    try:
        before_dt = None
        
        if before_date:
            try:
                before_dt = datetime.fromisoformat(before_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid before_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )
        
        deleted_count = history_service.clear_history(before_date=before_dt)
        
        message = f"Cleared {deleted_count} conversations"
        if before_date:
            message += f" before {before_date}"
        
        logger.info(message)
        
        return {
            "status": "success",
            "message": message,
            "deleted_count": deleted_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to clear conversation history"
        )


@router.get("/history/stats")
async def get_history_stats():
    """
    Get statistics about conversation history
    
    Returns:
        Dict: History statistics
    """
    try:
        history = history_service.load_history()
        
        if not history:
            return {
                "total_conversations": 0,
                "date_range": None,
                "avg_confidence": 0.0,
                "avg_sources": 0.0
            }
        
        # Calculate statistics
        total_conversations = len(history)
        
        # Date range
        timestamps = [conv.get("timestamp") for conv in history if conv.get("timestamp")]
        date_range = None
        if timestamps:
            try:
                dates = [datetime.fromisoformat(ts) for ts in timestamps]
                date_range = {
                    "earliest": min(dates).isoformat(),
                    "latest": max(dates).isoformat()
                }
            except ValueError:
                pass
        
        # Average confidence and sources
        confidences = [conv.get("confidence", 0.0) for conv in history]
        sources_counts = [conv.get("sources_count", 0) for conv in history]
        
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        avg_sources = sum(sources_counts) / len(sources_counts) if sources_counts else 0.0
        
        # Recent activity (last 7 days)
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_conversations = 0
        for conv in history:
            try:
                conv_date = datetime.fromisoformat(conv.get("timestamp", ""))
                if conv_date >= recent_cutoff:
                    recent_conversations += 1
            except ValueError:
                continue
        
        return {
            "total_conversations": total_conversations,
            "recent_conversations_7d": recent_conversations,
            "date_range": date_range,
            "avg_confidence": round(avg_confidence, 2),
            "avg_sources": round(avg_sources, 1),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get history stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get history statistics"
        )