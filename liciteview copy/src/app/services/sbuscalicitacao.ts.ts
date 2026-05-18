import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { BuscaLicitacao } from '../models/licitacao.model';

@Injectable({
  providedIn: 'root',
})

export class SbuscalicitacaoTs {
  private http = inject(HttpClient);
  private readonly API_URL = ''; // A rota que você criará no FastAPI

postFiltros(dados: BuscaLicitacao) {
    // Aqui você envia o JSON para o FastAPI
    return this.http.post(this.API_URL, dados);
  }
}


