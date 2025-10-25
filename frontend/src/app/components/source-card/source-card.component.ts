import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Source } from '../../models/source.model';

@Component({
  selector: 'app-source-card',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatExpansionModule,
    MatIconModule,
    MatButtonModule
  ],
  template: `
    <mat-expansion-panel class="source-card">
      <mat-expansion-panel-header>
        <mat-panel-title>
          <mat-icon>article</mat-icon>
          <span style="margin-left: 8px;">{{ source.document_name }}</span>
        </mat-panel-title>
        <mat-panel-description>
          <span *ngIf="source.article">{{ source.article }}</span>
          <span *ngIf="source.chapter" class="chapter">{{ source.chapter }}</span>
        </mat-panel-description>
      </mat-expansion-panel-header>
      
      <div class="source-content">
        <p>{{ source.content }}</p>
        
        <div class="source-metadata">
          <div *ngIf="source.pages" class="metadata-item">
            <strong>Pages:</strong> {{ source.pages }}
          </div>
          <div *ngIf="source.chapter" class="metadata-item">
            <strong>Chapitre:</strong> {{ source.chapter }}
          </div>
          <div *ngIf="source.article" class="metadata-item">
            <strong>Article:</strong> {{ source.article }}
          </div>
        </div>
        
        <div class="actions">
          <button mat-stroked-button (click)="copySource()">
            <mat-icon>content_copy</mat-icon>
            Copier
          </button>
        </div>
      </div>
    </mat-expansion-panel>
  `,
  styles: [`
    .source-card {
      margin-bottom: 8px;
      
      .mat-expansion-panel-header {
        font-weight: 500;
      }
      
      .chapter {
        margin-left: 8px;
        font-style: italic;
      }
      
      .relevance {
        margin-left: auto;
        font-size: 0.9em;
        color: #666;
      }
    }
    
    .source-content {
      padding: 16px 0;
      
      p {
        margin-bottom: 16px;
        line-height: 1.6;
      }
    }
    
    .source-metadata {
      background-color: #f5f5f5;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
      
      .metadata-item {
        margin-bottom: 4px;
        
        &:last-child {
          margin-bottom: 0;
        }
        
        strong {
          color: #333;
        }
      }
    }
    
    .actions {
      display: flex;
      justify-content: flex-end;
    }
  `]
})
export class SourceCardComponent {
  @Input() source!: Source;

  constructor(private snackBar: MatSnackBar) {}

  copySource(): void {
    const sourceText = `
Document: ${this.source.document_name}
${this.source.article ? 'Article: ' + this.source.article : ''}
${this.source.chapter ? 'Chapitre: ' + this.source.chapter : ''}
${this.source.section ? 'Section: ' + this.source.section : ''}
${this.source.pages ? 'Pages: ' + this.source.pages : ''}

Contenu:
${this.source.content}
    `.trim();

    navigator.clipboard.writeText(sourceText).then(() => {
      this.snackBar.open('Source copiée dans le presse-papiers', 'Fermer', {
        duration: 2000
      });
    }).catch(() => {
      this.snackBar.open('Erreur lors de la copie', 'Fermer', {
        duration: 2000
      });
    });
  }
}