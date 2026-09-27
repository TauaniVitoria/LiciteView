import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { Produto, ProdutoCreate } from '../models/produto.model';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ProdutoService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/cliente/produtos`;

  private readonly _produtos = signal<Produto[]>([]);
  readonly produtos = this._produtos.asReadonly();

  constructor() {
    this.carregar().subscribe();
  }

  carregar(): Observable<Produto[]> {
    return this.http.get<Produto[]>(this.url).pipe(
      tap((lista) => this._produtos.set(lista)),
    );
  }

  criar(dados: ProdutoCreate): Observable<Produto> {
    return this.http.post<Produto>(this.url, dados).pipe(
      tap((novo) => this._produtos.update((arr) => [novo, ...arr])),
    );
  }

  atualizar(id: string, dados: Partial<ProdutoCreate>): Observable<Produto> {
    return this.http.put<Produto>(`${this.url}/${id}`, dados).pipe(
      tap((atualizado) =>
        this._produtos.update((arr) =>
          arr.map((p) => (p.id === id ? atualizado : p)),
        ),
      ),
    );
  }

  remover(id: string): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}`).pipe(
      tap(() => this._produtos.update((arr) => arr.filter((p) => p.id !== id))),
    );
  }
}
