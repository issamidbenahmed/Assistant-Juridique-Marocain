"""
Text processing utilities for legal documents
"""
import re
from typing import List, Dict, Any, Optional
import unicodedata

class TextProcessor:
    """Utilities for text cleaning and preprocessing"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text content"""
        if not text or not isinstance(text, str):
            return ""
        
        # Remove extra whitespace first
        text = TextProcessor.remove_extra_whitespace(text)
        
        # Normalize unicode characters
        text = unicodedata.normalize('NFKC', text)
        
        # Remove or replace problematic characters
        text = re.sub(r'["""]', '"', text)  # Normalize quotes
        text = re.sub(r"[''']", "'", text)  # Normalize apostrophes
        text = re.sub(r'[–—]', '-', text)   # Normalize dashes
        text = re.sub(r'…', '...', text)    # Normalize ellipsis
        
        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Clean up common legal document artifacts
        text = re.sub(r'\s*\[\s*\]', '', text)  # Remove empty brackets
        text = re.sub(r'\s*\(\s*\)', '', text)  # Remove empty parentheses
        
        return text.strip()
    
    @staticmethod
    def remove_extra_whitespace(text: str) -> str:
        """Remove extra whitespace and normalize spacing"""
        if not text or not isinstance(text, str):
            return ""
        
        # Replace multiple whitespace characters with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Clean up spacing around punctuation
        text = re.sub(r'\s*([,.;:!?])\s*', r'\1 ', text)
        text = re.sub(r'\s*([(){}])\s*', r'\1', text)
        text = re.sub(r'\s*(\[)', r' \1', text)  # Space before opening bracket
        text = re.sub(r'(\])\s*', r'\1', text)   # No space after closing bracket
        
        # Remove extra spaces created by punctuation cleanup
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    @staticmethod
    def extract_metadata_from_text(text: str) -> Dict[str, Any]:
        """Extract metadata patterns from legal text"""
        if not text or not isinstance(text, str):
            return {}
        
        metadata = {}
        
        # Extract article numbers
        article_match = re.search(r'Article\s+(\d+(?:\.\d+)*)\s*[:\-]?', text, re.IGNORECASE)
        if article_match:
            metadata['article_number'] = article_match.group(1)
        
        # Extract law references (Loi n° XX-XX)
        law_match = re.search(r'Loi\s+n°\s*(\d+[-\s]*\d+)', text, re.IGNORECASE)
        if law_match:
            metadata['law_reference'] = law_match.group(1)
        
        # Extract dahir references
        dahir_match = re.search(r'dahir\s+n°\s*([^\s,;.]+)', text, re.IGNORECASE)
        if dahir_match:
            metadata['dahir_reference'] = dahir_match.group(1)
        
        # Extract page references [X] or [X-Y]
        page_matches = re.findall(r'\[(\d+(?:-\d+)?)\]', text)
        if page_matches:
            metadata['page_references'] = page_matches
        
        # Extract dates (various formats)
        date_patterns = [
            r'\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}',
            r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}'
        ]
        
        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, text, re.IGNORECASE))
        
        if dates:
            metadata['dates'] = dates
        
        # Extract monetary amounts (dirhams)
        money_matches = re.findall(r'(\d+(?:\s*\d+)*)\s*(?:dirhams?|DH)', text, re.IGNORECASE)
        if money_matches:
            metadata['monetary_amounts'] = money_matches
        
        # Extract percentages
        percentage_matches = re.findall(r'(\d+(?:[.,]\d+)?)\s*%', text)
        if percentage_matches:
            metadata['percentages'] = percentage_matches
        
        # Calculate text statistics
        metadata['text_length'] = len(text)
        metadata['word_count'] = len(text.split())
        metadata['sentence_count'] = len(re.findall(r'[.!?]+', text))
        
        return metadata
    
    @staticmethod
    def chunk_text(text: str, max_length: int = 1000, overlap: int = 100) -> List[Dict[str, Any]]:
        """Split text into chunks for processing with metadata"""
        if not text or not isinstance(text, str):
            return []
        
        if max_length <= overlap:
            raise ValueError("max_length must be greater than overlap")
        
        chunks = []
        words = text.split()
        
        if not words:
            return []
        
        # If text is shorter than max_length, return as single chunk
        if len(text) <= max_length:
            return [{
                'text': text,
                'start_word': 0,
                'end_word': len(words) - 1,
                'chunk_index': 0,
                'total_chunks': 1,
                'word_count': len(words),
                'char_count': len(text)
            }]
        
        current_pos = 0
        chunk_index = 0
        
        while current_pos < len(words):
            # Calculate chunk boundaries
            chunk_words = []
            current_length = 0
            word_start = current_pos
            
            # Add words until we reach max_length
            while current_pos < len(words) and current_length < max_length:
                word = words[current_pos]
                # Check if adding this word would exceed max_length
                if current_length + len(word) + 1 > max_length and chunk_words:
                    break
                
                chunk_words.append(word)
                current_length += len(word) + (1 if chunk_words else 0)  # +1 for space
                current_pos += 1
            
            if not chunk_words:  # Safety check for very long words
                chunk_words = [words[current_pos]]
                current_pos += 1
            
            chunk_text = ' '.join(chunk_words)
            
            chunks.append({
                'text': chunk_text,
                'start_word': word_start,
                'end_word': word_start + len(chunk_words) - 1,
                'chunk_index': chunk_index,
                'total_chunks': 0,  # Will be updated after all chunks are created
                'word_count': len(chunk_words),
                'char_count': len(chunk_text)
            })
            
            chunk_index += 1
            
            # Calculate overlap for next chunk
            if current_pos < len(words):
                overlap_words = min(overlap // 10, len(chunk_words) // 2)  # Approximate overlap in words
                current_pos = max(word_start + len(chunk_words) - overlap_words, word_start + 1)
        
        # Update total_chunks for all chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk['total_chunks'] = total_chunks
        
        return chunks
    
    @staticmethod
    def extract_legal_entities(text: str) -> Dict[str, List[str]]:
        """Extract legal entities and terms from text"""
        if not text or not isinstance(text, str):
            return {}
        
        entities = {
            'companies': [],
            'legal_forms': [],
            'institutions': [],
            'legal_terms': []
        }
        
        # Company types and legal forms
        legal_forms_patterns = [
            r'société\s+anonyme|SA\b',
            r'société\s+à\s+responsabilité\s+limitée|SARL\b',
            r'société\s+en\s+nom\s+collectif|SNC\b',
            r'société\s+en\s+commandite|SCS\b',
            r'société\s+civile|SC\b'
        ]
        
        for pattern in legal_forms_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['legal_forms'].extend([match.strip() for match in matches])
        
        # Legal institutions
        institution_patterns = [
            r'registre\s+du\s+commerce',
            r'tribunal\s+de\s+commerce',
            r'cour\s+d\'appel',
            r'cour\s+de\s+cassation',
            r'conseil\s+d\'état'
        ]
        
        for pattern in institution_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['institutions'].extend([match.strip() for match in matches])
        
        # Common legal terms
        legal_terms_patterns = [
            r'capital\s+social',
            r'assemblée\s+générale',
            r'conseil\s+d\'administration',
            r'commissaire\s+aux\s+comptes',
            r'statuts?\s+(?:de\s+la\s+)?société',
            r'immatriculation',
            r'personnalité\s+morale'
        ]
        
        for pattern in legal_terms_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['legal_terms'].extend([match.strip() for match in matches])
        
        # Remove duplicates and empty strings
        for key in entities:
            entities[key] = list(set(filter(None, entities[key])))
        
        return entities
    
    @staticmethod
    def preprocess_for_embedding(text: str) -> str:
        """Preprocess text specifically for embedding generation"""
        if not text or not isinstance(text, str):
            return ""
        
        # Clean the text first
        text = TextProcessor.clean_text(text)
        
        # Convert to lowercase for better embedding consistency
        text = text.lower()
        
        # Remove page references and other metadata that might interfere with semantic meaning
        text = re.sub(r'\s*\[\s*\d+(?:-\d+)?\s*\]\s*', ' ', text)  # Remove page references
        text = re.sub(r'\s*\([^)]*\)\s*', ' ', text)  # Remove parenthetical content
        
        # Normalize legal abbreviations
        abbreviations = {
            r'\bsa\b': 'société anonyme',
            r'\bsarl\b': 'société à responsabilité limitée',
            r'\bsnc\b': 'société en nom collectif',
            r'\bscs\b': 'société en commandite simple',
            r'\bdh\b': 'dirhams',
            r'\bn°': 'numéro'
        }
        
        for abbrev, full_form in abbreviations.items():
            text = re.sub(abbrev, full_form, text, flags=re.IGNORECASE)
        
        # Final cleanup
        text = TextProcessor.remove_extra_whitespace(text)
        
        return text