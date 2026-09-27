import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, interval, switchMap, catchError, of, tap, startWith } from 'rxjs';
import { Notificacao } from '../models/notificacao.model';
import { environment } from '../../../environments/environment';
import { TOKEN_KEY } from '../interceptors/auth.interceptor';

const POLL_MS = 30_000;

@Injectable({ providedIn: 'root' })
export class NotificacaoService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/cliente/notificacoes`;

  private readonly _lista = signal<Notificacao[]>([]);
  readonly notificacoes = this._lista.asReadonly();
  readonly naoLidas     = computed(() => this._lista().filter((n) => !n.lida).length);

  constructor() {
    // Poll imediato + a cada 30s
    interval(POLL_MS).pipe(
      startWith(0),
      switchMap(() => this._fetch()),
    ).subscribe();
  }

  marcarLida(id: string): Observable<void> {
    return this.http.patch<void>(`${this.url}/${id}/lida`, {}).pipe(
      tap(() => this._lista.update((ns) => ns.map((n) => n.id === id ? { ...n, lida: true } : n))),
    );
  }

  marcarTodasLidas(): Observable<void> {
    return this.http.patch<void>(`${this.url}/marcar-todas-lidas`, {}).pipe(
      tap(() => this._lista.update((ns) => ns.map((n) => ({ ...n, lida: true })))),
    );
  }

  private _fetch(): Observable<Notificacao[]> {
    if (!localStorage.getItem(TOKEN_KEY)) {
      return of([]);
    }
    return this.http.get<Notificacao[]>(this.url).pipe(
      tap((ns) => this._lista.set(ns)),
      catchError(() => of([])),
    );
  }
}
