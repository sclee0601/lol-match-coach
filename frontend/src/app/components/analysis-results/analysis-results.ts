import { Component, Input, OnChanges, Output, EventEmitter, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AnalysisResult, Player, MatchService } from '../../services/match';
import { MarkdownToHtmlPipe } from '../../pipes/markdown-to-html-pipe';

@Component({
  selector: 'app-analysis-results',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownToHtmlPipe],
  templateUrl: './analysis-results.html',
  styleUrl: './analysis-results.scss',
})
export class AnalysisResultsComponent implements OnChanges {
  @Input() result!: AnalysisResult;
  @Input() champion: string = '';
  @Input() matchId: string = '';
  @Output() newSession = new EventEmitter<void>();
  @Output() goToUpload = new EventEmitter<void>();
  @Output() resultUpdated = new EventEmitter<AnalysisResult>();

  blueTeam: Player[] = [];
  redTeam: Player[] = [];
  reanalyzing = false;

  // Tabs
  activeTab: 'laning' | 'events' | 'teamfight' = 'laning';
  laningContent = '';
  eventsContent = '';
  teamfightContent = '';

  readonly languages = [
    { code: 'English', label: 'English' },
    { code: 'Korean', label: '\ud55c\uad6d\uc5b4' },
    { code: 'Japanese', label: '\u65e5\u672c\u8a9e' },
    { code: 'Chinese', label: '\u4e2d\u6587' },
    { code: 'Spanish', label: 'Espa\u00f1ol' },
    { code: 'Portuguese', label: 'Portugu\u00eas' },
    { code: 'French', label: 'Fran\u00e7ais' },
    { code: 'German', label: 'Deutsch' },
  ];
  selectedLanguage = 'English';

  constructor(private matchService: MatchService, private cdr: ChangeDetectorRef) {}

  ngOnChanges(): void {
    if (!this.result) return;
    this.blueTeam = this.result.players.filter(p => p.team === 'Blue');
    this.redTeam = this.result.players.filter(p => p.team === 'Red');
    this.splitAnalysis();
  }

  onLanguageChange(): void {
    if (!this.result || !this.matchId) return;
    this.reanalyzing = true;
    this.matchService
      .analyzeMatch(this.matchId, this.champion || undefined, this.selectedLanguage)
      .subscribe({
        next: (result) => {
          this.result = result;
          this.blueTeam = result.players.filter(p => p.team === 'Blue');
          this.redTeam = result.players.filter(p => p.team === 'Red');
          this.splitAnalysis();
          this.reanalyzing = false;
          this.resultUpdated.emit(result);
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.error('reanalyze error:', err);
          this.reanalyzing = false;
        },
      });
  }

  private splitAnalysis(): void {
    const text = this.result.analysis || '';
    // Split on ## or ### headers
    const sections = text.split(/(?=^###? )/m);

    this.laningContent = '';
    this.eventsContent = '';
    this.teamfightContent = '';

    for (const s of sections) {
      const lower = s.toLowerCase();
      if (
        lower.startsWith('## laning') ||
        lower.startsWith('### 1.') ||
        lower.startsWith('### cs') ||
        lower.startsWith('### 2.') ||
        lower.includes('cs & gold') ||
        lower.includes('deaths in laning')
      ) {
        this.laningContent += s + '\n';
      } else if (
        lower.startsWith('## key') ||
        lower.startsWith('## deaths') ||
        lower.startsWith('### 3.') ||
        lower.includes('mid/late game') ||
        lower.includes('key events') ||
        lower.includes('objectives')
      ) {
        this.eventsContent += s + '\n';
      } else if (
        lower.startsWith('### 4.') ||
        lower.includes('strategic fixes') ||
        lower.includes('top 3') ||
        lower.includes('teamfight') ||
        lower.startsWith('## teamfight') ||
        lower.startsWith('## top')
      ) {
        this.teamfightContent += s + '\n';
      } else if (s.trim()) {
        // Unmatched content — put in teamfights tab
        this.teamfightContent += s + '\n';
      }
    }
  }

  get gameLength(): string {
    const secs = this.result?.players?.[0]?.game_length_seconds ?? 0;
    return `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
  }

  csPerMin(p: Player): string {
    const min = (p.game_length_seconds / 60) || 1;
    return (p.cs / min).toFixed(1);
  }

  /** Performance score 0-10 weighted by role */
  score(p: Player): number {
    const min = (p.game_length_seconds / 60) || 1;
    const csPerMin = p.cs / min;
    const kdaRatio = p.deaths === 0 ? (p.kills + p.assists) : (p.kills + p.assists) / p.deaths;
    const dmgPerMin = p.damage_dealt / min;
    const visionPerMin = p.vision_score / min;
    const killParticipation = (p.kills + p.assists); // raw, compared within team later

    // Role-specific weights
    const role = (p.position || '').toUpperCase();
    let csW = 2, kdaW = 3.5, dmgW = 2.5, visW = 1, kpW = 1;

    if (role === 'BOTTOM') {
      // ADC: CS and damage matter most
      csW = 3; kdaW = 2.5; dmgW = 3; visW = 0.5; kpW = 1;
    } else if (role === 'UTILITY') {
      // Support: vision and KP matter most, CS irrelevant
      csW = 0; kdaW = 2; dmgW = 0.5; visW = 4; kpW = 3.5;
    } else if (role === 'JUNGLE') {
      // Jungle: KDA, objectives (approx via KP), moderate CS
      csW = 1.5; kdaW = 3; dmgW = 2; visW = 1.5; kpW = 2;
    } else if (role === 'MIDDLE') {
      // Mid: damage and KDA
      csW = 2.5; kdaW = 3; dmgW = 3; visW = 0.5; kpW = 1;
    } else {
      // Top: CS, KDA, moderate damage
      csW = 2.5; kdaW = 3; dmgW = 2.5; visW = 1; kpW = 1;
    }

    const totalW = csW + kdaW + dmgW + visW + kpW;

    // Normalize each stat to 0-1
    const csNorm = Math.min(csPerMin / 8, 1);
    const kdaNorm = Math.min(kdaRatio / 5, 1);
    const dmgNorm = Math.min(dmgPerMin / 700, 1);
    const visNorm = Math.min(visionPerMin / 1.5, 1);
    const kpNorm = Math.min(killParticipation / 25, 1);

    const raw = (csNorm * csW + kdaNorm * kdaW + dmgNorm * dmgW + visNorm * visW + kpNorm * kpW) / totalW;
    return Math.round(raw * 100) / 10; // 0.0 - 10.0
  }

  scoreColor(s: number): string {
    if (s >= 8) return '#22c55e';
    if (s >= 6) return '#f0c040';
    if (s >= 4) return '#f97316';
    return '#ef4444';
  }
}
