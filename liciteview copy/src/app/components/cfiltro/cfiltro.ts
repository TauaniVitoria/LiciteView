import { Component, EventEmitter, Output, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

// PrimeNG imports
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { MultiSelectModule } from 'primeng/multiselect';
import { AutoCompleteModule } from 'primeng/autocomplete';
import { InputNumberModule } from 'primeng/inputnumber';
import { SelectButtonModule } from 'primeng/selectbutton';
import { ButtonModule } from 'primeng/button';
import { BadgeModule } from 'primeng/badge';
import { InputGroupModule } from 'primeng/inputgroup';
import { InputGroupAddonModule } from 'primeng/inputgroupaddon';

interface Orgao {
  nome: string;
  codigo: string;
}

@Component({
  selector: 'app-filtro-busca',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    InputTextModule,
    MultiSelectModule,
    SelectModule,
    AutoCompleteModule,
    InputNumberModule,
    SelectButtonModule,
    ButtonModule,
    BadgeModule,
    InputGroupModule,
    InputGroupAddonModule
  ],
  templateUrl: './cfiltro.html',
  styleUrls: ['./cfiltro.css']
})
export class FiltroBuscaComponent implements OnInit {
  @Output() filtroAplicado = new EventEmitter<any>();
  @Output() filtroLimpo = new EventEmitter<void>();

  filtroForm: FormGroup;
  painelAberto = true;

  // Dados para os selects
  ufs = [
    { label: 'Acre', value: 'AC' },
    { label: 'Alagoas', value: 'AL' },
    { label: 'Amapá', value: 'AP' },
    { label: 'Amazonas', value: 'AM' },
    { label: 'Bahia', value: 'BA' },
    { label: 'Ceará', value: 'CE' },
    { label: 'Distrito Federal', value: 'DF' },
    { label: 'Espírito Santo', value: 'ES' },
    { label: 'Goiás', value: 'GO' },
    { label: 'Maranhão', value: 'MA' },
    { label: 'Mato Grosso', value: 'MT' },
    { label: 'Mato Grosso do Sul', value: 'MS' },
    { label: 'Minas Gerais', value: 'MG' },
    { label: 'Pará', value: 'PA' },
    { label: 'Paraíba', value: 'PB' },
    { label: 'Paraná', value: 'PR' },
    { label: 'Pernambuco', value: 'PE' },
    { label: 'Piauí', value: 'PI' },
    { label: 'Rio de Janeiro', value: 'RJ' },
    { label: 'Rio Grande do Norte', value: 'RN' },
    { label: 'Rio Grande do Sul', value: 'RS' },
    { label: 'Rondônia', value: 'RO' },
    { label: 'Roraima', value: 'RR' },
    { label: 'Santa Catarina', value: 'SC' },
    { label: 'São Paulo', value: 'SP' },
    { label: 'Sergipe', value: 'SE' },
    { label: 'Tocantins', value: 'TO' }
  ];

  municipios = [
    { label: 'São Paulo', value: 'SAO_PAULO' },
    { label: 'Rio de Janeiro', value: 'RIO_JANEIRO' },
    { label: 'Belo Horizonte', value: 'BELO_HORIZONTE' },
    { label: 'Brasília', value: 'BRASILIA' },
    { label: 'Salvador', value: 'SALVADOR' },
    { label: 'Fortaleza', value: 'FORTALEZA' },
    { label: 'Curitiba', value: 'CURITIBA' },
    { label: 'Manaus', value: 'MANAUS' },
    { label: 'Recife', value: 'RECIFE' },
    { label: 'Porto Alegre', value: 'PORTO_ALEGRE' }
  ];

  esferas = [
    { label: 'Federal', value: 'federal' },
    { label: 'Estadual', value: 'estadual' },
    { label: 'Municipal', value: 'municipal' }
  ];

  modalidades = [
    { label: 'Pregão Eletrônico', value: 'pregao_eletronico' },
    { label: 'Concorrência', value: 'concorrencia' },
    { label: 'Tomada de Preços', value: 'tomada_precos' },
    { label: 'Convite', value: 'convite' },
    { label: 'Concurso', value: 'concurso' },
    { label: 'Leilão', value: 'leilao' },
    { label: 'Dispensa de Licitação', value: 'dispensa' },
    { label: 'Inexigibilidade', value: 'inexigibilidade' }
  ];

