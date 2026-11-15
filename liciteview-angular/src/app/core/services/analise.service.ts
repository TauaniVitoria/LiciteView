import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, tap } from 'rxjs';
import { Analise, QuantidadeOrigem } from '../models/analise.model';
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
  distancia_km?: number | null;
  quantidade_considerada?: number | null;
  quantidade_origem?: QuantidadeOrigem | null;
  uf_origem?: string | null;
  uf_destino?: string | null;
  avisos?: string[];
  preco_proposta?: number | null;
  valor_unitario_edital?: number | null;
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
    justificativa:    res.justificativa ?? undefined,
    avisos:           res.avisos ?? [],
    distanciaKm:      res.distancia_km != null ? Number(res.distancia_km) : undefined,
    quantidade:       res.quantidade_considerada ?? undefined,
    quantidadeOrigem: res.quantidade_origem ?? undefined,
    ufOrigem:         res.uf_origem ?? undefined,
    ufDestino:        res.uf_destino ?? undefined,
    precoProduto:        res.preco_venda_snapshot != null ? Number(res.preco_venda_snapshot) : undefined,
    precoProposta:       res.preco_proposta != null ? Number(res.preco_proposta) : undefined,
    valorUnitarioEdital: res.valor_unitario_edital != null ? Number(res.valor_unitario_edital) : undefined,
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
   * O backend recalcula a cada chamada e mantém uma análise por edital + produto.
   */
  analisar(editalId: string, produtoId: string, licitacaoId: string, quantidade?: number): Observable<Analise> {
    const body: any = {
      edital_id:  editalId,
      produto_id: produtoId,
    };
    // Opcional: sem ela, o backend usa a quantidade do item encontrado no edital
    if (quantidade !== undefined && quantidade !== null && quantidade > 0) {
      body.quantidade = quantidade;
    }
    return this.http
      .post<AnaliseBackendResponse>(`${this.url}/analise`, body)
      .pipe(
        map((res) => mapToAnalise(res, licitacaoId)),
        tap((analise) => this._analises.update((m) => ({ ...m, [licitacaoId]: analise }))),
      );
  }

  /**
   * Busca a análise já salva para o edital (se houver) e a coloca no signal.
   * Usado ao abrir a tela, para o resultado não sumir ao recarregar a página.
   */
  carregar(editalId: string, licitacaoId: string): Observable<Analise | null> {
    return this.http
      .get<AnaliseBackendResponse | null>(`${this.url}/editais/${editalId}/analise`)
      .pipe(
        map((res) => (res ? mapToAnalise(res, licitacaoId) : null)),
        tap((analise) => {
          if (analise) this._analises.update((m) => ({ ...m, [licitacaoId]: analise }));
        }),
        catchError(() => of(null)),
      );
  }

  clear(licitacaoId: string): void {
    this._analises.update((m) => { const c = { ...m }; delete c[licitacaoId]; return c; });
  }
}
