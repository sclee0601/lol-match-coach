import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatchService, AnalysisResult, MatchCard, TopChampion, CompResult } from '../../services/match';
import { AnalysisResultsComponent } from '../../components/analysis-results/analysis-results';

@Component({
  selector: 'app-match-history',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, AnalysisResultsComponent],
  templateUrl: './match-history.html',
  styleUrl: './match-history.scss',
})
export class MatchHistoryComponent implements OnInit, OnDestroy {
  summoner = '';

  // Lookup state
  loading = true;
  error = '';
  matches: MatchCard[] = [];
  topChampions: TopChampion[] = [];
  compResults: CompResult[] = [];
  primaryRole = '';
  statsLoading = false;

  // Match selection
  selectedMatchId = '';
  selectedMatchChampions: { blue: string[]; red: string[] } = { blue: [], red: [] };
  selectedChampion = '';
  selectedLanguage = 'English';

  // Analysis
  analyzing = false;
  analysisError = '';
  result: AnalysisResult | null = null;

  // Live champ select (handled by local helper app, kept for local dev)
  inChampSelect = false;
  champSelectData: any = null;
  private champSelectInterval: any = null;

  readonly languages = [
    { code: 'English', label: 'English' },
    { code: 'Korean', label: '한국어' },
    { code: 'Japanese', label: '日本語' },
    { code: 'Chinese', label: '中文' },
    { code: 'Spanish', label: 'Español' },
    { code: 'Portuguese', label: 'Português' },
    { code: 'French', label: 'Français' },
    { code: 'German', label: 'Deutsch' },
  ];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private matchService: MatchService,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    const raw = this.route.snapshot.paramMap.get('summoner') || '';
    this.summoner = decodeURIComponent(raw);
    if (!this.summoner) {
      this.router.navigate(['/']);
      return;
    }
    this.loadData();
  }

  ngOnDestroy(): void {
    this.stopChampSelectPolling();
  }

  private loadData(): void {
    this.loading = true;
    this.matchService.lookupSummoner(this.summoner).subscribe({
      next: (res) => {
        this.matches = res.matches;
        this.loading = false;
        this.cdr.detectChanges();

        // Load stats
        this.statsLoading = true;
        this.matchService.getPlayerStats(this.summoner).subscribe({
          next: (stats) => {
            this.topChampions = stats.top_champions || [];
            this.compResults = (stats.comp_analysis || []).slice(0, 5);
            this.primaryRole = (stats as any).primary_role || '';
            this.statsLoading = false;
            this.cdr.detectChanges();
          },
          error: () => { this.statsLoading = false; },
        });

        // Build ban/pick profile + start polling
        this.matchService.buildBanpickProfile(this.summoner).subscribe();
        this.startChampSelectPolling();
      },
      error: (err) => {
        this.loading = false;
        if (err.status === 404) {
          this.error = 'Summoner not found. Check the Riot ID and tag.';
        } else {
          this.error = err.error?.detail ?? 'Something went wrong.';
        }
      },
    });
  }

  // ---------------------------------------------------------------------------
  // Match selection
  // ---------------------------------------------------------------------------

  selectMatch(match: MatchCard): void {
    this.selectedMatchId = match.match_id;
    this.selectedMatchChampions = { blue: match.blue_team, red: match.red_team };
    this.selectedChampion = match.my_champion;
    this.analysisError = '';
    this.result = null;
  }

  selectChampion(champ: string): void {
    this.selectedChampion = this.selectedChampion === champ ? '' : champ;
  }

  backToMatches(): void {
    this.selectedMatchId = '';
    this.result = null;
  }

  // ---------------------------------------------------------------------------
  // Analysis
  // ---------------------------------------------------------------------------

  analyze(): void {
    if (!this.selectedMatchId) return;
    this.analyzing = true;
    this.analysisError = '';

    this.matchService
      .analyzeMatch(this.selectedMatchId, this.selectedChampion || undefined, this.selectedLanguage)
      .subscribe({
        next: (result) => {
          this.analyzing = false;
          this.result = result;
          this.cdr.detectChanges();
        },
        error: (err) => {
          this.analyzing = false;
          this.analysisError = err.error?.detail ?? 'Analysis failed.';
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Live champ select polling
  // ---------------------------------------------------------------------------

  private startChampSelectPolling(): void {
    this.champSelectInterval = setInterval(() => {
      this.matchService.getChampSelect(this.summoner).subscribe({
        next: (data) => {
          this.inChampSelect = data.in_champ_select || false;
          this.champSelectData = data.in_champ_select ? data : null;
          if (data.phase === 'InProgress' || data.phase === 'WaitingForStats') {
            this.stopChampSelectPolling();
            setTimeout(() => this.startChampSelectPolling(), 300000);
          }
          this.cdr.detectChanges();
        },
        error: () => {
          this.inChampSelect = false;
          this.champSelectData = null;
        },
      });
    }, 3000);
  }

  private stopChampSelectPolling(): void {
    if (this.champSelectInterval) {
      clearInterval(this.champSelectInterval);
      this.champSelectInterval = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  formatDuration(seconds: number): string {
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }

  formatDate(ms: number): string {
    return new Date(ms).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  queueLabel(queueId: number): string {
    const map: Record<number, string> = { 420: 'Ranked Solo', 440: 'Ranked Flex', 400: 'Normal Draft', 430: 'Normal Blind', 450: 'ARAM' };
    return map[queueId] ?? 'Match';
  }
}