  tiposInstrumento = [
    { label: 'Edital', value: 'edital' },
    { label: 'Aviso', value: 'aviso' },
    { label: 'Comunicado', value: 'comunicado' },
    { label: 'Retificação', value: 'retificacao' }
  ];

  poderes = [
    { label: 'Executivo', value: 'executivo' },
    { label: 'Legislativo', value: 'legislativo' },
    { label: 'Judiciário', value: 'judiciario' }
  ];

  forcasOrcamentarias = [
    { label: 'Orçamento Fiscal', value: 'fiscal' },
    { label: 'Orçamento da Seguridade Social', value: 'seguridade' },
    { label: 'Orçamento de Investimento', value: 'investimento' }
  ];

  margensPreferencia = [
    { label: 'ME/EPP', value: 'me_epp' },
    { label: 'Brasileiro', value: 'brasileiro' },
    { label: 'Local', value: 'local' },
    { label: 'Regional', value: 'regional' }
  ];

  opcoesSimNao = [
    { label: 'Sim', value: true },
    { label: 'Não', value: false }
  ];

  // Dados para autocomplete
  filtroOrgaos: Orgao[] = [];

  constructor(private fb: FormBuilder) {
    this.filtroForm = this.fb.group({
      palavraChave: [''],
      tipoInstrumentoConvocatorio: [''],
      modalidade: [''],
      orgaos: [''],
      uf: [''],
      municipio: [''],
      esfera: [''],
      poderes: [[]],
      forcasOrcamentarias: [[]],
      tiposMargensPreferencia: [[]],
      exigenciaConteudoNacional: [null],
      emendaParlamentar: [null],
      valorMinimo: [null],
      valorMaximo: [null],
      dataInicial: [null],
      dataFinal: [null]
    });
  }

  ngOnInit(): void {
    // Observa mudanças na UF para habilitar/desabilitar municípios
    this.filtroForm.get('uf')?.valueChanges.subscribe(() => {
      this.filtroForm.get('municipio')?.reset();
    });
  }

  onSubmit(): void {
    const filtros = this.filtroForm.value;
    // Remove campos vazios, null ou undefined
    const filtrosAtivos = Object.fromEntries(
      Object.entries(filtros).filter(([_, value]) => {
        if (value === '' || value === null || value === undefined) return false;
        if (Array.isArray(value) && value.length === 0) return false;
        return true;
      })
    );
    this.filtroAplicado.emit(filtrosAtivos);
  }

  limparFiltros(): void {
    this.filtroForm.reset({
      palavraChave: '',
      tipoInstrumentoConvocatorio: '',
      modalidade: '',
      orgaos: '',
      uf: '',
      municipio: '',
      esfera: '',
      poderes: [],
      forcasOrcamentarias: [],
      tiposMargensPreferencia: [],
      exigenciaConteudoNacional: null,
      emendaParlamentar: null,
      valorMinimo: null,
      valorMaximo: null,
      dataInicial: null,
      dataFinal: null
    });
    this.filtroLimpo.emit();
  }

  togglePainel(): void {
    this.painelAberto = !this.painelAberto;
  }

  getTotalFiltrosAtivos(): number {
    const values = this.filtroForm.value;
    let count = 0;
    
    Object.keys(values).forEach(key => {
      const value = values[key];
      if (value !== '' && value !== null && value !== undefined) {
        if (Array.isArray(value) && value.length === 0) return;
        count++;
      }
    });
    
    return count;
  }

  buscarOrgaos(event: any): void {
    // Mock de busca de órgãos - em produção, isso viria da API do PNCP
    const orgaosMock: Orgao[] = [
      { nome: 'Ministério da Economia', codigo: 'ME' },
      { nome: 'Ministério da Saúde', codigo: 'MS' },
      { nome: 'Ministério da Educação', codigo: 'MEC' },
      { nome: 'Prefeitura de São Paulo', codigo: 'PMSP' },
      { nome: 'Governo do Estado de São Paulo', codigo: 'GESP' },
      { nome: 'Tribunal de Justiça', codigo: 'TJ' }
    ];

    this.filtroOrgaos = orgaosMock.filter(orgao => 
      orgao.nome.toLowerCase().includes(event.query.toLowerCase())
    );
  }
}