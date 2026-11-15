import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, interval, switchMap, startWith, takeWhile, share, timeout, catchError, EMPTY, of } from 'rxjs';
import { ResumoEdital } from '../models/licitacao.model';
import { environment } from '../../../environments/environment';

export interface EditalProcessarRequest {
  id_pncp: string;
  titulo?: string;
  orgao: string;
  objeto: string;
  modalidade?: string;
  valor_estimado?: number;
  url_origem?: string;
  url_pdf?: string;
  uf?: string;
  municipio?: string;
  reprocessar?: boolean;   // true só no botão "Tentar novamente"
  data_publicacao?: string;
  data_abertura?: string;
}

export interface EditalProcessarResponse {
  edital_id: string;
  status: string;
}

export type StatusProcessamento = 'PENDENTE' | 'PROCESSANDO' | 'PROCESSADO' | 'ERRO';

export interface EditalStatus {
  edital_id: string;
  id_pncp: string;
  status: StatusProcessamento;
  resumo: ResumoEdital | null;
  total_chunks: number;
  erro_mensagem: string | null;
  url_pdf: string | null;
  tempo_decorrido?: number | null;
}

export interface PerguntaSalva {
  id: string;
  pergunta: string;
  resposta: string | null;
  trecho_fonte: string | null;
  pagina_fonte: number | null;
  criada_em: string;
}

export interface PerguntaResponse {
  resposta: string;
  trecho_fonte: string | null;
  pagina_fonte?: number | null;
  pagina_fonte_final?: number | null;
  chunks_utilizados: number;
}

const POLL_INTERVAL_MS = 8000;           // poll a cada 8s (era 3s)
const POLL_TIMEOUT_MS  = 5 * 60 * 1000; // para após 5 minutos

// PROCESSADO só encerra o polling quando o resumo já veio: durante um reprocessamento
// o backend pode responder PROCESSADO sem resumo, e parar ali deixava a tela presa.
function isTerminal(s: EditalStatus): boolean {
  return s.status === 'ERRO' || (s.status === 'PROCESSADO' && !!s.resumo);
}

@Injectable({ providedIn: 'root' })
export class EditalService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/cliente/editais`;

  processar(req: EditalProcessarRequest): Observable<EditalProcessarResponse> {
    return this.http.post<EditalProcessarResponse>(`${this.url}/processar`, req);
  }

  getStatus(editalId: string): Observable<EditalStatus> {
    return this.http.get<EditalStatus>(`${this.url}/${editalId}/status`);
  }

  uploadPdf(file: File, editalId?: string): Observable<EditalProcessarResponse> {
    const formData = new FormData();
    formData.append('arquivo', file);
    const targetUrl = editalId
      ? `${this.url}/${editalId}/upload-pdf`
      : `${this.url}/upload-pdf`;
    return this.http.post<EditalProcessarResponse>(targetUrl, formData);
  }

  perguntar(editalId: string, pergunta: string): Observable<PerguntaResponse> {
    return this.http.post<PerguntaResponse>(
      `${this.url}/${editalId}/perguntar`,
      { pergunta },
    );
  }

  /** Perguntas já respondidas do usuário sobre o edital, da mais antiga para a mais nova. */
  historicoPerguntas(editalId: string): Observable<PerguntaSalva[]> {
    return this.http
      .get<PerguntaSalva[]>(`${this.url}/${editalId}/perguntas`)
      .pipe(catchError(() => of([])));
  }

  /**
   * Faz polling a cada 3s até o status ser PROCESSADO ou ERRO.
   * Emite cada resposta intermediária para que o componente atualize a UI.
   */
  poll(editalId: string): Observable<EditalStatus> {
    return interval(POLL_INTERVAL_MS).pipe(
      startWith(0),
      switchMap(() => this.getStatus(editalId)),
      takeWhile((s) => !isTerminal(s), true),
      timeout(POLL_TIMEOUT_MS),
      catchError(() => EMPTY),  // após timeout, encerra silenciosamente
      share(),
    );
  }
}
