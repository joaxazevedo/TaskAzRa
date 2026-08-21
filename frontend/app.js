const API = "";
const POLL_INTERVAL_MS = 8000;

let token = localStorage.getItem("taskazra_token");
let currentUser = null;
let editingTaskId = null;
let isComposingComment = false;
let users = [];

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(API + path, { headers, ...options });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    if (resp.status === 401) {
      // Sessão inválida/expirada: derruba pra tela de login.
      logoutLocal();
    }
    throw new Error(body.detail || `Erro ${resp.status}`);
  }
  return resp.status === 204 ? null : resp.json();
}

function priorityClass(priority) {
  return `priority-${priority}`;
}

// ---------- Autenticação ----------
function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app-container").classList.remove("hidden");
}

function showLogin() {
  document.getElementById("app-container").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
  // A tela de entrada é neutra: sempre escura por padrão, independente do
  // tema salvo pelo último usuário que fez login neste navegador.
  applyTheme("dark");
}

function logoutLocal() {
  token = null;
  currentUser = null;
  localStorage.removeItem("taskazra_token");
  showLogin();
}

document.getElementById("show-register-btn").addEventListener("click", () => {
  document.getElementById("login-form").classList.add("hidden");
  document.getElementById("register-form").classList.remove("hidden");
  document.getElementById("show-register-btn").classList.add("hidden");
  document.getElementById("show-login-btn").classList.remove("hidden");
});

document.getElementById("show-login-btn").addEventListener("click", () => {
  document.getElementById("register-form").classList.add("hidden");
  document.getElementById("login-form").classList.remove("hidden");
  document.getElementById("show-login-btn").classList.add("hidden");
  document.getElementById("show-register-btn").classList.remove("hidden");
});

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("login-username").value;
  const pin = document.getElementById("login-pin").value;
  try {
    const data = await api("/users/login", {
      method: "POST",
      body: JSON.stringify({ username, pin }),
    });
    token = data.token;
    currentUser = data.user;
    localStorage.setItem("taskazra_token", token);
    document.getElementById("login-form").reset();
    await afterLogin();
  } catch (err) {
    alert(`Erro ao entrar: ${err.message}`);
  }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    name: document.getElementById("register-name").value,
    username: document.getElementById("register-username").value,
    pin: document.getElementById("register-pin").value,
    email: document.getElementById("register-email").value || null,
  };
  try {
    await api("/users", { method: "POST", body: JSON.stringify(payload) });
    e.target.reset();
    alert("Conta criada! Agora faça login.");
    document.getElementById("show-login-btn").click();
    document.getElementById("login-username").value = payload.username;
  } catch (err) {
    alert(`Erro ao cadastrar: ${err.message}`);
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await api("/users/logout", { method: "POST" });
  } catch (err) {
    // ignora falha de rede no logout, limpa localmente de qualquer forma
  }
  logoutLocal();
});

// ---------- Tema ----------
// A preferência de tema é salva no cadastro do usuário (banco de dados).
// O localStorage só guarda um cache do último tema aplicado, pra evitar
// flash de tema errado antes do login terminar de carregar.
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.getElementById("theme-toggle").textContent = theme === "dark" ? "☀️" : "🌙";
  localStorage.setItem("taskazra_theme_cache", theme);
}

document.getElementById("theme-toggle").addEventListener("click", async () => {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  applyTheme(next);

  if (!currentUser) return;
  currentUser.theme = next;
  try {
    await api(`/users/${currentUser.id}/theme`, {
      method: "PATCH",
      body: JSON.stringify({ theme: next }),
    });
  } catch (err) {
    alert(`Erro ao salvar tema: ${err.message}`);
  }
});

applyTheme(document.documentElement.getAttribute("data-theme") || "light");

// ---------- Tamanho da fonte ----------
const FONT_SCALE_MIN = 80;
const FONT_SCALE_MAX = 160;
const FONT_SCALE_STEP = 10;

function getFontScale() {
  const current = parseInt(document.documentElement.style.fontSize, 10);
  return Number.isFinite(current) ? current : 100;
}

