import {
  Component, ChangeDetectionStrategy, Input, inject,
  signal, ViewChild, ElementRef, AfterViewChecked, OnChanges, SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { Licitacao } from '../../core/models/licitacao.model';
import { EditalService } from '../../core/services/edital.service';

interface ChatMessage {
  role: 'user' | 'bot';
  text: string;
  citation?: string;
}

@Component({
  selector: 'lv-chat-tab',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="chat">

      <!-- Mensagens -->
      <div class="chat__messages" #msgs>
        <div *ngFor="let m of messages(); trackBy: trackMsg" class="msg" [ngClass]="m.role">
          <div>{{ m.text }}</div>
          <div *ngIf="m.citation" class="citation">↳ {{ m.citation }}</div>
        </div>

        <!-- Indicador de digitação -->
        <div *ngIf="typing()" class="msg bot" style="display: flex; gap: 4px; align-items: center;">
          <span class="chat-dot"></span>
          <span class="chat-dot" style="animation-delay: 0.15s;"></span>
          <span class="chat-dot" style="animation-delay: 0.3s;"></span>
        </div>
      </div>

      <!-- Perguntas sugeridas -->
      <div *ngIf="editalId && messages().length <= 1" class="chat__suggested">
        <button *ngFor="let q of suggestedQuestions" type="button" (click)="send(q)">
          {{ q }}
        </button>
      </div>

      <!-- Aviso quando edital ainda não processado -->
      <div *ngIf="!editalId" style="padding: 10px 14px; background: var(--surface-2); border-top: 1px solid var(--border); font-size: 12.5px; color: var(--ink-3); display: flex; align-items: center; gap: 8px;">
        <i class="pi pi-info-circle"></i>
        O chat estará disponível após o processamento do edital na aba <strong style="margin: 0 4px;">Resumo IA</strong>.
      </div>

      <!-- Composição -->
      <div class="chat__compose">
        <textarea
          [(ngModel)]="input"
          placeholder="Pergunte algo sobre este edital..."
          [disabled]="!editalId"
          (keydown.enter)="onEnter($event)">
        </textarea>
        <button pButton type="button" label="Enviar" icon="pi pi-send" iconPos="right"
                (click)="send(input)"
                [disabled]="!input.trim() || !editalId || typing()">
        </button>
      </div>

    </div>
  `,
})
export class ChatTabComponent implements AfterViewChecked, OnChanges {
  private readonly editalSvc = inject(EditalService);

  @Input({ required: true }) licitacao!: Licitacao;
  @Input() editalId: string | null = null;

  @ViewChild('msgs') msgsRef!: ElementRef<HTMLDivElement>;

  readonly suggestedQuestions = [
    'Qual o prazo de entrega ou execução?',
    'Quais os requisitos de habilitação técnica?',
    'Quais são as multas ou penalidades por descumprimento?',
    'Como funciona o reajuste de preços?',
    'Quais os documentos exigidos para a proposta?'
  ];

  readonly messages = signal<ChatMessage[]>([
    {
      role: 'bot',
      text: 'Olá! Sou a assistente do LiciteView para este edital. Faça perguntas sobre obrigações, prazos, habilitação e penalidades — as respostas são geradas a partir do PDF do edital via RAG.',
    },
  ]);
  readonly typing = signal(false);
  input = '';

  private _historicoCarregado = false;

  // Carrega as perguntas já feitas quando o id do edital fica disponível,
  // para a conversa não sumir ao recarregar a página.
  ngOnChanges(changes: SimpleChanges): void {
    if (!changes['editalId'] || !this.editalId || this._historicoCarregado) return;
    this._historicoCarregado = true;
    this.editalSvc.historicoPerguntas(this.editalId).subscribe((perguntas) => {
      const anteriores: ChatMessage[] = perguntas.flatMap((p) => [
        { role: 'user' as const, text: p.pergunta },
        { role: 'bot' as const, text: p.resposta ?? '', citation: p.pagina_fonte ? `A partir da página ${p.pagina_fonte} do edital` : p.trecho_fonte ? 'Trecho do edital' : undefined },
      ]);
      if (anteriores.length) {
        // Mantém a saudação, depois o histórico, depois o que já foi enviado nesta sessão
        this.messages.update((m) => [m[0], ...anteriores, ...m.slice(1)]);
      }
    });
  }

  ngAfterViewChecked(): void {
    if (this.msgsRef) {
      this.msgsRef.nativeElement.scrollTop = this.msgsRef.nativeElement.scrollHeight;
    }
  }

  trackMsg(_: number, m: ChatMessage): string {
    return m.role + m.text;
  }

  onEnter(e: Event): void {
    const ke = e as KeyboardEvent;
    if (!ke.shiftKey) {
      ke.preventDefault();
      this.send(this.input);
    }
  }

  send(text: string): void {
    if (!text.trim() || !this.editalId || this.typing()) return;

    this.messages.update((m) => [...m, { role: 'user', text }]);
    this.input = '';
    this.typing.set(true);

    this.editalSvc.perguntar(this.editalId, text).subscribe({
      next: (res) => {
        const fim = res.pagina_fonte_final;
        const origem = !res.pagina_fonte ? 'Trecho do edital'
          : fim && fim !== res.pagina_fonte ? `Páginas ${res.pagina_fonte}–${fim} do edital`
          : `Página ${res.pagina_fonte} do edital`;
        const citation = res.trecho_fonte
          ? `${origem} · ${res.chunks_utilizados} trecho(s) consultado(s)`
          : `${res.chunks_utilizados} trecho(s) consultado(s)`;

        this.messages.update((m) => [
          ...m,
          { role: 'bot', text: res.resposta, citation },
        ]);
        this.typing.set(false);
      },
      error: (e: { error?: { detail?: unknown } }) => {
        const detalhe = typeof e?.error?.detail === 'string' ? e.error.detail : null;
        this.messages.update((m) => [
          ...m,
          {
            role: 'bot',
            text: detalhe ?? 'Não foi possível obter resposta. Verifique se o edital foi processado e tente novamente.',
          },
        ]);
        this.typing.set(false);
      },
    });
  }
}
