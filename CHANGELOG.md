# Changelog

Todas as mudanças notáveis do TaskAzRa são registradas aqui.

## [0.15.2] - 2026-08-20
### Corrigido
- `GET /tags` (usado no autocomplete do campo de tags em Nova tarefa/Editar) agora só retorna tags de tarefas com pelo menos uma instância pendente — tags cujas tarefas já foram todas concluídas não aparecem mais como sugestão.

## [0.15.1] - 2026-08-20
### Adicionado
- Suporte a banco de testes separado via variável de ambiente `TASKAZRA_DB_PATH`, pra rodar verificações sem sujar o banco real (`data/taskazra.db`).

## [0.15.0] - 2026-08-20
### Adicionado
- Seletor "Agrupar por" na tela de Pendentes, permitindo alternar entre agrupar por prioridade (padrão) ou por tags. Uma tarefa com várias tags aparece em cada grupo correspondente; tarefas sem tag ficam num grupo "Sem tag". A escolha fica salva no navegador.

## [0.14.3] - 2026-08-13
### Corrigido
- Bloco de comentários de uma tarefa fechava sozinho no próximo refresh automático (a cada 8s) se você tivesse aberto ele mas não estivesse com o campo de texto focado. Agora o bloco permanece aberto até ser fechado manualmente, independente do polling.

## [0.14.2] - 2026-08-13
### Alterado
- Ao confirmar ou devolver a última tarefa pendente de confirmação, a tela volta automaticamente para "Tarefas".

## [0.14.1] - 2026-08-13
### Corrigido
- Na tela de Confirmar, os botões "Concluir"/"Devolver para pendências" ficavam colados no campo de comentário. Adicionado espaçamento entre eles.

## [0.14.0] - 2026-08-13
### Adicionado
- Tarefas podem exigir confirmação de quem criou pra serem concluídas: checkbox "Precisa de confirmação..." na criação/edição da tarefa. Ao marcar uma dessas como feita (no site ou pelo `/feito` do bot), ela vai para o status "aguardando confirmação" em vez de concluir direto.
- Novo botão "Confirmar" na navegação do site, visível só quando existem tarefas suas aguardando confirmação. Na tela, quem criou a tarefa pode confirmar a conclusão ou devolvê-la para pendências — nos dois casos um comentário é obrigatório.
- Novo endpoint `POST /instances/{id}/confirmar` (`action`: `concluir` ou `devolver`, `comment` obrigatório), com checagem de que só quem criou a tarefa pode confirmar. `GET /instances` agora aceita `status=aguardando_confirmacao` e retorna `confirmation_requested_by`/`confirmation_requested_by_name`.

## [0.13.1] - 2026-08-13
### Corrigido
- Refresh automático da tela de Tarefas (a cada 8s) recriava a lista inteira e apagava o que você estava digitando num comentário no meio da tarefa. O polling agora pausa sozinho enquanto o campo de comentário está focado, e retoma ao sair dele.

## [0.13.0] - 2026-08-13
### Adicionado
- Comentários nas tarefas — uma conversa por atividade. No site, botão "💬 N" em cada card abre uma seção expansível com o histórico e um campo pra adicionar novo comentário (carregado sob demanda, só ao abrir pela primeira vez). No bot do Telegram, `/comentar <id> <texto>` adiciona um comentário na tarefa (usa o mesmo id que aparece em `/tarefas`).
- Novos endpoints: `GET /tasks/{id}/comments` e `POST /tasks/{id}/comments`; `GET /instances` passou a incluir `comment_count` por tarefa.

## [0.12.0] - 2026-08-13
### Adicionado
- Busca por texto no `/tarefas`: qualquer texto sem `#` filtra por trecho do título (substring, não palavra inteira — `ver` encontra "verificar" e "versão").

### Alterado
- Filtro por múltiplas tags no `/tarefas` mudou de E (precisa ter todas) pra OU (basta ter pelo menos uma). Texto e tags podem ser combinados no mesmo comando (`/tarefas ver #tech`), aplicados em conjunto.

