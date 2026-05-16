import { Routes } from '@angular/router';
import { DashboardComponent } from './pages/dashboard/dashboard';
import { MatchHistoryComponent } from './pages/match-history/match-history';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'history/:summoner', component: MatchHistoryComponent },
];
