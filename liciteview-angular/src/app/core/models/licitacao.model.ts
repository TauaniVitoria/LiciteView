export type Verdict = 'green' | 'amber' | 'red';

export type LicitacaoStatus =
  | 'A Receber/Recebendo Proposta'
  | 'Em Julgamento/Propostas Encerradas'
  | 'Encerradas';

export interface Licitacao {
  id: string;
  titulo: string;
  orgao: string;
  unidade: string;
  modalidade: string;
  instrumento: string;
  uf: string;
  municipio: string;
  esfera: string;
  poder: string;
  valor: number | null;
  abertura: string;
  encerramento: string;
  status: LicitacaoStatus;
  diasRestantes: number;
  url_origem: string | null;
  status_processamento?: 'PENDENTE' | 'PROCESSANDO' | 'PROCESSADO' | 'ERRO';
}

// ── Resumo estruturado gerado pelo pipeline RAG ───────────────────────────────

export interface Bloco1VisaoGeral {
  objeto: string | null;
  orgao: string | null;
  modalidade: string | null;
  criterio_julgamento: string | null;
  numero_edital: string | null;
}

export interface Bloco2Prazos {
  prazo_entrega: string | null;
  vigencia_contrato: string | null;
  local_entrega: string | null;
  data_abertura: string | null;
}

export interface Bloco3Documentacao {
  documentos_habilitacao: string[];
  regularidade_fiscal: string[];
  qualificacao_tecnica: string[];
}

export interface Bloco4RequisitosTecnicos {
  especificacoes_resumo: string | null;
  certificacoes_exigidas: string[];
  exige_amostra: boolean | null;
  outros_requisitos: string[];
}

export interface Bloco5Riscos {
  multas: string[];
  sancoes: string[];
  clausulas_criticas: string[];
  pontos_atencao: string[];
}

export interface ResumoEdital {
  bloco1_visao_geral: Bloco1VisaoGeral;
  bloco2_prazos: Bloco2Prazos;
  bloco3_documentacao: Bloco3Documentacao;
  bloco4_requisitos_tecnicos: Bloco4RequisitosTecnicos;
  bloco5_riscos: Bloco5Riscos;
}

export interface SearchFilters {
  keyword?: string;
  status?: 'recebendo' | 'julgamento' | 'encerradas' | 'todos';
  instrumento?: string;
  modalidade?: string;
  orgao?: string;
  unidade?: string;
  uf?: string;
  municipio?: string;
  esfera?: string;
  poder?: string;
  fonteOrcam?: string;
  margemPref?: string;
  conteudoNac?: string;
  emendaParl?: string;
}

// ── Tipos da API de busca interna do PNCP ────────────────────────────────────

// Estrutura real da API /api/search/ do PNCP (verificada via devtools em 2026-05-19)
export interface PncpItem {
  id?: string;                          // hash interno do índice de busca
  numero_controle_pncp?: string;        // ex: "18307447000173-1-000024/2026"
  title?: string;                       // "Edital nº 011/2026"
  description?: string;                 // objeto da compra (campo principal)
  item_url?: string;                    // URL relativa: "/compras/{cnpj}/{ano}/{seq}"
  orgao_nome?: string;                  // nome do órgão (campo plano)
  orgao_cnpj?: string;
  unidade_nome?: string;                // nome da unidade (campo plano)
  esfera_id?: string;                   // 'F' | 'E' | 'M' | 'D'
  esfera_nome?: string;                 // "Municipal", "Federal", etc.
  poder_id?: string;                    // 'E' | 'L' | 'J' | 'N'
  poder_nome?: string;
  municipio_nome?: string;              // campo plano
  uf?: string;                          // sigla do estado, campo plano
  modalidade_licitacao_nome?: string;   // "Pregão - Eletrônico"
  situacao_id?: string;
  situacao_nome?: string;               // "Divulgada no PNCP"
  data_publicacao_pncp?: string;
  data_inicio_vigencia?: string;        // abertura das propostas
  data_fim_vigencia?: string;           // encerramento das propostas
  valor_global?: number | null;
  tipo_nome?: string;                   // "Edital", "Aviso de Contratação Direta"
  cancelado?: boolean;
  status_processamento?: 'PENDENTE' | 'PROCESSANDO' | 'PROCESSADO' | 'ERRO';
}

export interface PncpSearchResponse {
  items?: PncpItem[];   // a API usa "items"
  total?: number;       // a API usa "total"
  // Fallbacks caso a estrutura mude
  data?: PncpItem[];
  totalRegistros?: number;
}

// ── Mapper PNCP → Licitacao ───────────────────────────────────────────────────

const ESFERA_MAP: Record<string, string> = {
  F: 'Federal', E: 'Estadual', M: 'Municipal', D: 'Distrital',
};

const PODER_MAP: Record<string, string> = {
  E: 'Executivo', L: 'Legislativo', J: 'Judiciário', M: 'Ministério Público',
};

function calcDiasRestantes(encerramento: string): number {
  if (!encerramento) return 0;
  const diff = new Date(encerramento).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / 86_400_000));
}

function mapSituacao(nome?: string, cancelado = false): LicitacaoStatus {
  if (cancelado) return 'Encerradas';
  const s = (nome ?? '').toLowerCase();
  if (s.includes('encerr') || s.includes('cancel') || s.includes('revog') || s.includes('homolog')) return 'Encerradas';
  if (s.includes('julg') || s.includes('suspens') || s.includes('impugn')) return 'Em Julgamento/Propostas Encerradas';
  return 'A Receber/Recebendo Proposta';
}

export function mapPncpItemToLicitacao(item: PncpItem): Licitacao {
  const encerramento = item.data_fim_vigencia ?? '';
  return {
    id:         item.numero_controle_pncp ?? item.id ?? crypto.randomUUID(),
    titulo:     item.description?.trim() || item.title || 'Objeto não informado',
    orgao:      item.orgao_nome ?? '',
    unidade:    item.unidade_nome ?? '',
    modalidade: item.modalidade_licitacao_nome ?? '',
    instrumento: item.tipo_nome ?? 'Edital',
    uf:         item.uf ?? '',
    municipio:  item.municipio_nome ?? '',
    esfera:     item.esfera_nome ?? ESFERA_MAP[item.esfera_id ?? ''] ?? '',
    poder:      item.poder_nome ?? PODER_MAP[item.poder_id ?? ''] ?? '',
    valor:      item.valor_global ?? null,
    abertura:   item.data_inicio_vigencia ?? '',
    encerramento,
    status:      mapSituacao(item.situacao_nome, item.cancelado),
    diasRestantes: calcDiasRestantes(encerramento),
    url_origem:  item.item_url ? `https://pncp.gov.br${item.item_url}` : null,
    status_processamento: item.status_processamento,
  };
}
