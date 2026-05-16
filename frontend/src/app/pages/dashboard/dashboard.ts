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

  constructor(private router: Router) {}

  search(): void {
    const s = this.summonerInput.trim();
    if (!s) return;
    if (!s.includes('#')) {
      this.error = 'Enter your Riot ID as Name#TAG (e.g. Faker#NA1)';
      return;
    }
    this.error = '';
    // Encode the summoner name to handle # in URLs
    this.router.navigate(['/history', encodeURIComponent(s)]);
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') this.search();
  }
}