function setFontScale(scale) {
  const clamped = Math.min(FONT_SCALE_MAX, Math.max(FONT_SCALE_MIN, scale));
  document.documentElement.style.fontSize = `${clamped}%`;
  localStorage.setItem("taskazra_font_scale", String(clamped));
}

document.getElementById("font-increase-btn").addEventListener("click", () => {
  setFontScale(getFontScale() + FONT_SCALE_STEP);
});

document.getElementById("font-decrease-btn").addEventListener("click", () => {
  setFontScale(getFontScale() - FONT_SCALE_STEP);
});

// ---------- Navegação ----------
function switchView(viewName) {
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  document.querySelector(`.nav-btn[data-view="${viewName}"]`).classList.add("active");
  document.getElementById(`view-${viewName}`).classList.remove("hidden");
  if (viewName === "relatorios") {
    loadReports();
  }
  if (viewName === "usuarios") {
    loadAllUsersList();
    loadLinksView();
  }
  if (viewName === "confirmar") {
    loadConfirmacoes();
  }
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.view === "nova") {
      resetTaskFormToCreateMode();
    }
    switchView(btn.dataset.view);
  });
});

function parseTagsInput() {
  const raw = document.getElementById("task-tags").value;
  const seen = new Set();
  const tags = [];
  raw.split(",").forEach((part) => {
    const tag = part.trim();
    if (tag && !seen.has(tag.toLowerCase())) {
      seen.add(tag.toLowerCase());
      tags.push(tag);
    }
  });
  return tags;
}

async function loadTagsDatalist() {
  try {
    const tags = await api("/tags");
    const datalist = document.getElementById("tags-datalist");
    datalist.innerHTML = tags.map((t) => `<option value="${t.name}">`).join("");
  } catch (err) {
    // não crítico, silenciosamente ignora
  }
}

function resetTaskFormToCreateMode() {
  editingTaskId = null;
  document.getElementById("task-form-title").textContent = "Nova tarefa";
  document.getElementById("task-form-submit-btn").textContent = "Criar tarefa";
  document.getElementById("task-form").reset();
  document.getElementById("task-type").disabled = false;
  document.getElementById("recurrence-fields").classList.add("hidden");
  document.getElementById("due-date-fields").classList.remove("hidden");
  document.getElementById("due-date").disabled = true;
  resetRecurrenceFields();
}

async function startEditTask(taskId) {
  const task = await api(`/tasks/${taskId}`);
  await refreshAssignedOptions();

  editingTaskId = taskId;
  document.getElementById("task-title").value = task.title;
  document.getElementById("task-description").value = task.description || "";
  document.getElementById("task-priority").value = task.priority;
  document.getElementById("task-assigned").value = task.assigned_to || "";
  document.getElementById("task-tags").value = (task.tags || []).join(", ");
  document.getElementById("task-needs-confirmation").checked = Boolean(task.needs_confirmation);

  document.getElementById("task-type").value = task.type;
  document.getElementById("task-type").disabled = true;
  document.getElementById("recurrence-fields").classList.add("hidden");

  const dueDateFields = document.getElementById("due-date-fields");
  const hasDueDateCheckbox = document.getElementById("has-due-date");
  const dueDateInput = document.getElementById("due-date");
  if (task.type === "unica") {
    dueDateFields.classList.remove("hidden");
    hasDueDateCheckbox.checked = Boolean(task.due_date);
    dueDateInput.disabled = !task.due_date;
    dueDateInput.value = task.due_date || "";
  } else {
    dueDateFields.classList.add("hidden");
  }

  document.getElementById("task-form-title").textContent = `Editar tarefa #${taskId}`;
  document.getElementById("task-form-submit-btn").textContent = "Salvar alterações";

  switchView("nova");
}

document.getElementById("task-type").addEventListener("change", (e) => {
  document.getElementById("recurrence-fields").classList.toggle("hidden", e.target.value !== "periodica");
  // Data limite só faz sentido pra tarefa única; nos outros tipos ela é
  // substituída pelos campos específicos (recorrência, ou nenhum campo extra).
  document.getElementById("due-date-fields").classList.toggle("hidden", e.target.value !== "unica");
});

