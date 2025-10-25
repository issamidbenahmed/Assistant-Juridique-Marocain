import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTabsModule } from '@angular/material/tabs';
import { ChatComponent } from './components/chat/chat.component';
import { HistoryComponent } from './components/history/history.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    MatToolbarModule,
    MatIconModule,
    MatButtonModule,
    MatTabsModule,
    ChatComponent,
    HistoryComponent
  ],
  template: `
    <mat-toolbar color="primary">
      <mat-icon>gavel</mat-icon>
      <span style="margin-left: 10px;">Assistant Juridique Marocain</span>
      <span class="spacer"></span>
      <button mat-icon-button (click)="checkHealth()" [title]="healthStatus">
        <mat-icon [color]="healthColor">{{ healthIcon }}</mat-icon>
      </button>
    </mat-toolbar>
    
    <div class="container">
      <mat-tab-group>
        <mat-tab label="Chat">
          <app-chat></app-chat>
        </mat-tab>
        <mat-tab label="Historique">
          <app-history></app-history>
        </mat-tab>
      </mat-tab-group>
    </div>
  `,
  styles: [`
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0;
    }
    
    .spacer {
      flex: 1 1 auto;
    }
    
    mat-tab-group {
      height: calc(100vh - 64px);
    }
  `]
})
export class AppComponent {
  title = 'Assistant Juridique Marocain';
  healthStatus = 'Vérification...';
  healthColor = 'warn';
  healthIcon = 'help';

  constructor() {
    this.checkHealth();
  }

  async checkHealth() {
    try {
      const response = await fetch('http://localhost:8000/health');
      const health = await response.json();
      
      if (health.status === 'healthy') {
        this.healthStatus = 'Services opérationnels';
        this.healthColor = 'primary';
        this.healthIcon = 'check_circle';
      } else {
        this.healthStatus = 'Services dégradés';
        this.healthColor = 'warn';
        this.healthIcon = 'warning';
      }
    } catch (error) {
      this.healthStatus = 'Services indisponibles';
      this.healthColor = 'warn';
      this.healthIcon = 'error';
    }
  }
}