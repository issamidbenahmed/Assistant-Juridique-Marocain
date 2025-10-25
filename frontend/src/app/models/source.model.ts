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

export interface ConversationEntry {
  id: string;
  question: string;
  response: string;
  sources_count: number;
  confidence: number;
  timestamp: string;
  metadata: any;
}