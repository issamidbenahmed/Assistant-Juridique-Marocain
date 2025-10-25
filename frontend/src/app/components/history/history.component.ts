import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatDividerModule } from '@angular/material/divider';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService, ConversationEntry, ConversationHistory } from '../../services/api.service';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatInputModule,
    MatFormFieldModule,
    MatIconModule,
    MatListModule,
    MatDividerModule,
    MatPaginatorModule,
    MatSnackBarModule
  ],
  template: `
    <mat-card>
      <mat-card-header>
        <mat-card-title>Historique des conversations</mat-card-title>
      </mat-card-header>
      
      <mat-card-content>
        <div class="search-container">
          <mat-form-field appearance="outline" style="width: 100%;">
            <mat-label>Rechercher dans l'historique</mat-label>
            <input matInput [(ngModel)]="searchQuery" (input)="onSearch()">
            <mat-icon matSuffix>search</mat-icon>
          </mat-form-field>
        </div>
        
        <div class="actions">
          <button mat-stroked-button (click)="exportHistory()">
            <mat-icon>download</mat-icon>
            Exporter
          </button>
          <button mat-stroked-button color="warn" (click)="clearHistory()">
            <mat-icon>delete</mat-icon>
            Effacer tout
          </button>
        </div>
        
        <mat-list>
          <div *ngFor="let entry of conversations; let last = last">
            <mat-list-item>
              <div class="history-entry">
                <div class="question">
                  <strong>Q:</strong> {{ entry.question }}
                </div>
                <div class="response">
                  <strong>R:</strong> {{ entry.response | slice:0:200 }}
                  <span *ngIf="entry.response.length > 200">...</span>
                </div>
                <div class="metadata">
                  <span class="timestamp">{{ entry.timestamp | date:'short' }}</span>
                  <span class="sources-count">{{ entry.sources_count }} source(s)</span>
                  <span class="confidence">Confiance: {{ entry.confidence }}%</span>
                  <button mat-icon-button color="warn" (click)="deleteConversation(entry.id)">
                    <mat-icon>delete</mat-icon>
                  </button>
                </div>
              </div>
            </mat-list-item>
            <mat-divider *ngIf="!last"></mat-divider>
          </div>
        </mat-list>
        
        <div *ngIf="conversations.length === 0 && !isLoading" class="no-results">
          <p>Aucun résultat trouvé</p>
        </div>
        
        <div *ngIf="isLoading" class="loading">
          <p>Chargement...</p>
        </div>
        
        <mat-paginator 
          *ngIf="totalCount > pageSize"
          [length]="totalCount"
          [pageSize]="pageSize"
          [pageSizeOptions]="[10, 25, 50, 100]"
          (page)="onPageChange($event)"
          showFirstLastButtons>
        </mat-paginator>
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .search-container {
      margin-bottom: 16px;
    }
    
    .actions {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
    }
    
    .history-entry {
      width: 100%;
      
      .question {
        margin-bottom: 8px;
        color: #333;
      }
      
      .response {
        margin-bottom: 8px;
        color: #666;
        line-height: 1.4;
      }
      
      .metadata {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.9em;
        color: #999;
        
        .confidence {
          margin-left: 10px;
        }
      }
    }
    
    .no-results {
      text-align: center;
      padding: 40px;
      color: #666;
    }
  `]
})
export class HistoryComponent implements OnInit {
  conversations: ConversationEntry[] = [];
  searchQuery = '';
  isLoading = false;
  currentPage = 1;
  pageSize = 50;
  totalCount = 0;
  hasMore = false;

  constructor(
    private apiService: ApiService,
    private snackBar: MatSnackBar
  ) { }

  ngOnInit(): void {
    this.loadHistory();
  }

  loadHistory(): void {
    this.isLoading = true;

    this.apiService.getHistory(
      this.currentPage,
      this.pageSize,
      this.searchQuery || undefined
    ).subscribe({
      next: (response: ConversationHistory) => {
        this.conversations = response.conversations;
        this.totalCount = response.total_count;
        this.hasMore = response.has_more;
        this.isLoading = false;
      },
      error: (error) => {
        console.error('Failed to load history:', error);
        this.snackBar.open('Erreur lors du chargement de l\'historique', 'Fermer', { duration: 3000 });
        this.isLoading = false;
      }
    });
  }

  onSearch(): void {
    this.currentPage = 1;
    this.loadHistory();
  }

  onPageChange(event: any): void {
    this.currentPage = event.pageIndex + 1;
    this.pageSize = event.pageSize;
    this.loadHistory();
  }

  deleteConversation(conversationId: string): void {
    if (confirm('Êtes-vous sûr de vouloir supprimer cette conversation ?')) {
      this.apiService.deleteConversation(conversationId).subscribe({
        next: () => {
          this.snackBar.open('Conversation supprimée', 'Fermer', { duration: 2000 });
          this.loadHistory(); // Reload the list
        },
        error: (error) => {
          console.error('Failed to delete conversation:', error);
          this.snackBar.open('Erreur lors de la suppression', 'Fermer', { duration: 3000 });
        }
      });
    }
  }

  exportHistory(): void {
    // Get all history for export
    this.apiService.getHistory(1, 1000).subscribe({
      next: (response: ConversationHistory) => {
        const data = JSON.stringify(response.conversations, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `historique-assistant-juridique-${new Date().toISOString().split('T')[0]}.json`;
        link.click();
        window.URL.revokeObjectURL(url);

        this.snackBar.open('Historique exporté', 'Fermer', { duration: 2000 });
      },
      error: (error) => {
        console.error('Failed to export history:', error);
        this.snackBar.open('Erreur lors de l\'export', 'Fermer', { duration: 3000 });
      }
    });
  }

  clearHistory(): void {
    if (confirm('Êtes-vous sûr de vouloir effacer tout l\'historique ?')) {
      this.apiService.clearHistory().subscribe({
        next: (response) => {
          this.snackBar.open(`${response.deleted_count} conversations supprimées`, 'Fermer', { duration: 3000 });
          this.loadHistory(); // Reload the list
        },
        error: (error) => {
          console.error('Failed to clear history:', error);
          this.snackBar.open('Erreur lors de la suppression', 'Fermer', { duration: 3000 });
        }
      });
    }
  }
}