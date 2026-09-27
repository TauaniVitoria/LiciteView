# liciteview-angular — Frontend LicitiView

Interface web em **Angular 17** para busca e análise de licitações públicas do PNCP.

> O backend precisa estar rodando antes de usar o frontend.
> Veja as instruções em `../licitacoes-ws/README.md`.

---

## Pré-requisitos

| Ferramenta | Versão mínima |
| --- | --- |
| Node.js | 18.x |
| npm | 9.x (incluído no Node.js) |

Verifique as versões instaladas:

```bash
node -v
npm -v
```

---

## Instalação

```bash
# 1. Entre na pasta do frontend
cd liciteview-angular

# 2. Instale as dependências
npm install
```

---

## Rodando o projeto

```bash
npm start
```

O navegador abrirá automaticamente em <http://localhost:4200>.

O frontend espera a API em `http://127.0.0.1:8000` (padrão do backend em dev).
Se precisar mudar, edite `src/environments/environment.ts`:

```typescript
export const environment = {
  production: false,
  apiUrl: 'http://127.0.0.1:8000',
};
```

---

## Scripts disponíveis

| Comando | Descrição |
| --- | --- |
| `npm start` | Servidor de desenvolvimento (abre o navegador) |
| `npm run build` | Build de desenvolvimento na pasta `dist/` |
| `ng build --configuration production` | Build otimizado para produção |

---

## Estrutura do Projeto

```text
src/
├── app/
│   ├── app.component.ts        # Componente raiz (RouterOutlet)
│   ├── app.config.ts           # Providers globais, interceptors HTTP
│   ├── app.routes.ts           # Rotas com authGuard (lazy loading)
│   ├── core/
│   │   ├── models/             # Interfaces TypeScript (Licitacao, Produto, Analise...)
│   │   ├── services/           # AuthService, LicitacaoService, EditalService...
│   │   └── interceptors/       # Injeta token JWT em todas as requisições
│   ├── features/
│   │   ├── auth/               # Telas de login e cadastro
│   │   ├── pesquisa/           # Busca de licitações com filtros do PNCP
│   │   ├── edital/             # Detalhes do edital: Resumo / Viabilidade / Chat
│   │   ├── produtos/           # Catálogo de produtos (lista + formulário)
│   │   └── historico/          # Histórico de análises realizadas
│   └── layout/                 # Shell da aplicação (navbar + sidebar)
├── environments/
│   ├── environment.ts          # Configuração de desenvolvimento
│   └── environment.prod.ts     # Configuração de produção
└── styles.scss                 # Tema global e tokens de design
```

---

## Rotas da Aplicação

| Rota | Tela |
| --- | --- |
| `/login` | Login |
| `/register` | Cadastro de fornecedor |
| `/pesquisa` | Busca de licitações (PNCP) |
| `/edital/:id` | Detalhes do edital (Resumo / Viabilidade / Chat) |
| `/produtos` | Lista de produtos do fornecedor |
| `/produtos/novo` | Criar ou editar produto |
| `/historico` | Histórico de análises |

---

## Solução de Problemas

**`ng serve` não reconhecido**
→ Instale o Angular CLI: `npm install -g @angular/cli@17`

**Erros de CORS ao chamar a API**
→ Confirme que `ALLOWED_ORIGINS` no `.env` do backend contém `http://localhost:4200`.

**Tela em branco após login**
→ Abra o DevTools (F12) → Console e verifique se a API responde em <http://127.0.0.1:8000/health>.

**`npm install` com erros**
→ Confirme Node.js 18+: `node -v`. Se necessário, limpe o cache: `npm cache clean --force`.
