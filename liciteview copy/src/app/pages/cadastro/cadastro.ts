import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { ButtonModule } from 'primeng/button';
import { ChipModule } from 'primeng/chip';

@Component({
  selector: 'app-cadastro',
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule, InputTextModule, 
    InputNumberModule, ButtonModule, ChipModule
  ],
  templateUrl: './cadastro.html',
  styleUrls: ['./cadastro.scss']
})
export class CadastroComponent implements OnInit {
  cadastroForm!: FormGroup;

  categorias = [
    { label: 'Tecnologia', selected: false },
    { label: 'Mobiliário', selected: false },
    { label: 'Vestuário', selected: false },
    { label: 'Alimentação', selected: false },
    { label: 'Saúde', selected: false },
    { label: 'Veículos', selected: false },
    { label: 'Serviços', selected: false },
    { label: 'Material de Construção', selected: false },
    { label: 'Material de Escritório', selected: false },
    { label: 'Equipamentos Industriais', selected: false }
  ];

  constructor(private fb: FormBuilder) {}

  ngOnInit() {
    this.cadastroForm = this.fb.group({
      nomeEmpresa: ['', Validators.required],
      cep: ['', Validators.required],
      custoMedio: [0, Validators.required],
      margemMinima: [10, Validators.required]
    });
  }

  toggleCategoria(categoria: any) {
    categoria.selected = !categoria.selected;
  }

  onSubmit() {
    if (this.cadastroForm.valid) {
      const selectedCategories = this.categorias.filter(c => c.selected).map(c => c.label);
      console.log('Dados salvos:', {
        ...this.cadastroForm.value,
        categoriasInteresse: selectedCategories
      });
      // Lógica de salvar
    } else {
      this.cadastroForm.markAllAsTouched();
    }
  }
}
