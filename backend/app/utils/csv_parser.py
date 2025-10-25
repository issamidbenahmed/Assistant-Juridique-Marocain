"""
CSV parsing utilities for legal documents
"""
import pandas as pd
from typing import List, Dict, Any
import os
import uuid
from datetime import datetime
import logging

from ..models.document import LegalDocument

logger = logging.getLogger(__name__)

class CSVParser:
    """Parser for different CSV formats of legal documents"""
    
    def __init__(self, data_path: str = "./data"):
        self.data_path = data_path
    
    async def parse_csv_file(self, file_path: str) -> List[LegalDocument]:
        """Parse a CSV file and return LegalDocument objects"""
        try:
            # Read CSV file
            df = pd.read_csv(file_path, encoding='utf-8')
            
            # Detect format based on columns
            columns = [col.strip().lower() for col in df.columns]
            
            if 'contenu' in columns:
                # This is a legal document CSV
                return await self._parse_legal_csv(df, file_path)
            else:
                logger.warning(f"Unknown CSV format in {file_path}: {df.columns.tolist()}")
                return []
                
        except Exception as e:
            logger.error(f"Error parsing CSV file {file_path}: {e}")
            return []
    
    async def _parse_legal_csv(self, df: pd.DataFrame, file_path: str) -> List[LegalDocument]:
        """Parse legal document CSV with flexible column mapping"""
        documents = []
        file_name = os.path.basename(file_path)
        
        # Normalize column names
        df.columns = [col.strip() for col in df.columns]
        
        # Create column mapping (case-insensitive)
        column_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ['contenu', 'content']:
                column_map['content'] = col
            elif col_lower in ['doc', 'document', 'document_name']:
                column_map['document'] = col
            elif col_lower in ['article']:
                column_map['article'] = col
            elif col_lower in ['chapitre', 'chapter']:
                column_map['chapter'] = col
            elif col_lower in ['section']:
                column_map['section'] = col
            elif col_lower in ['pages', 'page']:
                column_map['pages'] = col
            elif col_lower in ['titre', 'title']:
                column_map['title'] = col
            elif col_lower in ['livre', 'book']:
                column_map['book'] = col
            elif col_lower in ['partie', 'part']:
                column_map['part'] = col
        
        # Check if we have the minimum required columns
        if 'content' not in column_map:
            logger.error(f"No content column found in {file_path}")
            return []
        
        for index, row in df.iterrows():
            try:
                # Skip rows with empty content
                content = str(row[column_map['content']]).strip()
                if not content or content.lower() in ['nan', 'null', '']:
                    continue
                
                # Extract document information
                document_name = str(row[column_map.get('document', '')]).strip() if column_map.get('document') else file_name
                article = str(row[column_map.get('article', '')]).strip() if column_map.get('article') else None
                chapter = str(row[column_map.get('chapter', '')]).strip() if column_map.get('chapter') else None
                section = str(row[column_map.get('section', '')]).strip() if column_map.get('section') else None
                pages = str(row[column_map.get('pages', '')]).strip() if column_map.get('pages') else None
                
                # Clean up None values
                if article and article.lower() in ['nan', 'null', '']:
                    article = None
                if chapter and chapter.lower() in ['nan', 'null', '']:
                    chapter = None
                if section and section.lower() in ['nan', 'null', '']:
                    section = None
                if pages and pages.lower() in ['nan', 'null', '']:
                    pages = None
                
                # Create metadata
                metadata = {
                    "source_file": file_name,
                    "row_index": index,
                    "content_length": len(content)
                }
                
                # Add additional columns as metadata
                for col in df.columns:
                    if col not in column_map.values():
                        value = str(row[col]).strip()
                        if value and value.lower() not in ['nan', 'null', '']:
                            metadata[col.lower().replace(' ', '_')] = value
                
                # Create LegalDocument
                doc = LegalDocument(
                    id=str(uuid.uuid4()),
                    content=content,
                    document_name=document_name,
                    article=article,
                    chapter=chapter,
                    section=section,
                    pages=pages,
                    metadata=metadata,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                documents.append(doc)
                
            except Exception as e:
                logger.error(f"Error processing row {index} in {file_path}: {e}")
                continue
        
        logger.info(f"Parsed {len(documents)} documents from {file_path}")
        return documents
    
    def parse_dataset1_lois(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse Dataset 1 (Lois) format: DOC, Titre, Chapitre, Section, Article, Contenu, Pages"""
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            documents = []
            
            for _, row in df.iterrows():
                if pd.notna(row.get('Contenu', '')):
                    doc = {
                        'content': str(row['Contenu']).strip(),
                        'document_name': str(row.get('DOC', '')).strip(),
                        'title': str(row.get('Titre', '')).strip(),
                        'chapter': str(row.get('Chapitre', '')).strip(),
                        'section': str(row.get('Section', '')).strip(),
                        'article': str(row.get('Article', '')).strip(),
                        'pages': str(row.get('Pages', '')).strip(),
                        'source_type': 'lois'
                    }
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error parsing Lois dataset {file_path}: {e}")
            return []
    
    def parse_dataset2_instructions(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse Dataset 2 (Instructions) format: Doc, Chapitre, Titre, SousTitre1, SousTitre2, SousTitre3, Article, Contenu, Pages"""
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            documents = []
            
            for _, row in df.iterrows():
                if pd.notna(row.get('Contenu', '')):
                    doc = {
                        'content': str(row['Contenu']).strip(),
                        'document_name': str(row.get('Doc', '')).strip(),
                        'chapter': str(row.get('Chapitre', '')).strip(),
                        'title': str(row.get('Titre', '')).strip(),
                        'subtitle1': str(row.get('SousTitre1', '')).strip(),
                        'subtitle2': str(row.get('SousTitre2', '')).strip(),
                        'subtitle3': str(row.get('SousTitre3', '')).strip(),
                        'article': str(row.get('Article', '')).strip(),
                        'pages': str(row.get('Pages', '')).strip(),
                        'source_type': 'instructions'
                    }
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error parsing Instructions dataset {file_path}: {e}")
            return []
    
    def parse_dataset3_codes(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse Dataset 3 (Codes) format: DOC, Livre, Partie, Chapitre, Section, Article, Contenu, Pages, Index"""
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            documents = []
            
            for _, row in df.iterrows():
                if pd.notna(row.get('Contenu', '')):
                    doc = {
                        'content': str(row['Contenu']).strip(),
                        'document_name': str(row.get('DOC', '')).strip(),
                        'book': str(row.get('Livre', '')).strip(),
                        'part': str(row.get('Partie', '')).strip(),
                        'chapter': str(row.get('Chapitre', '')).strip(),
                        'section': str(row.get('Section', '')).strip(),
                        'article': str(row.get('Article', '')).strip(),
                        'pages': str(row.get('Pages', '')).strip(),
                        'index': str(row.get('Index', '')).strip(),
                        'source_type': 'codes'
                    }
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error parsing Codes dataset {file_path}: {e}")
            return []
    
    def get_all_csv_files(self) -> List[str]:
        """Get all CSV files from the data directory"""
        if not os.path.exists(self.data_path):
            logger.warning(f"Data directory {self.data_path} does not exist")
            return []
        
        csv_files = []
        for file in os.listdir(self.data_path):
            if file.endswith('.csv'):
                csv_files.append(os.path.join(self.data_path, file))
        
        return csv_files
    
    async def parse_all_files(self) -> List[LegalDocument]:
        """Parse all CSV files and return unified document list"""
        all_documents = []
        csv_files = self.get_all_csv_files()
        
        for file_path in csv_files:
            documents = await self.parse_csv_file(file_path)
            all_documents.extend(documents)
        
        logger.info(f"Parsed total of {len(all_documents)} documents from {len(csv_files)} files")
        return all_documents