import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './sidebar.html',
  styleUrls: ['./sidebar.scss']
})
export class SidebarComponent {
  navItems = [
    { label: 'Radar', route: '/radar', icon: 'pi pi-bullseye' },
    { label: 'Cadastro', route: '/cadastro', icon: 'pi pi-building' }
  ];
}
