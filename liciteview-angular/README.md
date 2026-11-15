# liciteview-angular — Frontend LiciteView

Interface web em **Angular 17** para busca e análise de licitações públicas do PNCP.

> O backend precisa estar rodando antes de usar o frontend.
> Veja as instruções em [`../licitacoes-ws/README.md`](../licitacoes-ws/README.md).

Documentação técnica completa: [`../docs/documentacao-tecnica.md`](../docs/documentacao-tecnica.md).

---

## Pré-requisitos

| Ferramenta | Versão mínima |
| --- | --- |
| Node.js | 18.x |
| npm | 9.x (incluído no Node.js) |

---

## Instalação

```bash
cd liciteview-angular
npm install
```

> A pasta `node_modules` depende do sistema operacional. Não a copie de outra máquina:
> apague-a e rode `npm install` de novo.

---

## Rodando o projeto

```bash
npm start
```

O navegador abre em <http://localhost:4200>.

**Se a porta 4200 estiver ocupada**, o Angular sobe em uma porta aleatória, e o backend recusa as chamadas por CORS. Nesse caso, fixe a porta e inclua o endereço em `ALLOWED_ORIGINS`, no `.env` do backend:

```bash
npm start -- --port 4201
```

O frontend espera a API em `http://127.0.0.1:8000`. Para mudar, edite `src/environments/environment.ts`:

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
| `npm run build` | Build de produção na pasta `dist/` |
| `npx ngc -p tsconfig.app.json --noEmit` | Verifica tipos e templates sem gerar arquivos |

**Testes.** Existem arquivos `.spec.ts` para os serviços, mas o projeto ainda não tem executor de testes configurado (não há Karma nem script `npm test`).

---

## Estrutura do projeto

```text
src/
├── app/
│   ├── app.component.ts        # Componente raiz (RouterOutlet)
│   ├── app.config.ts           # Providers globais e interceptor HTTP
│   ├── app.routes.ts           # Rotas com authGuard (lazy loading)
│   ├── core/
│   │   ├── models/             # Interfaces TypeScript (Licitacao, Produto, Analise...)
│   │   ├── services/           # AuthService, LicitacaoService, EditalService, AnaliseService...
│   │   └── interceptors/       # Envia o token JWT em todas as requisições
│   ├── features/
│   │   ├── auth/               # Login e cadastro
│   │   ├── pesquisa/           # Busca de licitações com filtros do PNCP
│   │   ├── edital/             # Edital: Resumo / Viabilidade / Chat
│   │   ├── produtos/           # Lista e formulário de produtos (cadastro e edição)
│   │   └── historico/          # Editais abertos pelo usuário
│   └── layout/                 # Estrutura da aplicação e notificações
├── environments/
│   ├── environment.ts          # Desenvolvimento
│   └── environment.prod.ts     # Produção
└── styles.scss                 # Tema global
```

---

## Rotas da aplicação

| Rota | Tela |
| --- | --- |
| `/login` | Login |
| `/register` | Cadastro de fornecedor |
| `/pesquisa` | Busca de licitações (PNCP) |
| `/edital/:id` | Edital: Resumo, Viabilidade e Chat |
| `/produtos` | Lista de produtos do fornecedor |
| `/produtos/novo` | Cadastro de produto |
| `/produtos/:id/editar` | Edição de produto |
| `/historico` | Editais abertos pelo usuário, com status e classificação de viabilidade |

O `:id` do edital é o número de controle do PNCP, que contém uma barra. Em links montados à mão, a barra precisa estar codificada (`%2F`).

---

## Solução de problemas

**Cadastro ou login não funcionam, e o backend registra `OPTIONS ... 400`**
→ É CORS. O endereço do frontend, com a porta, não está em `ALLOWED_ORIGINS` no `.env` do backend. Ver "Rodando o projeto".

**`ng serve` falha ao iniciar depois de copiar o projeto de outra máquina**
→ A pasta `node_modules` veio de outro sistema operacional. Apague-a e rode `npm install`.

**Tela em branco após o login**
→ Abra o DevTools (F12) → Console e verifique se a API responde em <http://127.0.0.1:8000/health>.

**A tela do edital fica em "Processando" por muito tempo**
→ Confira no terminal do backend se o worker Celery está rodando. Ver o README do backend.

**`npm install` com erros**
→ Confirme Node.js 18 ou superior: `node -v`. Se necessário: `npm cache clean --force`.
