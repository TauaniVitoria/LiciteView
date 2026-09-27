export type CategoriaProduto =
  | 'MEDICAMENTO'
  | 'MATERIAL_HOSPITALAR'
  | 'EQUIPAMENTO'
  | 'SERVICO'
  | 'OUTRO';

export interface Produto {
  id: string;
  usuario_id: string;
  nome: string;
  descricao: string | null;
  categoria: CategoriaProduto;
  ncm: string | null;
  preco_venda: number | null;
  custo_produto: number;
  margem_minima: number;      // 0–1 (ex: 0.15 = 15%)
  peso_kg: number | null;
  impostos: number;           // % (ex: 18.5)
  cep: string | null;
  uf: string | null;
  capacidade_mensal: number | null;
  ativo: boolean;
  criado_em: string;
}

export interface ProdutoCreate {
  nome: string;
  descricao?: string;
  categoria?: CategoriaProduto;
  ncm?: string;
  preco_venda?: number;
  custo_produto: number;
  margem_minima: number;
  peso_kg?: number;
  impostos: number;
  cep?: string;
  uf?: string;
  capacidade_mensal?: number;
}
