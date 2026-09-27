import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TableModule } from 'primeng/table';
import { ProdutoService } from '../../core/services/produto.service';

@Component({
  selector: 'lv-produtos-list',
  standalone: true,
  imports: [CommonModule, ButtonModule, TableModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page-h">
      <div>
        <h1>Meus Produtos</h1>
        <p>Cadastros usados para calcular viabilidade, frete e margem em cada edital.</p>
      </div>
      <button pButton type="button" label="Novo produto" icon="pi pi-plus" (click)="novo()"></button>
    </div>

    <div class="card">
      <p-table [value]="produtos()">
        <ng-template pTemplate="header">
          <tr>
            <th>Produto</th>
            <th style="text-align: right;">Custo</th>
            <th style="text-align: right;">Impostos</th>
            <th>Origem</th>
            <th style="width: 130px;"></th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-p>
          <tr>
            <td>
              <div style="font-weight: 600;">{{ p.nome }}</div>
              <div style="font-size: 12px; color: var(--ink-3);">{{ p.descricao }}</div>
            </td>
            <td class="mono" style="text-align: right;">{{ p.custo_produto | currency:'BRL':'symbol':'1.2-2':'pt-BR' }}</td>
            <td class="mono" style="text-align: right;">{{ p.impostos }}%</td>
            <td>{{ p.cep }} · {{ p.uf }}</td>
            <td>
              <div style="display: flex; gap: 4px; justify-content: flex-end;">
                <button pButton type="button" icon="pi pi-pencil" class="p-button-text p-button-sm"></button>
                <button pButton type="button" icon="pi pi-trash" class="p-button-text p-button-sm p-button-danger" (click)="remove(p.id)"></button>
              </div>
            </td>
          </tr>
        </ng-template>
        <ng-template pTemplate="emptymessage">
          <tr><td colspan="5"><div class="empty">Nenhum produto cadastrado ainda.</div></td></tr>
        </ng-template>
      </p-table>
    </div>

    <div style="margin-top: 12px; font-size: 12.5px; color: var(--ink-3); display: flex; gap: 6px; align-items: center;">
    </div>
  `,
})
export class ProdutosListComponent {
  private readonly svc = inject(ProdutoService);
  private readonly router = inject(Router);

  readonly produtos = this.svc.produtos;

  novo(): void {
    this.router.navigateByUrl('/produtos/novo');
  }

  remove(id: string): void {
    this.svc.remover(id).subscribe();
  }
}
