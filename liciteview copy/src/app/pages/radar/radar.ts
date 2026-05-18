import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms';
import { Subject, takeUntil, finalize } from 'rxjs';

// PrimeNG Modules
import { AccordionModule } from 'primeng/accordion';
import { DrawerModule } from 'primeng/drawer';
import { SelectModule } from 'primeng/select';
import { MultiSelectModule } from 'primeng/multiselect';
import { InputTextModule } from 'primeng/inputtext';
import { ButtonModule } from 'primeng/button';
import { TableModule } from 'primeng/table';
import { PaginatorModule } from 'primeng/paginator';
import { TagModule } from 'primeng/tag';
import { CardModule } from 'primeng/card';
import { ToolbarModule } from 'primeng/toolbar';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { DatePicker } from 'primeng/datepicker';

import { LicitacaoService, FiltrosBusca, ResultadoBusca, LicitacaoItem } from '../../services/licitacao.service';

@Component({
  selector: 'app-radar',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    AccordionModule,
    DrawerModule,
    SelectModule,
    MultiSelectModule,
    InputTextModule,
    ButtonModule,
    TableModule,
    PaginatorModule,
    TagModule,
    CardModule,
    ToolbarModule,
    ProgressSpinnerModule,
    DatePicker
  ],
  templateUrl: './radar.html',
  styleUrls: ['./radar.scss']
})
export class RadarComponent implements OnInit, OnDestroy {
  filterForm: FormGroup;

  licitacoes: LicitacaoItem[] = [];
  totalRecords: number = 0;
  loading: boolean = false;
  error: string | null = null;
  mobileSidebarVisible: boolean = false;

  ufs = [
    { label: 'Acre (AC)', value: 'AC' },
    { label: 'Alagoas (AL)', value: 'AL' },
    { label: 'Amapá (AP)', value: 'AP' },
    { label: 'Amazonas (AM)', value: 'AM' },
    { label: 'Bahia (BA)', value: 'BA' },
    { label: 'Ceará (CE)', value: 'CE' },
    { label: 'Distrito Federal (DF)', value: 'DF' },
    { label: 'Espírito Santo (ES)', value: 'ES' },
    { label: 'Goiás (GO)', value: 'GO' },
    { label: 'Maranhão (MA)', value: 'MA' },
    { label: 'Mato Grosso (MT)', value: 'MT' },
    { label: 'Mato Grosso do Sul (MS)', value: 'MS' },
    { label: 'Minas Gerais (MG)', value: 'MG' },
    { label: 'Pará (PA)', value: 'PA' },
    { label: 'Paraíba (PB)', value: 'PB' },
    { label: 'Paraná (PR)', value: 'PR' },
    { label: 'Pernambuco (PE)', value: 'PE' },
    { label: 'Piauí (PI)', value: 'PI' },
    { label: 'Rio de Janeiro (RJ)', value: 'RJ' },
    { label: 'Rio Grande do Norte (RN)', value: 'RN' },
    { label: 'Rio Grande do Sul (RS)', value: 'RS' },
    { label: 'Rondônia (RO)', value: 'RO' },
    { label: 'Roraima (RR)', value: 'RR' },
    { label: 'Santa Catarina (SC)', value: 'SC' },
    { label: 'São Paulo (SP)', value: 'SP' },
    { label: 'Sergipe (SE)', value: 'SE' },
    { label: 'Tocantins (TO)', value: 'TO' }
  ];

  modalidades = [
    { label: 'Concorrência Eletrônica', value: '4' },
    { label: 'Concorrência Presencial', value: '5' },
    { label: 'Pregão Eletrônico', value: '6' },
    { label: 'Pregão Presencial', value: '7' },
    { label: 'Dispensa de Licitação', value: '8' },
    { label: 'Inexigibilidade', value: '9' },
    { label: 'Leilão Eletrônico', value: '1' },
    { label: 'Diálogo Competitivo', value: '2' },
    { label: 'Concurso Eletrônico', value: '3' }
  ];

