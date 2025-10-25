import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService, AskRequest, AskResponse } from '../../services/api.service';
import { HistoryService } from '../../services/history.service';
import { SourceCardComponent } from '../source-card/source-card.component';

interface ChatMessage {
  type: 'user' | 'assistant';
  content: string;
  sources?: any[];
  timestamp: Date;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatInputModule,
    MatFormFieldModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    SourceCardComponent
  ],
  template: `
    <div class="chat-container">
      <div class="messages-container" #messagesContainer>
        <div *ngFor="let message of messages" class="message" [ngClass]="message.type">
          <div class="message-content">
            <p>{{ message.content }}</p>
            <div *ngIf="message.sources && message.sources.length > 0" class="sources">
              <app-source-card 
                *ngFor="let source of message.sources" 
                [source]="source">
              </app-source-card>
            </div>
          </div>
        </div>
        
        <div *ngIf="isLoading" class="loading-spinner">
          <mat-spinner diameter="40"></mat-spinner>
          <span style="margin-left: 10px;">Traitement de votre question...</span>
        </div>
      </div>
      
      <div class="input-container">
        <mat-form-field appearance="outline" style="width: 100%;">
          <mat-label>Posez votre question juridique...</mat-label>
          <input 
            matInput 
            [(ngModel)]="currentQuestion" 
            (keyup.enter)="askQuestion()"
            [disabled]="isLoading"
            placeholder="Ex: Qu'est-ce qu'une société anonyme selon la loi marocaine?">
          <button 
            mat-icon-button 
            matSuffix 
            (click)="askQuestion()" 
            [disabled]="!currentQuestion.trim() || isLoading">
            <mat-icon>send</mat-icon>
          </button>
        </mat-form-field>
      </div>
    </div>
  `,
  styles: [`
    .chat-container {
      height: calc(100vh - 120px);
      display: flex;
      flex-direction: column;
    }

    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      background-color: #f5f5f5;
    }

    .input-container {
      padding: 20px;
      background-color: white;
      border-top: 1px solid #e0e0e0;
    }

    .message {
      margin-bottom: 20px;
      
      &.user {
        text-align: right;
        
        .message-content {
          background-color: #3f51b5;
          color: white;
          display: inline-block;
          padding: 12px 16px;
          border-radius: 18px 18px 4px 18px;
          max-width: 70%;
        }
      }
      
      &.assistant {
        text-align: left;
        
        .message-content {
          background-color: white;
          color: #333;
          display: inline-block;
          padding: 12px 16px;
          border-radius: 18px 18px 18px 4px;
          max-width: 70%;
          box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        }
      }
    }

    .sources {
      margin-top: 10px;
    }

    .loading-spinner {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 20px;
    }
  `]
})
export class ChatComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  messages: ChatMessage[] = [];
  currentQuestion = '';
  isLoading = false;

  constructor(
    private apiService: ApiService,
    private historyService: HistoryService,
    private snackBar: MatSnackBar
  ) { }

  ngOnInit(): void {
    // Add welcome message
    this.messages.push({
      type: 'assistant',
      content: 'Bonjour ! Je suis votre assistant juridique spécialisé dans la législation marocaine. Posez-moi vos questions juridiques et je vous fournirai des réponses basées sur les textes officiels.',
      timestamp: new Date()
    });
  }

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  askQuestion(): void {
    if (!this.currentQuestion.trim() || this.isLoading) {
      return;
    }

    const question = this.currentQuestion.trim();
    this.currentQuestion = '';

    // Add user message
    this.messages.push({
      type: 'user',
      content: question,
      timestamp: new Date()
    });

    this.isLoading = true;

    // Call API
    const request: AskRequest = {
      question: question,
      max_sources: 3,  // Reduced from 5 to 3 for faster responses
      similarity_threshold: 0.002,  // Fixed: Use correct threshold for new similarity calculation
      validate_response: false
    };

    this.apiService.askQuestion(request).subscribe({
      next: (response: AskResponse) => {
        this.messages.push({
          type: 'assistant',
          content: response.response,
          sources: response.sources,
          timestamp: new Date()
        });

        // Save to history via API
        this.apiService.saveConversation({
          question: question,
          response: response.response,
          sources_count: response.sources?.length || 0,
          confidence: response.metadata?.confidence || 0,
          metadata: response.metadata
        }).subscribe({
          next: () => {
            console.log('Conversation saved to history');
          },
          error: (error) => {
            console.error('Failed to save conversation:', error);
          }
        });

        this.isLoading = false;
      },
      error: (error) => {
        this.messages.push({
          type: 'assistant',
          content: 'Désolé, une erreur est survenue lors du traitement de votre question. Veuillez réessayer.',
          timestamp: new Date()
        });

        this.snackBar.open(error, 'Fermer', { duration: 5000 });
        this.isLoading = false;
      }
    });
  }

  private scrollToBottom(): void {
    try {
      this.messagesContainer.nativeElement.scrollTop = this.messagesContainer.nativeElement.scrollHeight;
    } catch (err) {
      console.error('Error scrolling to bottom:', err);
    }
  }
}