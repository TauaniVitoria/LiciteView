import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputTextareaModule } from 'primeng/inputtextarea';
import { InputNumberModule } from 'primeng/inputnumber';
import { DropdownModule } from 'primeng/dropdown';
import { ProdutoService } from '../../core/services/produto.service';
import { FILTRO_OPCOES } from '../../core/services/mock-data';

@Component({
  selector: 'lv-produto-form',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, InputTextModule, InputTextareaModule, InputNumberModule, DropdownModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page-h">
      <div>
        <button pButton type="button" label="Voltar" icon="pi pi-arrow-left" class="p-button-text p-button-sm" (click)="back()" style="margin-bottom: 8px;"></button>
        <h1>Cadastrar novo produto</h1>
        <p>Preencha as informações usadas pela análise de viabilidade.</p>
      </div>
    </div>

    <div class="card">
      <div class="card__body">

        <h3 class="section-h"><span class="step">1</span> Identificação</h3>
        <div class="field" style="margin-bottom: 16px;">
          <label class="field__label">Nome do produto *</label>
          <input pInputText [(ngModel)]="form.nome" placeholder="Ex.: Notebook corporativo i5 16GB" style="width: 100%;" />
        </div>
        <div class="field" style="margin-bottom: 16px;">
          <label class="field__label">Descrição técnica</label>
          <textarea pInputTextarea [(ngModel)]="form.descricao" rows="3" placeholder="Especificações, marcas aceitas, certificações..."></textarea>
        </div>

        <h3 class="section-h"><span class="step">2</span> Custos e tributação</h3>
        <div class="produto-grid--3" style="margin-bottom: 16px;">
          <div class="field">
            <label class="field__label">Custo de produção (R$) *</label>
            <p-inputNumber [(ngModel)]="form.custo_produto" mode="currency" currency="BRL" locale="pt-BR" [style]="{ width: '100%' }"></p-inputNumber>
          </div>
          <div class="field">
            <label class="field__label">Preço de venda esperado (R$)</label>
            <p-inputNumber [(ngModel)]="form.preco_venda" mode="currency" currency="BRL" locale="pt-BR" [style]="{ width: '100%' }"></p-inputNumber>
          </div>
          <div class="field">
            <label class="field__label">Carga tributária (%)</label>
            <p-inputNumber [(ngModel)]="form.impostos" suffix="%" [min]="0" [max]="100" [style]="{ width: '100%' }"></p-inputNumber>
          </div>
        </div>
        <div class="produto-grid--3" style="margin-bottom: 16px;">
          <div class="field">
            <label class="field__label">Margem mínima aceitável (%) *</label>
            <p-inputNumber [(ngModel)]="form.margem_minima_pct" suffix="%" [min]="0" [max]="100" [style]="{ width: '100%' }"></p-inputNumber>
          </div>
          <div class="field">
            <label class="field__label">Peso por unidade (kg)</label>
            <p-inputNumber [(ngModel)]="form.peso_kg" suffix=" kg" [style]="{ width: '100%' }"></p-inputNumber>
          </div>
        </div>

        <h3 class="section-h"><span class="step">3</span> Logística</h3>
        <div class="produto-grid--3" style="margin-bottom: 16px;">
          <div class="field">
            <label class="field__label">CEP de origem</label>
            <input pInputText [(ngModel)]="form.cep" class="mono" placeholder="04567-000" />
          </div>
          <div class="field">
            <label class="field__label">UF de origem</label>
            <p-dropdown [options]="ufs" [(ngModel)]="form.uf" appendTo="body" [style]="{ width: '100%' }"></p-dropdown>
          </div>
        </div>

        <div *ngIf="error()" style="margin: 16px 0; padding: 10px 14px; background: var(--red-50); border: 1px solid var(--red); border-radius: var(--r-sm); font-size: 13px; color: var(--red);">
          {{ error() }}
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border);">
          <button pButton type="button" label="Cancelar" class="p-button-outlined" (click)="back()"></button>
          <button pButton type="button" label="Salvar produto" icon="pi pi-check" [loading]="loading()" (click)="save()"></button>
        </div>
      </div>
    </div>
  `,
})
export class ProdutoFormComponent {
  private readonly svc    = inject(ProdutoService);
  private readonly router = inject(Router);

  readonly ufs = FILTRO_OPCOES.uf;

  readonly loading = signal(false);
  readonly error   = signal('');

  form = {
    nome:             '',
    descricao:        '',
    custo_produto:    0,
    preco_venda:      0,
    impostos:         18,
    margem_minima_pct: 15,  // exibido em %, convertido para 0-1 no save()
    peso_kg:          0,
    cep:              '',
    uf:               'SP',
  };

  save(): void {
    if (!this.form.nome.trim()) {
      this.error.set('O nome do produto é obrigatório.');
      return;
    }
    if (this.form.custo_produto <= 0) {
      this.error.set('Informe um custo de produção maior que zero.');
      return;
    }

    this.loading.set(true);
    this.error.set('');

    this.svc.criar({
      nome:             this.form.nome.trim(),
      descricao:        this.form.descricao || undefined,
      custo_produto:    this.form.custo_produto,
      preco_venda:      this.form.preco_venda || undefined,
      margem_minima:    this.form.margem_minima_pct / 100,
      peso_kg:          this.form.peso_kg || undefined,
      impostos:         this.form.impostos,
      cep:              this.form.cep || undefined,
      uf:               this.form.uf || undefined,
    }).subscribe({
      next: () => this.router.navigateByUrl('/produtos'),
      error: () => {
        this.error.set('Erro ao salvar produto. Tente novamente.');
        this.loading.set(false);
      },
    });
  }

  back(): void {
    this.router.navigateByUrl('/produtos');
  }
}