// ---------- Data limite (tarefas únicas) ----------
document.getElementById("has-due-date").addEventListener("change", (e) => {
  const dueDateInput = document.getElementById("due-date");
  dueDateInput.disabled = !e.target.checked;
  if (!e.target.checked) {
    dueDateInput.value = "";
  }
});

// ---------- Campos de recorrência ----------
function toggleRecurrenceValueFields() {
  const kind = document.getElementById("recurrence-kind").value;
  document.getElementById("recurrence-interval-wrapper").classList.toggle("hidden", kind !== "intervalo_dias");
  document.getElementById("recurrence-month-day-wrapper").classList.toggle("hidden", kind !== "dia_fixo_mes");
  document.getElementById("recurrence-weekday-wrapper").classList.toggle("hidden", kind !== "dia_semana");
}

document.getElementById("recurrence-kind").addEventListener("change", toggleRecurrenceValueFields);
toggleRecurrenceValueFields();

function toggleRecurrenceEndFields() {
  const endType = document.getElementById("recurrence-end-type").value;
  document.getElementById("recurrence-end-date-wrapper").classList.toggle("hidden", endType !== "date");
  document.getElementById("recurrence-end-count-wrapper").classList.toggle("hidden", endType !== "count");
}

document.getElementById("recurrence-end-type").addEventListener("change", toggleRecurrenceEndFields);
toggleRecurrenceEndFields();

// Data de fim da recorrência: não pode ser no passado nem passar de 10 anos
(function setupRecurrenceEndDateLimits() {
  const input = document.getElementById("recurrence-end-date");
  const today = new Date();
  const maxDate = new Date(today);
  maxDate.setFullYear(maxDate.getFullYear() + 10);

  const toISODate = (d) => d.toISOString().split("T")[0];
  input.min = toISODate(today);
  input.max = toISODate(maxDate);
})();

// Em navegadores baseados em Chromium, clicar num <input type="date"> fora do
// pequeno ícone do calendário só deixa digitar, sem abrir o seletor visual.
// Forçamos a abertura do componente nativo ao clicar em qualquer parte do campo.
function attachDatePicker(input) {
  input.addEventListener("click", () => {
    if (!input.disabled && typeof input.showPicker === "function") {
      try {
        input.showPicker();
      } catch (err) {
        // ignora navegadores/estados que não suportam showPicker()
      }
    }
  });
}

attachDatePicker(document.getElementById("due-date"));
attachDatePicker(document.getElementById("recurrence-end-date"));

function buildRecurrenceValue() {
  const kind = document.getElementById("recurrence-kind").value;
  if (kind === "intervalo_dias") {
    return document.getElementById("recurrence-interval").value;
  }
  if (kind === "dia_fixo_mes") {
    return document.getElementById("recurrence-month-day").value;
  }
  if (kind === "dia_semana") {
    const checked = Array.from(
      document.querySelectorAll("#recurrence-weekday-wrapper input[type=checkbox]:checked")
    ).map((cb) => cb.value);
    return checked.join(",");
  }
  return "";
}

function validateRecurrenceValue(kind, value) {
  if (kind === "intervalo_dias") {
    const n = Number(value);
    if (!value || !Number.isInteger(n) || n < 1) {
      alert("Informe um número de dias válido (>= 1).");
      return false;
    }
  } else if (kind === "dia_fixo_mes") {
    const n = Number(value);
    if (!value || !Number.isInteger(n) || n < 1 || n > 31) {
      alert("Informe um dia do mês entre 1 e 31.");
      return false;
    }
  } else if (kind === "dia_semana") {
    if (!value) {
      alert("Selecione ao menos um dia da semana.");
      return false;
    }
  }
  return true;
}

function resetRecurrenceFields() {
  document.getElementById("recurrence-interval").value = "";
  document.getElementById("recurrence-month-day").value = "";
  document.querySelectorAll("#recurrence-weekday-wrapper input[type=checkbox]").forEach((cb) => {
    cb.checked = false;
  });
  document.getElementById("recurrence-end-type").value = "never";
  document.getElementById("recurrence-end-date").value = "";
  document.getElementById("recurrence-end-count").value = "";
  toggleRecurrenceValueFields();
  toggleRecurrenceEndFields();
}

