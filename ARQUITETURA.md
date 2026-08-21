# TaskAzRa — Arquitetura e Implementação

Documento técnico do sistema: como as peças se encaixam e por quê.

## 1. Visão geral

TaskAzRa é um gerenciador de tarefas compartilhado entre duas pessoas, com três formas de interação (site, bot do Telegram, lembretes automáticos) todas lendo e escrevendo no mesmo banco SQLite. Não há framework de frontend, não há ORM, e o bot não usa nenhuma lib de Telegram — tudo é feito com bibliotecas mínimas (`fastapi`, `uvicorn`, `requests`), replicando o padrão de um projeto anterior do autor.

```
                 ┌──────────────┐
                 │  frontend/   │  HTML/CSS/JS puro, servido como estático
                 │ (polling)    │  pelo próprio FastAPI
                 └──────┬───────┘
                        │ HTTP (fetch)
                        ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ bot/          │   │  backend/    │   │ scheduler/    │
│ telegram_bot  │──▶│  main.py     │◀──│ scheduler.py  │
│ (polling      │   │  (FastAPI)   │   │ (recorrência +│
│ getUpdates)   │   │              │   │  lembretes)   │
└──────┬────────┘   └──────┬───────┘   └──────┬────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                            │
                     ┌──────▼───────┐
                     │  common/db.py │
                     │ SQLite (raw   │
                     │ SQL, sem ORM) │
                     └───────────────┘
```

Os três processos (`api`, `bot`, `scheduler`) rodam de forma independente, orquestrados por `orchestrator.py` via `multiprocessing`. O bot acessa o banco **diretamente** (não passa pela API HTTP) — como é um único arquivo SQLite local e o volume de escrita é baixo (duas pessoas), isso evita uma camada HTTP extra sem risco prático de contenção.

## 2. Estrutura de pastas

```
TaskAzRa/
├── orchestrator.py        # sobe api + bot + scheduler como processos
├── config.json             # token do bot, portas, intervalos (gitignored)
├── config.example.json     # template do config.json
├── requirements.txt
├── common/
│   ├── db.py                # schema SQL + get_connection()/init_db()
│   ├── config.py             # carrega config.json
│   └── auth.py                # hash/verificação de PIN
├── backend/
│   ├── main.py               # app FastAPI, monta routers + frontend estático
│   ├── schemas.py             # modelos Pydantic (validação de request)
│   └── routers/
│       ├── users.py           # cadastro/login
│       ├── tasks.py           # tarefas + instâncias
│       ├── reports.py         # relatórios
│       └── reminders.py       # configuração de lembretes
├── bot/
│   └── telegram_bot.py       # polling getUpdates + comandos, acesso direto ao DB
├── scheduler/
│   └── scheduler.py           # gera instâncias periódicas + dispara lembretes
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js                 # fetch + polling, sem build step
└── data/
    └── taskazra.db             # arquivo SQLite (gitignored)
```

## 3. Modelo de dados

Todo o schema está em `common/db.py` (`SCHEMA_SQL`), criado via `CREATE TABLE IF NOT EXISTS` — sem migrations, porque o projeto é pequeno e roda local.

### `users`
Cadastro simples: `name`, `username` (único), `pin_hash`, `email`, `telegram_chat_id` (único, preenchido quando o usuário vincula a conta pelo bot).

### `tasks`
A "definição" de uma tarefa — não é a ocorrência em si. Campos principais:
- `type`: `unica` | `periodica` | `manual` — define o comportamento (ver seção 4).
- `recurrence_kind` / `recurrence_value`: só usados quando `type = 'periodica'`.
- `priority`: `baixa` | `media` | `alta`.
- `assigned_to`: dono da tarefa, ou `NULL` pra "qualquer um dos dois".
- `active`: permite desativar uma tarefa periódica sem apagar o histórico.

### `task_instances`
Cada **ocorrência concreta** de uma tarefa — é isso que aparece na lista de pendentes e o que se marca como concluído. Uma tarefa `unica` tem exatamente uma instância; uma `periodica` ganha uma nova instância a cada ciclo; uma `manual` ganha uma instância cada vez que é "ativada".
- `status`: `pendente` | `feito`.
- `completed_by` / `completed_at`: quem e quando concluiu — é o que alimenta os relatórios de tempo de conclusão.

### `reminder_configs`
Horários (`HH:MM`) em que cada usuário quer receber um resumo de pendências no Telegram. `last_sent_date` evita reenviar o mesmo lembrete duas vezes no mesmo dia.

### `task_comments`
Uma conversa por tarefa (não por instância): `task_id`, `user_id`, `text`, `created_at`. Qualquer um dos dois pode comentar, sem exigir vínculo com a tarefa.