## [0.11.0] - 2026-08-13
### Adicionado
- Filtro por tags no `/tarefas` do bot: `/tarefas #urgente` lista só as tarefas pendentes com essa tag; com múltiplas tags (`/tarefas #mercado #urgente`) exige que a tarefa tenha todas elas (E, não OU). Sem argumento continua listando tudo como antes.

## [0.10.1] - 2026-08-13
### Alterado
- Campo de busca da tela de Tarefas perdeu o label "Buscar" ao lado — o texto agora fica só como placeholder dentro do próprio campo.

## [0.10.0] - 2026-08-13
### Adicionado
- Campo de busca ao lado do filtro de Responsável na tela de Tarefas, filtrando por título em tempo real. Só pesquisa entre as tarefas ativas/pendentes já carregadas — não busca nas concluídas. Filtragem 100% no navegador (sem round-trip à API a cada tecla).

## [0.9.1] - 2026-08-13
### Corrigido
- Título "Nova tarefa"/"Editar tarefa" ficava alinhado à esquerda da página inteira, enquanto o formulário abaixo estava centralizado em 700px — visualmente desalinhados. Título agora usa a mesma largura/centralização do formulário.

## [0.9.0] - 2026-08-13
### Adicionado
- Tags nas atividades — estrutura de dados (`tags` + `task_tags`, nomes únicos sem diferenciar maiúsculas/minúsculas) pronta pra servir de base a filtros futuros.
- Campo "Tags" no formulário de nova tarefa/edição (separadas por vírgula, com sugestão automática das tags já usadas via `<datalist>`).
- Tags exibidas como badges nos cards da tela de Tarefas.
- No bot do Telegram, `/nova` aceita hashtags no texto (ex: `/nova Comprar leite #mercado #urgente`) — extraídas automaticamente do título e salvas como tags; aparecem também no `/tarefas`.
- Novos endpoints: `GET /tags` (lista todas as tags existentes), `tags` aceito em `POST /tasks` e `PATCH /tasks/{id}`, e `GET /tasks/{id}`/`GET /instances` retornam as tags de cada tarefa.

## [0.8.4] - 2026-08-13
### Corrigido
- Formulário de "Nova tarefa"/edição tinha ficado estreito demais (480px) quando limitamos a largura dos formulários pra caber a tela mais larga do layout responsivo. Voltou pra uma largura mais confortável (700px, centralizado na página), próxima do tamanho original; os demais formulários (login, cadastro, vínculo) continuam em 480px.

## [0.8.3] - 2026-08-13
### Adicionado
- Botão "▾ Recolher" / "▸ Expandir" pra compactar o bloco "Concluídas nos últimos 7 dias".

### Alterado
- Lista de "Concluídas nos últimos 7 dias" limitada a 9 itens (os mais recentes); quando há mais, o título mostra "(9 de N)".

## [0.8.2] - 2026-08-13
### Alterado
- Cabeçalho (nome do sistema + menu de navegação) agora fica fixo no topo ao rolar a página, em vez de sumir de vista em listas longas.

## [0.8.1] - 2026-08-13
### Alterado
- Termo "Qualquer um" trocado por "Todos" no seletor de responsável e nos cards de tarefa sem responsável definido.

## [0.8.0] - 2026-08-13
### Alterado
- Tela de Tarefas pendentes passou a separar as tarefas em três grades independentes por prioridade (Alta, Média, Baixa), cada uma com seu próprio título. Antes era uma grade única contínua, onde tarefas de prioridade menor podiam "subir" pra preencher espaço vazio numa linha de prioridade maior — agora cada grupo reserva sua própria linha, ficando vazio se não tiver itens suficientes pra completar.

## [0.7.2] - 2026-08-13
### Alterado
- Cards de tarefa aumentados (320-420px → 480-620px) pra resultar em ~2 colunas confortáveis na maioria das telas largas, em vez de várias colunas compactadas.