// ---------- Usuários ----------
async function loadAllUsers() {
  users = await api("/users");
  await refreshAssignedOptions();
}

// Só é possível atribuir tarefas (ou filtrar por pessoa) a si mesmo ou a usuários vinculados
async function refreshAssignedOptions() {
  const assignedSelect = document.getElementById("task-assigned");
  assignedSelect.innerHTML = '<option value="">Todos</option>';

  const filterSelect = document.getElementById("pendentes-filter-person");
  const previousFilterValue = filterSelect.value;
  filterSelect.innerHTML = '<option value="">Todos</option>';

  if (!currentUser) return;

  const optSelf = document.createElement("option");
  optSelf.value = currentUser.id;
  optSelf.textContent = `${currentUser.name} (eu)`;
  assignedSelect.appendChild(optSelf);
  filterSelect.appendChild(optSelf.cloneNode(true));

  const links = await api(`/users/${currentUser.id}/links`);
  links.forEach((u) => {
    const opt = document.createElement("option");
    opt.value = u.id;
    opt.textContent = u.name;
    assignedSelect.appendChild(opt);
    filterSelect.appendChild(opt.cloneNode(true));
  });

  filterSelect.value = previousFilterValue;
}

async function loadAllUsersList() {
  users = await api("/users");
  const list = document.getElementById("all-users-list");
  list.innerHTML = "";
  users.forEach((u) => {
    const li = document.createElement("li");
    li.innerHTML = `<div><strong>${u.name}</strong><br><span class="meta">@${u.username}${u.email ? " · " + u.email : ""}</span></div>`;
    list.appendChild(li);
  });
}

async function loadLinksView() {
  if (!currentUser) return;

  const targetSelect = document.getElementById("link-target");
  targetSelect.innerHTML = "";
  const links = await api(`/users/${currentUser.id}/links`);
  const linkedIds = new Set(links.map((u) => u.id));

  users
    .filter((u) => u.id !== currentUser.id && !linkedIds.has(u.id))
    .forEach((u) => {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.textContent = u.name;
      targetSelect.appendChild(opt);
    });

  const linksList = document.getElementById("links-list");
  linksList.innerHTML = "";
  if (!links.length) {
    linksList.innerHTML = "<li>Nenhum vínculo ainda.</li>";
  }
  links.forEach((u) => {
    const li = document.createElement("li");
    const info = document.createElement("div");
    info.innerHTML = `<strong>${u.name}</strong><br><span class="meta">@${u.username}</span>`;
    const btn = document.createElement("button");
    btn.textContent = "Desvincular";
    btn.addEventListener("click", async () => {
      await api(`/users/${currentUser.id}/links/${u.id}`, { method: "DELETE" });
      await loadLinksView();
      await refreshAssignedOptions();
    });
    li.appendChild(info);
    li.appendChild(btn);
    linksList.appendChild(li);
  });
}

document.getElementById("link-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const linkedUserId = Number(document.getElementById("link-target").value);
  if (!linkedUserId) return;
  try {
    await api(`/users/${currentUser.id}/links`, {
      method: "POST",
      body: JSON.stringify({ linked_user_id: linkedUserId }),
    });
    await loadLinksView();
    await refreshAssignedOptions();
  } catch (err) {
    alert(`Erro ao vincular: ${err.message}`);
  }
});

// ---------- Pendentes ----------
document.getElementById("pendentes-filter-person").addEventListener("change", loadPendentes);

