import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class DashboardComponent {
  summonerInput = '';
  error = '';
  recentSearches: string[] = [];

  constructor(private router: Router) {
    // Load recent searches from localStorage
    const saved = localStorage.getItem('recentSearches');
    if (saved) {
      this.recentSearches = JSON.parse(saved);
    }
  }

  search(): void {
    const s = this.summonerInput.trim();
    if (!s) return;
    if (!s.includes('#')) {
      this.error = 'Enter your Riot ID as Name#TAG (e.g. Faker#NA1)';
      return;
    }
    this.error = '';
    this._saveSearch(s);
    this.router.navigate(['/history', encodeURIComponent(s)]);
  }

  selectRecent(summoner: string): void {
    this.summonerInput = summoner;
    this.search();
  }

  removeRecent(summoner: string, event: Event): void {
    event.stopPropagation();
    this.recentSearches = this.recentSearches.filter(s => s !== summoner);
    localStorage.setItem('recentSearches', JSON.stringify(this.recentSearches));
  }

  private _saveSearch(summoner: string): void {
    // Add to front, remove duplicates, keep max 5
    this.recentSearches = [summoner, ...this.recentSearches.filter(s => s !== summoner)].slice(0, 5);
    localStorage.setItem('recentSearches', JSON.stringify(this.recentSearches));
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') this.search();
  }
}