  esferas = [
    { label: 'Federal', value: 'F' },
    { label: 'Estadual', value: 'E' },
    { label: 'Municipal', value: 'M' },
    { label: 'Distrital', value: 'D' }
  ];

  poderes = [
    { label: 'Executivo', value: 'E' },
    { label: 'Legislativo', value: 'L' },
    { label: 'Judiciário', value: 'J' }
  ];

  opcoesSimNao = [
    { label: 'Todos', value: '' },
    { label: 'Sim', value: 'S' },
    { label: 'Não', value: 'N' }
  ];

  tiposInstrumento = [
    { label: 'Edital', value: '1' },
    { label: 'Aviso de Contratação Direta', value: '2' }
  ];

  private destroy$ = new Subject<void>();

  constructor(
    private fb: FormBuilder,
    private licitacaoService: LicitacaoService
  ) {
    this.filterForm = this.fb.group({
      pagina: [1],
      uf: [''],
      modalidade: [''],
      palavraChave: [''],
      dataInicial: [null],
      dataFinal: [null],
      tipoInstrumento: [''],
      orgao: [''],
      unidade: [''],
      municipio: [''],
      esfera: [''],
      poder: [''],
      fonteOrcamentaria: [''],
      tipoMargemPreferencia: [''],
      exigenciaConteudoNacional: [''],
      emendaParlamentar: ['']
    });
  }

  ngOnInit(): void {
    // Busca inicial
    this.buscar();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  buscar(): void {
    if (this.filterForm.invalid) return;

    this.loading = true;
    this.error = null;

    const formValues = this.filterForm.value;

    // Formata datas se necessário
    const formatData = (data: Date) => {
      if (!data) return undefined;
      const d = new Date(data);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };

    const filtros: FiltrosBusca = {
      pagina: formValues.pagina,
      uf: formValues.uf || '',
      modalidade: formValues.modalidade || '',
      palavraChave: formValues.palavraChave || '',
      dataInicial: formatData(formValues.dataInicial),
      dataFinal: formatData(formValues.dataFinal),
      tipoInstrumento: formValues.tipoInstrumento || '',
      orgao: formValues.orgao || '',
      unidade: formValues.unidade || '',
      municipio: formValues.municipio || '',
      esfera: formValues.esfera || '',
      poder: formValues.poder || '',
      fonteOrcamentaria: formValues.fonteOrcamentaria || '',
      tipoMargemPreferencia: formValues.tipoMargemPreferencia || '',
      exigenciaConteudoNacional: formValues.exigenciaConteudoNacional || '',
      emendaParlamentar: formValues.emendaParlamentar || ''
    };

    this.licitacaoService.buscarEditais(filtros)
      .pipe(
        takeUntil(this.destroy$),
        finalize(() => this.loading = false)
      )
      .subscribe({
        next: (res: ResultadoBusca) => {
          this.licitacoes = res.items || [];
          this.totalRecords = res.totalItens || 0;
          this.mobileSidebarVisible = false; // Fecha no mobile após busca
        },
        error: (err) => {
          console.error('Erro ao buscar licitações:', err);
          this.error = 'Ocorreu um erro ao carregar as licitações. Tente novamente mais tarde.';
          this.licitacoes = [];
          this.totalRecords = 0;
        }
      });
  }

  limparFiltros(): void {
    this.filterForm.patchValue({
      uf: '',
      modalidade: '',
      palavraChave: '',
      dataInicial: null,
      dataFinal: null,
      pagina: 1,
      tipoInstrumento: '',
      orgao: '',
      unidade: '',
      municipio: '',
      esfera: '',
      poder: '',
      fonteOrcamentaria: '',
      tipoMargemPreferencia: '',
      exigenciaConteudoNacional: '',
      emendaParlamentar: ''
    });
    this.buscar();
  }

  onPageChange(event: any): void {
    // event.page is 0-indexed in PrimeNG, we add 1 for our 1-indexed API
    this.filterForm.patchValue({ pagina: event.page + 1 });
    this.buscar();
  }
}
