import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, interval, switchMap, startWith, takeWhile, share, timeout, catchError, EMPTY } from 'rxjs';
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

export interface PerguntaResponse {
  resposta: string;
  trecho_fonte: string | null;
  chunks_utilizados: number;
}

const POLL_INTERVAL_MS = 8000;           // poll a cada 8s (era 3s)
const POLL_TIMEOUT_MS  = 5 * 60 * 1000; // para após 5 minutos
const TERMINAL_STATUSES: StatusProcessamento[] = ['PROCESSADO', 'ERRO'];

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

  perguntar(editalId: string, pergunta: string): Observable<PerguntaResponse> {
    return this.http.post<PerguntaResponse>(
      `${this.url}/${editalId}/perguntar`,
      { pergunta },
    );
  }

  /**
   * Faz polling a cada 3s até o status ser PROCESSADO ou ERRO.
   * Emite cada resposta intermediária para que o componente atualize a UI.
   */
  poll(editalId: string): Observable<EditalStatus> {
    return interval(POLL_INTERVAL_MS).pipe(
      startWith(0),
      switchMap(() => this.getStatus(editalId)),
      takeWhile((s) => !TERMINAL_STATUSES.includes(s.status), true),
      timeout(POLL_TIMEOUT_MS),
      catchError(() => EMPTY),  // após timeout, encerra silenciosamente
      share(),
    );
  }
}
