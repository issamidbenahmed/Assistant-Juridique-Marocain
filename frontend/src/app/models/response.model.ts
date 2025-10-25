export interface Source {
  document_name: string;
  article: string;
  chapter: string;
  section: string;
  pages: string;
  content: string;
  relevance_score: number;
  rank: number;
}

export interface ResponseMetadata {
  question: string;
  sources_found: number;
  confidence: number;
  validated: boolean;
  validation_score?: number;
  timestamp: string;
  processing_time: number;
}

export interface RAGResponse {
  response: string;
  sources: Source[];
  metadata: ResponseMetadata;
  performance: {
    embedding_time: number;
    search_time: number;
    generation_time: number;
    validation_time: number;
    total_time: number;
  };
}