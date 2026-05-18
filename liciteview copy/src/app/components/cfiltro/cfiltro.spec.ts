import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FiltroBuscaComponent } from '../cfiltro/cfiltro';

describe('FiltroBuscaComponent', () => {
  let component: FiltroBuscaComponent;
  let fixture: ComponentFixture<FiltroBuscaComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FiltroBuscaComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(FiltroBuscaComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
