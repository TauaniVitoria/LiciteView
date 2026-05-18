import { TestBed } from '@angular/core/testing';

import { SbuscalicitacaoTs } from './sbuscalicitacao.ts';

describe('SbuscalicitacaoTs', () => {
  let service: SbuscalicitacaoTs;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(SbuscalicitacaoTs);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
