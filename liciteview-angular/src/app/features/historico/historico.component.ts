import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TableModule } from 'primeng/table';
import { LicitacaoService } from '../../core/services/licitacao.service';
import { Licitacao } from '../../core/models/licitacao.model';

@Component({
  selector: 'lv-historico',
  standalone: true,
  imports: [CommonModule, ButtonModule, TableModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page-h">
      <div>
        <h1>Histórico de Consultas</h1>
        <p>Acompanhe o andamento das análises de editais processados por IA ou revise licitações consultadas anteriormente.</p>
      </div>
    </div>

    <div class="card">
      <p-table [value]="editais()" [loading]="loading()">
        <ng-template pTemplate="header">
          <tr>
            <th style="width: 140px;">Identificador</th>
            <th>Objeto / Resumo</th>
            <th>Órgão Entidade</th>
            <th>Modalidade</th>
            <th style="width: 150px;">Abertura</th>
            <th style="width: 150px; text-align: center;">Status do Resumo</th>
            <th style="width: 110px;">Ações</th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-e>
          <tr>
            <td class="mono" style="font-size: 11.5px;">{{ e.id }}</td>
            <td>
              <div style="font-weight: 600; line-height: 1.4; color: var(--ink);">{{ e.titulo }}</div>
              <div style="font-size: 12px; color: var(--ink-3); margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis;" [title]="e.description">
                {{ e.description }}
              </div>
            </td>
            <td>
              <div style="font-size: 13px; font-weight: 500; color: var(--ink-2); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis;" [title]="e.orgao">
                {{ e.orgao }}
              </div>
            </td>
            <td>
              <span class="badge badge--navy">{{ e.modalidade }}</span>
            </td>
            <td class="mono" style="font-size: 12.5px;">
              {{ e.abertura ? (e.abertura | date:'dd/MM/yyyy') : '—' }}
            </td>
            <td style="text-align: center;">
              <span class="badge" [ngClass]="getBadgeClass(e.status_processamento)">
                <span class="dot" [ngClass]="getDotClass(e.status_processamento)" [style.background]="e.status_processamento === 'PENDENTE' ? 'var(--navy)' : null"></span>
                {{ getStatusLabel(e.status_processamento) }}
              </span>
            </td>
            <td>
              <div style="display: flex; gap: 4px;">
                <button pButton type="button" label="Acessar" icon="pi pi-arrow-right" 
                        class="p-button-text p-button-sm" (click)="acessar(e)"></button>
              </div>
            </td>
          </tr>
        </ng-template>
        <ng-template pTemplate="emptymessage">
          <tr>
            <td colspan="7">
              <div class="empty" style="padding: 48px 0;">
                <i class="pi pi-history" style="font-size: 32px; color: var(--ink-3); margin-bottom: 8px;"></i>
                <div style="font-weight: 600; color: var(--ink-2);">Nenhum edital no histórico</div>
                <p style="font-size: 12.5px; color: var(--ink-3); margin-top: 4px; max-width: 380px; margin-left: auto; margin-right: auto; line-height: 1.4;">
                  Os editais que você visualizar a partir da busca do PNCP serão guardados aqui automaticamente para que possa acompanhar o processamento.
                </p>
              </div>
            </td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `,
})
export class HistoricoComponent implements OnInit {
  private readonly licitacaoSvc = inject(LicitacaoService);
  private readonly router = inject(Router);

  readonly editais = signal<Licitacao[]>([]);
  readonly loading = signal(true);

  ngOnInit(): void {
    this.carregarHistorico();
  }

  carregarHistorico(): void {
    this.loading.set(true);
    this.licitacaoSvc.getHistorico().subscribe({
      next: (dados) => {
        this.editais.set(dados);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
      }
    });
  }

  acessar(e: Licitacao): void {
    this.router.navigate(['/edital', e.id]);
  }

  getBadgeClass(status?: string): string {
    switch (status) {
      case 'PROCESSADO':
        return 'badge--green';
      case 'PROCESSANDO':
        return 'badge--amber';
      case 'ERRO':
        return 'badge--red';
      case 'PENDENTE':
      default:
        return 'badge--navy';
    }
  }

  getDotClass(status?: string): string {
    switch (status) {
      case 'PROCESSADO':
        return 'dot--green';
      case 'PROCESSANDO':
        return 'dot--amber';
      case 'ERRO':
        return 'dot--red';
      case 'PENDENTE':
      default:
        return '';
    }
  }

  getStatusLabel(status?: string): string {
    switch (status) {
      case 'PROCESSADO':
        return 'Processado';
      case 'PROCESSANDO':
        return 'Processando';
      case 'ERRO':
        return 'Falha';
      case 'PENDENTE':
      default:
        return 'Pendente';
    }
  }
}
