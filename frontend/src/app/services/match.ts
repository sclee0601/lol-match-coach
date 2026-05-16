import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Player {
  summoner_name: string;
  champion: string;
  team: string;
  position: string;
  kills: number;
  deaths: number;
  assists: number;
  cs: number;
  gold: number;
  damage_dealt: number;
  vision_score: number;
  wards_placed: number;
  wards_killed: number;
  game_length_seconds: number;
  win: boolean;
}

export interface AnalysisResult {
  analysis: string;
  players_analyzed: string[];
  champion_filter: string | null;
  players: Player[];
  has_timeline: boolean;
}

export interface MatchCard {
  match_id: string;
  game_duration: number;
  queue_id: number;
  game_creation: number;
  blue_team: string[];
  red_team: string[];
  my_champion: string;
  my_team: string;
  my_win: boolean;
  my_kda: { kills: number; deaths: number; assists: number };
}

export interface LookupResult {
  puuid: string;
  matches: MatchCard[];
}

export interface TopChampion {
  champion: string;
  games: number;
  winrate: number;
  avg_kda: number;
  cs_per_min: number;
  score: number;
}

export interface TopChampionsResult {
  top_champions: TopChampion[];
  total_matches_analyzed: number;
}

export interface CompAdc {
  champion: string;
  games: number;
  winrate: number;
  avg_kda: number;
  cs_per_min: number;
  dmg_per_min: number;
}

export interface CompResult {
  comp_type: string;
  games: number;
  wins: number;
  winrate: number;
  best_adcs: CompAdc[];
  role_breakdown?: { [role: string]: { champion: string; games: number; winrate: number }[] };
}

export interface CompAnalysisResult {
  comp_analysis: CompResult[];
  total_matches_analyzed: number;
}

const API = (window as any).__API_URL__ || 'http://localhost:8000/api';

@Injectable({ providedIn: 'root' })
export class MatchService {
  constructor(private http: HttpClient) {}

  // --- Summoner lookup ---
  lookupSummoner(summoner: string): Observable<LookupResult> {
    const params = new HttpParams().set('summoner', summoner);
    return this.http.get<LookupResult>(`${API}/lookup`, { params });
  }

  // --- Player stats (combined: top champions + comp analysis) ---
  getPlayerStats(summoner: string): Observable<{ top_champions: TopChampion[]; comp_analysis: CompResult[]; total_matches_analyzed: number }> {
    const params = new HttpParams().set('summoner', summoner);
    return this.http.get<{ top_champions: TopChampion[]; comp_analysis: CompResult[]; total_matches_analyzed: number }>(`${API}/player-stats`, { params });
  }

  // --- Top champions (legacy, kept for compatibility) ---
  getTopChampions(summoner: string): Observable<TopChampionsResult> {
    const params = new HttpParams().set('summoner', summoner);
    return this.http.get<TopChampionsResult>(`${API}/top-champions`, { params });
  }

  // --- Comp analysis (legacy, kept for compatibility) ---
  getCompAnalysis(summoner: string): Observable<CompAnalysisResult> {
    const params = new HttpParams().set('summoner', summoner);
    return this.http.get<CompAnalysisResult>(`${API}/comp-analysis`, { params });
  }

  // --- Analyze by match ID (Riot API) ---
  analyzeMatch(matchId: string, champion?: string, language?: string): Observable<AnalysisResult> {
    return this.http.post<AnalysisResult>(`${API}/analyze-match`, {
      match_id: matchId,
      champion: champion || null,
      language: language || 'English',
    });
  }

  // --- Chat ---
  chat(
    analysis: string,
    history: { role: string; content: string }[],
    question: string,
    language: string
  ): Observable<{ reply: string }> {
    return this.http.post<{ reply: string }>(`${API}/chat`, {
      analysis, history, question, language,
    });
  }

  // --- LCU / Champ Select ---
  getLcuStatus(): Observable<{ connected: boolean; phase: string | null }> {
    return this.http.get<{ connected: boolean; phase: string | null }>(`${API}/lcu/status`);
  }

  getChampSelect(summoner: string): Observable<any> {
    const params = new HttpParams().set('summoner', summoner);
    return this.http.get<any>(`${API}/lcu/champ-select`, { params });
  }

  buildBanpickProfile(summoner: string): Observable<any> {
    const params = new HttpParams().set('summoner', summoner);
    return this.http.post<any>(`${API}/banpick-profile`, null, { params });
  }
}
