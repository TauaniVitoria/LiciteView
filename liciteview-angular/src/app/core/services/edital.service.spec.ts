import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { fakeAsync, tick } from '@angular/core/testing';
import { EditalService, EditalStatus } from './edital.service';
import { environment } from '../../../environments/environment';

const BASE = `${environment.apiUrl}/cliente/editais`;

const STATUS_PROCESSANDO: EditalStatus = {
  edital_id: 'uuid-1', id_pncp: 'PNCP-001',
  status: 'PROCESSANDO', resumo: null, total_chunks: 0, erro_mensagem: null,
  url_pdf: null, tempo_decorrido: null,
};

const STATUS_PROCESSADO: EditalStatus = {
  edital_id: 'uuid-1', id_pncp: 'PNCP-001',
  status: 'PROCESSADO', resumo: { bloco1_visao_geral: {} } as any,
  total_chunks: 42, erro_mensagem: null,
  url_pdf: null, tempo_decorrido: null,
};

describe('EditalService', () => {
  let service: EditalService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(EditalService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('processar deve chamar POST /editais/processar', () => {
    service.processar({ id_pncp: 'PNCP-001', orgao: 'Ministério', objeto: 'Notebooks' }).subscribe();

    const req = http.expectOne(`${BASE}/processar`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body.id_pncp).toBe('PNCP-001');
    req.flush({ edital_id: 'uuid-1', status: 'PROCESSANDO' });
  });

  it('getStatus deve chamar GET /editais/{id}/status', () => {
    service.getStatus('uuid-1').subscribe();

    const req = http.expectOne(`${BASE}/uuid-1/status`);
    expect(req.request.method).toBe('GET');
    req.flush(STATUS_PROCESSADO);
  });

  it('perguntar deve chamar POST /editais/{id}/perguntar', () => {
    service.perguntar('uuid-1', 'Exige atestado?').subscribe();

    const req = http.expectOne(`${BASE}/uuid-1/perguntar`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body.pergunta).toBe('Exige atestado?');
    req.flush({ resposta: 'Sim, exige.', trecho_fonte: 'Item 8.3.2...', chunks_utilizados: 3 });
  });

  it('poll deve emitir até status terminal e parar', fakeAsync(() => {
    const emitidos: EditalStatus[] = [];
    service.poll('uuid-1').subscribe((s) => emitidos.push(s));

    // Primeira emissão imediata (startWith(0))
    http.expectOne(`${BASE}/uuid-1/status`).flush(STATUS_PROCESSANDO);
    expect(emitidos.length).toBe(1);
    expect(emitidos[0].status).toBe('PROCESSANDO');

    // Após 3s, nova emissão com status terminal
    tick(3000);
    http.expectOne(`${BASE}/uuid-1/status`).flush(STATUS_PROCESSADO);
    expect(emitidos.length).toBe(2);
    expect(emitidos[1].status).toBe('PROCESSADO');

    // takeWhile(inclusive) para quando terminal — não deve haver mais chamadas
    tick(3000);
    http.expectNone(`${BASE}/uuid-1/status`);
  }));
});