## [0.7.1] - 2026-08-13
### Corrigido
- Grid responsivo de tarefas sobrava muita margem lateral em monitores ultrawide (o `main` ficava limitado a 1200px fixos). Largura máxima do `main` passou a ser fluida (`min(2000px, 95vw)`), e os cards de tarefa ganharam um tamanho máximo (320-420px) em vez de esticar pra preencher o espaço — assim aparecem mais colunas compactas ao invés de poucas colunas esticadas.

## [0.7.0] - 2026-08-13
### Alterado
- Listas de tarefas (pendentes, concluídas recentes, relatórios) agora usam layout em grid responsivo — em telas largas (monitor) mostram automaticamente 2+ colunas, no celular voltam pra 1 coluna, sem precisar de configuração manual (CSS `auto-fill`/`minmax`, sem JS). `main` ficou mais largo (1200px) pra caber as colunas extras; formulários mantidos numa largura confortável (480px) pra não ficarem esparsos.

## [0.6.6] - 2026-08-13
### Alterado
- Filtro "Responsável" da tela de Tarefas movido pra direita do título "Tarefas pendentes", na mesma linha, em vez de ficar numa linha separada abaixo.

## [0.6.5] - 2026-08-13
### Alterado
- Bloco de data limite reorganizado numa linha só ("Definir data limite: [checkbox] [data]"), em vez de dois campos empilhados verticalmente.

## [0.6.4] - 2026-08-13
### Corrigido
- Campo de data limite (na criação e edição de tarefas) não abria o seletor visual de calendário ao clicar — em navegadores baseados em Chromium, `<input type="date">` só abre o componente nativo se o clique acertar o pequeno ícone no canto, senão só permite digitar. Agora o clique em qualquer parte do campo chama `showPicker()` pra abrir o calendário.

## [0.6.3] - 2026-08-13
### Adicionado
- Tarefas com data limite agora mostram `[Limite: MM-DD]` (ou `[Limite: AA-MM-DD]` se o vencimento for em outro ano) ao lado da prioridade, tanto no `/tarefas` quanto nos lembretes automáticos do bot.

## [0.6.2] - 2026-08-13
### Alterado
- Lista de tarefas do bot (`/tarefas`) e o resumo enviado nos lembretes automáticos passaram a ordenar por prioridade (alta → média → baixa) e depois por id, igual já acontecia na tela de Tarefas do site.

## [0.6.1] - 2026-08-13
### Corrigido
- Data limite não aparecia no formulário de edição de tarefas únicas (o bloco de data ficava sempre escondido nesse fluxo). Agora, ao editar uma tarefa única, o campo de prazo aparece pré-preenchido com o valor atual (se houver), e pode ser adicionado, alterado ou removido. `GET /tasks/{id}` passou a incluir o `due_date` da instância pendente mais recente; `PATCH /tasks/{id}` atualiza esse prazo.

## [0.6.0] - 2026-08-13
### Adicionado
- Botão de edição (ícone ✏️ pequeno) antes do "Concluir" em cada tarefa pendente. Abre o formulário de "Nova tarefa" reaproveitado em modo de edição, permitindo alterar título, descrição, prioridade e responsável. Tipo e recorrência não são editáveis por enquanto (o formulário trava o campo "Tipo" durante a edição).
- Novos endpoints `GET /tasks/{id}` e `PATCH /tasks/{id}`, com a mesma regra de autorização de vínculo usada na criação (só é possível atribuir a si mesmo ou a um usuário vinculado).

## [0.5.4] - 2026-08-12
### Corrigido
- `/nova` no bot do Telegram mostrava o id da **tarefa** (`tasks.id`) na confirmação, mas `/tarefas` e `/feito` trabalham com o id da **instância** (`task_instances.id`) — sequências diferentes, então o número mostrado ao criar não batia com o número usado pra concluir. Agora `/nova` mostra o id da instância, que é o mesmo usado em `/tarefas` e aceito por `/feito`.