function formatCommentDate(createdAt) {
  return new Date(createdAt.replace(" ", "T")).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderComments(listEl, comments) {
  listEl.innerHTML = comments.length
    ? comments
        .map(
          (c) => `
        <div class="comment-item">
          <div>${c.text}</div>
          <div class="meta">${c.user_name} · ${formatCommentDate(c.created_at)}</div>
        </div>
      `
        )
        .join("")
    : '<p class="meta">Nenhum comentário ainda.</p>';
  listEl.scrollTop = listEl.scrollHeight;
}

// Tarefas com o bloco de comentários aberto — precisa sobreviver ao
// re-render da lista causado pelo polling automático, senão o bloco
// fecha sozinho mesmo sem o usuário estar digitando.
const expandedComments = new Set();

async function loadCommentsInto(taskId, section) {
  const listEl = section.querySelector(".comments-list");
  try {
    const comments = await api(`/tasks/${taskId}/comments`);
    renderComments(listEl, comments);
    section.dataset.loaded = "1";
  } catch (err) {
    listEl.innerHTML = `<p class="meta">Erro ao carregar comentários: ${err.message}</p>`;
  }
}

async function toggleComments(taskId, section, countBtn) {
  const isHidden = section.classList.toggle("hidden");
  if (isHidden) {
    expandedComments.delete(taskId);
    return;
  }
  expandedComments.add(taskId);
  if (section.dataset.loaded) return;
  await loadCommentsInto(taskId, section);
}

function buildPendenteCard(inst) {
  const li = document.createElement("li");
  li.className = priorityClass(inst.priority);
  const header = document.createElement("div");
  header.className = "card-header";

  const info = document.createElement("div");
  const criadaEm = new Date(inst.task_created_at.replace(" ", "T")).toLocaleDateString("pt-BR");
  const responsavel = inst.assigned_to_name || "Todos";
  const tagsHtml =
    inst.tags && inst.tags.length
      ? `<div class="tag-badges">${inst.tags.map((t) => `<span class="tag-badge">#${t}</span>`).join("")}</div>`
      : "";
  info.innerHTML = `
    <strong>#${inst.id} - ${inst.title}</strong>
    ${inst.due_date ? `<div class="meta">Prazo: ${inst.due_date}</div>` : ""}
    <div class="meta">Criada em ${criadaEm} por ${inst.created_by_name}</div>
    <div class="meta">Responsável: ${responsavel}</div>
    ${tagsHtml}
  `;
  const actions = document.createElement("div");
  actions.className = "task-actions";

  const editBtn = document.createElement("button");
  editBtn.className = "icon-btn";
  editBtn.textContent = "✏️";
  editBtn.title = "Editar tarefa";
  editBtn.addEventListener("click", () => startEditTask(inst.task_id));

  const wasExpanded = expandedComments.has(inst.task_id);
  const commentsSection = document.createElement("div");
  commentsSection.className = wasExpanded ? "comments-section" : "comments-section hidden";
  commentsSection.innerHTML = `
    <div class="comments-list"></div>
    <form class="comment-form">
      <input type="text" placeholder="Escrever um comentário..." required>
      <button type="submit">Enviar</button>
    </form>
  `;
  if (wasExpanded) {
    loadCommentsInto(inst.task_id, commentsSection);
  }

  const commentBtn = document.createElement("button");
  commentBtn.className = "icon-btn";
  commentBtn.textContent = `💬 ${inst.comment_count || 0}`;
  commentBtn.title = "Comentários";
  commentBtn.addEventListener("click", () => toggleComments(inst.task_id, commentsSection, commentBtn));

  const form = commentsSection.querySelector(".comment-form");
  const input = commentsSection.querySelector("input");
  // Enquanto o usuário está digitando um comentário, o refresh automático
  // (polling) não pode recriar a lista — isso apagaria o texto no meio da
  // digitação. Ver flag isComposingComment.
  input.addEventListener("focus", () => {
    isComposingComment = true;
  });
  input.addEventListener("blur", () => {
    isComposingComment = false;
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    try {
      await api(`/tasks/${inst.task_id}/comments`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      input.value = "";
      const comments = await api(`/tasks/${inst.task_id}/comments`);
      renderComments(commentsSection.querySelector(".comments-list"), comments);
      commentBtn.textContent = `💬 ${comments.length}`;
    } catch (err) {
      alert(`Erro ao comentar: ${err.message}`);
    }
  });

  const btn = document.createElement("button");
  btn.textContent = "Concluir";
  btn.addEventListener("click", async () => {
    await api(`/instances/${inst.id}/feito`, { method: "POST" });
    loadPendentes();
    loadConcluidasRecentes();
  });

  actions.appendChild(editBtn);
  actions.appendChild(commentBtn);
  actions.appendChild(btn);
  header.appendChild(info);
  header.appendChild(actions);
  li.appendChild(header);
  li.appendChild(commentsSection);
  return li;
}

const PRIORITY_GROUPS = [
  { key: "alta", label: "Alta prioridade" },
  { key: "media", label: "Média prioridade" },
  { key: "baixa", label: "Baixa prioridade" },
];

let currentPendentesInstances = [];

function renderPendentesList() {
  const searchTerm = document.getElementById("pendentes-search").value.trim().toLowerCase();
  // A busca só filtra as tarefas já carregadas aqui (ativas/pendentes) —
  // não pesquisa entre as concluídas.
  const instances = searchTerm
    ? currentPendentesInstances.filter((inst) => inst.title.toLowerCase().includes(searchTerm))
    : currentPendentesInstances;

  const container = document.getElementById("pendentes-list");
  container.innerHTML = "";

  if (!instances.length) {
    container.innerHTML = searchTerm
      ? "<p>Nenhuma tarefa encontrada pra essa busca.</p>"
      : "<p>Nenhuma tarefa pendente 🎉</p>";
    return;
  }

  // Cada prioridade forma sua própria grade — se a Alta tiver só 1 ou 2
  // tarefas, o resto da linha fica vazio em vez de "puxar" itens da
  // Média pra preencher, como aconteceria numa grade única contínua.
  PRIORITY_GROUPS.forEach(({ key, label }) => {
    const group = instances.filter((inst) => inst.priority === key);
    if (!group.length) return;

    const heading = document.createElement("h4");
    heading.className = "priority-group-title";
    heading.textContent = label;
    container.appendChild(heading);

    const ul = document.createElement("ul");
    ul.className = "task-list";
    group.forEach((inst) => ul.appendChild(buildPendenteCard(inst)));
    container.appendChild(ul);
  });
}

document.getElementById("pendentes-search").addEventListener("input", renderPendentesList);

async function loadPendentes() {
  const filterPersonId = document.getElementById("pendentes-filter-person").value;
  const query = filterPersonId
    ? `/instances?status=pendente&assigned_to_exact=${filterPersonId}`
    : "/instances?status=pendente";
  currentPendentesInstances = await api(query);
  renderPendentesList();
  loadConcluidasRecentes();
  refreshConfirmacoes();
}

// ---------- Confirmação de tarefas ----------
async function refreshConfirmacoes() {
  const pending = await api("/instances?status=aguardando_confirmacao");
  const mine = pending.filter((i) => i.created_by === currentUser.id);
  document.getElementById("nav-confirmar-btn").classList.toggle("hidden", mine.length === 0);
  if (!document.getElementById("view-confirmar").classList.contains("hidden")) {
    renderConfirmarList(mine);
  }
}

async function loadConfirmacoes() {
  const pending = await api("/instances?status=aguardando_confirmacao");
  const mine = pending.filter((i) => i.created_by === currentUser.id);
  document.getElementById("nav-confirmar-btn").classList.toggle("hidden", mine.length === 0);
  renderConfirmarList(mine);
}

function renderConfirmarList(items) {
  const container = document.getElementById("confirmar-list");
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = '<p class="meta">Nenhuma tarefa aguardando confirmação.</p>';
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "task-list";
  items.forEach((inst) => {
    const li = document.createElement("li");
    li.className = priorityClass(inst.priority);
    li.innerHTML = `
      <div>
        <strong>#${inst.task_id} - ${inst.title}</strong>
        <div class="meta">Marcada como feita por ${inst.confirmation_requested_by_name || "?"}</div>
      </div>
      <label>Comentário (obrigatório)
        <input type="text" class="confirmar-comment-input" placeholder="Escreva um comentário...">
      </label>
      <div class="task-actions">
        <button type="button" class="confirmar-btn" data-action="concluir">Concluir</button>
        <button type="button" class="confirmar-btn" data-action="devolver">Devolver para pendências</button>
      </div>
    `;
    const input = li.querySelector(".confirmar-comment-input");
    input.addEventListener("focus", () => { isComposingComment = true; });
    input.addEventListener("blur", () => { isComposingComment = false; });
    li.querySelectorAll(".confirmar-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const comment = input.value.trim();
        if (!comment) {
          alert("Um comentário é obrigatório para confirmar ou devolver a tarefa.");
          return;
        }
        try {
          await api(`/instances/${inst.id}/confirmar`, {
            method: "POST",
            body: JSON.stringify({ action: btn.dataset.action, comment }),
          });
          isComposingComment = false;
          await loadConfirmacoes();
          loadPendentes();
          if (document.getElementById("nav-confirmar-btn").classList.contains("hidden")) {
            switchView("pendentes");
          }
        } catch (err) {
          alert(`Erro: ${err.message}`);
        }
      });
    });
    ul.appendChild(li);
  });
  container.appendChild(ul);
}

