export interface BuscaLicitacao {
  palavra_chave: string;
  status: string;
  filtros: {
    tipos_de_instrumento_convocatorio: string[];
    modalidades_da_contratacao: string[];
    orgaos: string[];
    unidades: string[];
    ufs: string[];
    municipios: string[];
    esferas: string[];
    // ... adicione os outros campos do PDF
  };
  paginacao: {
    pagina: number;
    itens_por_pagina: number;
  };
  ordenacao: {
    campo: string | null;
    direcao: string | null;
  };
}