### Confirmação de conclusão
`tasks.needs_confirmation` (checkbox na criação/edição) muda o que acontece quando a tarefa é marcada como feita: em vez de ir direto pra `status = 'feito'`, a instância vai pra `status = 'aguardando_confirmacao'` e grava `task_instances.confirmation_requested_by` (quem tentou concluir). Só quem criou a tarefa (`tasks.created_by`) pode resolver essa pendência — confirmando (`feito`, `completed_by` = quem originalmente pediu) ou devolvendo (`pendente`, limpa `confirmation_requested_by`/`completed_by`/`completed_at`). Os dois caminhos exigem um comentário, que é gravado em `task_comments` como parte da decisão.

**Por que separar `tasks` de `task_instances`?** Porque "a tarefa" (ex: "Limpar a casa, toda semana") e "a ocorrência de hoje dessa tarefa" são coisas diferentes — sem essa separação, tarefas recorrentes não teriam como ter várias execuções com históricos de conclusão independentes.

## 4. Lógica dos três tipos de tarefa

| Tipo | Quando gera instância | Onde está a lógica |
|---|---|---|
| `unica` | Na hora da criação (uma vez só) | `backend/routers/tasks.py::create_task` |
| `manual` | Quando o usuário manda `/ativar` (bot) ou `POST /tasks/{id}/ativar` (site) | `backend/routers/tasks.py::ativar_tarefa_manual` e `bot/telegram_bot.py::handle_ativar` |
| `periodica` | Automaticamente, pelo processo `scheduler` | `scheduler/scheduler.py::generate_periodic_instances` |

### Cálculo da próxima data (tarefas periódicas)

`scheduler.py::compute_next_due_date(recurrence_kind, recurrence_value, reference)`:
- **`intervalo_dias`**: `reference + N dias`.
- **`dia_fixo_mes`**: próximo dia `D` do mês (mês atual se `D` ainda não passou, senão mês seguinte; usa `calendar.monthrange` pra não estourar meses curtos).
- **`dia_semana`**: percorre os próximos 7 dias a partir de `reference` procurando o primeiro que bate com um dos códigos (`SEG,TER,QUA,QUI,SEX,SAB,DOM`).

A cada ciclo do scheduler (padrão: 60s, configurável em `config.json`), `generate_periodic_instances` roda para toda tarefa `periodica` ativa:
1. Busca a última instância dessa tarefa.
2. Se ela ainda está `pendente`, não faz nada (evita duplicar antes de concluir a atual).
3. Senão, calcula a referência (data da última instância, ou data de criação da tarefa se nunca gerou nenhuma) e a próxima data de vencimento.
4. Se a próxima data já chegou (`<= hoje`), cria a instância.

## 5. Backend (FastAPI)

`backend/main.py` monta os routers e, por último, monta `frontend/` como arquivos estáticos na raiz (`/`) — como os routers da API são registrados antes, eles têm prioridade sobre o catch-all de arquivos estáticos.

**Autenticação por sessão/token:** `POST /users` (cadastro) e `POST /users/login` são as únicas rotas públicas — todo o resto exige um header `Authorization: Bearer <token>`. O login gera um token opaco (`secrets.token_urlsafe(32)`) e grava uma linha em `sessions` (`token`, `user_id`); a dependency `backend/deps.py::get_current_user` resolve esse header pro usuário da sessão em cada request protegido, retornando 401 se o token não existir/expirar (na prática "expira" só quando alguém desloga, já que não há TTL — aceitável pro escopo doméstico). Ações que identificavam o usuário por um campo enviado pelo cliente (`created_by` em `POST /tasks`, `completed_by` em `POST /instances/{id}/feito`) passaram a usar o usuário autenticado — o cliente não escolhe mais "por quem" a ação é feita. Rotas com `{user_id}` no path (tema, vínculos) usam `require_self()` pra impedir que um usuário logado mexa na conta de outro.

Principais endpoints:

```
POST   /users                    cria usuário (hash do PIN) — público
POST   /users/login              valida usuário + PIN, cria sessão e retorna token — público
POST   /users/logout             invalida o token atual
GET    /users/me                 retorna o usuário da sessão atual
GET    /users                    lista usuários
PATCH  /users/{id}/theme         atualiza tema (só a própria conta)
POST   /users/{id}/links         vincula duas contas (só a própria conta)
GET    /users/{id}/links         lista vínculos (só a própria conta)
DELETE /users/{id}/links/{id}    desvincula (só a própria conta)

POST   /tasks                    cria tarefa (qualquer tipo); created_by vem da sessão
GET    /tasks                    lista tarefas
POST   /tasks/{id}/ativar        ativa instância de tarefa manual
GET    /tasks/{id}/comments      lista comentários da tarefa
POST   /tasks/{id}/comments      adiciona comentário na tarefa

GET    /instances                lista instâncias (filtros: status, assigned_to); inclui comment_count e dados de confirmação
POST   /instances/{id}/feito     marca instância como concluída (ou 'aguardando_confirmacao', se a tarefa exigir); completed_by vem da sessão
POST   /instances/{id}/confirmar confirma ou devolve uma instância aguardando confirmação (action: concluir|devolver, comment obrigatório) — só quem criou a tarefa

GET    /reports/completed        concluídas no período + tempo até concluir
GET    /reports/pending          pendentes ordenadas por tempo parado

POST   /reminders                cadastra horário de lembrete pra própria conta
GET    /reminders                lista lembretes da própria conta
```

