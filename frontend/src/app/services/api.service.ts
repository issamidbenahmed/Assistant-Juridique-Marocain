import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map, timeout } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { RAGResponse } from '../models/response.model';

export interface AskRequest {
  question: string;
  max_sources?: number;
  similarity_threshold?: number;
  validate_response?: boolean;
}

export interface AskResponse {
  response: string;
  sources: any[];
  metadata: any;
  performance: any;
}

export interface ReloadDataRequest {
  reset_collection?: boolean;
  data_directory?: string;
  incremental?: boolean;
}

export interface ReloadDataResponse {
  status: string;
  message: string;
  statistics: any;
  task_id?: string;
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

export interface ConversationHistory {
  conversations: ConversationEntry[];
  total_count: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface SaveConversationRequest {
  question: string;
  response: string;
  sources_count?: number;
  confidence?: number;
  metadata?: any;
}

export interface HealthStatus {
  status: string;
  components?: any;
  timestamp: string;
}

export interface ApiInfo {
  api: any;
  configuration: any;
  services: any;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // Question processing endpoints
  askQuestion(request: AskRequest): Observable<AskResponse> {
    return this.http.post<AskResponse>(`${this.baseUrl}/ask`, request)
      .pipe(
        timeout(600000), // 10 minute timeout for LLM requests
        catchError(this.handleError)
      );
  }

  getAskHealth(): Observable<HealthStatus> {
    return this.http.get<HealthStatus>(`${this.baseUrl}/ask/health`)
      .pipe(catchError(this.handleError));
  }

  getAskInfo(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/ask/info`)
      .pipe(catchError(this.handleError));
  }

  // Data management endpoints
  reloadData(request: ReloadDataRequest = {}): Observable<ReloadDataResponse> {
    return this.http.post<ReloadDataResponse>(`${this.baseUrl}/reload-data`, request)
      .pipe(catchError(this.handleError));
  }

  getReloadStatus(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/reload-data/status`)
      .pipe(catchError(this.handleError));
  }

  getCollectionStats(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/collection/stats`)
      .pipe(catchError(this.handleError));
  }

  getCollectionHealth(): Observable<HealthStatus> {
    return this.http.get<HealthStatus>(`${this.baseUrl}/collection/health`)
      .pipe(catchError(this.handleError));
  }

  getCollectionInfo(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/collection/info`)
      .pipe(catchError(this.handleError));
  }

  backupCollection(backupPath?: string): Observable<any> {
    const body = backupPath ? { backup_path: backupPath } : {};
    return this.http.post<any>(`${this.baseUrl}/collection/backup`, body)
      .pipe(catchError(this.handleError));
  }

  // History management endpoints
  getHistory(
    page: number = 1,
    pageSize: number = 50,
    search?: string,
    startDate?: string,
    endDate?: string
  ): Observable<ConversationHistory> {
    let params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    if (search) {
      params = params.set('search', search);
    }
    if (startDate) {
      params = params.set('start_date', startDate);
    }
    if (endDate) {
      params = params.set('end_date', endDate);
    }

    return this.http.get<ConversationHistory>(`${this.baseUrl}/history`, { params })
      .pipe(catchError(this.handleError));
  }

  saveConversation(request: SaveConversationRequest): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/history`, request)
      .pipe(catchError(this.handleError));
  }

  deleteConversation(conversationId: string): Observable<any> {
    return this.http.delete<any>(`${this.baseUrl}/history/${conversationId}`)
      .pipe(catchError(this.handleError));
  }

  clearHistory(beforeDate?: string): Observable<any> {
    let params = new HttpParams();
    if (beforeDate) {
      params = params.set('before_date', beforeDate);
    }

    return this.http.delete<any>(`${this.baseUrl}/history`, { params })
      .pipe(catchError(this.handleError));
  }

  getHistoryStats(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/history/stats`)
      .pipe(catchError(this.handleError));
  }

  // General API endpoints
  getHealth(): Observable<HealthStatus> {
    return this.http.get<HealthStatus>(`${environment.apiUrl.replace('/api/v1', '')}/health`)
      .pipe(catchError(this.handleError));
  }

  getApiInfo(): Observable<ApiInfo> {
    return this.http.get<ApiInfo>(`${environment.apiUrl.replace('/api/v1', '')}/info`)
      .pipe(catchError(this.handleError));
  }

  // Utility methods
  testConnection(): Observable<boolean> {
    return this.getHealth().pipe(
      map(health => health.status === 'healthy' || health.status === 'degraded'),
      catchError(() => throwError(() => false))
    );
  }

  private handleError(error: HttpErrorResponse | any) {
    let errorMessage = 'Une erreur est survenue';
    
    // Handle timeout errors specifically
    if (error.name === 'TimeoutError') {
      errorMessage = 'La requête a pris trop de temps. Le système traite peut-être une question complexe. Veuillez réessayer.';
      console.error('Request timeout:', error);
      return throwError(() => errorMessage);
    }
    
    if (error.error instanceof ErrorEvent) {
      // Client-side error
      errorMessage = `Erreur de connexion: ${error.error.message}`;
    } else {
      // Server-side error
      if (error.error && error.error.detail) {
        errorMessage = error.error.detail;
      } else if (error.error && error.error.message) {
        errorMessage = error.error.message;
      } else {
        switch (error.status) {
          case 0:
            errorMessage = 'Impossible de se connecter au serveur. Vérifiez que le backend est démarré.';
            break;
          case 400:
            errorMessage = 'Requête invalide. Vérifiez les données envoyées.';
            break;
          case 404:
            errorMessage = 'Endpoint non trouvé.';
            break;
          case 500:
            errorMessage = 'Erreur interne du serveur.';
            break;
          case 503:
            errorMessage = 'Service temporairement indisponible.';
            break;
          case 504:
            errorMessage = 'Timeout du serveur. La requête prend trop de temps à traiter.';
            break;
          default:
            errorMessage = `Erreur ${error.status}: ${error.message}`;
        }
      }
    }
    
    console.error('API Error:', error);
    return throwError(() => errorMessage);
  }
}