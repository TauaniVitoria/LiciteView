import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { LicitacaoService } from './licitacao.service';
import { environment } from '../../../environments/environment';

const BASE = `${environment.apiUrl}/cliente/licitacoes/buscar`;

const ITEM_PNCP = {
  numeroControlePNCP: 'CTRL-001',
  objetoCompra: 'Aquisição de notebooks',
  orgaoEntidade: { razaoSocial: 'Ministério da Saúde', esferaId: 'F', poderId: 'E' },
  unidadeOrgao: { nomeUnidade: 'DLOG', ufSigla: 'DF', municipioNome: 'Brasília' },
  modalidadeNome: 'Pregão Eletrônico',
  tipoInstrumentoConvocatorioNome: 'Edital',
  valorTotalEstimado: 500000,
  dataAberturaProposta: '2026-06-01T10:00:00',
  dataEncerramentoProposta: '2026-07-01T17:00:00',
  situacaoCompraId: 1,
  situacaoCompraNome: 'Divulgada no PNCP',
};

describe('LicitacaoService', () => {
  let service: LicitacaoService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(LicitacaoService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('search deve chamar GET /cliente/licitacoes/buscar', () => {
    service.search({}).subscribe();
    const req = http.expectOne((r) => r.url === BASE);
    expect(req.request.method).toBe('GET');
    req.flush({ data: [], totalRegistros: 0 });
  });

  it('search mapeia status recebendo → recebendo_proposta', () => {
    service.search({ status: 'recebendo' }).subscribe();
    const req = http.expectOne((r) => r.url === BASE);
    expect(req.request.params.get('status')).toBe('recebendo_proposta');
    req.flush({ data: [], totalRegistros: 0 });
  });

  it('search mapeia UF para parâmetro ufs', () => {
    service.search({ uf: 'SP' }).subscribe();
    const req = http.expectOne((r) => r.url === BASE);
    expect(req.request.params.get('ufs')).toBe('SP');
    req.flush({ data: [], totalRegistros: 0 });
  });

  it('search não envia parâmetro status quando filtro é todos', () => {
    service.search({ status: 'todos' }).subscribe();
    const req = http.expectOne((r) => r.url === BASE);
    expect(req.request.params.has('status')).toBeFalse();
    req.flush({ data: [], totalRegistros: 0 });
  });

  it('search converte PncpItem para Licitacao corretamente', () => {
    service.search({}).subscribe((res) => {
      expect(res.items.length).toBe(1);
      const l = res.items[0];
      expect(l.id).toBe('CTRL-001');
      expect(l.titulo).toBe('Aquisição de notebooks');
      expect(l.orgao).toBe('Ministério da Saúde');
      expect(l.uf).toBe('DF');
      expect(l.esfera).toBe('Federal');
      expect(l.poder).toBe('Executivo');
      expect(l.valor).toBe(500000);
      expect(l.status).toBe('A Receber/Recebendo Proposta');
    });
    http.expectOne((r) => r.url === BASE)
      .flush({ data: [ITEM_PNCP], totalRegistros: 1 });
  });

  it('search retorna total do servidor', () => {
    service.search({}).subscribe((res) => {
      expect(res.total).toBe(42);
    });
    http.expectOne((r) => r.url === BASE)
      .flush({ data: [], totalRegistros: 42 });
  });

  it('byId retorna item do cache após search', () => {
    service.search({}).subscribe();
    http.expectOne((r) => r.url === BASE)
      .flush({ data: [ITEM_PNCP], totalRegistros: 1 });

    service.byId('CTRL-001').subscribe((l) => {
      expect(l?.id).toBe('CTRL-001');
    });
  });
});
