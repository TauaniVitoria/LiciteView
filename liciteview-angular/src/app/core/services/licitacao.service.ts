import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map, of, catchError } from 'rxjs';
import {
  Licitacao, ResumoEdital, SearchFilters,
  PncpSearchResponse, mapPncpItemToLicitacao,
} from '../models/licitacao.model';
import { FILTRO_OPCOES, MOCK_RESUMO } from './mock-data';
import { environment } from '../../../environments/environment';

export interface SearchResult {
  items: Licitacao[];
  total: number;
}

// Mapeamento Angular → parâmetros da API de busca interna do PNCP
const STATUS_PNCP: Record<string, string> = {
  recebendo:   'recebendo_proposta',
  julgamento:  'encerrado',
  encerradas:  'cancelado',
};

// Códigos de esfera confirmados pelo padrão PNCP
const ESFERA_PNCP: Record<string, string> = {
  Federal: 'F', Estadual: 'E', Municipal: 'M', Distrital: 'D',
};

// Códigos de poder confirmados pelo padrão PNCP
const PODER_PNCP: Record<string, string> = {
  Executivo: 'E', Legislativo: 'L', 'Judiciário': 'J',
};

// IDs numéricos de modalidade confirmados com a API real do PNCP
const MODALIDADE_PNCP: Record<string, number> = {
  'Leilão - Eletrônico': 1,
  'Diálogo Competitivo': 2,
  'Concurso': 3,
  'Concorrência - Eletrônica': 4,
  'Concorrência - Presencial': 5,
  'Pregão - Eletrônico': 6,
  'Pregão - Presencial': 7,
  'Dispensa': 8,
  'Inexigibilidade': 9,
  'Manifestação de Interesse': 10,
  'Pré-qualificação': 11,
  'Credenciamento': 12,
  'Leilão - Presencial': 13,
  'Chamada pública': 15,
};

// TODO: confirmar IDs numéricos de instrumento com a API real após testes
const INSTRUMENTO_PNCP: Record<string, number> = {
  Edital: 1,
  'Aviso de Contratação Direta': 2,
  Aviso: 2,
  'Termo Aditivo': 3,
};

@Injectable({ providedIn: 'root' })
export class LicitacaoService {
  private readonly http = inject(HttpClient);
  readonly filtroOpcoes = FILTRO_OPCOES;

  // Cache local: preenchido pelo search(), consumido pelo byId()
  private readonly _cache = new Map<string, Licitacao>();

  search(filters: SearchFilters, pagina = 1, tamPagina = 20): Observable<SearchResult> {
    let params = new HttpParams()
      .set('pagina', pagina)
      .set('tam_pagina', tamPagina)
      .set('ordenacao', '-data');

    if (filters.keyword)                        params = params.set('q', filters.keyword);
    if (filters.status && filters.status !== 'todos') {
      const s = STATUS_PNCP[filters.status];
      if (s)                                    params = params.set('status', s);
    }
    if (filters.uf)                             params = params.set('ufs', filters.uf);
    if (filters.esfera) {
      const e = ESFERA_PNCP[filters.esfera];
      if (e)                                    params = params.set('esferas', e);
    }
    if (filters.poder) {
      const p = PODER_PNCP[filters.poder];
      if (p)                                    params = params.set('poderes', p);
    }
    if (filters.modalidade) {
      const m = MODALIDADE_PNCP[filters.modalidade];
      if (m)                                    params = params.set('modalidades', m);
    }
    if (filters.instrumento) {
      const t = INSTRUMENTO_PNCP[filters.instrumento];
      if (t)                                    params = params.set('tipos', t);
    }

    return this.http
      .get<PncpSearchResponse>(`${environment.apiUrl}/cliente/licitacoes/buscar`, { params })
      .pipe(
        map((res) => {
          const raw = res.data ?? res.items ?? [];
          const items = raw.map(mapPncpItemToLicitacao);
          items.forEach((l) => this._cache.set(l.id, l));
          return { items, total: res.totalRegistros ?? res.total ?? items.length };
        }),
      );
  }

  byId(id: string): Observable<Licitacao | undefined> {
    const cached = this._cache.get(id);
    if (cached) {
      return of(cached);
    }
    return this.http.get<any>(`${environment.apiUrl}/cliente/licitacoes/${id}`).pipe(
      map((item) => {
        const mapped = mapPncpItemToLicitacao(item);
        this._cache.set(id, mapped);
        return mapped;
      }),
      catchError(() => of(undefined))
    );
  }

  getHistorico(): Observable<Licitacao[]> {
    return this.http.get<any[]>(`${environment.apiUrl}/cliente/editais/historico`).pipe(
      map((items) => {
        const mapped = items.map(mapPncpItemToLicitacao);
        mapped.forEach((l) => this._cache.set(l.id, l));
        return mapped;
      }),
      catchError(() => of([]))
    );
  }

  resumo(_id: string): Observable<ResumoEdital> {
    // Fase 3: GET /cliente/editais/{id}/resumo (pós pipeline RAG)
    return of(MOCK_RESUMO);
  }
}
