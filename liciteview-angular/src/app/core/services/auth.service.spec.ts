import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from './auth.service';
import { TOKEN_KEY } from '../interceptors/auth.interceptor';
import { environment } from '../../../environments/environment';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [provideRouter([])],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
    // Drena eventual GET /auth/me disparado no constructor
    http.match(`${environment.apiUrl}/auth/me`).forEach(r => r.flush({}));
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  it('deve retornar false para isAuthenticated sem token', () => {
    expect(service.isAuthenticated()).toBeFalse();
  });

  it('login deve chamar POST /auth/login com email e senha', () => {
    service.login('user@test.com', 'senha123').subscribe();

    const loginReq = http.expectOne(`${environment.apiUrl}/auth/login`);
    expect(loginReq.request.method).toBe('POST');
    expect(loginReq.request.body).toEqual({ email: 'user@test.com', senha: 'senha123' });
    loginReq.flush({ access_token: 'fake-token', token_type: 'bearer' });

    const meReq = http.expectOne(`${environment.apiUrl}/auth/me`);
    meReq.flush({ id: '1', nome: 'Teste', razao_social: 'Empresa', email: 'user@test.com', cnpj: '', cep: '', cidade: null, uf: null, perfil: 'FORNECEDOR', ativo: true, criado_em: '' });
  });

  it('login deve salvar token no localStorage', () => {
    service.login('user@test.com', 'senha123').subscribe();

    http.expectOne(`${environment.apiUrl}/auth/login`)
      .flush({ access_token: 'meu-token', token_type: 'bearer' });
    http.expectOne(`${environment.apiUrl}/auth/me`)
      .flush({ id: '1', nome: 'Teste', razao_social: 'Empresa', email: '', cnpj: '', cep: '', cidade: null, uf: null, perfil: 'FORNECEDOR', ativo: true, criado_em: '' });

    expect(localStorage.getItem(TOKEN_KEY)).toBe('meu-token');
  });

  it('login deve preencher userDisplay após sucesso', () => {
    service.login('user@test.com', 'senha123').subscribe();

    http.expectOne(`${environment.apiUrl}/auth/login`)
      .flush({ access_token: 'tok', token_type: 'bearer' });
    http.expectOne(`${environment.apiUrl}/auth/me`)
      .flush({ id: '1', nome: 'Ana Teixeira', razao_social: 'Arctec Soluções', email: '', cnpj: '', cep: '', cidade: null, uf: null, perfil: 'FORNECEDOR', ativo: true, criado_em: '' });

    const display = service.userDisplay();
    expect(display?.initials).toBe('AT');
    expect(display?.name).toBe('Ana Teixeira');
    expect(display?.empresa).toBe('Arctec Soluções');
  });

  it('logout deve remover token do localStorage', () => {
    localStorage.setItem(TOKEN_KEY, 'tok');
    service.logout();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('isAuthenticated deve retornar true se token existir', () => {
    localStorage.setItem(TOKEN_KEY, 'tok');
    expect(service.isAuthenticated()).toBeTrue();
  });
});
