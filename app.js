const loginScreen = document.querySelector('#login-screen');
const appScreen = document.querySelector('#app-screen');
const loginForm = document.querySelector('#login-form');
const loginError = document.querySelector('#login-error');
const messageInput = document.querySelector('#message-input');
const messages = document.querySelector('#messages');
const composer = document.querySelector('#composer');
const typing = document.querySelector('#typing');
const sendButton = document.querySelector('#send-button');
const ticketList = document.querySelector('#ticket-list');
const messageCount = document.querySelector('#message-count');
const handoffBanner = document.querySelector('#handoff-banner');
const MAX_MESSAGES = 30;

let remaining = MAX_MESSAGES;
let awaitingHuman = false;
let sending = false;
let selectedTicket = '';

async function request(path, data) {
  const response = await fetch(path, {
    method: data === undefined ? 'GET' : 'POST',
    headers: data === undefined ? {} : { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Não foi possível concluir a solicitação.');
  return result;
}

function showApp(user) {
  loginScreen.classList.add('hidden');
  appScreen.classList.remove('hidden');
  document.querySelector('#user-name').textContent = user;
  document.querySelector('#user-avatar').textContent = user.trim().charAt(0).toUpperCase() || 'N';
  renderWelcome();
}

function renderWelcome() {
  messages.replaceChildren();
  const welcome = document.createElement('div');
  welcome.className = 'welcome-block';
  welcome.innerHTML = `
    <div class="welcome-icon">✳</div>
    <span class="eyebrow">SEU ASSISTENTE NEXO</span>
    <h2>Como posso ajudar<br><em>hoje?</em></h2>
    <p>Posso tirar dúvidas, consultar seus chamados ou registrar um novo problema.</p>
    <div class="suggestion-row">
      <button class="suggestion-chip" data-prompt="Quais são meus chamados?">Ver meus chamados <span>↗</span></button>
      <button class="suggestion-chip" data-prompt="Esqueci minha senha">Redefinir senha <span>↗</span></button>
      <button class="suggestion-chip" data-prompt="Quero falar com um analista">Falar com uma pessoa <span>↗</span></button>
    </div>`;
  messages.append(welcome);
}

function appendUser(text) {
  const row = document.createElement('article');
  row.className = 'message-row user';
  const content = document.createElement('div');
  content.className = 'message-content';
  const author = document.createElement('div');
  author.className = 'message-author';
  author.textContent = document.querySelector('#user-name').textContent;
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;
  content.append(author, bubble);
  row.append(content);
  messages.append(row);
  scrollToBottom();
}

function appendAssistant(result) {
  const welcome = messages.querySelector('.welcome-block');
  if (welcome) welcome.remove();
  const row = document.createElement('article');
  row.className = 'message-row assistant';
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = 'n';
  const content = document.createElement('div');
  content.className = 'message-content';

  if (result.trace) content.append(renderTrace(result.trace));
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = result.message || '';
  content.append(bubble);
  if (result.ticket) {
    if (result.ticket.items) {
      result.ticket.items.forEach((ticket) => content.append(renderTicket(ticket, true)));
      refreshTickets(result.ticket.items);
    } else {
      content.append(renderTicket(result.ticket, false));
      refreshTickets();
    }
  }
  if (result.draft || result.confirmation) content.append(renderConfirmation(result));
  if (result.quick_replies?.length) content.append(renderQuickReplies(result.quick_replies));
  row.append(avatar, content);
  messages.append(row);
  if (result.handoff) setHandoff(true);
  if (typeof result.mensagens_restantes === 'number') updateRemaining(result.mensagens_restantes);
  scrollToBottom();
}

function renderTrace(trace) {
  const details = document.createElement('details');
  details.className = 'trace';
  const summary = document.createElement('summary');
  summary.className = 'trace-summary';
  summary.textContent = trace.actions?.length ? trace.actions.join(' · ') : trace.action;
  const panel = document.createElement('div');
  panel.className = 'trace-details';
  const addField = (label, value) => {
    const field = document.createElement('div');
    field.className = 'trace-field';
    const title = document.createElement('strong');
    title.textContent = label;
    const text = document.createElement('span');
    text.textContent = value;
    field.append(title, text);
    panel.append(field);
  };
  addField('Entendeu', trace.understood);
  addField('Ação', trace.action);
  addField('Motivo', trace.reason);
  const confidence = document.createElement('div');
  confidence.className = 'trace-field';
  const label = document.createElement('strong');
  label.textContent = 'Segurança';
  const value = document.createElement('div');
  value.className = 'confidence';
  const percent = document.createElement('span');
  percent.textContent = `${trace.confidence}%`;
  const track = document.createElement('span');
  track.className = 'confidence-track';
  const fill = document.createElement('span');
  fill.style.width = `${trace.confidence}%`;
  track.append(fill);
  value.append(percent, track);
  confidence.append(label, value);
  panel.append(confidence);
  if (trace.actions?.length) {
    const field = document.createElement('div');
    field.className = 'trace-field';
    const title = document.createElement('strong');
    title.textContent = 'Passos';
    const actions = document.createElement('div');
    actions.className = 'trace-actions';
    trace.actions.forEach((action) => {
      const chip = document.createElement('span');
      chip.className = 'trace-action';
      chip.textContent = action;
      actions.append(chip);
    });
    field.append(title, actions);
    panel.append(field);
  }
  details.append(summary, panel);
  return details;
}

function renderTicket(ticket, compact) {
  const card = document.createElement('div');
  card.className = 'ticket-card';
  const head = document.createElement('div');
  head.className = 'ticket-card-head';
  const id = document.createElement('span');
  id.className = 'ticket-id';
  id.textContent = ticket.id;
  const priority = document.createElement('span');
  priority.className = `ticket-priority ${ticket.prioridade?.toLowerCase() || ''}`;
  priority.textContent = ticket.prioridade;
  head.append(id, priority);
  const title = document.createElement('p');
  title.className = 'ticket-title';
  title.textContent = ticket.titulo;
  const meta = document.createElement('div');
  meta.className = 'ticket-meta';
  meta.textContent = `${ticket.status}${ticket.analista ? ` · ${ticket.analista}` : ''}`;
  card.append(head, title, meta);
  if (!compact && ticket.historico?.length) {
    const history = document.createElement('ul');
    history.className = 'ticket-history';
    ticket.historico.slice(-3).forEach((item) => {
      const line = document.createElement('li');
      line.textContent = item;
      history.append(line);
    });
    card.append(history);
  }
  if (compact) {
    const select = document.createElement('button');
    select.className = 'ticket-select-note';
    select.textContent = 'Ver detalhes →';
    select.type = 'button';
    select.addEventListener('click', () => sendMessage(`Qual o status do ${ticket.id}?`));
    card.append(select);
  }
  return card;
}

function renderConfirmation(result) {
  const card = document.createElement('div');
  card.className = 'confirm-card';
  const title = document.createElement('div');
  title.className = 'confirm-title';
  title.textContent = result.draft ? 'Rascunho para revisar' : 'Confirma esta ação?';
  card.append(title);
  if (result.draft) {
    const preview = document.createElement('div');
    preview.className = 'draft-preview';
    preview.textContent = `${result.draft.titulo} · prioridade ${result.draft.prioridade}`;
    card.append(preview);
  }
  const actions = document.createElement('div');
  actions.className = 'confirm-actions';
  const confirm = document.createElement('button');
  confirm.className = 'confirm-button';
  confirm.type = 'button';
  confirm.textContent = result.confirmation?.kind === 'cancel' ? 'Confirmar cancelamento' : 'Confirmar abertura';
  confirm.addEventListener('click', async () => {
    confirm.disabled = true;
    try {
      const response = await request('/api/confirm', { confirmar: true });
      card.remove();
      appendAssistant(response);
    } catch (error) {
      showError(error.message);
      confirm.disabled = false;
    }
  });
  const cancel = document.createElement('button');
  cancel.className = 'cancel-button';
  cancel.type = 'button';
  cancel.textContent = result.confirmation?.kind === 'cancel' ? 'Manter chamado' : 'Descartar';
  cancel.addEventListener('click', async () => {
    try {
      const response = await request('/api/confirm', { confirmar: false });
      card.remove();
      appendAssistant(response);
    } catch (error) {
      showError(error.message);
    }
  });
  actions.append(confirm, cancel);
  card.append(actions);
  return card;
}

function renderQuickReplies(options) {
  const row = document.createElement('div');
  row.className = 'quick-replies';
  options.forEach((option) => {
    const button = document.createElement('button');
    button.className = 'quick-reply';
    button.type = 'button';
    button.textContent = option;
    button.addEventListener('click', () => {
      if (option === 'Confirmar abertura' || option === 'Confirmar cancelamento') {
        request('/api/confirm', { confirmar: true }).then(appendAssistant).catch((error) => showError(error.message));
      } else if (option === 'Manter chamado') {
        request('/api/confirm', { confirmar: false }).then(appendAssistant).catch((error) => showError(error.message));
      } else {
        sendMessage(option);
      }
    });
    row.append(button);
  });
  return row;
}

function refreshTickets(tickets) {
  const update = (items) => {
    ticketList.replaceChildren();
    document.querySelector('#ticket-count').textContent = String(items.length);
    document.querySelector('#empty-tickets').classList.toggle('hidden', items.length > 0);
    items.forEach((ticket) => {
      const button = document.createElement('button');
      button.className = `ticket-item ${selectedTicket === ticket.id ? 'selected' : ''}`;
      button.type = 'button';
      const id = document.createElement('span');
      id.className = 'ticket-item-id';
      id.textContent = ticket.id;
      const title = document.createElement('span');
      title.className = 'ticket-item-title';
      title.textContent = ticket.titulo;
      const status = document.createElement('span');
      status.className = 'ticket-item-status';
      status.textContent = ticket.status;
      button.append(id, title, status);
      button.addEventListener('click', () => {
        selectedTicket = ticket.id;
        refreshTickets(items);
        sendMessage(`Qual o status do ${ticket.id}?`);
      });
      ticketList.append(button);
    });
  };
  if (tickets) update(tickets);
  else request('/api/tickets').then((result) => update(result.chamados)).catch((error) => showError(error.message));
}

function updateRemaining(value) {
  remaining = value;
  messageCount.textContent = String(remaining);
  messageInput.disabled = awaitingHuman || remaining < 2;
  sendButton.disabled = awaitingHuman || remaining < 2;
  if (remaining < 2 && !awaitingHuman) messageInput.placeholder = 'Limite de 30 mensagens atingido';
}

function setHandoff(value) {
  awaitingHuman = value;
  handoffBanner.classList.toggle('hidden', !value);
  composer.classList.toggle('is-paused', value);
  updateRemaining(remaining);
}

function scrollToBottom() {
  requestAnimationFrame(() => { messages.scrollTop = messages.scrollHeight; });
}

function showError(message) {
  const notice = document.createElement('div');
  notice.className = 'message-row assistant';
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = message;
  notice.append(bubble);
  messages.append(notice);
  scrollToBottom();
}

async function sendMessage(value) {
  const text = (value ?? messageInput.value).trim();
  if (!text || sending || awaitingHuman || remaining < 2) return;
  sending = true;
  messageInput.value = '';
  messageInput.style.height = 'auto';
  appendUser(text);
  typing.classList.remove('hidden');
  sendButton.disabled = true;
  try {
    const result = await request('/api/chat', { message: text });
    appendAssistant(result);
  } catch (error) {
    showError(error.message);
  } finally {
    typing.classList.add('hidden');
    sending = false;
    updateRemaining(remaining);
    if (!awaitingHuman) messageInput.focus();
  }
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  loginError.textContent = '';
  const data = new FormData(loginForm);
  try {
    const result = await request('/api/login', {
      usuario: data.get('usuario'),
      senha: data.get('senha'),
    });
    showApp(result.usuario);
    const state = await request('/api/me');
    updateRemaining(state.mensagens_restantes);
    setHandoff(state.aguardando_atendente);
    refreshTickets(state.chamados);
  } catch (error) {
    loginError.textContent = error.message;
  }
});

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  sendMessage();
});
messageInput.addEventListener('input', () => {
  messageInput.style.height = 'auto';
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 100)}px`;
});
messageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});
messages.addEventListener('click', (event) => {
  const button = event.target.closest('[data-prompt]');
  if (button) sendMessage(button.dataset.prompt);
});
document.querySelector('#new-chat-button').addEventListener('click', () => {
  request('/api/new-session', {}).then((result) => {
    messages.replaceChildren();
    renderWelcome();
    selectedTicket = '';
    setHandoff(false);
    updateRemaining(result.mensagens_restantes);
  }).catch((error) => showError(error.message));
});
document.querySelector('#logout-button').addEventListener('click', async () => {
  try {
    await request('/api/logout', {});
    window.location.reload();
  } catch (error) {
    showError(error.message);
  }
});

request('/api/me').then((state) => {
  showApp(state.usuario);
  updateRemaining(state.mensagens_restantes);
  setHandoff(state.aguardando_atendente);
  refreshTickets(state.chamados);
}).catch(() => {});
