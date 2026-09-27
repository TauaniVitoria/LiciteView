import { Component, ChangeDetectionStrategy, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Licitacao, ResumoEdital } from '../../core/models/licitacao.model';

@Component({
  selector: 'lv-resumo-tab',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="resumo-banner" style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding: 10px 14px; background: var(--cyan-50); border: 1px solid rgba(22,168,221,0.2); border-radius: var(--r-md); color: var(--cyan-600); font-size: 12.5px;">
      <i class="pi pi-sparkles"></i>
      <span>Resumo gerado por IA · pipeline: PyMuPDF → Chunking → Qdrant → Groq LLM</span>
    </div>

    <div class="sum-grid">
      <!-- Coluna esquerda -->
      <div>

        <!-- Bloco 1 — Visão Geral -->
        <div class="sum-block">
          <h4><i class="pi pi-file"></i> Visão geral</h4>
          <dl class="kv">
            <dt>Objeto</dt><dd>{{ b1.objeto ?? '—' }}</dd>
            <dt>Órgão</dt><dd>{{ b1.orgao ?? licitacao.orgao }}</dd>
            <dt>Modalidade</dt><dd>{{ b1.modalidade ?? licitacao.modalidade }}</dd>
            <dt>Critério de julgamento</dt><dd>{{ b1.criterio_julgamento ?? '—' }}</dd>
            <dt>Número do edital</dt><dd class="mono">{{ b1.numero_edital ?? '—' }}</dd>
          </dl>
        </div>

        <!-- Bloco 2 — Prazos -->
        <div class="sum-block">
          <h4><i class="pi pi-calendar"></i> Prazos e execução</h4>
          <dl class="kv">
            <dt>Prazo de entrega</dt>
            <dd>{{ b2.prazo_entrega || '—' }}</dd>
            <dt>Vigência do contrato</dt>
            <dd>{{ b2.vigencia_contrato || '—' }}</dd>
            <dt>Local de entrega</dt>
            <dd>{{ b2.local_entrega || '—' }}</dd>
            <dt>Data de abertura</dt>
            <dd>{{ b2.data_abertura || (licitacao.abertura ? (licitacao.abertura | date:'dd/MM/yyyy HH:mm') : '—') }}</dd>
            <dt>Encerramento</dt>
            <dd>{{ licitacao.encerramento ? (licitacao.encerramento | date:'dd/MM/yyyy HH:mm') : '—' }}</dd>
          </dl>
        </div>

        <!-- Bloco 4 — Requisitos Técnicos -->
        <div class="sum-block">
          <h4><i class="pi pi-cog"></i> Requisitos técnicos</h4>
          <p *ngIf="b4.especificacoes_resumo">{{ b4.especificacoes_resumo }}</p>
          <div *ngIf="b4.certificacoes_exigidas?.length" style="margin-bottom: 8px;">
            <div style="font-size: 12px; font-weight: 600; color: var(--ink-3); margin-bottom: 4px;">Certificações</div>
            <ul><li *ngFor="let c of arr(b4.certificacoes_exigidas)">{{ c }}</li></ul>
          </div>
          <div *ngIf="b4.exige_amostra != null" style="font-size: 13px; color: var(--ink-2);">
            <i class="pi" [ngClass]="b4.exige_amostra ? 'pi-check-circle' : 'pi-times-circle'"
               [style.color]="b4.exige_amostra ? 'var(--green)' : 'var(--ink-3)'"></i>
            {{ b4.exige_amostra ? 'Exige amostra' : 'Não exige amostra' }}
          </div>
          <ul *ngIf="b4.outros_requisitos?.length" style="margin-top: 8px;">
            <li *ngFor="let r of b4.outros_requisitos">{{ r }}</li>
          </ul>
        </div>

      </div>

      <!-- Coluna direita -->
      <div>

        <!-- Bloco 3 — Documentação -->
        <div class="sum-block">
          <h4><i class="pi pi-check"></i> Documentação exigida</h4>
          <div *ngIf="arr(b3.documentos_habilitacao).length">
            <div style="font-size: 12px; font-weight: 600; color: var(--ink-3); margin-bottom: 4px;">Habilitação</div>
            <ul><li *ngFor="let d of arr(b3.documentos_habilitacao)">{{ d }}</li></ul>
          </div>
          <div *ngIf="arr(b3.regularidade_fiscal).length" style="margin-top: 10px;">
            <div style="font-size: 12px; font-weight: 600; color: var(--ink-3); margin-bottom: 4px;">Regularidade Fiscal</div>
            <ul><li *ngFor="let d of arr(b3.regularidade_fiscal)">{{ d }}</li></ul>
          </div>
          <div *ngIf="arr(b3.qualificacao_tecnica).length" style="margin-top: 10px;">
            <div style="font-size: 12px; font-weight: 600; color: var(--ink-3); margin-bottom: 4px;">Qualificação Técnica</div>
            <ul><li *ngFor="let d of arr(b3.qualificacao_tecnica)">{{ d }}</li></ul>
          </div>
        </div>

        <!-- Bloco 5 — Riscos -->
        <div class="sum-block">
          <h4><i class="pi pi-bell"></i> Riscos e penalidades</h4>
          <div *ngIf="b5.multas?.length">
            <div style="font-size: 12px; font-weight: 600; color: var(--red); margin-bottom: 4px;">Multas</div>
            <ul><li *ngFor="let m of arr(b5.multas)" style="color: var(--ink-2);">{{ m }}</li></ul>
          </div>
          <div *ngIf="b5.sancoes?.length" style="margin-top: 8px;">
            <div style="font-size: 12px; font-weight: 600; color: var(--amber); margin-bottom: 4px;">Sanções</div>
            <ul><li *ngFor="let s of arr(b5.sancoes)" style="color: var(--ink-2);">{{ s }}</li></ul>
          </div>
          <div *ngIf="b5.pontos_atencao?.length" style="margin-top: 8px;">
            <div style="font-size: 12px; font-weight: 600; color: var(--ink-3); margin-bottom: 4px;">Pontos de atenção</div>
            <ul><li *ngFor="let p of arr(b5.pontos_atencao)" style="color: var(--ink-2);">{{ p }}</li></ul>
          </div>
        </div>

        <!-- Metadados da licitação -->
        <div class="sum-block" style="background: linear-gradient(150deg, rgba(22,168,221,0.07), rgba(44,62,90,0.05)); border-color: rgba(22,168,221,0.2);">
          <h4><i class="pi pi-info-circle"></i> Dados da licitação</h4>
          <dl class="kv">
            <dt>Valor estimado</dt>
            <dd class="mono">{{ licitacao.valor | currency:'BRL':'symbol':'1.0-0':'pt-BR' }}</dd>
            <dt>Encerramento</dt>
            <dd class="mono">{{ licitacao.encerramento | date:'dd/MM/yyyy HH:mm' }}</dd>
            <dt>Local</dt>
            <dd>{{ licitacao.municipio }}/{{ licitacao.uf }}</dd>
          </dl>
        </div>

      </div>
    </div>
  `,
})
export class ResumoTabComponent {
  @Input({ required: true }) licitacao!: Licitacao;
  @Input({ required: true }) resumo!: ResumoEdital;

  get b1() { return this.resumo.bloco1_visao_geral; }
  get b2() { return this.resumo.bloco2_prazos; }
  get b3() { return this.resumo.bloco3_documentacao; }
  get b4() { return this.resumo.bloco4_requisitos_tecnicos; }
  get b5() { return this.resumo.bloco5_riscos; }

  // Normaliza itens de lista — o LLM às vezes retorna objetos em vez de strings
  str(val: unknown): string {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val.trim();
    if (typeof val === 'object') {
      // Pega o primeiro valor string não-nulo do objeto
      // Ex: {"valor":null,"descricao":"Multa"} → "Multa"
      const strings = Object.values(val as Record<string, unknown>)
        .filter(v => v !== null && v !== undefined && typeof v === 'string' && (v as string).trim());
      if (strings.length > 0) return strings[0] as string;
      // Fallback: concatena todos os valores não-nulos
      const nonNull = Object.values(val as Record<string, unknown>)
        .filter(v => v !== null && v !== undefined)
        .map(v => String(v).trim())
        .filter(Boolean);
      return nonNull.join(' — ') || '';
    }
    return String(val).trim();
  }

  arr(list: unknown[]): string[] {
    return (list ?? []).map((v) => this.str(v)).filter(Boolean);
  }
}
