import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map, tap } from 'rxjs';
import { Analise } from '../models/analise.model';
import { Verdict } from '../models/licitacao.model';
import { environment } from '../../../environments/environment';

export interface PipelineStep { index: number; label: string; }

export const PIPELINE_STEPS: PipelineStep[] = [
  { index: 0, label: 'Verificando edital e produto' },
  { index: 1, label: 'Calculando custo operacional (produção + impostos)' },
  { index: 2, label: 'Estimando quantidade pelo valor do edital' },
  { index: 3, label: 'Calculando custo logístico (Tabela ANTT)' },
  { index: 4, label: 'Calculando margem estimada' },
  { index: 5, label: 'Comparando com margem mínima definida' },
  { index: 6, label: 'Gerando score de atratividade' },
  { index: 7, label: 'Consolidando resultado' },
];

type Classificacao = 'VALE_A_PENA' | 'ATENCAO' | 'NAO_RECOMENDADO';

interface AnaliseBackendResponse {
  id: string;
  edital_id: string;
  produto_id: string;
  margem_minima_snapshot: number;
  preco_venda_snapshot: number | null;
  custo_produto_snapshot: number;
  custo_frete_estimado: number | null;
  custo_total_estimado: number | null;
  receita_estimada: number | null;
  margem_estimada: number | null;
  dentro_margem: boolean;
  classificacao: Classificacao;
  justificativa: string | null;
  gerado_em: string;
}

function mapToAnalise(res: AnaliseBackendResponse, licitacaoId: string): Analise {
  const marg    = Number(res.margem_estimada ?? 0);
  const margMin = Number(res.margem_minima_snapshot ?? 0.15);

  const verdict: Verdict =
    res.classificacao === 'VALE_A_PENA' ? 'green' :
    res.classificacao === 'ATENCAO'     ? 'amber' : 'red';

  let score: number;
  if (marg <= 0) score = Math.max(0, 30 + Math.round(marg * 100));
  else           score = Math.min(100, Math.round(50 + (marg / Math.max(margMin, 0.01)) * 40));

  const custoTotal  = Number(res.custo_total_estimado  ?? 0);
  const custoFrete  = Number(res.custo_frete_estimado  ?? 0);

  return {
    licitacaoId,
    produtoId:       res.produto_id,
    verdict,
    score,
    margemPct:       marg * 100,
    custoOperacional: custoTotal - custoFrete,
    custoLogistico:   custoFrete,
    analyzedAt:       res.gerado_em,
    receitaEstimada:  res.receita_estimada ? Number(res.receita_estimada) : undefined,
  };
}

@Injectable({ providedIn: 'root' })
export class AnaliseService {
  private readonly http = inject(HttpClient);
  private readonly url  = `${environment.apiUrl}/cliente`;

  private readonly _analises = signal<Record<string, Analise>>({});
  readonly analises = this._analises.asReadonly();

  get(licitacaoId: string): Analise | undefined {
    return this._analises()[licitacaoId];
  }

  /**
   * Envia POST /cliente/analise e armazena o resultado no signal.
   * O backend retorna análise cacheada se já existe para esse par edital+produto.
   */
  analisar(editalId: string, produtoId: string, licitacaoId: string, valorReferencia?: number): Observable<Analise> {
    const body: any = {
      edital_id:  editalId,
      produto_id: produtoId,
    };
    if (valorReferencia !== undefined && valorReferencia !== null) {
      body.valor_referencia = valorReferencia;
    }
    return this.http
      .post<AnaliseBackendResponse>(`${this.url}/analise`, body)
      .pipe(
        map((res) => mapToAnalise(res, licitacaoId)),
        tap((analise) => this._analises.update((m) => ({ ...m, [licitacaoId]: analise }))),
      );
  }

  clear(licitacaoId: string): void {
    this._analises.update((m) => { const c = { ...m }; delete c[licitacaoId]; return c; });
  }
}
