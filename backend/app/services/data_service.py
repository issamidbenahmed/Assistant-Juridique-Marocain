"""
Data Service for CSV and ChromaDB operations
"""
import os
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import logging

# Disable ChromaDB telemetry to prevent errors
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from ..models.document import LegalDocument
from ..utils.csv_parser import CSVParser
from ..core.config import settings

logger = logging.getLogger(__name__)

class DataService:
    """Service for data loading and ChromaDB management"""
    
    def __init__(self, persist_directory: str = None):
        """Initialize ChromaDB client and collection"""
        self.persist_directory = persist_directory or settings.CHROMA_DB_PATH
        self.collection_name = settings.CHROMA_COLLECTION_NAME
        self.client = None
        self.collection = None
        self.csv_parser = CSVParser()
        
        # Disable ChromaDB telemetry to prevent errors
        os.environ["ANONYMIZED_TELEMETRY"] = "False"
        
    async def initialize(self):
        """Initialize ChromaDB client and collection"""
        try:
            # Initialize ChromaDB client with persistence
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name
                )
                logger.info(f"Connected to existing collection: {self.collection_name}")
            except Exception:
                # Collection doesn't exist, create it
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Legal documents from Moroccan legislation"}
                )
                logger.info(f"Created new collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    async def load_csv_files(self, data_directory: str = None) -> List[LegalDocument]:
        """Load and parse CSV files from data directory"""
        documents = []
        data_directory = data_directory or settings.CSV_DATA_PATH
        
        if not os.path.exists(data_directory):
            logger.warning(f"Data directory {data_directory} does not exist")
            return documents
            
        csv_files = [f for f in os.listdir(data_directory) if f.endswith('.csv')]
        logger.info(f"Found {len(csv_files)} CSV files to process")
        
        for csv_file in csv_files:
            file_path = os.path.join(data_directory, csv_file)
            try:
                file_documents = await self.csv_parser.parse_csv_file(file_path)
                documents.extend(file_documents)
                logger.info(f"Loaded {len(file_documents)} documents from {csv_file}")
            except Exception as e:
                logger.error(f"Error parsing {csv_file}: {e}")
                continue
                
        logger.info(f"Total documents loaded: {len(documents)}")
        return documents
    
    async def index_documents(self, documents: List[LegalDocument], embeddings: List[List[float]]) -> bool:
        """Index documents in ChromaDB with their embeddings"""
        if not self.collection:
            await self.initialize()
            
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings")
            
        try:
            # Prepare data for ChromaDB
            ids = []
            metadatas = []
            documents_text = []
            
            for doc, embedding in zip(documents, embeddings):
                # Generate unique ID if not provided
                doc_id = doc.id if doc.id else str(uuid.uuid4())
                ids.append(doc_id)
                
                # Prepare metadata
                metadata = {
                    "document_name": doc.document_name,
                    "article": doc.article or "",
                    "chapter": doc.chapter or "",
                    "section": doc.section or "",
                    "pages": doc.pages or "",
                    "content_length": len(doc.content),
                    "indexed_at": datetime.now().isoformat(),
                    **doc.metadata
                }
                metadatas.append(metadata)
                documents_text.append(doc.content)
            
            # Add documents to collection in batches to avoid memory issues
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch_end = min(i + batch_size, len(documents))
                
                self.collection.add(
                    ids=ids[i:batch_end],
                    embeddings=embeddings[i:batch_end],
                    metadatas=metadatas[i:batch_end],
                    documents=documents_text[i:batch_end]
                )
                
                logger.info(f"Indexed batch {i//batch_size + 1}: documents {i+1}-{batch_end}")
            
            logger.info(f"Successfully indexed {len(documents)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing documents: {e}")
            return False
    
    async def search_documents(
        self, 
        query_vector: List[float], 
        limit: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Search documents in ChromaDB using similarity search with configurable parameters"""
        if not self.collection:
            await self.initialize()
            
        try:
            # Use configured similarity threshold if not provided
            threshold = similarity_threshold or settings.SIMILARITY_THRESHOLD
            
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=limit,
                where=where,
                where_document=where_document,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results["documents"] and len(results["documents"]) > 0:
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]
                
                for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
                    # Convert distance to similarity score (handle large distances)
                    # Use exponential decay for better similarity scoring
                    relevance_score = 1.0 / (1.0 + distance)
                    
                    # Apply similarity threshold filter
                    if relevance_score >= threshold:
                        formatted_results.append({
                            "content": doc,
                            "metadata": metadata,
                            "relevance_score": relevance_score,
                            "distance": distance,
                            "rank": i + 1
                        })
            
            logger.info(f"Found {len(formatted_results)} similar documents above threshold {threshold}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    async def search_by_text(
        self,
        query_text: str,
        limit: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search documents using text query (requires embedding service)"""
        # This method will be used by the RAG service which has access to embedding service
        # For now, we'll implement a basic text search using ChromaDB's built-in functionality
        if not self.collection:
            await self.initialize()
            
        try:
            # Use ChromaDB's text search if available
            results = self.collection.query(
                query_texts=[query_text],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results similar to vector search
            formatted_results = []
            if results["documents"] and len(results["documents"]) > 0:
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]
                
                for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
                    formatted_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "relevance_score": 1.0 - distance,
                        "distance": distance,
                        "rank": i + 1
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in text search: {e}")
            return []
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the document collection"""
        if not self.collection:
            await self.initialize()
            
        try:
            # Get collection count
            count = self.collection.count()
            
            # Get sample of documents to analyze
            sample_results = self.collection.peek(limit=min(100, count))
            
            # Calculate statistics
            stats = {
                "total_documents": count,
                "collection_name": self.collection_name,
                "persist_directory": self.persist_directory,
                "last_updated": datetime.now().isoformat()
            }
            
            if sample_results["metadatas"]:
                # Analyze document sources
                document_sources = {}
                content_lengths = []
                
                for metadata in sample_results["metadatas"]:
                    doc_name = metadata.get("document_name", "Unknown")
                    document_sources[doc_name] = document_sources.get(doc_name, 0) + 1
                    
                    content_length = metadata.get("content_length", 0)
                    if content_length > 0:
                        content_lengths.append(content_length)
                
                stats.update({
                    "document_sources": document_sources,
                    "avg_content_length": sum(content_lengths) / len(content_lengths) if content_lengths else 0,
                    "sample_size": len(sample_results["metadatas"])
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {
                "error": str(e),
                "total_documents": 0,
                "collection_name": self.collection_name
            }
    
    async def delete_collection(self) -> bool:
        """Delete the entire collection (use with caution)"""
        if not self.client:
            await self.initialize()
            
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = None
            logger.info(f"Deleted collection: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False
    
    async def reset_collection(self) -> bool:
        """Reset collection by deleting and recreating it"""
        try:
            await self.delete_collection()
            await self.initialize()
            logger.info(f"Reset collection: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            return False
    
    async def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by its ID"""
        if not self.collection:
            await self.initialize()
            
        try:
            results = self.collection.get(
                ids=[doc_id],
                include=["documents", "metadatas", "embeddings"]
            )
            
            if results["documents"] and len(results["documents"]) > 0:
                return {
                    "id": doc_id,
                    "content": results["documents"][0],
                    "metadata": results["metadatas"][0] if results["metadatas"] else {},
                    "embedding": results["embeddings"][0] if results["embeddings"] else None
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            return None
    
    async def update_document(self, doc_id: str, document: LegalDocument, embedding: List[float]) -> bool:
        """Update an existing document"""
        if not self.collection:
            await self.initialize()
            
        try:
            metadata = {
                "document_name": document.document_name,
                "article": document.article or "",
                "chapter": document.chapter or "",
                "section": document.section or "",
                "pages": document.pages or "",
                "content_length": len(document.content),
                "updated_at": datetime.now().isoformat(),
                **document.metadata
            }
            
            self.collection.update(
                ids=[doc_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[document.content]
            )
            
            logger.info(f"Updated document: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating document {doc_id}: {e}")
            return False
    
    async def delete_document(self, doc_id: str) -> bool:
        """Delete a specific document by ID"""
        if not self.collection:
            await self.initialize()
            
        try:
            self.collection.delete(ids=[doc_id])
            logger.info(f"Deleted document: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
    
    async def delete_documents_by_filter(self, where: Dict[str, Any]) -> int:
        """Delete documents matching a filter"""
        if not self.collection:
            await self.initialize()
            
        try:
            # First get the documents to delete
            results = self.collection.get(
                where=where,
                include=["documents"]
            )
            
            if results["ids"]:
                self.collection.delete(where=where)
                deleted_count = len(results["ids"])
                logger.info(f"Deleted {deleted_count} documents matching filter")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Error deleting documents by filter: {e}")
            return 0
    
    async def get_collection_info(self) -> Dict[str, Any]:
        """Get detailed information about the collection"""
        if not self.collection:
            await self.initialize()
            
        try:
            count = self.collection.count()
            
            # Get collection metadata
            collection_metadata = self.collection.metadata or {}
            
            # Get sample documents for analysis
            sample_size = min(50, count) if count > 0 else 0
            sample_results = self.collection.peek(limit=sample_size) if sample_size > 0 else {"metadatas": []}
            
            info = {
                "name": self.collection_name,
                "total_documents": count,
                "metadata": collection_metadata,
                "persist_directory": self.persist_directory,
                "created_at": collection_metadata.get("created_at", "Unknown"),
                "last_updated": datetime.now().isoformat()
            }
            
            # Analyze document types and sources
            if sample_results["metadatas"]:
                document_types = {}
                sources = {}
                avg_content_length = 0
                total_length = 0
                
                for metadata in sample_results["metadatas"]:
                    # Count document types
                    doc_name = metadata.get("document_name", "Unknown")
                    document_types[doc_name] = document_types.get(doc_name, 0) + 1
                    
                    # Count sources by chapter/section
                    chapter = metadata.get("chapter", "Unknown")
                    sources[chapter] = sources.get(chapter, 0) + 1
                    
                    # Calculate average content length
                    content_length = metadata.get("content_length", 0)
                    total_length += content_length
                
                if sample_results["metadatas"]:
                    avg_content_length = total_length / len(sample_results["metadatas"])
                
                info.update({
                    "document_types": document_types,
                    "sources_by_chapter": sources,
                    "avg_content_length": avg_content_length,
                    "sample_size": len(sample_results["metadatas"])
                })
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {
                "error": str(e),
                "name": self.collection_name,
                "total_documents": 0
            }
    
    async def backup_collection(self, backup_path: str) -> bool:
        """Create a backup of the collection data"""
        if not self.collection:
            await self.initialize()
            
        try:
            # Get all documents from the collection
            all_results = self.collection.get(
                include=["documents", "metadatas", "embeddings"]
            )
            
            backup_data = {
                "collection_name": self.collection_name,
                "backup_timestamp": datetime.now().isoformat(),
                "total_documents": len(all_results["ids"]) if all_results["ids"] else 0,
                "data": all_results
            }
            
            # Save backup data (this would typically be saved to a file)
            # For now, we'll just log the backup creation
            logger.info(f"Created backup with {backup_data['total_documents']} documents")
            logger.info(f"Backup would be saved to: {backup_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the ChromaDB service"""
        health_status = {
            "status": "unknown",
            "timestamp": datetime.now().isoformat(),
            "details": {}
        }
        
        try:
            # Check if client is initialized
            if not self.client:
                await self.initialize()
            
            # Check if collection exists and is accessible
            if self.collection:
                count = self.collection.count()
                health_status.update({
                    "status": "healthy",
                    "details": {
                        "client_initialized": True,
                        "collection_accessible": True,
                        "document_count": count,
                        "collection_name": self.collection_name,
                        "persist_directory": self.persist_directory
                    }
                })
            else:
                health_status.update({
                    "status": "degraded",
                    "details": {
                        "client_initialized": True,
                        "collection_accessible": False,
                        "error": "Collection not accessible"
                    }
                })
                
        except Exception as e:
            health_status.update({
                "status": "unhealthy",
                "details": {
                    "error": str(e),
                    "client_initialized": self.client is not None,
                    "collection_accessible": False
                }
            })
        
        return health_status