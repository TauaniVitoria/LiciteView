import { Component, ChangeDetectionStrategy, inject, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { OverlayPanelModule } from 'primeng/overlaypanel';
import { BadgeModule } from 'primeng/badge';
import { OverlayPanel } from 'primeng/overlaypanel';
import { AuthService } from '../core/services/auth.service';
import { NotificacaoService } from '../core/services/notificacao.service';
import { Notificacao } from '../core/models/notificacao.model';

@Component({
  selector: 'lv-app-shell',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive, ButtonModule, OverlayPanelModule, BadgeModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="app">
      <aside class="sidebar">
        <div class="sidebar__brand">
          <img src="assets/logo-liciteview.png" alt="LiciteView" />
        </div>
        <nav class="sidebar__nav">
          <a class="nav-item" routerLink="/pesquisa" routerLinkActive="is-active">
            <i class="pi pi-search"></i>
            Pesquisar Licitações
          </a>
          <a class="nav-item" routerLink="/historico" routerLinkActive="is-active">
            <i class="pi pi-history"></i>
            Histórico
          </a>
          <a class="nav-item" routerLink="/produtos" routerLinkActive="is-active">
            <i class="pi pi-box"></i>
            Meus Produtos
          </a>
        </nav>
        <div class="sidebar__footer">
          <div style="font-size: 11px; color: var(--ink-3); margin-bottom: 2px;">Conectado a</div>
          <div style="font-size: 12px; font-weight: 600; color: var(--ink-2);">
            <span class="dot dot--green" style="margin-right: 6px;"></span>
            PNCP — API pública
          </div>
        </div>
      </aside>

      <header class="topbar">
        <div class="topbar__user">

          <!-- Bell com badge -->
          <div style="position: relative; display: inline-flex;">
            <button class="p-button p-button-text p-button-sm" pButton type="button"
                    icon="pi pi-bell" (click)="bellPanel.toggle($event)">
            </button>
            <span *ngIf="naoLidas() > 0"
                  style="position: absolute; top: 2px; right: 2px; background: var(--red); color: white; border-radius: 50%; width: 16px; height: 16px; font-size: 10px; font-weight: 700; display: flex; align-items: center; justify-content: center; pointer-events: none;">
              {{ naoLidas() > 9 ? '9+' : naoLidas() }}
            </span>
          </div>

          <!-- Painel de notificações -->
          <p-overlayPanel #bellPanel>
            <div style="width: 340px;">
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border);">
                <span style="font-weight: 700; font-size: 14px;">Notificações</span>
                <button *ngIf="naoLidas() > 0"
                        (click)="marcarTodas()"
                        style="font-size: 12px; color: var(--cyan-600); background: none; border: none; cursor: pointer; padding: 0;">
                  Marcar todas como lidas
                </button>
              </div>

              <div style="max-height: 380px; overflow-y: auto;">
                <ng-container *ngIf="notificacoes().length === 0">
                  <div style="padding: 32px; text-align: center; color: var(--ink-3); font-size: 13px;">
                    <i class="pi pi-bell" style="font-size: 24px; display: block; margin-bottom: 8px;"></i>
                    Nenhuma notificação
                  </div>
                </ng-container>

                <div *ngFor="let n of notificacoes()"
                     [style.background]="!n.lida ? 'var(--cyan-50)' : 'var(--surface)'"
                     style="padding: 12px 16px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background .15s;"
                     (click)="abrirNotificacao(n, bellPanel)">
                  <div style="display: flex; align-items: flex-start; gap: 10px;">
                    <i class="pi"
                       [ngClass]="n.tipo === 'EDITAL_PROCESSADO' ? 'pi-check-circle' : 'pi-exclamation-circle'"
                       [style.color]="n.tipo === 'EDITAL_PROCESSADO' ? 'var(--green)' : 'var(--red)'"
                       style="margin-top: 2px; flex-shrink: 0;"></i>
                    <div style="flex: 1; min-width: 0;">
                      <div style="font-size: 13px; font-weight: 500; color: var(--ink);">{{ n.titulo }}</div>
                      <div *ngIf="n.mensagem" style="font-size: 12px; color: var(--ink-3); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ n.mensagem }}</div>
                      <div style="font-size: 11px; color: var(--ink-3); margin-top: 4px;">{{ n.criada_em | date:'dd/MM HH:mm' }}</div>
                    </div>
                    <span *ngIf="!n.lida" style="width: 8px; height: 8px; background: var(--cyan); border-radius: 50%; flex-shrink: 0; margin-top: 4px;"></span>
                  </div>
                </div>
              </div>
            </div>
          </p-overlayPanel>

          <ng-container *ngIf="auth.userDisplay() as u">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="avatar">{{ u.initials }}</div>
              <div style="font-size: 12.5px; line-height: 1.3;">
                <div style="font-weight: 600;">{{ u.name }}</div>
                <div style="color: var(--ink-3);">{{ u.empresa }}</div>
              </div>
            </div>
          </ng-container>
          <button class="p-button p-button-text p-button-sm" pButton type="button" icon="pi pi-sign-out" (click)="logout()"></button>
        </div>
      </header>

      <main class="main">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
})
export class AppShellComponent {
  readonly auth = inject(AuthService);
  readonly notifSvc = inject(NotificacaoService);
  private readonly router = inject(Router);

  @ViewChild('bellPanel') bellPanel!: OverlayPanel;

  readonly notificacoes = this.notifSvc.notificacoes;
  readonly naoLidas = this.notifSvc.naoLidas;

  abrirNotificacao(n: Notificacao, panel: OverlayPanel): void {
    panel.hide();
    if (!n.lida) this.notifSvc.marcarLida(n.id).subscribe();
    if (n.referencia) this.router.navigate(['/edital', n.referencia]);
  }

  marcarTodas(): void {
    this.notifSvc.marcarTodasLidas().subscribe();
  }

  logout(): void {
    this.auth.logout();
  }
}
