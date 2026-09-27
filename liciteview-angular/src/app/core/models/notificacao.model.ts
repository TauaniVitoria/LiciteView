export type TipoNotificacao = 'EDITAL_PROCESSADO' | 'EDITAL_ERRO';

export interface Notificacao {
  id: string;
  tipo: TipoNotificacao;
  titulo: string;
  mensagem: string | null;
  edital_id: string | null;
  referencia: string | null;   // id_pncp para navegação
  lida: boolean;
  criada_em: string;
}