Toda query usa SQL parametrizado (`?`) — nunca concatenação de string — pra evitar SQL injection, apesar do app ser local.

## 6. Bot do Telegram

`bot/telegram_bot.py` não usa nenhuma lib de bot. Duas funções fazem tudo:
- `api_call()` — `POST` genérico pra `https://api.telegram.org/bot{token}/{method}`.
- `send_message()` — atalho pra `sendMessage`.

O loop principal (`run()`) faz **long polling** em `getUpdates`, guardando o `offset` (id do último update processado) em memória — a cada chamada, o Telegram só devolve mensagens novas. Cada mensagem recebida vira uma chamada a `process_message()`, que:
1. Ignora tudo que não começa com `/`.
2. Trata `/start` e `/vincular` sem exigir usuário já vinculado (é como a conta se conecta ao chat).
3. Pra qualquer outro comando, busca o usuário pelo `telegram_chat_id`; se não achar, pede pra vincular primeiro.
4. Despacha pro handler correspondente (`handle_tarefas`, `handle_feito`, etc.), que lê/escreve direto no SQLite.

Erros de rede (`requests.RequestException`) fazem o loop esperar 5s e tentar de novo, em vez de derrubar o processo.

## 7. Scheduler

`scheduler/scheduler.py::run()` roda em loop infinito (intervalo configurável), e a cada ciclo:
1. `generate_periodic_instances(conn)` — cria novas ocorrências de tarefas periódicas que venceram.
2. `send_reminders(conn, token)` — para cada `reminder_config` cujo horário bate com o minuto atual e que ainda não foi disparado hoje, monta a lista de pendências do usuário e manda via Telegram, atualizando `last_sent_date`.

Como a checagem de horário compara `HH:MM` exato, o intervalo do scheduler precisa ser menor que 60s pra não pular o minuto configurado (o padrão de 60s tem uma pequena chance de desalinhar; se isso incomodar, baixar `scheduler_interval_seconds` pra 30 no `config.json` resolve).

## 8. Frontend

Sem build step, sem framework — só `index.html` + `style.css` + `app.js`, servidos como estático pelo FastAPI. `app.js`:
- Guarda o token de sessão no `localStorage` (`taskazra_token`) — não guarda mais um `user_id` livre. Ao abrir o site, se houver token salvo, chama `GET /users/me` pra validar; se inválido/expirado, cai na tela de login.
- Tela de login (`#login-screen`) fica visível até autenticar; o app (`#app-container`) só aparece depois. Cadastro de conta nova também mora nessa tela (alterna entre os formulários de login/cadastro).
- `api()` injeta `Authorization: Bearer <token>` em toda chamada quando há sessão ativa; um 401 de qualquer endpoint dispara logout automático (limpa o token e volta pra tela de login).
- Faz `fetch` direto pros endpoints da API (mesma origem, então sem CORS).
- **Polling**: `loadPendentes()` roda a cada 8 segundos (`POLL_INTERVAL_MS`), mesmo padrão usado no projeto anterior — sem WebSockets, sem Server-Sent Events, só requisição simples e repetida.

## 9. Orquestração de processos

`orchestrator.py` usa `multiprocessing.Process` pra subir três processos independentes (`api`, `bot`, `scheduler`), cada um rodando sua própria função `run()`. Um laço de supervisão verifica a cada 2s se todos continuam vivos; se qualquer um morrer, os demais são terminados (`SystemExit`). `Ctrl+C` (`KeyboardInterrupt`) encerra tudo de forma organizada, dando `terminate()` + `join(timeout=5)` em cada processo.

Não há Docker, containers ou orquestração cloud — igual ao projeto anterior, tudo roda como processos locais na mesma máquina.

## 10. Decisões de design e limitações conhecidas

- **Sem ORM (SQLAlchemy):** SQL escrito à mão em todas as queries, por decisão explícita — mantém consistência com o projeto anterior e evita uma dependência a mais.
- **Sem lib de bot:** implementação própria sobre a API HTTP do Telegram, mesmo padrão do projeto anterior.
- **Autenticação por token opaco sem expiração:** o token de sessão (`sessions.token`) não expira sozinho — só é invalidado no logout explícito. Simples e suficiente pro uso doméstico local, mas não tem rotação/TTL como um JWT teria; se o app crescer além de duas pessoas de confiança, vale revisitar.
- **Sem tela de cadastro de lembretes no site:** hoje só é possível via chamada direta à API (`POST /reminders`, autenticado). Pode virar uma tela simples no frontend depois, se fizer sentido.
- **Concorrência do SQLite:** com duas pessoas escrevendo esporadicamente, não há risco prático de lock; se o uso crescer muito, a migração natural seria trocar o arquivo SQLite por outro backend, mantendo a mesma camada de SQL cru.
