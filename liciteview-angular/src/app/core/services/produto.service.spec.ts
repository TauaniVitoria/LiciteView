import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ProdutoService } from './produto.service';
import { environment } from '../../../environments/environment';

const BASE = `${environment.apiUrl}/cliente/produtos`;

const PRODUTO_MOCK = {
  id: 'uuid-1',
  usuario_id: 'usr-1',
  nome: 'Notebook i5',
  descricao: null,
  categoria: 'EQUIPAMENTO',
  ncm: '8471.30.12',
  preco_venda: null,
  custo_produto: 2450,
  margem_minima: 0.15,
  peso_kg: null,
  impostos: 18.5,
  cep: '04567-000',
  uf: 'SP',
  capacidade_mensal: 1500,
  ativo: true,
  criado_em: '2026-01-01T00:00:00',
};

describe('ProdutoService', () => {
  let service: ProdutoService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(ProdutoService);
    http = TestBed.inject(HttpTestingController);
    // Drena o GET disparado no constructor
    http.expectOne(BASE).flush([PRODUTO_MOCK]);
  });

  afterEach(() => http.verify());

  it('deve carregar produtos na inicialização', () => {
    expect(service.produtos().length).toBe(1);
    expect(service.produtos()[0].nome).toBe('Notebook i5');
  });

  it('criar deve chamar POST e adicionar ao signal', () => {
    const novo = { nome: 'Monitor 24"', custo_produto: 680, margem_minima: 0.2, impostos: 18 };
    service.criar(novo).subscribe();

    const req = http.expectOne(BASE);
    expect(req.request.method).toBe('POST');
    expect(req.request.body.nome).toBe('Monitor 24"');
    expect(req.request.body.margem_minima).toBe(0.2);
    req.flush({ ...PRODUTO_MOCK, id: 'uuid-2', nome: 'Monitor 24"' });

    expect(service.produtos().length).toBe(2);
    expect(service.produtos()[0].nome).toBe('Monitor 24"');  // inserido no início
  });

  it('remover deve chamar DELETE e tirar do signal', () => {
    service.remover('uuid-1').subscribe();

    const req = http.expectOne(`${BASE}/uuid-1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);

    expect(service.produtos().length).toBe(0);
  });

  it('atualizar deve chamar PUT e atualizar o signal', () => {
    service.atualizar('uuid-1', { nome: 'Notebook i7' }).subscribe();

    const req = http.expectOne(`${BASE}/uuid-1`);
    expect(req.request.method).toBe('PUT');
    req.flush({ ...PRODUTO_MOCK, nome: 'Notebook i7' });

    expect(service.produtos()[0].nome).toBe('Notebook i7');
  });
});