const CONCLUIDAS_RECENTES_LIMIT = 9;

async function loadConcluidasRecentes() {
  const start = new Date();
  start.setDate(start.getDate() - 7);
  const startStr = start.toISOString().split("T")[0];

  const completed = await api(`/reports/completed?start=${startStr}`);
  const list = document.getElementById("concluidas-recentes-list");
  list.innerHTML = "";

  const heading = document.getElementById("concluidas-recentes-title");
  heading.textContent =
    completed.length > CONCLUIDAS_RECENTES_LIMIT
      ? `Concluídas nos últimos 7 dias (${CONCLUIDAS_RECENTES_LIMIT} de ${completed.length})`
      : "Concluídas nos últimos 7 dias";

  if (!completed.length) {
    list.innerHTML = "<li>Nenhuma tarefa concluída nos últimos 7 dias.</li>";
    return;
  }

  completed.slice(0, CONCLUIDAS_RECENTES_LIMIT).forEach((r) => {
    const li = document.createElement("li");
    li.className = priorityClass(r.priority);
    const dias = r.dias_para_completar != null ? r.dias_para_completar.toFixed(1) : "-";
    const concluidaPor = r.completed_by_name || "?";
    li.innerHTML = `
      <div>
        <strong>#${r.task_id} - ${r.title}</strong>
        <div class="meta">Concluída por ${concluidaPor} em ${r.completed_at}</div>
        <div class="meta">Levou ${dias} dia(s)</div>
      </div>
    `;
    list.appendChild(li);
  });
}