## [0.5.3] - 2026-08-12
### Alterado
- Linhas "Concluída por" e "Concluída/Concluído em" dos cards de tarefas concluídas unificadas numa só ("Concluída por X em Y"), corrigindo também uma inconsistência de gênero gramatical entre as duas listas.

## [0.5.2] - 2026-08-12
### Alterado
- Id da tarefa movido pra antes do título nos cards ("#5 - Comprar pão"), em vez de aparecer numa linha separada abaixo.

## [0.5.1] - 2026-08-12
### Alterado
- Cards de tarefas (pendentes, concluídas recentes, e as duas listas da aba Relatórios) reformatados: prioridade não aparece mais por escrito (a cor da borda já indica) e cada informação (id, prazo, criação, responsável, conclusão, tempo) ficou em sua própria linha, em vez de tudo junto separado por "·".

## [0.5.0] - 2026-08-12
### Adicionado
- Campo de data limite para tarefas únicas: checkbox "Definir data limite" abaixo do seletor de tipo, com o campo de data desabilitado até marcar. Ao trocar o tipo pra periódica/manual, esse bloco é substituído pelos campos específicos de cada tipo. Backend valida formato e impede data no passado; `due_date` só é aceito para tarefas do tipo `unica`.

## [0.4.2] - 2026-08-12
### Alterado
- Opção "Qualquer um (nós dois)" no seletor de responsável simplificada pra só "Qualquer um".

## [0.4.1] - 2026-08-12
### Corrigido
- Tela de login estava herdando o tema salvo do último usuário que tinha logado no navegador (ex: se a última conta usava tema claro, a tela de entrada aparecia clara mesmo com o padrão sendo escuro). Agora a tela de login/logout sempre força o tema escuro, independente de qualquer preferência de conta salva em cache.

## [0.4.0] - 2026-08-12
### Adicionado
- Botões "A-"/"A+" ao lado do seletor de tema pra aumentar/diminuir o tamanho da fonte do site (80% a 160%, em passos de 10%). Preferência salva no navegador (`localStorage`), aplicada antes da renderização pra não piscar no tamanho errado ao carregar.

## [0.3.5] - 2026-08-12
### Corrigido
- Card de tarefa concluída mostrava o **responsável designado** (que costuma ser "Qualquer um" quando a tarefa não tem dono fixo), o que não fazia sentido numa lista de concluídas. Agora mostra "concluída por: <nome>", com quem de fato marcou a tarefa como feita (`completed_by`).

## [0.3.4] - 2026-08-12
### Alterado
- Cards de tarefas concluídas (na aba Relatórios e na lista "Concluídas nos últimos 7 dias") passaram a mostrar o id da tarefa e o responsável, igual já acontecia nos cards de pendentes.

## [0.3.3] - 2026-08-12
### Adicionado
- Bot passou a logar no console toda mensagem recebida do Telegram (chat_id, remetente, texto) e toda resposta enviada, com timestamp.

### Corrigido
- Saída dos processos `bot` e `scheduler` (e do próprio `orchestrator.py`) ficava presa em buffer quando redirecionada pra arquivo/log, aparecendo só depois de um tempo (ou nunca, até o processo encerrar). Agora roda com `PYTHONUNBUFFERED=1` e todos os `print()` usam `flush=True`.

## [0.3.2] - 2026-08-12
### Corrigido
- Tarefas periódicas não geravam nenhuma instância na criação — ficavam invisíveis na lista de Tarefas até o processo `scheduler` calcular a primeira ocorrência, o que nunca acontece se só a API estiver rodando (`python -m backend.main`, sem `orchestrator.py`). Agora a primeira ocorrência é criada junto com a tarefa, igual já acontecia com tarefas únicas.

## [0.3.1] - 2026-08-12
### Alterado
- Tema escuro passou a ser o padrão desde a tela de login (antes seguia a preferência do sistema operacional). Contas novas também nascem com tema escuro por padrão; após o login, a preferência salva de cada usuário continua prevalecendo.

