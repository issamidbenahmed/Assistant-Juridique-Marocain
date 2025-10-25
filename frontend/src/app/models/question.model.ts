export interface QuestionRequest {
  question: string;
  include_validation?: boolean;
  max_sources?: number;
}