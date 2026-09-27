import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, EMPTY, tap, switchMap, map, catchError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TOKEN_KEY } from '../interceptors/auth.interceptor';

export interface UsuarioLogado {
  id: string;
  nome: string;
  email: string;
  razao_social: string;
  cnpj: string;
  cep: string;
  cidade: string | null;
  uf: string | null;
  perfil: 'ADMIN' | 'FORNECEDOR';
  ativo: boolean;
  criado_em: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private readonly _user = signal<UsuarioLogado | null>(null);
  readonly user = this._user.asReadonly();

  // Objeto pronto para exibição no template
  readonly userDisplay = computed(() => {
    const u = this._user();
    if (!u) return null;
    const partes = u.nome.trim().split(/\s+/);
    const iniciais = ((partes[0]?.[0] ?? '') + (partes[1]?.[0] ?? '')).toUpperCase();
    return { initials: iniciais, name: u.nome, empresa: u.razao_social };
  });

  constructor() {
    if (this.hasToken()) {
      this.fetchMe().subscribe();
    }
  }

  isAuthenticated(): boolean {
    return this.hasToken();
  }

  registrar(dados: {
    nome: string; email: string; senha: string;
    razao_social: string; cnpj: string; cep: string;
    cidade?: string; uf?: string;
  }): Observable<void> {
    return this.http
      .post(`${environment.apiUrl}/auth/register`, dados)
      .pipe(switchMap(() => this.login(dados.email, dados.senha)));
  }

  login(email: string, senha: string): Observable<void> {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/login`, { email, senha })
      .pipe(
        tap(({ access_token }) => localStorage.setItem(TOKEN_KEY, access_token)),
        switchMap(() => this.fetchMe()),
      );
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    this._user.set(null);
    this.router.navigateByUrl('/login');
  }

  private hasToken(): boolean {
    return !!localStorage.getItem(TOKEN_KEY);
  }

  private fetchMe(): Observable<void> {
    return this.http.get<UsuarioLogado>(`${environment.apiUrl}/auth/me`).pipe(
      tap((u) => this._user.set(u)),
      map(() => void 0),
      catchError(() => {
        localStorage.removeItem(TOKEN_KEY);
        return EMPTY;
      }),
    );
  }
}
