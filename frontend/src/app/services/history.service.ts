import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { ConversationEntry } from '../models/source.model';

@Injectable({
  providedIn: 'root'
})
export class HistoryService {
  private readonly STORAGE_KEY = 'assistant-juridique-history';
  private historySubject = new BehaviorSubject<ConversationEntry[]>([]);
  
  public history$ = this.historySubject.asObservable();

  constructor() {
    this.loadHistory();
  }

  addEntry(entry: ConversationEntry): void {
    const currentHistory = this.historySubject.value;
    const updatedHistory = [entry, ...currentHistory];
    this.historySubject.next(updatedHistory);
    this.saveHistory(updatedHistory);
  }

  clearHistory(): void {
    this.historySubject.next([]);
    localStorage.removeItem(this.STORAGE_KEY);
  }

  searchHistory(query: string): ConversationEntry[] {
    const history = this.historySubject.value;
    if (!query.trim()) {
      return history;
    }
    
    return history.filter(entry => 
      entry.question.toLowerCase().includes(query.toLowerCase()) ||
      entry.response.toLowerCase().includes(query.toLowerCase())
    );
  }

  exportHistory(): string {
    const history = this.historySubject.value;
    return JSON.stringify(history, null, 2);
  }

  importHistory(jsonData: string): void {
    try {
      const history = JSON.parse(jsonData) as ConversationEntry[];
      this.historySubject.next(history);
      this.saveHistory(history);
    } catch (error) {
      console.error('Error importing history:', error);
      throw new Error('Format de données invalide');
    }
  }

  private loadHistory(): void {
    const stored = localStorage.getItem(this.STORAGE_KEY);
    if (stored) {
      try {
        const history = JSON.parse(stored) as ConversationEntry[];
        this.historySubject.next(history);
      } catch (error) {
        console.error('Error loading history:', error);
      }
    }
  }

  private saveHistory(history: ConversationEntry[]): void {
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(history));
  }
}