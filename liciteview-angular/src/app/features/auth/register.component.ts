import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { DropdownModule } from 'primeng/dropdown';
import { CheckboxModule } from 'primeng/checkbox';
import { AuthService } from '../../core/services/auth.service';
import { FILTRO_OPCOES } from '../../core/services/mock-data';

@Component({
  selector: 'lv-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ButtonModule, InputTextModule, PasswordModule, DropdownModule, CheckboxModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="auth">
      <div class="auth__brand">
        <div class="auth__brand-top">
          <img src="assets/logo-liciteview.png" alt="LiciteView" />
        </div>
        <div class="auth__brand-body">
          <h2>Crie sua conta gratuita.<br/>Comece pelos editais que importam.</h2>
          <p>Cadastro em 2 etapas. Você poderá adicionar seus produtos logo após validar seu e-mail corporativo.</p>
        </div>
      </div>

      <div class="auth__form">
        <div class="auth__form-inner">
          <h1>Criar conta</h1>
          <p class="sub">Etapa {{ step() }} de 2 — {{ step() === 1 ? 'seus dados' : 'sua empresa' }}</p>

          <ng-container *ngIf="step() === 1; else step2">
            <form (submit)="$event.preventDefault(); avancar()">
              <div class="field">
                <label class="field__label">Nome completo *</label>
                <input pInputText [(ngModel)]="nome" name="nome" placeholder="João da Silva" />
              </div>
              <div class="field">
                <label class="field__label">E-mail corporativo *</label>
                <input pInputText type="email" [(ngModel)]="email" name="email" placeholder="voce@empresa.com.br" />
              </div>
              <div class="field">
                <label class="field__label">Senha (mínimo 8 caracteres) *</label>
                <p-password [(ngModel)]="password" name="password" [toggleMask]="true" styleClass="w-full" inputStyleClass="w-full"></p-password>
              </div>
              <p-checkbox [(ngModel)]="agreed" name="agreed" [binary]="true" label="Li e concordo com os Termos de Uso" styleClass="my-3"></p-checkbox>
              <div *ngIf="erro()" style="margin: 8px 0; color: var(--red); font-size: 13px;">{{ erro() }}</div>
              <button pButton type="submit" label="Continuar" icon="pi pi-arrow-right" iconPos="right" class="w-full mt-2"></button>
            </form>
          </ng-container>

          <ng-template #step2>
            <form (submit)="$event.preventDefault(); submit()">
              <div class="field">
                <label class="field__label">Razão social *</label>
                <input pInputText [(ngModel)]="razao" name="razao" placeholder="Arctec Soluções LTDA" />
              </div>
              <div class="field">
                <label class="field__label">CNPJ *</label>
                <input pInputText [(ngModel)]="cnpj" name="cnpj" placeholder="00.000.000/0001-00" class="mono" />
              </div>
              <div class="produto-row">
                <div class="field">
                  <label class="field__label">CEP *</label>
                  <input pInputText [(ngModel)]="cep" name="cep" placeholder="00000-000" class="mono" />
                </div>
                <div class="field">
                  <label class="field__label">UF</label>
                  <p-dropdown [options]="ufs" [(ngModel)]="uf" name="uf" appendTo="body"></p-dropdown>
                </div>
              </div>
              <div class="field">
                <label class="field__label">Município</label>
                <input pInputText [(ngModel)]="municipio" name="municipio" placeholder="São Paulo" />
              </div>

              <div *ngIf="erro()" style="margin: 8px 0; padding: 10px 14px; background: var(--red-50); border: 1px solid var(--red); border-radius: var(--r-sm); font-size: 13px; color: var(--red);">
                {{ erro() }}
              </div>

              <div style="display: flex; gap: 10px; margin-top: 16px;">
                <button pButton type="button" label="Voltar" icon="pi pi-arrow-left" class="p-button-outlined" (click)="step.set(1)"></button>
                <button pButton type="submit" label="Criar conta" icon="pi pi-check" iconPos="right" class="flex-1" [loading]="loading()"></button>
              </div>
            </form>
          </ng-template>

          <div class="auth__switch">
            Já tem uma conta? <a routerLink="/login">Entrar</a>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class RegisterComponent {
  private readonly auth   = inject(AuthService);
  private readonly router = inject(Router);

  readonly step    = signal(1);
  readonly loading = signal(false);
  readonly erro    = signal('');
  readonly ufs     = FILTRO_OPCOES.uf;

  // Passo 1
  nome     = '';
  email    = '';
  password = '';
  agreed   = false;

  // Passo 2
  razao    = '';
  cnpj     = '';
  cep      = '';
  uf       = 'SP';
  municipio = '';

  avancar(): void {
    if (!this.nome.trim() || !this.email.trim() || this.password.length < 8) {
      this.erro.set('Preencha nome, e-mail e senha (mínimo 8 caracteres).');
      return;
    }
    if (!this.agreed) {
      this.erro.set('Aceite os Termos de Uso para continuar.');
      return;
    }
    this.erro.set('');
    this.step.set(2);
  }

  submit(): void {
    if (!this.razao.trim() || !this.cnpj.trim() || !this.cep.trim()) {
      this.erro.set('Preencha razão social, CNPJ e CEP.');
      return;
    }
    this.loading.set(true);
    this.erro.set('');

    this.auth.registrar({
      nome:         this.nome.trim(),
      email:        this.email.trim(),
      senha:        this.password,
      razao_social: this.razao.trim(),
      cnpj:         this.cnpj.trim(),
      cep:          this.cep.trim(),
      cidade:       this.municipio.trim() || undefined,
      uf:           this.uf || undefined,
    }).subscribe({
      next: () => this.router.navigateByUrl('/pesquisa'),
      error: (e: HttpErrorResponse) => {
        const msg = e.error?.detail ?? '';
        if (msg.includes('CNPJ')) this.erro.set('CNPJ já cadastrado.');
        else if (msg.includes('E-mail') || msg.includes('email')) this.erro.set('E-mail já cadastrado.');
        else if (e.status === 422) this.erro.set('Dados inválidos. Verifique o formato do CNPJ (00.000.000/0001-00) e CEP (00000-000).');
        else this.erro.set('Erro ao criar conta. Tente novamente.');
        this.loading.set(false);
      },
    });
  }
}