## [0.3.0] - 2026-08-12
### Adicionado
- Filtro por pessoa na tela de Tarefas — só aparecem no seletor o próprio usuário e quem estiver vinculado a ele. Novo parâmetro `assigned_to_exact` em `GET /instances`, com a mesma verificação de vínculo usada na criação de tarefas (403 se tentar filtrar por alguém não vinculado).
- Lista "Concluídas nos últimos 7 dias" logo abaixo das tarefas pendentes na tela de Tarefas, usando `GET /reports/completed` com a data de início calculada automaticamente.

## [0.2.1] - 2026-08-12
### Alterado
- Lista de tarefas (`GET /instances`) agora ordena por prioridade (alta → média → baixa) e, dentro de cada prioridade, por data de criação.
- Botão de navegação "Pendentes" renomeado para "Tarefas".
- Ao criar uma tarefa, o site volta automaticamente pra tela de Tarefas em vez de ficar no formulário.
- Card de cada tarefa passou a mostrar data de criação, quem criou e o responsável.

## [0.2.0] - 2026-08-12
### Adicionado
- Login de verdade com PIN: antes qualquer pessoa podia agir como qualquer usuário só escolhendo num seletor no site, sem senha. Agora existe uma tela de login/cadastro, sessão por token (`POST /users/login` retorna um token, guardado no navegador), e todos os endpoints (exceto cadastro e login) exigem `Authorization: Bearer <token>`.
- `created_by` e `completed_by` deixaram de ser enviados pelo cliente — o backend sempre usa o usuário da sessão autenticada, fechando a brecha de um usuário criar/concluir tarefas em nome de outro.
- Ações sobre a própria conta (tema, vínculos) agora verificam que o usuário logado só mexe na própria conta (`require_self`), retornando 403 caso contrário.
- Botão "Sair" no site, que encerra a sessão (invalida o token no servidor).

### Alterado
- Tela "Usuários" do site perdeu o formulário de cadastro (movido pra tela de login, já que precisa funcionar antes de autenticar) — continua com a lista de usuários e o gerenciamento de vínculos.

## [0.1.3] - 2026-08-12
### Corrigido
- `POST /tasks` e `POST /instances/{id}/feito` quebravam com erro 500 (`sqlite3.IntegrityError: FOREIGN KEY constraint failed`) quando o usuário salvo no navegador não existia mais no banco (ex: banco resetado). Agora retorna um erro 404 tratável, e o site se recupera sozinho limpando o usuário salvo localmente e recarregando a lista de usuários.

## [0.1.2] - 2026-08-12
### Corrigido
- Valor de "dia do mês" na recorrência não era validado (aceitava qualquer número, ex: 99) — agora o backend exige um valor entre 1 e 31, e o frontend valida antes de enviar. Mesma validação passou a existir para "a cada X dias" (>= 1) e "dias da semana" (códigos válidos).
- Data de fim da recorrência não tinha limites — agora não pode ser no passado nem passar de 10 anos a partir de hoje, validado tanto no backend quanto no seletor de data do site.

## [0.1.1] - 2026-08-12
### Corrigido
- Trocado `@app.on_event("startup")` (depreciado) pelo padrão `lifespan` do FastAPI.

## [0.1] - 2026-08-12
### Adicionado
- Estrutura inicial do projeto: banco SQLite (SQL puro, sem ORM), backend FastAPI, bot do Telegram via `requests` puro, scheduler de recorrências/lembretes, frontend HTML/CSS/JS puro com polling, orquestração via `orchestrator.py`.
- Cadastro de usuários com PIN, vínculo entre usuários (só é possível atribuir tarefa a si mesmo ou a alguém vinculado).
- Três tipos de tarefa: única, periódica (intervalo de dias, dia fixo do mês, dias da semana) e ativação manual.
- Limite de recorrência por data de fim ou número de repetições.
- Relatórios de tarefas concluídas (com tempo até concluir) e pendentes (com tempo parado).
- Tema claro/escuro, salvo por usuário no banco.
- Número de versão exposto em `/version` e exibido no site.
