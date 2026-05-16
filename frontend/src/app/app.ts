import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReplayUploadComponent } from './components/replay-upload/replay-upload';
import { AnalysisResultsComponent } from './components/analysis-results/analysis-results';
import { AnalysisResult } from './services/replay';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, ReplayUploadComponent, AnalysisResultsComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  result: AnalysisResult | null = null;
  champion = '';
  matchId = '';
  showUpload = false;

  onAnalysisReady(payload: {
    result: AnalysisResult;
    champion: string;
    matchId: string;
  }): void {
    this.result   = payload.result;
    this.champion = payload.champion;
    this.matchId  = payload.matchId;
    this.showUpload = false;
  }

  newSession(): void {
    this.result   = null;
    this.champion = '';
    this.matchId  = '';
    this.showUpload = false;
  }

  goToUpload(): void {
    this.showUpload = true;
  }
}
