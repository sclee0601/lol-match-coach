import { Component, EventEmitter, Output, ChangeDetectorRef, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatchService, AnalysisResult, MatchCard, TopChampion, CompResult } from '../../services/match';

@Component({
  selector: 'app-match-lookup',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './match-lookup.html',
  styleUrl: './match-lookup.scss',
})
export class MatchLookupComponent implements OnDestroy {
  @Output() analysisReady = new EventEmitter<{
    result: AnalysisResult;
    champion: string;
    matchId: string;
  }>();

  // Lookup state
  summonerInput = '';
  lookupLoading = false;
  lookupError = '';
  matches: MatchCard[] = [];
  topChampions: TopChampion[] = [];
  topChampionsLoading = false;
  topChampionsError = '';

  // Comp analysis state
  compResults: CompResult[] = [];
  compLoading = false;
  compError = '';
  primaryRole = '';

  // Selected match state
  selectedMatchId = '';
  selectedMatchChampions: { blue: string[]; red: string[] } = { blue: [], red: [] };
  selectedChampion = '';
  selectedLanguage = 'English';

  // Analyze state
  loading = false;
  error = '';

  // Live champ select state
  lcuConnected = false;
  inChampSelect = false;
  champSelectData: any = null;
  champSelectPolling = false;
  private champSelectInterval: any = null;

  readonly languages = [
    { code: 'English',    label: 'English' },
    { code: 'Korean',     label: '?œêµ­?? },
    { code: 'Japanese',   label: '?¥æœ¬èª? },
    { code: 'Chinese',    label: 'ä¸?–‡' },
    { code: 'Spanish',    label: 'EspaÃ±ol' },
    { code: 'Portuguese', label: 'PortuguÃªs' },
    { code: 'French',     label: 'FranÃ§ais' },
    { code: 'German',     label: 'Deutsch' },
  ];

  constructor(private matchService: MatchService, private cdr: ChangeDetectorRef) {}

  ngOnDestroy(): void {
    this.stopChampSelectPolling();
  }

  private startChampSelectPolling(): void {
    if (this.champSelectPolling) return;
    this.champSelectPolling = true;
    this.champSelectInterval = setInterval(() => {
      if (!this.summonerInput.trim()) return;
      this.matchService.getChampSelect(this.summonerInput.trim()).subscribe({
        next: (data) => {
          this.inChampSelect = data.in_champ_select || false;
          this.champSelectData = data.in_champ_select ? data : null;

          // Pause polling during active game (resume when game ends)
          if (data.phase === 'InProgress' || data.phase === 'WaitingForStats') {
            this.stopChampSelectPolling();
            // Resume polling after 5 minutes (game likely still going)
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
    this.champSelectPolling = false;
  }

  // ---------------------------------------------------------------------------
  // Lookup
  // ---------------------------------------------------------------------------

  lookup(): void {
    const s = this.summonerInput.trim();
    if (!s) return;
    if (!s.includes('#')) {
      this.lookupError = 'Enter your Riot ID as  Name#TAG  (e.g. Faker#NA1)';
      return;
    }
    this.lookupLoading = true;
    this.lookupError = '';
    this.matches = [];
    this.topChampions = [];
    this.compResults = [];
    this.selectedMatchId = '';
    this.selectedChampion = '';
    this.error = '';

    // Fetch matches
    this.matchService.lookupSummoner(s).subscribe({
      next: (res) => {
        this.matches = res.matches;
        this.lookupLoading = false;
        this.cdr.detectChanges();

        // Fetch player stats (top champions + comp analysis) in one request
        this.topChampionsLoading = true;
        this.compLoading = true;
        this.topChampionsError = '';
        this.compError = '';
        this.matchService.getPlayerStats(s).subscribe({
          next: (res) => {
            this.topChampions = res.top_champions || [];
            this.compResults = (res.comp_analysis || []).slice(0, 5);
            this.primaryRole = (res as any).primary_role || '';
            this.topChampionsLoading = false;
            this.compLoading = false;
            this.cdr.detectChanges();
          },
          error: (err) => {
            this.topChampionsLoading = false;
            this.compLoading = false;
            this.topChampionsError = err.error?.detail ?? 'Could not load player stats.';
            this.cdr.detectChanges();
          },
        });

        // Build ban/pick profile and start polling for champ select
        this.matchService.buildBanpickProfile(s).subscribe();
        this.startChampSelectPolling();
      },
      error: (err) => {
        const status = err.status;
        if (status === 404) {
          this.lookupError = 'User does not exist. Please check the Riot ID and tag.';
        } else {
          this.lookupError = err.error?.detail ?? 'Something went wrong. Please try again.';
        }
        this.lookupLoading = false;
      },
    });
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') this.lookup();
  }

  // ---------------------------------------------------------------------------
  // Match / champion selection
  // ---------------------------------------------------------------------------

  selectMatch(match: MatchCard): void {
    this.selectedMatchId = match.match_id;
    this.selectedMatchChampions = { blue: match.blue_team, red: match.red_team };
    this.selectedChampion = match.my_champion; // pre-select the queried player
    this.error = '';
  }

  selectChampion(champ: string): void {
    this.selectedChampion = this.selectedChampion === champ ? '' : champ;
  }

  // ---------------------------------------------------------------------------
  // Analyze
  // ---------------------------------------------------------------------------

  analyze(): void {
    if (!this.selectedMatchId) return;
    this.loading = true;
    this.error = '';

    this.matchService
      .analyzeMatch(this.selectedMatchId, this.selectedChampion || undefined, this.selectedLanguage)
      .subscribe({
        next: (result) => {
          this.loading = false;
          this.analysisReady.emit({
            result,
            champion: this.selectedChampion,
            matchId: this.selectedMatchId,
          });
        },
        error: (err) => {
          this.loading = false;
          this.error = err.error?.detail ?? 'Analysis failed. Check the backend.';
        },
      });
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
    const map: Record<number, string> = {
      420: 'Ranked Solo',
      440: 'Ranked Flex',
      400: 'Normal Draft',
      430: 'Normal Blind',
      450: 'ARAM',
    };
    return map[queueId] ?? 'Match';
  }
}
