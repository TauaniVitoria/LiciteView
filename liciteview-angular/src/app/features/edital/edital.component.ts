import {
  Component, ChangeDetectionStrategy, inject, signal, OnInit, OnDestroy, Input,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { TabViewModule } from 'primeng/tabview';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { Subscription } from 'rxjs';

import { LicitacaoService } from '../../core/services/licitacao.service';
import { EditalService } from '../../core/services/edital.service';
import { AnaliseService } from '../../core/services/analise.service';
import { Licitacao, ResumoEdital } from '../../core/models/licitacao.model';
import { ResumoTabComponent } from './resumo-tab.component';
import { ViabilidadeTabComponent } from './viabilidade-tab.component';
import { ChatTabComponent } from './chat-tab.component';

const STEPS = [
  { label: 'Baixando PDF do edital' },
  { label: 'Extraindo texto' },
  { label: 'Dividindo em chunks semânticos' },
  { label: 'Gerando embeddings e indexando no Qdrant' },
  { label: 'Gerando resumo em 5 blocos via LLM' },
];

@Component({
  selector: 'lv-edital',
  standalone: true,
  imports: [
    CommonModule, TabViewModule, ButtonModule, ProgressSpinnerModule,
    ResumoTabComponent, ViabilidadeTabComponent, ChatTabComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button pButton type="button" label="Voltar para resultados" icon="pi pi-arrow-left"
            class="p-button-text p-button-sm" (click)="back()" style="margin-bottom: 12px;"></button>

    <ng-container *ngIf="licitacao() as l">
      <div class="edital-h">
        <div>
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span class="mono" style="font-size: 12px; color: var(--ink-3); font-weight: 600;">{{ l.id }}</span>
            <span class="badge badge--navy">{{ l.modalidade }}</span>
            <span class="badge badge--cyan">{{ l.status }}</span>
          </div>
          <h1>{{ l.titulo }}</h1>
          <div class="edital-h__meta">
            <span><strong>{{ l.orgao }}</strong></span>
            <span>{{ l.unidade }}</span>
            <span><i class="pi pi-map-marker"></i> {{ l.municipio }}/{{ l.uf }}</span>
            <span><i class="pi pi-calendar"></i> Encerra em {{ l.encerramento | date:'dd/MM/yyyy HH:mm' }}</span>
          </div>
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
          <div style="display: flex; gap: 6px;">
            <a *ngIf="urlPdf()" [href]="urlPdf()!" target="_blank" rel="noopener" download
               pButton type="button" label="Baixar PDF" icon="pi pi-download"
               class="p-button-outlined p-button-sm"></a>
            <a *ngIf="!urlPdf() && l.url_origem" [href]="'https://pncp.gov.br' + (l.url_origem.startsWith('http') ? '' : '') + l.url_origem" target="_blank" rel="noopener"
               pButton type="button" label="Ver no PNCP" icon="pi pi-external-link"
               class="p-button-outlined p-button-sm"></a>
          </div>
          <div style="text-align: right;">
            <!-- <div style="font-size: 11px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Valor estimado</div> -->
            <div class="mono" style="font-size: 22px; font-weight: 700; color: var(--ink);">{{ l.valor | currency:'BRL':'symbol':'1.0-0':'pt-BR' }}</div>
          </div>
        </div>
      </div>

      <p-tabView [(activeIndex)]="activeTab">

        <!-- Aba Resumo IA -->
        <p-tabPanel header="Resumo IA" leftIcon="pi pi-sparkles">

          <!-- Carregando (estado inicial enquanto processar() está em voo) -->
          <ng-container *ngIf="carregando() && !processando() && !erro() && !resumo()">
            <div style="padding: 48px 32px; text-align: center;">
              <p-progressSpinner styleClass="w-3rem h-3rem" strokeWidth="3" animationDuration=".9s"></p-progressSpinner>
              <p style="margin-top: 16px; font-size: 13px; color: var(--ink-3);">Verificando status do edital...</p>
            </div>
          </ng-container>

          <!-- Processando -->
          <ng-container *ngIf="processando()">
            <div class="card" style="padding: 0;">
              <div style="padding: 48px 32px; max-width: 520px; margin: 0 auto; text-align: center;">
                <p-progressSpinner styleClass="w-3rem h-3rem" strokeWidth="3" animationDuration=".9s"></p-progressSpinner>
                <h2 style="font-size: 16px; font-weight: 700; margin: 16px 0 4px; color: var(--ink);">Processando edital</h2>
                <p style="font-size: 12.5px; color: var(--ink-3); margin: 0 0 4px;">Pipeline IA em execução em segundo plano.</p>
                <p style="font-size: 12px; color: var(--green); margin: 0 0 24px; display: flex; align-items: center; gap: 6px; justify-content: center;">
                  <i class="pi pi-check-circle"></i> Você pode navegar livremente · notificaremos quando terminar
                </p>
                <ol style="list-style: none; padding: 0; margin: 0; text-align: left;">
                  <li *ngFor="let s of steps; let i = index"
                      style="display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border);"
                      [style.opacity]="i <= stepAtual() ? 1 : 0.4">
                    <span style="width: 18px; height: 18px; border-radius: 50%; border: 1px solid; display: flex; align-items: center; justify-content: center; color: white; flex-shrink: 0; font-size: 10px;"
                          [style.background]="i < stepAtual() ? 'var(--green)' : i === stepAtual() ? 'var(--cyan)' : 'var(--surface-2)'"
                          [style.borderColor]="i < stepAtual() ? 'var(--green)' : i === stepAtual() ? 'var(--cyan)' : 'var(--border-strong)'">
                      <i *ngIf="i < stepAtual()" class="pi pi-check" style="font-size: 10px;"></i>
                      <span *ngIf="i === stepAtual()" style="width: 6px; height: 6px; background: white; border-radius: 50%;"></span>
                    </span>
                    <span style="font-size: 13px;"
                          [style.color]="i === stepAtual() ? 'var(--ink)' : 'var(--ink-3)'"
                          [style.fontWeight]="i === stepAtual() ? 600 : 400">
                      {{ s.label }}
                    </span>
                  </li>
                </ol>
              </div>
            </div>
          </ng-container>

          <!-- Erro -->
          <ng-container *ngIf="erro()">
            <div class="card" style="padding: 24px;">
              <div style="display: flex; align-items: center; gap: 12px; color: var(--red);">
                <i class="pi pi-exclamation-triangle" style="font-size: 24px;"></i>
                <div>
                  <div style="font-weight: 700; margin-bottom: 4px;">Falha no processamento</div>
                  <div style="font-size: 13px; color: var(--ink-3);">{{ erro() }}</div>
                </div>
              </div>
              <button pButton type="button" label="Tentar novamente" icon="pi pi-refresh"
                      class="p-button-outlined" style="margin-top: 16px;" (click)="iniciarProcessamento(l)"></button>
            </div>
          </ng-container>

          <!-- Resumo pronto -->
          <ng-container *ngIf="resumo() && !processando()">
            <lv-resumo-tab [licitacao]="l" [resumo]="resumo()!"></lv-resumo-tab>
          </ng-container>

        </p-tabPanel>

        <!-- Aba Viabilidade -->
        <p-tabPanel header="Viabilidade">
          <ng-template pTemplate="header">
            <ng-container *ngIf="analysisFor(l.id) as a; else semAnalise">
              <span class="dot" [ngClass]="'dot--' + a.verdict" style="margin-right: 6px;"></span>
            </ng-container>
            <ng-template #semAnalise>
              <i class="pi pi-chart-bar" style="margin-right: 6px;"></i>
            </ng-template>
            Viabilidade
          </ng-template>
          <lv-viabilidade-tab [licitacao]="l" [editalId]="editalId()"></lv-viabilidade-tab>
        </p-tabPanel>

        <!-- Aba Chat -->
        <p-tabPanel header="Chat do edital" leftIcon="pi pi-comments">
          <lv-chat-tab [licitacao]="l" [editalId]="editalId()"></lv-chat-tab>
        </p-tabPanel>

      </p-tabView>
    </ng-container>
  `,
})
export class EditalComponent implements OnInit, OnDestroy {
  private readonly licitacaoSvc = inject(LicitacaoService);
  private readonly editalSvc   = inject(EditalService);
  private readonly analise      = inject(AnaliseService);
  private readonly router       = inject(Router);

  @Input() id!: string;

  readonly steps     = STEPS;
  readonly licitacao   = signal<Licitacao | null>(null);
  readonly resumo      = signal<ResumoEdital | null>(null);
  readonly editalId    = signal<string | null>(null);
  readonly urlPdf      = signal<string | null>(null);
  readonly carregando  = signal(true);   // true até processar() retornar
  readonly processando = signal(false);
  readonly stepAtual   = signal(0);
  readonly erro        = signal('');

  activeTab = 0;
  private _pollSub?: Subscription;
  private _stepTimer?: ReturnType<typeof setInterval>;

  analysisFor(id: string) {
    return this.analise.get(id);
  }

  ngOnInit(): void {
    this.licitacaoSvc.byId(this.id).subscribe((l) => {
      if (l) {
        this.licitacao.set(l);
        this.iniciarProcessamento(l);
      } else {
        this.carregando.set(false);
        this.erro.set('Não foi possível carregar os dados desta licitação. Verifique se o identificador está correto ou se a API do PNCP está acessível.');
      }
    });
  }

  ngOnDestroy(): void {
    this._pollSub?.unsubscribe();
    if (this._stepTimer) clearInterval(this._stepTimer);
  }

  iniciarProcessamento(l: Licitacao): void {
    this._pollSub?.unsubscribe();
    this.erro.set('');

    this.editalSvc.processar({
      id_pncp:        l.id,
      titulo:         l.titulo,
      orgao:          l.orgao,
      objeto:         l.titulo,
      modalidade:     l.modalidade,
      valor_estimado: l.valor ?? undefined,
      url_origem:     l.url_origem ?? undefined,
      data_abertura:  l.abertura ? l.abertura.split('T')[0] : undefined,
    }).subscribe({
      next: (res) => {
        this.carregando.set(false);
        if (res.status === 'PROCESSADO') {
          this.editalId.set(res.edital_id);
          this._buscarResumo(res.edital_id);
        } else {
          this._iniciarPolling(res.edital_id);
        }
      },
      error: (e: import('@angular/common/http').HttpErrorResponse) => {
        this.carregando.set(false);
        if (e.status === 503) {
          this.erro.set('Redis não está rodando. Inicie o Redis e o worker Celery para processar editais.');
        } else if (e.status === 0) {
          this.erro.set('Backend inacessível. Verifique se o servidor FastAPI está rodando.');
        } else {
          this.erro.set(e.error?.detail ?? 'Erro ao iniciar processamento.');
        }
      },
    });
  }

  private _buscarResumo(editalId: string): void {
    this.editalSvc.getStatus(editalId).subscribe((s) => {
      if (s.resumo) this.resumo.set(s.resumo);
      if (s.url_pdf) this.urlPdf.set(s.url_pdf);
    });
  }

  private _iniciarPolling(editalId: string): void {
    this.processando.set(true);
    this.stepAtual.set(0);
    this._simularSteps();

    this._pollSub = this.editalSvc.poll(editalId).subscribe({
      next: (s) => {
        if (s.tempo_decorrido != null) {
          const estStep = Math.min(Math.floor(s.tempo_decorrido / 8), STEPS.length - 1);
          if (estStep > this.stepAtual()) {
            this.stepAtual.set(estStep);
          }
        }

        if (s.status === 'PROCESSADO' && s.resumo) {
          this.resumo.set(s.resumo);
          this.editalId.set(s.edital_id);
          if (s.url_pdf) this.urlPdf.set(s.url_pdf);
          this.processando.set(false);
          if (this._stepTimer) clearInterval(this._stepTimer);
        }
        if (s.status === 'ERRO') {
          this.erro.set(s.erro_mensagem ?? 'Erro desconhecido no processamento.');
          this.processando.set(false);
          if (this._stepTimer) clearInterval(this._stepTimer);
        }
      },
      error: () => {
        this.erro.set('Perda de conexão durante o processamento.');
        this.processando.set(false);
      },
    });
  }

  // Avança o step visual a cada ~8s para dar feedback enquanto aguarda
  private _simularSteps(): void {
    if (this._stepTimer) clearInterval(this._stepTimer);
    this._stepTimer = setInterval(() => {
      this.stepAtual.update((v) => Math.min(v + 1, STEPS.length - 1));
    }, 8000);
  }

  back(): void {
    this.router.navigateByUrl('/pesquisa');
  }
}
