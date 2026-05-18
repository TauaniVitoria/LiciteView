import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Cdashboard } from './cdashboard';

describe('Cdashboard', () => {
  let component: Cdashboard;
  let fixture: ComponentFixture<Cdashboard>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Cdashboard],
    }).compileComponents();

    fixture = TestBed.createComponent(Cdashboard);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