document.getElementById("toggle-concluidas-btn").addEventListener("click", (e) => {
  const list = document.getElementById("concluidas-recentes-list");
  const collapsed = list.classList.toggle("hidden");
  e.target.textContent = collapsed ? "▸ Expandir" : "▾ Recolher";
});

// ---------- Nova tarefa ----------
document.getElementById("task-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  if (editingTaskId) {
    const payload = {
      title: document.getElementById("task-title").value,
      description: document.getElementById("task-description").value || null,
      priority: document.getElementById("task-priority").value,
      assigned_to: document.getElementById("task-assigned").value
        ? Number(document.getElementById("task-assigned").value)
        : null,
      tags: parseTagsInput(),
      needs_confirmation: document.getElementById("task-needs-confirmation").checked,
    };
    if (document.getElementById("task-type").value === "unica") {
      const hasDueDate = document.getElementById("has-due-date").checked;
      if (hasDueDate) {
        const dueDate = document.getElementById("due-date").value;
        if (!dueDate) {
          alert("Informe a data limite ou desmarque a opção.");
          return;
        }
        payload.due_date = dueDate;
      } else {
        payload.due_date = null;
      }
    }
    try {
      await api(`/tasks/${editingTaskId}`, { method: "PATCH", body: JSON.stringify(payload) });
      resetTaskFormToCreateMode();
      loadPendentes();
      switchView("pendentes");
      alert("Tarefa atualizada!");
    } catch (err) {
      alert(`Erro ao salvar edição: ${err.message}`);
    }
    return;
  }

  const type = document.getElementById("task-type").value;
  const payload = {
    title: document.getElementById("task-title").value,
    description: document.getElementById("task-description").value || null,
    priority: document.getElementById("task-priority").value,
    type,
    assigned_to: document.getElementById("task-assigned").value
      ? Number(document.getElementById("task-assigned").value)
      : null,
    tags: parseTagsInput(),
    needs_confirmation: document.getElementById("task-needs-confirmation").checked,
  };
  if (type === "unica") {
    const hasDueDate = document.getElementById("has-due-date").checked;
    if (hasDueDate) {
      const dueDate = document.getElementById("due-date").value;
      if (!dueDate) {
        alert("Informe a data limite ou desmarque a opção.");
        return;
      }
      payload.due_date = dueDate;
    }
  }
  if (type === "periodica") {
    payload.recurrence_kind = document.getElementById("recurrence-kind").value;
    payload.recurrence_value = buildRecurrenceValue();

    if (!validateRecurrenceValue(payload.recurrence_kind, payload.recurrence_value)) {
      return;
    }

    const endType = document.getElementById("recurrence-end-type").value;
    if (endType === "date") {
      const endDateInput = document.getElementById("recurrence-end-date");
      const endDateValue = endDateInput.value;
      if (!endDateValue || endDateValue < endDateInput.min || endDateValue > endDateInput.max) {
        alert("A data final deve estar entre hoje e 10 anos a partir de hoje.");
        return;
      }
      payload.recurrence_end_date = endDateValue;
    } else if (endType === "count") {
      const count = document.getElementById("recurrence-end-count").value;
      payload.recurrence_max_occurrences = count ? Number(count) : null;
    }
  }

  try {
    await api("/tasks", { method: "POST", body: JSON.stringify(payload) });
    resetTaskFormToCreateMode();
    loadPendentes();
    loadTagsDatalist();
    switchView("pendentes");
    alert("Tarefa criada!");
  } catch (err) {
    alert(`Erro ao criar tarefa: ${err.message}`);
  }
});

