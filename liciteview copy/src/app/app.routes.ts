import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./layout/main-layout/main-layout').then(m => m.MainLayoutComponent),
    children: [
      {
        path: 'radar',
        loadComponent: () => import('./pages/radar/radar').then(m => m.RadarComponent)
      },
      {
        path: 'cadastro',
        loadComponent: () => import('./pages/cadastro/cadastro').then(m => m.CadastroComponent)
      },
      {
        path: '',
        redirectTo: 'radar',
        pathMatch: 'full'
      }
    ]
  }
];