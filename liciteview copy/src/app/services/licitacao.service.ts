import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface FiltrosBusca {
  pagina: number;
  uf: string;
  palavraChave: string;
  modalidade: string;
  dataInicial?: string;
  dataFinal?: string;
  tipoInstrumento?: string;
  orgao?: string;
  unidade?: string;
  municipio?: string;
  esfera?: string;
  poder?: string;
  fonteOrcamentaria?: string;
  tipoMargemPreferencia?: string;
  exigenciaConteudoNacional?: string;
  emendaParlamentar?: string;
  tipo?: string;
  status?: string;
}

export interface LicitacaoItem {
  id?: string;
  titulo: string;
  orgao: string;
  modalidade: string;
  uf?: string;
  data: string;
  valorEstimado: string;
  status?: string;
  statusClass?: string;
}

export interface ResultadoBusca {
  pagina: number;
  totalPaginas: number;
  totalItens: number;
  items: LicitacaoItem[];
}

@Injectable({
  providedIn: 'root'
})
export class LicitacaoService {
  private apiUrl = 'http://127.0.0.1:8000/buscar-editais';

  constructor(private http: HttpClient) {}

  buscarEditais(filtros: FiltrosBusca): Observable<ResultadoBusca> {
    return this.http.post<ResultadoBusca>(this.apiUrl, filtros);
  }
}
