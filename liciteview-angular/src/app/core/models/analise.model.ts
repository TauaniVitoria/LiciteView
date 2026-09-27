import { Verdict } from './licitacao.model';

export interface Analise {
  licitacaoId: string;
  produtoId: string;
  verdict: Verdict;
  score: number;
  margemPct: number;
  custoOperacional: number;
  custoLogistico: number;
  analyzedAt: string;
  receitaEstimada?: number;
}
