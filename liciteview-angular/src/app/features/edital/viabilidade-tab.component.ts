import { Component, ChangeDetectionStrategy, Input, inject, signal, computed, OnChanges, OnDestroy, OnInit, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DropdownModule } from 'primeng/dropdown';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { InputTextModule } from 'primeng/inputtext';
import { Licitacao } from '../../core/models/licitacao.model';
import { Produto } from '../../core/models/produto.model';
import { ProdutoService } from '../../core/services/produto.service';
import { AnaliseService, PIPELINE_STEPS } from '../../core/services/analise.service';

@Component({
  selector: 'lv-viabilidade-tab',
  standalone: true,
  imports: [CommonModule, FormsModule, DropdownModule, ButtonModule, ProgressSpinnerModule, InputTextModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- Running -->
    <ng-container *ngIf="running(); else notRunning">
      <div class="card" style="padding: 0;">
        <div style="padding: 48px 32px; max-width: 520px; margin: 0 auto;">
          <div style="text-align: center; margin-bottom: 24px;">
            <p-progressSpinner styleClass="w-3rem h-3rem" strokeWidth="3" animationDuration=".9s"></p-progressSpinner>
            <h2 style="font-size: 16px; font-weight: 700; margin: 16px 0 4px; color: var(--ink);">Analisando edital</h2>
            <p style="font-size: 12.5px; color: var(--ink-3); margin: 0;">Pipeline IA em execução · não feche esta aba</p>
          </div>
          <ol style="list-style: none; padding: 0; margin: 0;">
            <li *ngFor="let s of steps"
                style="display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border);"
                [style.opacity]="s.index <= step() ? 1 : 0.4">
              <span [style.background]="s.index < step() ? 'var(--green)' : s.index === step() ? 'var(--cyan)' : 'var(--surface-2)'"
                    [style.borderColor]="s.index < step() ? 'var(--green)' : s.index === step() ? 'var(--cyan)' : 'var(--border-strong)'"
                    style="width: 18px; height: 18px; border-radius: 50%; border: 1px solid; display: flex; align-items: center; justify-content: center; color: white; flex-shrink: 0;">
                <i *ngIf="s.index < step()" class="pi pi-check" style="font-size: 10px;"></i>
                <span *ngIf="s.index === step()" style="width: 6px; height: 6px; background: white; border-radius: 50%;"></span>
              </span>
              <span style="font-size: 13px;"
                    [style.color]="s.index < step() ? 'var(--ink-2)' : s.index === step() ? 'var(--ink)' : 'var(--ink-3)'"
                    [style.fontWeight]="s.index === step() ? 600 : 400">
                {{ s.label }}
              </span>
            </li>
          </ol>
        </div>
      </div>
    </ng-container>

    <ng-template #notRunning>
      <!-- Empty (not yet analyzed) -->
      <ng-container *ngIf="!analysis(); else hasAnalysis">
        <div class="card" style="padding: 0;">
          <div style="padding: 48px 32px; text-align: center; max-width: 560px; margin: 0 auto;">
            <div style="width: 56px; height: 56px; margin: 0 auto 18px; border-radius: 50%; background: var(--surface-2); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; color: var(--ink-3);">
              <i class="pi pi-chart-bar" style="font-size: 22px;"></i>
            </div>
            <h2 style="font-size: 18px; font-weight: 700; margin: 0 0 6px; color: var(--ink);">Esta licitação ainda não foi analisada</h2>
            <p style="font-size: 13.5px; color: var(--ink-3); margin: 0 0 24px; line-height: 1.55;">
              A análise procura o seu produto no edital, calcula o custo de produção e impostos, estima o frete pela Tabela ANTT e compara a margem com a mínima definida no produto.
            </p>

            <div *ngIf="erro()" style="margin-bottom: 16px; padding: 12px 16px; background: var(--red-50); border: 1px solid var(--red); border-radius: var(--r-md); font-size: 13px; color: var(--red); text-align: left; display: flex; align-items: flex-start; gap: 10px;">
              <i class="pi pi-exclamation-triangle" style="flex-shrink: 0; margin-top: 1px;"></i>
              <span>{{ erro() }}</span>
            </div>

            <div style="background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-md); padding: 14px; margin-bottom: 20px; text-align: left; display: flex; flex-direction: column; gap: 12px;">
              <div>
                <label class="field__label" style="margin-bottom: 8px; display: block;">Analisar como produto</label>
                <p-dropdown [options]="produtoOptions()" [(ngModel)]="selectedProd" placeholder="Selecione um produto" [style]="{ width: '100%' }" appendTo="body"></p-dropdown>
              </div>

              <div>
                <label class="field__label" style="margin-bottom: 8px; display: block;">Quantidade (opcional)</label>
                <input pInputText type="number" min="1" [(ngModel)]="quantidade" placeholder="Deixe em branco para usar a quantidade do edital" style="width: 100%;" />
                <div style="font-size: 11px; color: var(--ink-3); margin-top: 4px;">
                  A análise usa o preço e o custo do cadastro do produto e procura no edital a quantidade e o valor estimado do item.
                  Preencha apenas se quiser simular outra quantidade ou se o sistema não encontrar o produto no edital.
                </div>
              </div>

              <div style="font-size: 11.5px; color: var(--ink-3); border-top: 1px solid var(--border); padding-top: 8px;">
                Tempo estimado: ~15s
              </div>
            </div>
            <button pButton type="button" label="Analisar viabilidade" icon="pi pi-sparkles" (click)="start()" [disabled]="!selectedProd || !editalId"></button>
          </div>
        </div>
      </ng-container>

      <!-- Result -->
      <ng-template #hasAnalysis>
        <ng-container *ngIf="analysis() as a">
          <ng-container *ngIf="produtoFor(a.produtoId) as p">
            <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--surface-2); border-radius: var(--r-md);">
              <span style="font-size: 12.5px; color: var(--ink-2); font-weight: 600;">Analisado como:</span>
              <span class="badge badge--cyan">{{ p.nome }}</span>
              <span style="margin-left: auto; font-size: 12px; color: var(--ink-3);">
                Análise gerada em {{ a.analyzedAt | date:'dd/MM/yyyy HH:mm' }}
              </span>
              <button pButton type="button" label="Reanalisar" icon="pi pi-refresh" class="p-button-outlined p-button-sm" (click)="reset()"></button>
            </div>

            <div class="viability">
              <!-- Semaphore -->
              <div class="semaphore">
                <div class="semaphore__label">Classificação</div>
                <div class="semaphore__lights">
                  <div class="semaphore__light red" [class.is-on]="a.verdict === 'red'"></div>
                  <div class="semaphore__light amber" [class.is-on]="a.verdict === 'amber'"></div>
                  <div class="semaphore__light green" [class.is-on]="a.verdict === 'green'"></div>
                </div>
                <div class="semaphore__verdict" [ngClass]="a.verdict">{{ verdictLabel(a.verdict) }}</div>
                <div class="semaphore__score" *ngIf="!a.avisos.length">Score de atratividade: <strong>{{ a.score }}</strong>/100</div>
                <div class="semaphore__score" *ngIf="a.avisos.length">Resultado baseado em estimativas</div>
              </div>

              <!-- Metrics -->
              <div>
                <div *ngFor="let aviso of a.avisos"
                     style="margin-bottom: 12px; padding: 12px 16px; background: var(--amber-50, #fff7e6); border: 1px solid var(--amber, #d97706); border-radius: var(--r-md); font-size: 13px; color: var(--ink-2); display: flex; align-items: flex-start; gap: 10px;">
                  <i class="pi pi-exclamation-triangle" style="flex-shrink: 0; margin-top: 2px; color: var(--amber, #d97706);"></i>
                  <span>{{ aviso }}</span>
                </div>
                <div *ngIf="a.precoProposta" style="margin-bottom: 12px; padding: 12px 16px; background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-md); font-size: 13px; color: var(--ink-2); display: flex; flex-wrap: wrap; gap: 6px 24px;">
                  <span>Seu preço: <strong class="mono">{{ a.precoProduto | currency:'BRL':'symbol':'1.2-2':'pt-BR' }}</strong></span>
                  <span *ngIf="a.valorUnitarioEdital; else semTeto">Valor estimado no edital: <strong class="mono">{{ a.valorUnitarioEdital | currency:'BRL':'symbol':'1.2-2':'pt-BR' }}</strong></span>
                  <ng-template #semTeto><span>Valor estimado no edital: <strong>não encontrado</strong></span></ng-template>
                  <span>Preço considerado: <strong class="mono">{{ a.precoProposta | currency:'BRL':'symbol':'1.2-2':'pt-BR' }}</strong></span>
                </div>
                <div class="metric-grid">
                  <div class="metric">
                    <div class="metric__label">Margem estimada</div>
                    <div class="metric__value" [style.color]="a.margemPct >= 0 ? 'var(--green)' : 'var(--red)'">
                      {{ a.margemPct >= 0 ? '+' : '' }}{{ a.margemPct | number:'1.1-1' }}%
                    </div>
                    <div class="metric__delta" [ngClass]="a.margemPct >= 0 ? 'up' : 'down'">
                      {{ ((a.receitaEstimada ?? licitacao.valor ?? 0) * a.margemPct / 100) | currency:'BRL':'symbol':'1.0-0':'pt-BR' }}
                    </div>
                  </div>
                  <div class="metric">
                    <div class="metric__label">Custo operacional</div>
                    <div class="metric__value">{{ a.custoOperacional | currency:'BRL':'symbol':'1.0-0':'pt-BR' }}</div>
                    <div class="metric__delta">{{ a.quantidade | number:'1.0-0':'pt-BR' }} un. · produção + impostos {{ p.impostos }}%</div>
                  </div>
                  <div class="metric">
                    <div class="metric__label">Custo logístico</div>
                    <div class="metric__value">{{ a.custoLogistico | currency:'BRL':'symbol':'1.0-0':'pt-BR' }}</div>
                    <div class="metric__delta">{{ a.ufOrigem }} → {{ a.ufDestino }} · {{ a.distanciaKm | number:'1.0-0':'pt-BR' }} km · Tabela ANTT</div>
                  </div>
                </div>

                <div class="card">
                  <div class="card__header"><i class="pi pi-chart-bar"></i><h3 class="card__title">Como o resultado foi calculado</h3></div>
                  <div class="card__body">
                    <p style="font-size: 13.5px; color: var(--ink-2); margin: 0; line-height: 1.6;">{{ a.justificativa }}</p>
                  </div>
                </div>
              </div>
            </div>
          </ng-container>
        </ng-container>
      </ng-template>
    </ng-template>
  `,
})
export class ViabilidadeTabComponent implements OnChanges, OnDestroy, OnInit {
  private readonly produtoSvc = inject(ProdutoService);
  private readonly analiseSvc = inject(AnaliseService);

  @Input({ required: true }) licitacao!: Licitacao;
  @Input() editalId: string | null = null;

  readonly steps   = PIPELINE_STEPS;
  readonly produtos = this.produtoSvc.produtos;
  readonly produtoOptions = computed(() =>
    this.produtos().map((p: Produto) => ({ label: p.nome, value: p.id }))
  );
  readonly running = signal(false);
  readonly step    = signal(0);
  readonly erro    = signal('');

  selectedProd: string = this.produtos()[0]?.id ?? '';
  quantidade: number | null = null;

  private _stepTimer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {}

  // O id do edital chega depois que a página abre (vem da resposta do processamento).
  // Quando chega, busca a análise já salva para o resultado não sumir ao recarregar.
  ngOnChanges(changes: SimpleChanges): void {
    if (changes['editalId'] && this.editalId && !this.analysis()) {
      this.analiseSvc.carregar(this.editalId, this.licitacao.id).subscribe((a) => {
        if (a) this.selectedProd = a.produtoId;
      });
    }
  }

  ngOnDestroy(): void {
    if (this._stepTimer) clearInterval(this._stepTimer);
  }

  analysis() {
    return this.analiseSvc.get(this.licitacao.id);
  }

  produtoFor(id: string): Produto | undefined {
    return this.produtos().find((p: Produto) => p.id === id);
  }

  start(): void {
    if (!this.selectedProd || !this.editalId) return;
    this.running.set(true);
    this.step.set(0);
    this.erro.set('');

    // Avança steps visualmente enquanto o backend calcula
    this._stepTimer = setInterval(() => {
      this.step.update((s: number) => Math.min(s + 1, PIPELINE_STEPS.length - 1));
    }, 500);

    this.analiseSvc.analisar(
      this.editalId,
      this.selectedProd,
      this.licitacao.id,
      this.quantidade ? Number(this.quantidade) : undefined
    ).subscribe({
      next: () => {
        clearInterval(this._stepTimer);
        this.step.set(PIPELINE_STEPS.length);
        this.running.set(false);
      },
      error: (e: import('@angular/common/http').HttpErrorResponse) => {
        clearInterval(this._stepTimer);
        const msg = e.error?.detail
          ?? (e.status === 422 ? 'Este edital não tem valor estimado — informe o valor do item ou lote para calcular a viabilidade.' : 'Erro ao calcular viabilidade.');
        this.erro.set(msg);
        this.running.set(false);
      },
    });
  }

  reset(): void {
    this.analiseSvc.clear(this.licitacao.id);
  }

  verdictLabel(v: 'green' | 'amber' | 'red'): string {
    return v === 'green' ? 'Vale a pena' : v === 'amber' ? 'Atenção' : 'Não recomendado';
  }
}
