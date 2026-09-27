import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AnaliseService } from './analise.service';
import { environment } from '../../../environments/environment';

const BASE = `${environment.apiUrl}/cliente/analise`;

const RESP_VERDE = {
  id: 'av-1',
  edital_id: 'e-uuid',
  produto_id: 'p-uuid',
  margem_minima_snapshot: 0.15,
  preco_venda_snapshot: null,
  custo_produto_snapshot: 2450,
  custo_frete_estimado: 24000,
  custo_total_estimado: 376000,
  receita_estimada: 400000,
  margem_estimada: 0.06,
  dentro_margem: false,
  classificacao: 'ATENCAO',
  justificativa: 'Margem apertada.',
  gerado_em: '2026-01-01T00:00:00',
};

describe('AnaliseService', () => {
  let service: AnaliseService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(AnaliseService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('analisar deve chamar POST /analise com edital_id e produto_id', () => {
    service.analisar('e-uuid', 'p-uuid', 'pncp-001').subscribe();

    const req = http.expectOne(BASE);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ edital_id: 'e-uuid', produto_id: 'p-uuid' });
    req.flush(RESP_VERDE);
  });

  it('analisar mapeia classificacao ATENCAO para verdict amber', () => {
    service.analisar('e-uuid', 'p-uuid', 'pncp-001').subscribe((a) => {
      expect(a.verdict).toBe('amber');
      expect(a.licitacaoId).toBe('pncp-001');
      expect(a.produtoId).toBe('p-uuid');
    });
    http.expectOne(BASE).flush(RESP_VERDE);
  });

  it('analisar armazena resultado no signal', () => {
    service.analisar('e-uuid', 'p-uuid', 'pncp-001').subscribe();
    http.expectOne(BASE).flush(RESP_VERDE);

    expect(service.get('pncp-001')).toBeDefined();
    expect(service.get('pncp-001')?.verdict).toBe('amber');
  });

  it('clear remove do signal', () => {
    service.analisar('e-uuid', 'p-uuid', 'pncp-001').subscribe();
    http.expectOne(BASE).flush(RESP_VERDE);

    service.clear('pncp-001');
    expect(service.get('pncp-001')).toBeUndefined();
  });

  it('analisar mapeia custos corretamente', () => {
    service.analisar('e-uuid', 'p-uuid', 'pncp-001').subscribe((a) => {
      expect(a.custoLogistico).toBe(24000);
      expect(a.custoOperacional).toBe(376000 - 24000);
      expect(a.margemPct).toBeCloseTo(6, 0);
    });
    http.expectOne(BASE).flush(RESP_VERDE);
  });
});
