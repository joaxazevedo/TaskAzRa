# TaskAzRa — Guia do Usuário

Gerenciador de tarefas do dia a dia, com site local e bot no Telegram, feito pra organizar as atividades entre vocês dois.

## 1. Como rodar o sistema

1. Ative o ambiente virtual e instale as dependências (só na primeira vez):
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Para subir **só o site** (sem bot nem lembretes automáticos), não precisa de nenhuma configuração extra:
   ```
   python -m backend.main
   ```
   Acesse em **http://127.0.0.1:8284**. Pra desligar, `Ctrl+C`.
3. Para subir o **sistema completo** (site + bot do Telegram + lembretes automáticos), copie `config.example.json` para `config.json` e preencha o `telegram_bot_token` (peça um ao [@BotFather](https://t.me/BotFather) no Telegram, se ainda não tiver). Depois:
   ```
   python orchestrator.py
   ```
   Host, porta e demais ajustes já vêm com valores padrão prontos para uso — só é preciso mexer no `config.json` se quiser mudá-los ou ligar o bot.

## 2. Primeiro acesso

Na tela inicial do site, clique em **"Cadastre-se"** e crie sua conta (nome, usuário, PIN, e-mail opcional). Repita pra sua esposa. Depois, cada um faz **login** com seu próprio usuário e PIN — o site não deixa mais escolher livremente "quem está usando" num seletor; é preciso saber a senha da conta.

Depois de logado, vá até a aba **Usuários** e vincule sua conta à da sua esposa (e vice-versa, cada um vincula pelo próprio login). Esse vínculo é obrigatório: só é possível atribuir uma tarefa a alguém que esteja vinculado a você (ou a si mesmo).

## 3. Usando o site

- **Login:** entra com usuário + PIN. A sessão fica salva no navegador (não precisa logar de novo toda vez que abrir o site) até você clicar em **Sair**.
- **Pendentes:** lista tudo que está aberto, com prioridade destacada por cor (verde = baixa, laranja = média, vermelho = alta). Clique em **Concluir** pra marcar como feita.
  - Cada tarefa tem um botão **💬 N** que abre um bloco de comentários — histórico da conversa sobre aquela tarefa, com campo pra adicionar um novo a qualquer momento.
- **Nova tarefa:** formulário pra criar uma tarefa. Escolha o tipo:
  - **Única** — tarefa pontual, some da lista quando concluída.
  - **Periódica** — se repete automaticamente. Escolha:
    - *A cada X dias* (ex: a cada 3 dias)
    - *Dia fixo do mês* (ex: todo dia 15)
    - *Dias da semana* (marque os dias direto nos checkboxes)
  - **Ativação manual** — não aparece sozinha; você "ativa" ela quando precisar (ex: "Tirar o lixo" só quando o lixo estiver cheio).
  - Você também escolhe a **prioridade** (baixa/média/alta) e o **responsável** (só você mesmo ou alguém vinculado a você — ou deixa "Todos" pra ficar visível pros dois).
  - Marque **"Precisa de confirmação..."** se quiser que, ao ser concluída, a tarefa não feche na hora — ela fica esperando você (quem criou) confirmar ou devolver.
- **Confirmar:** aba que só aparece quando você tem tarefas suas aguardando confirmação (alguém marcou como feita e está esperando você validar). Pra cada uma, você escreve um comentário (obrigatório) e escolhe **Confirmar** (fecha a tarefa) ou **Devolver para pendências** (volta a valer como pendente).
- **Relatórios:** duas listas —
  - **Concluídas:** filtra por período e mostra quanto tempo cada tarefa levou até ser concluída.
  - **Pendentes:** mostra o que está em aberto, ordenado pelas que estão paradas há mais tempo.
- **Usuários:** mostra todos os usuários cadastrados e permite vincular/desvincular sua conta com a de outra pessoa (só dá pra atribuir tarefa a quem está vinculado). Cadastro de conta nova é feito na tela de login, não aqui.
- **Tema:** o botão 🌙/☀️ no topo alterna entre claro e escuro — a preferência fica salva na sua conta.

O site atualiza a lista de pendentes automaticamente a cada poucos segundos — não precisa dar F5.

## 4. Usando o bot no Telegram

1. Procure o seu bot no Telegram (o nome que você configurou no @BotFather) e mande `/start`. Ele vai te devolver o seu `chat_id`.
2. Vincule sua conta ao chat mandando:
   ```
   /vincular seu_usuario 1234
   ```
   (troque pelo usuário e PIN cadastrados)
3. A partir daí, os comandos disponíveis são:

| Comando | O que faz |
|---|---|
| `/tarefas` | Lista suas tarefas pendentes |
| `/feito <id>` | Marca a tarefa como concluída (o id aparece na listagem) |
| `/nova <título>` | Cria uma tarefa única |
| `/manual <título>` | Cria uma tarefa de ativação manual |
| `/ativar <id_da_tarefa>` | Ativa uma instância de uma tarefa manual existente |
| `/comentar <id> <texto>` | Adiciona um comentário na tarefa (usa o mesmo id que aparece em `/tarefas`) |
| `/ajuda` | Mostra os comandos disponíveis |

> Tarefas periódicas ainda não têm um comando dedicado no bot — crie pelo site na aba "Nova tarefa". O mesmo vale pra confirmar/devolver uma tarefa que precisa de confirmação — isso só é feito pelo site, na aba "Confirmar".

## 5. Lembretes automáticos

Você pode configurar horários em que o bot te manda um resumo das tarefas pendentes. Por enquanto isso é feito pela API (uma tela no site pra isso ainda não existe):

```
POST http://127.0.0.1:8284/reminders
Authorization: Bearer <token retornado no login>
{
  "hour": "09:00"
}
```

Isso faz o bot te mandar, todo dia às 9h, a lista de tarefas pendentes atribuídas a você (ou sem responsável definido). Pode cadastrar quantos horários quiser por pessoa. O `token` é obtido fazendo login (`POST /users/login`) — o mesmo usado pelo site.

## 6. Perguntas comuns

**Preciso deixar o computador ligado pro bot funcionar?**
Sim, por enquanto o sistema roda local — o `orchestrator.py` precisa estar rodando pra API, o bot e os lembretes funcionarem.

**Esqueci o PIN, e agora?**
Ainda não existe recuperação de PIN pelo site/bot. É preciso reeditar o registro do usuário direto no banco (ou recriar o usuário).

**Uma tarefa periódica não apareceu na data certa, por quê?**
O gerador de tarefas periódicas roda em ciclos (a cada 60 segundos, por padrão) e só cria a próxima ocorrência quando a anterior já foi concluída (ou não existe nenhuma ainda). Se a tarefa atual está pendente, a próxima só é gerada depois que ela for marcada como feita.