// ---------- Relatórios ----------
async function loadReports() {
  const start = document.getElementById("report-start").value;
  const end = document.getElementById("report-end").value;
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);

  const completed = await api(`/reports/completed?${params.toString()}`);
  const completedList = document.getElementById("completed-list");
  completedList.innerHTML = "";
  completed.forEach((r) => {
    const li = document.createElement("li");
    li.className = priorityClass(r.priority);
    const dias = r.dias_para_completar != null ? r.dias_para_completar.toFixed(1) : "-";
    const concluidaPor = r.completed_by_name || "?";
    li.innerHTML = `
      <div>
        <strong>#${r.task_id} - ${r.title}</strong>
        <div class="meta">Concluída por ${concluidaPor} em ${r.completed_at}</div>
        <div class="meta">Levou ${dias} dia(s)</div>
      </div>
    `;
    completedList.appendChild(li);
  });

  const pending = await api("/reports/pending");
  const pendingList = document.getElementById("pending-report-list");
  pendingList.innerHTML = "";
  pending.forEach((r) => {
    const li = document.createElement("li");
    li.className = priorityClass(r.priority);
    const dias = r.dias_pendente != null ? r.dias_pendente.toFixed(1) : "-";
    li.innerHTML = `
      <div>
        <strong>#${r.id} - ${r.title}</strong>
        <div class="meta">Pendente há ${dias} dia(s)</div>
      </div>
    `;
    pendingList.appendChild(li);
  });
}

document.getElementById("report-filter-btn").addEventListener("click", loadReports);

// ---------- Inicialização ----------
async function loadVersion() {
  try {
    const { version } = await api("/version");
    document.getElementById("version-tag").textContent = `v${version}`;
    document.getElementById("version-tag-login").textContent = `v${version}`;
  } catch (err) {
    // não crítico, silenciosamente ignora
  }
}

async function afterLogin() {
  document.getElementById("current-user-name").textContent = currentUser.name;
  applyTheme(currentUser.theme || "light");
  showApp();
  await loadAllUsers();
  await loadPendentes();
  await loadTagsDatalist();
  setInterval(() => {
    if (!isComposingComment) loadPendentes();
  }, POLL_INTERVAL_MS);
}

async function init() {
  await loadVersion();

  if (token) {
    try {
      currentUser = await api("/users/me");
      await afterLogin();
      return;
    } catch (err) {
      // token inválido/expirado, api() já limpou e caiu na tela de login
    }
  }
  showLogin();
}

init();
