import { Component, ChangeDetectionStrategy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { DropdownModule } from 'primeng/dropdown';
import { RadioButtonModule } from 'primeng/radiobutton';
import { ChipModule } from 'primeng/chip';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { SelectButtonModule } from 'primeng/selectbutton';
import { LicitacaoService, SearchResult } from '../../core/services/licitacao.service';
import { AnaliseService } from '../../core/services/analise.service';
import { EditalService } from '../../core/services/edital.service';
import { Licitacao, SearchFilters } from '../../core/models/licitacao.model';

interface ViewOption { label: string; value: 'cards' | 'table' }

@Component({
  selector: 'lv-pesquisa',
  standalone: true,
  imports: [
    CommonModule, FormsModule, ButtonModule, InputTextModule, DropdownModule,
    RadioButtonModule, ChipModule, TableModule, TagModule, SelectButtonModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page-h">
      <div>
        <h1>Pesquisar Licitações</h1>
        <p>Editais publicados no PNCP — Portal Nacional de Contratações Públicas.</p>
      </div>
    </div>

    <!-- Filters -->
    <div class="card" style="margin-bottom: 20px;">
      <div class="card__body">
        <!-- Keyword + Status row -->
        <div class="filters-grid--keyword">
          <div class="field">
            <label class="field__label">Palavra-chave</label>
            <input pInputText placeholder="Digite um termo para pesquisar" [(ngModel)]="filters.keyword" />
          </div>
          <div class="field">
            <label class="field__label">Status</label>
            <div class="status-radios">
              <div class="p-field-radiobutton"><p-radioButton name="status" value="recebendo" [(ngModel)]="filters.status" inputId="s1"></p-radioButton><label for="s1">A Receber/Recebendo Proposta</label></div>
              <div class="p-field-radiobutton"><p-radioButton name="status" value="julgamento" [(ngModel)]="filters.status" inputId="s2"></p-radioButton><label for="s2">Em Julgamento/Propostas Encerradas</label></div>
              <div class="p-field-radiobutton"><p-radioButton name="status" value="encerradas" [(ngModel)]="filters.status" inputId="s3"></p-radioButton><label for="s3">Encerradas</label></div>
              <div class="p-field-radiobutton"><p-radioButton name="status" value="todos" [(ngModel)]="filters.status" inputId="s4"></p-radioButton><label for="s4">Todos</label></div>
            </div>
          </div>
        </div>

        <!-- Filter header -->
        <div class="filters-section-h">
          <h3 (click)="filtersOpen.set(!filtersOpen())" style="cursor: pointer;">
            <i class="pi pi-filter"></i> Filtros
            <span style="display: inline-block; transition: transform 0.2s;" [style.transform]="filtersOpen() ? 'rotate(0)' : 'rotate(-90deg)'">▾</span>
          </h3>
          <i class="pi pi-info-circle" title="Filtros do PNCP" style="color: var(--ink-3);"></i>
        </div>

        @if (filtersOpen()) {
          <div class="filters-grid">
            <div class="field"><label class="field__label">Tipos de Instrumento Convocatório</label><p-dropdown [options]="opt.instrumento" [(ngModel)]="filters.instrumento" [showClear]="true" placeholder="Selecione" appendTo="body"></p-dropdown></div>
            <div class="field"><label class="field__label">Modalidades da Contratação</label><p-dropdown [options]="opt.modalidade" [(ngModel)]="filters.modalidade" [showClear]="true" placeholder="Selecione" appendTo="body" [filter]="true"></p-dropdown></div>
            <div class="field"><label class="field__label">Órgãos</label><p-dropdown [options]="opt.orgao" [(ngModel)]="filters.orgao" [showClear]="true" placeholder="Selecione" appendTo="body" [filter]="true"></p-dropdown></div>
            <div class="field"><label class="field__label">Unidades</label><p-dropdown [options]="opt.unidade" [(ngModel)]="filters.unidade" [showClear]="true" placeholder="Selecione" appendTo="body" [filter]="true"></p-dropdown></div>
            <div class="field"><label class="field__label">UFs</label><p-dropdown [options]="opt.uf" [(ngModel)]="filters.uf" [showClear]="true" placeholder="Selecione" appendTo="body" [filter]="true"></p-dropdown></div>
            <div class="field"><label class="field__label">Municípios</label><p-dropdown [options]="opt.municipio" [(ngModel)]="filters.municipio" [showClear]="true" placeholder="Selecione" appendTo="body" [filter]="true"></p-dropdown></div>
            <div class="field"><label class="field__label">Esferas</label><p-dropdown [options]="opt.esfera" [(ngModel)]="filters.esfera" [showClear]="true" placeholder="Selecione" appendTo="body"></p-dropdown></div>
            <div class="field"><label class="field__label">Poderes</label><p-dropdown [options]="opt.poder" [(ngModel)]="filters.poder" [showClear]="true" placeholder="Selecione" appendTo="body"></p-dropdown></div>
            <div class="field"><label class="field__label">Fontes Orçamentárias</label><p-dropdown [options]="opt.fonteOrcam" [(ngModel)]="filters.fonteOrcam" [showClear]="true" placeholder="Selecione" appendTo="body"></p-dropdown></div>
            <div class="field"><label class="field__label">Tipos de Margens de Preferência</label><p-dropdown [options]="opt.margemPref" [(ngModel)]="filters.margemPref" [showClear]="true" placeholder="Selecione" appendTo="body"></p-dropdown></div>
            <div class="field"><label class="field__label">Exigência de Conteúdo Nacional</label><p-dropdown [options]="opt.conteudoNac" [(ngModel)]="filters.conteudoNac" [showClear]="true" placeholder="Selecione" appendTo="body"></p-dropdown></div>
            <div class="field"><label class="field__label">Emenda Parlamentar</label><p-dropdown [options]="opt.emendaParl" [(ngModel)]="filters.emendaParl" [showClear]="true" placeholder="Selecione" appendTo="body"></p-dropdown></div>
          </div>
        }

        @if (activeChips().length > 0) {
          <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--border);">
            <span style="font-size: 11.5px; color: var(--ink-3); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 4px; align-self: center;">Filtros ativos:</span>
            @for (chip of activeChips(); track chip.key) {
              <span class="filter-chip">{{ chip.value }} <button (click)="clearFilter(chip.key)" title="Remover"><i class="pi pi-times" style="font-size: 10px;"></i></button></span>
            }
          </div>
        }

        <div class="search-actions">
          <button pButton type="button" label="Limpar" icon="pi pi-times" class="p-button-outlined" (click)="clearAll()"></button>
          <button pButton type="button" label="Pesquisar" icon="pi pi-search" (click)="doSearch()"></button>
        </div>
      </div>
    </div>

    <!-- Results -->
    @if (hasSearched()) {
      <div class="results-toolbar">
        <div class="count"><strong>{{ total() }}</strong> {{ total() === 1 ? 'licitação encontrada' : 'licitações encontradas' }}</div>
        <div style="display: flex; gap: 12px; align-items: center;">
          <p-selectButton [options]="viewOptions" [(ngModel)]="layoutValue" optionLabel="label" optionValue="value"></p-selectButton>
        </div>
      </div>

      @if (results().length === 0) {
        <div class="card"><div class="empty">Nenhuma licitação encontrada com os filtros aplicados.</div></div>
      } @else if (layoutValue === 'cards') {
        <div style="display: flex; flex-direction: column; gap: 12px;">
          @for (l of results(); track l.id) {
            <div class="licit-card" (click)="open(l)">
              <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                  <span class="mono" style="font-size: 11px; color: var(--ink-3); font-weight: 600;">{{ l.id }}</span>
                  <span class="badge badge--navy">{{ l.modalidade }}</span>
                </div>
                <h3 class="licit-card__title">{{ l.titulo }}</h3>
                <div class="licit-card__meta">
                  <span><strong>{{ l.orgao }}</strong></span>
                  <span><i class="pi pi-map-marker" style="font-size: 11px;"></i> {{ l.municipio }}/{{ l.uf }}</span>
                </div>
                <div class="licit-card__tags">
                  <span class="badge">{{ l.esfera }}</span>
                  <span class="badge">{{ l.poder }}</span>
                  @if (analyses()[l.id]; as a) {
                    <span class="badge" [ngClass]="'badge--' + a.verdict">
                      <span class="dot" [ngClass]="'dot--' + a.verdict"></span>
                      {{ verdictLabel(a.verdict) }} · {{ a.score }}
                    </span>
                  } @else {
                    <span class="badge" style="background: transparent; border-style: dashed; color: var(--ink-3);">
                      <i class="pi pi-sparkles" style="font-size: 11px;"></i> Não analisado
                    </span>
                  }
                </div>
              </div>
              <div class="licit-card__right">
                <div *ngIf="l.valor">
                  <div style="font-size: 11px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Valor estimado</div>
                  <div class="licit-card__value">{{ l.valor | currency:'BRL':'symbol':'1.0-0':'pt-BR' }}</div>
                </div>
                <div class="licit-card__deadline">
                  Encerra em <strong>{{ l.encerramento | date:'dd/MM/yyyy' }}</strong>
                  @if (l.diasRestantes > 0) {
                    <div style="margin-top: 2px;">
                      <span class="badge" [ngClass]="l.diasRestantes <= 3 ? 'badge--red' : l.diasRestantes <= 7 ? 'badge--amber' : 'badge--cyan'">
                        D-{{ l.diasRestantes }}
                      </span>
                    </div>
                  }
                </div>
              </div>
            </div>
          }
        </div>
      } @else {
        <div class="card">
          <p-table [value]="results()" (onRowSelect)="open($event.data)" selectionMode="single" [scrollable]="true">
            <ng-template pTemplate="header">
              <tr>
                <th style="width: 110px;">ID</th>
                <th>Objeto</th>
                <th>Órgão</th>
                <th>UF</th>
                <th>Modalidade</th>
                <th style="text-align: right;">Valor</th>
                <th>Encerramento</th>
                <th>Viabilidade</th>
              </tr>
            </ng-template>
            <ng-template pTemplate="body" let-l>
              <tr [pSelectableRow]="l">
                <td class="mono" style="font-size: 12px;">{{ l.id }}</td>
                <td style="max-width: 380px;"><div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500;">{{ l.titulo }}</div></td>
                <td style="max-width: 200px;"><div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12.5px;">{{ l.orgao }}</div></td>
                <td>{{ l.uf }}</td>
                <td><span class="badge badge--navy">{{ l.modalidade }}</span></td>
                <td class="mono" style="text-align: right; font-weight: 600;">
                  {{ l.valor ? (l.valor | currency:'BRL':'symbol':'1.0-0':'pt-BR') : '—' }}
                </td>
                <td class="mono" style="font-size: 12px;">{{ l.encerramento | date:'dd/MM/yyyy' }}</td>
                <td>
                  @if (analyses()[l.id]; as a) {
                    <span class="badge" [ngClass]="'badge--' + a.verdict">
                      <span class="dot" [ngClass]="'dot--' + a.verdict"></span> {{ a.score }}
                    </span>
                  } @else {
                    <span style="font-size: 12px; color: var(--ink-3);">—</span>
                  }
                </td>
              </tr>
            </ng-template>
          </p-table>
        </div>
      }

      @if (totalPaginas() > 1) {
        <div style="margin-top: 20px; display: flex; justify-content: center; align-items: center; gap: 16px;">
          <button pButton type="button" icon="pi pi-chevron-left" class="p-button-outlined p-button-sm"
                  [disabled]="pagina() === 1" (click)="irPagina(pagina() - 1)"></button>
          <span style="font-size: 13px; color: var(--ink-2);">
            Página <strong>{{ pagina() }}</strong> de <strong>{{ totalPaginas() }}</strong>
          </span>
          <button pButton type="button" icon="pi pi-chevron-right" class="p-button-outlined p-button-sm"
                  [disabled]="pagina() >= totalPaginas()" (click)="irPagina(pagina() + 1)"></button>
        </div>
      }
    } @else {
      <div class="card">
        <div class="empty">
          <i class="pi pi-search" style="font-size: 28px;"></i>
          <div style="margin-top: 8px; font-weight: 600; color: var(--ink-2);">Configure seus filtros e clique em Pesquisar</div>
        </div>
      </div>
    }
  `,
})
export class PesquisaComponent {
  private readonly svc = inject(LicitacaoService);
  private readonly analise = inject(AnaliseService);
  private readonly editalSvc = inject(EditalService);
  private readonly router = inject(Router);

  readonly opt = this.svc.filtroOpcoes;
  readonly viewOptions: ViewOption[] = [{ label: 'Cards', value: 'cards' }, { label: 'Tabela', value: 'table' }];

  layoutValue: 'cards' | 'table' = 'cards';
  filters: SearchFilters = { status: 'recebendo' };

  readonly TAM_PAGINA = 20;

  readonly filtersOpen  = signal(false);
  readonly hasSearched  = signal(false);
  readonly results      = signal<Licitacao[]>([]);
  readonly total        = signal(0);
  readonly pagina       = signal(1);
  readonly analyses     = this.analise.analises;

  readonly totalPaginas = computed(() => Math.ceil(this.total() / this.TAM_PAGINA) || 1);

  readonly activeChips = computed(() => {
    const keys: Array<keyof SearchFilters> = ['instrumento','modalidade','orgao','unidade','uf','municipio','esfera','poder','fonteOrcam','margemPref','conteudoNac','emendaParl'];
    return keys
      .filter((k) => !!this.filters[k])
      .map((k) => ({ key: k, value: this.filters[k] as string }));
  });

  doSearch(resetPagina = true): void {
    if (resetPagina) this.pagina.set(1);
    this.hasSearched.set(true);
    this.svc.search(this.filters, this.pagina(), this.TAM_PAGINA).subscribe((r: SearchResult) => {
      this.results.set(r.items);
      this.total.set(r.total);
    });
  }

  irPagina(p: number): void {
    this.pagina.set(p);
    this.doSearch(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  clearAll(): void {
    this.filters = { status: 'recebendo' };
  }

  clearFilter(key: keyof SearchFilters): void {
    this.filters = { ...this.filters, [key]: undefined };
  }

  open(l: Licitacao): void {
    // Dispara o processamento em segundo plano imediatamente para garantir a inserção no histórico
    this.editalSvc.processar({
      id_pncp:        l.id,
      titulo:         l.titulo,
      orgao:          l.orgao,
      objeto:         l.titulo,
      modalidade:     l.modalidade,
      valor_estimado: l.valor ?? undefined,
      url_origem:     l.url_origem ?? undefined,
      data_abertura:  l.abertura ? l.abertura.split('T')[0] : undefined,
    }).subscribe();

    this.router.navigate(['/edital', l.id]);
  }

  verdictLabel(v: 'green' | 'amber' | 'red'): string {
    return v === 'green' ? 'Vale a pena' : v === 'amber' ? 'Atenção' : 'Não recomendado';
  }
}
