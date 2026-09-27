import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { CheckboxModule } from 'primeng/checkbox';
import { AuthService } from '../../core/services/auth.service';
import { HttpErrorResponse } from '@angular/common/http';

@Component({
  selector: 'lv-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ButtonModule, InputTextModule, PasswordModule, CheckboxModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="auth">
      <div class="auth__brand">
        <div class="auth__brand-top">
          <img src="assets/logo-liciteview.png" alt="LiciteView" />
        </div>
        <div class="auth__brand-body">
          <h2>Encontre a licitação certa.<br/>Decida em minutos.</h2>
          <p>
            Pesquise editais publicados no PNCP, receba resumos gerados por IA,
            converse com o edital e visualize a viabilidade do seu produto antes
            de submeter qualquer proposta.
          </p>
        </div>
        <div class="auth__brand-stats">
        </div>
      </div>

      <div class="auth__form">
        <div class="auth__form-inner">
          <h1>Acesso ao painel</h1>
          <p class="sub">Entre com suas credenciais para acessar o painel.</p>

          <form (submit)="$event.preventDefault(); submit()">
            <div class="field">
              <label class="field__label">E-mail corporativo</label>
              <input pInputText type="email" [(ngModel)]="email" name="email" placeholder="voce@empresa.com.br" />
            </div>
            <div class="field">
              <label class="field__label">Senha</label>
              <p-password [(ngModel)]="password" name="password" [feedback]="false" [toggleMask]="true" styleClass="w-full" inputStyleClass="w-full"></p-password>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;">
              <p-checkbox [(ngModel)]="remember" name="remember" [binary]="true" label="Lembrar de mim"></p-checkbox>
              <a href="#" (click)="$event.preventDefault()" style="font-size: 12.5px; font-weight: 500;">Esqueceu a senha?</a>
            </div>

            <div *ngIf="sessionExpired()" style="margin-bottom: 14px; padding: 10px 14px; background: var(--amber-50); border: 1px solid var(--amber); border-radius: var(--r-sm); font-size: 13px; color: var(--amber); display: flex; align-items: center; gap: 8px;">
              <i class="pi pi-info-circle" style="font-size: 14px;"></i>
              <span>Sua sessão expirou por inatividade. Faça login novamente para continuar.</span>
            </div>

            <div *ngIf="error()" style="margin-bottom: 14px; padding: 10px 14px; background: var(--red-50); border: 1px solid var(--red); border-radius: var(--r-sm); font-size: 13px; color: var(--red);">
              {{ error() }}
            </div>

            <button pButton type="submit" label="Entrar" icon="pi pi-arrow-right" iconPos="right" class="w-full" [loading]="loading()"></button>
          </form>

          <div class="auth__divider">ou</div>

          <div class="auth__switch">
            Ainda não tem uma conta?
            <a routerLink="/register">Cadastre-se</a>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  email = '';
  password = '';
  remember = false;

  readonly loading = signal(false);
  readonly error = signal('');
  readonly sessionExpired = signal(false);

  constructor() {
    this.route.queryParams.subscribe(params => {
      if (params['expired'] === 'true') {
        this.sessionExpired.set(true);
      }
    });
  }

  submit(): void {
    this.sessionExpired.set(false);
    if (!this.email || !this.password) {
      this.error.set('Preencha e-mail e senha.');
      return;
    }
    this.loading.set(true);
    this.error.set('');

    this.auth.login(this.email, this.password).subscribe({
      next: () => this.router.navigateByUrl('/pesquisa'),
      error: (e: HttpErrorResponse) => {
        this.error.set(
          e.status === 401 ? 'E-mail ou senha inválidos.' : 'Erro ao conectar. Verifique se o servidor está rodando.'
        );
        this.loading.set(false);
      },
    });
  }
}
