import { Verdict } from './licitacao.model';

export type QuantidadeOrigem = 'INFORMADA' | 'ITEM_EDITAL' | 'RESUMO_EDITAL' | 'ESTIMADA';

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
  // Detalhes do cálculo devolvidos pelo backend
  justificativa?: string;
  avisos: string[];
  distanciaKm?: number;
  quantidade?: number;
  quantidadeOrigem?: QuantidadeOrigem;
  ufOrigem?: string;
  ufDestino?: string;
  precoProduto?: number;          // preço de venda do cadastro
  precoProposta?: number;         // preço usado na receita (limitado pelo valor do edital)
  valorUnitarioEdital?: number;   // valor estimado do item no edital (máximo aceito)
}
