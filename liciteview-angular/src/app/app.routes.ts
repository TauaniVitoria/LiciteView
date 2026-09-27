import { Routes } from '@angular/router';
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './core/services/auth.service';

const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isAuthenticated()) return true;
  router.navigateByUrl('/login');
  return false;
};

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: '/pesquisa' },
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then(m => m.LoginComponent),
  },
  {
    path: 'register',
    loadComponent: () => import('./features/auth/register.component').then(m => m.RegisterComponent),
  },
  {
    path: '',
    loadComponent: () => import('./layout/app-shell.component').then(m => m.AppShellComponent),
    canActivate: [authGuard],
    children: [
      {
        path: 'pesquisa',
        loadComponent: () => import('./features/pesquisa/pesquisa.component').then(m => m.PesquisaComponent),
      },
      {
        path: 'historico',
        loadComponent: () => import('./features/historico/historico.component').then(m => m.HistoricoComponent),
      },
      {
        path: 'edital/:id',
        loadComponent: () => import('./features/edital/edital.component').then(m => m.EditalComponent),
      },
      {
        path: 'produtos',
        loadComponent: () => import('./features/produtos/produtos-list.component').then(m => m.ProdutosListComponent),
      },
      {
        path: 'produtos/novo',
        loadComponent: () => import('./features/produtos/produto-form.component').then(m => m.ProdutoFormComponent),
      },
    ],
  },
  { path: '**', redirectTo: '/pesquisa' },
];
