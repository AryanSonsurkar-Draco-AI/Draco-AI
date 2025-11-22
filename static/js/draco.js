const log = document.getElementById('log');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const stopSpeakBtn = document.getElementById('stopSpeakBtn');
const dot = document.getElementById('dot');
const statusText = document.getElementById('statusText');
const chatHero = document.getElementById('chatHero');
const heroGreeting = document.getElementById('heroGreeting');
const typingIndicator = document.getElementById('typing');
const memoryList = document.getElementById('memoryList');
const clearMemory = document.getElementById('clearMemory');
const modeBadge = document.getElementById('modeBadge');

const MEMORY_KEY = 'draco_memory_v2';
const MAX_MEMORY = 40;

const errorBanner = document.getElementById('errorBanner');
const errorText = document.getElementById('errorText');
const copyErrorBtn = document.getElementById('copyErrorBtn');
const retryBtn = document.getElementById('retryBtn');
let lastAction = null;

function showError(msg, retryFn) {
  const text = msg || 'Something went wrong.';
  appendItem(text, 'bot');
  lastAction = typeof retryFn === 'function' ? retryFn : null;
}

function hideError() {
  if (errorBanner) errorBanner.style.display = 'none';
}

if (copyErrorBtn) {
  copyErrorBtn.onclick = async () => {
    try {
      await navigator.clipboard.writeText(errorText?.textContent || '');
    } catch (e) {
      /* no-op */
    }
  };
}

if (retryBtn) {
  retryBtn.onclick = () => {
    hideError();
    if (lastAction) lastAction();
  };
}

const allButtons = () => Array.from(document.querySelectorAll('button.btn'));
function setBusy(on) {
  allButtons().forEach((b) => {
    b.disabled = !!on;
  });
}

let socket = null;
let user = { logged_in: false, email: null, profile: {} };
let historyItems = [];
let chatsList = [];

try {
  socket = io({ transports: ['websocket', 'polling'], withCredentials: false });
} catch (e) {
  socket = null;
}

function showTyping() {
  if (typingIndicator) typingIndicator.classList.remove('hidden');
}

function hideTyping() {
  if (typingIndicator) typingIndicator.classList.add('hidden');
}

function hideHero() {
  if (chatHero) chatHero.style.display = 'none';
}

function setMode(mode) {
  if (!modeBadge) return;
  modeBadge.className = 'mode ' + (mode || 'idle');
  modeBadge.innerText = mode ? mode.charAt(0).toUpperCase() + mode.slice(1) : 'Idle';
}

function saveMemory(item) {
  if (!memoryList) return;
  try {
    let mem = JSON.parse(localStorage.getItem(MEMORY_KEY) || '[]');
    mem.unshift({ time: Date.now(), text: item });
    mem = mem.slice(0, MAX_MEMORY);
    localStorage.setItem(MEMORY_KEY, JSON.stringify(mem));
    renderMemory();
  } catch (e) {
    /* no-op */
  }
}

function renderMemory() {
  if (!memoryList) return;
  try {
    const mem = JSON.parse(localStorage.getItem(MEMORY_KEY) || '[]');
    memoryList.innerHTML = '';
    mem.forEach((m) => {
      const li = document.createElement('li');
      li.innerText = `${new Date(m.time).toLocaleString()} — ${m.text}`;
      memoryList.appendChild(li);
    });
  } catch (e) {
    memoryList.innerHTML = '';
  }
}

function appendItem(text, who = 'bot') {
  if (!log) return;
  const el = document.createElement('div');
  el.className = 'item ' + (who === 'bot' ? 'bot-item' : 'user-item');
  el.innerHTML = `<div class="${who}">${text}</div>`;
  el.classList.add('fade-in');
  log.appendChild(el);
  hideHero();
  try {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  } catch (e) {
    window.scrollTo(0, document.body.scrollHeight);
  }
}

function initials(name) {
  if (!name) return 'U';
  const parts = name.trim().split(/\s+/);
  const a = parts[0]?.[0] || '';
  const b = parts[1]?.[0] || '';
  return (a + b).toUpperCase() || 'U';
}

function renderProfile() {
  const profName = document.getElementById('profName');
  const profEmail = document.getElementById('profEmail');
  if (profName) profName.textContent = 'Draco AI';
  if (profEmail) profEmail.textContent = 'Powered by Aryan and his co-workers';

  const memInfo = document.getElementById('memInfo');
  if (!memInfo) return;
  const p = user?.profile || {};
  const name = p.name || '—';
  const hobbies = Array.isArray(p.hobbies) ? p.hobbies.join(', ') : (p.hobbies || '—');
  const fav = p.favorite_subject || '—';
  memInfo.innerHTML = `
    <div><strong>Name:</strong> ${name}</div>
    <div><strong>Hobbies:</strong> ${hobbies}</div>
    <div><strong>Favorite Subject:</strong> ${fav}</div>
  `;
}

function renderHistory() {
  const container = document.getElementById('history');
  if (!container) return;
  container.innerHTML = '';

  const list = document.createElement('div');
  (chatsList || []).forEach((c) => {
    const d = document.createElement('div');
    d.className = 'hitem';
    d.textContent = c.name || 'New Chat';
    d.onclick = async () => {
      try {
        await fetch('/api/chats/select', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chat_id: c.id })
        });
        await loadHistory();
      } catch (e) {
        /* no-op */
      }
    };
    list.appendChild(d);
  });
  container.appendChild(list);

  historyItems.slice(-30).forEach((it) => {
    const text = (it.who === 'user' ? 'You: ' : 'Draco: ') + it.text;
    const d = document.createElement('div');
    d.className = 'hitem';
    d.textContent = text.length > 80 ? text.slice(0, 77) + '…' : text;
    try {
      d.title = new Date((it.ts || 0) * 1000).toLocaleString();
    } catch (e) {
      /* no-op */
    }
    d.onclick = () => {
      appendItem(it.text, it.who === 'user' ? 'user' : 'bot');
    };
    container.appendChild(d);
  });
}

let voiceEnabled = false;

function speakText(text) {
  try {
    if (!voiceEnabled) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.0;
    utter.pitch = 1.0;
    utter.lang = 'en-US';
    window.speechSynthesis.speak(utter);
  } catch (e) {
    /* no-op */
  }
}

if (stopSpeakBtn) {
  stopSpeakBtn.onclick = () => window.speechSynthesis.cancel();
}

async function loadGuestProfile() {
  try {
    const res = await fetch('/api/guest_profile');
    const data = await res.json();
    if (data?.ok && data.profile) {
      user.profile = data.profile;
      renderProfile();
    }
  } catch (e) {
    /* no-op */
  }
}

async function sendCommand(text) {
  if (!text) return;
  appendItem(text, 'user');
  saveMemory('You: ' + text);
  showTyping();
  hideError();
  setBusy(true);

  if (socket && socket.connected) {
    try {
      socket.emit('user_command', { text });
    } catch (e) {
      hideTyping();
    } finally {
      setBusy(false);
    }
    return;
  }

  try {
    const r = await fetch('/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    const data = await r.json();
    const t = data?.text ? String(data.text) : data?.error ? String(data.error) : 'No response';
    if (t) {
      appendItem(t, 'bot');
      speakText(t);
      saveMemory('Draco: ' + t);
    }
    if (Array.isArray(data?.sources_labeled) && data.sources_labeled.length) {
      const list = data.sources_labeled
        .map((s) => `<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.label}</a>`)
        .join(' | ');
      appendItem('Sources: ' + list, 'bot');
    }
    if (data?.action === 'open_url' && data.url) {
      try {
        window.open(data.url, '_blank');
      } catch (e) {
        /* no-op */
      }
    }
  } catch (e) {
    showError('Request failed. Please retry.', () => sendCommand(text));
  } finally {
    hideTyping();
    setBusy(false);
  }
}

async function loadHistory() {
  hideTyping();
  try {
    const [h, l] = await Promise.all([
      fetch('/api/chat_history'),
      fetch('/api/chats')
    ]);
    if (!h.ok) return;
    const d = await h.json();
    if (!d.ok) return;
    historyItems = d.items || [];
    if (l.ok) {
      const dl = await l.json();
      chatsList = dl?.ok ? dl.chats || [] : [];
    }
    if (log) log.innerHTML = '';
    if (historyItems.length) {
      if (chatHero) chatHero.style.display = 'none';
      historyItems.slice(-20).forEach((it) => {
        appendItem(it.text, it.who === 'user' ? 'user' : 'bot');
      });
    } else if (chatHero) {
      chatHero.style.display = '';
    }
    renderHistory();
  } catch (e) {
    /* no-op */
  }
}

if (sendBtn) {
  sendBtn.onclick = () => {
    const val = (input?.value || '').trim();
    if (!val) return;
    sendCommand(val);
    input.value = '';
    input.focus();
  };
}

if (input) {
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendBtn?.click();
  });
}

if (socket) {
  socket.on('connect', () => {
    appendItem('Connected to Draco!', 'bot');
    saveMemory('Draco: Connected to Draco!');
    dot?.classList.add('on');
    if (statusText) statusText.textContent = 'Online';
    if (sendBtn) sendBtn.disabled = false;
    if (micBtn) micBtn.disabled = false;
    loadHistory();
    loadGuestProfile();
  });

  socket.on('disconnect', () => {
    appendItem('Disconnected. Using HTTP fallback…', 'bot');
    saveMemory('Draco: Disconnected. Using HTTP fallback…');
    dot?.classList.remove('on');
    if (statusText) statusText.textContent = 'HTTP mode';
  });

  socket.on('draco_response', (data) => {
    hideTyping();
    if (!data) return;
    if (data.action === 'open_url' && data.url) {
      try {
        window.open(data.url, '_blank');
      } catch (e) {
        /* no-op */
      }
    }
    const text = data?.text ? String(data.text) : '';
    if (text) {
      appendItem(text, 'bot');
      speakText(text);
      saveMemory('Draco: ' + text);
    }
    if (Array.isArray(data?.sources_labeled) && data.sources_labeled.length) {
      const list = data.sources_labeled
        .map((s) => `<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.label}</a>`)
        .join(' | ');
      appendItem('Sources: ' + list, 'bot');
    }
    if (data?.doc) {
      appendItem(
        `Document ready: <a href="${data.doc}" target="_blank" rel="noopener noreferrer">Download</a>`,
        'bot'
      );
      saveMemory('Draco provided a document.');
    }
  });
} else if (statusText) {
  statusText.textContent = 'HTTP mode';
}

document.addEventListener(
  'click',
  () => {
    if (!voiceEnabled) {
      try {
        window.speechSynthesis.resume();
      } catch (e) {
        /* no-op */
      }
      voiceEnabled = true;
    }
  },
  { once: true }
);

let recognition = null;
let recognizing = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = 'en-IN';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    recognizing = true;
    if (micBtn) micBtn.innerText = '🎙️ (on)';
    setMode('listening');
  };
  recognition.onend = () => {
    recognizing = false;
    if (micBtn) micBtn.innerText = '🎙️';
    setMode('idle');
  };
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    if (input) input.value = transcript;
    sendBtn?.click();
  };
} else if (micBtn) {
  micBtn.style.display = 'none';
  appendItem('Voice recognition not supported in this browser.', 'bot');
}

if (micBtn) {
  micBtn.onclick = () => {
    if (!recognition) {
      appendItem('Speech recognition not supported in this browser.', 'bot');
      return;
    }
    try {
      micBtn.disabled = true;
      recognition.start();
    } catch (e) {
      micBtn.disabled = false;
    }
  };
}

const chipsEl = document.getElementById('chips');
if (chipsEl) {
  chipsEl.addEventListener('click', (e) => {
    const t = e.target.closest('.chip');
    if (!t) return;
    const cmd = t.getAttribute('data-cmd');
    if (input) input.value = cmd;
    sendBtn?.click();
  });
}

const layoutEl = document.getElementById('layout');
const toggleSide = document.getElementById('toggleSide');
const expandSide = document.getElementById('expandSide');
const sidebarEl = document.getElementById('sidebar');
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const mobileMenuLabel = mobileMenuBtn?.querySelector('.hamburger-label');
const mobileOverlay = document.getElementById('mobileSidebarOverlay');
const isMobileView = () => window.innerWidth <= 900;

const applySidebarAria = (isOpen) => {
  if (!sidebarEl) return;
  if (isMobileView()) {
    sidebarEl.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
  } else {
    sidebarEl.removeAttribute('aria-hidden');
  }
};

const setMobileSidebar = (open) => {
  if (!layoutEl || !mobileMenuBtn || !mobileOverlay) return;
  const allowOpen = isMobileView();
  const isOpen = !!open && allowOpen;
  layoutEl.classList.toggle('mobile-open', isOpen);
  document.body.classList.toggle('mobile-sidebar-open', isOpen);
  mobileMenuBtn.classList.toggle('active', isOpen);
  mobileMenuBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  mobileMenuBtn.setAttribute('aria-label', isOpen ? 'Close sidebar' : 'Open sidebar');
  if (mobileMenuLabel) mobileMenuLabel.textContent = isOpen ? 'Close' : 'Menu';
  mobileOverlay.classList.toggle('visible', isOpen);
  applySidebarAria(isOpen);
};

if (mobileMenuBtn) {
  mobileMenuBtn.addEventListener('click', () => {
    if (!isMobileView()) return;
    const next = !mobileMenuBtn.classList.contains('active');
    setMobileSidebar(next);
  });
}

if (mobileOverlay) {
  mobileOverlay.addEventListener('click', () => setMobileSidebar(false));
}

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && layoutEl?.classList.contains('mobile-open')) {
    setMobileSidebar(false);
  }
});

const syncSidebarState = () => {
  if (!isMobileView()) {
    setMobileSidebar(false);
    applySidebarAria(true);
  } else {
    applySidebarAria(layoutEl?.classList.contains('mobile-open'));
  }
};

window.addEventListener('resize', syncSidebarState);
syncSidebarState();

let collapsed = false;
let expanded = false;

if (toggleSide) {
  toggleSide.onclick = () => {
    collapsed = !collapsed;
    layoutEl?.classList.toggle('collapsed', collapsed);
    toggleSide.textContent = collapsed ? 'Show Sidebar' : 'Hide Sidebar';
  };
}

if (expandSide) {
  expandSide.onclick = () => {
    expanded = !expanded;
    layoutEl?.classList.toggle('expanded', expanded);
    expandSide.textContent = expanded ? 'Shrink' : 'Expand';
  };
}

renderProfile();

const quickActionsBtn = document.getElementById('quickActionsBtn');
const qaModal = document.getElementById('quickActionsModal');
const qaBackdrop = document.querySelector('#quickActionsModal .qa-backdrop');
const qaCloseBtn = document.getElementById('qaCloseBtn');

function openQAModal() {
  if (!qaModal) return;
  qaModal.classList.add('open');
  const topic = document.getElementById('genTopicSide');
  if (topic) setTimeout(() => topic.focus(), 50);
}

function closeQAModal() {
  if (!qaModal) return;
  qaModal.classList.remove('open');
}

if (quickActionsBtn) {
  quickActionsBtn.onclick = () => {
    try {
      openQAModal();
    } catch (e) {
      /* no-op */
    }
  };
}

qaBackdrop?.addEventListener('click', closeQAModal);
qaCloseBtn?.addEventListener('click', closeQAModal);

const newChatBtn = document.getElementById('newChatBtn');
const clearChatBtn = document.getElementById('clearChatBtn');

if (newChatBtn) {
  newChatBtn.onclick = () => {
    appendItem('Saved chats are a Draco Pro feature. Use the contact buttons to upgrade.', 'bot');
  };
}

if (clearChatBtn) {
  clearChatBtn.onclick = () => {
    if (log) log.innerHTML = '';
    historyItems = [];
    chatsList = [];
    renderHistory();
    appendItem('Chat cleared. Start a new conversation anytime.', 'bot');
  };
}

const THEME_KEY = 'draco-theme';
const themeCheckbox = document.getElementById('themeCheckbox');

function applyTheme(theme) {
  document.body.classList.remove('light-mode', 'dark-mode');
  document.body.classList.add(theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch (e) {
    /* no-op */
  }
  if (themeCheckbox) themeCheckbox.checked = theme === 'light-mode';
}

const savedTheme = (() => {
  try {
    return localStorage.getItem(THEME_KEY);
  } catch (e) {
    return null;
  }
})();

applyTheme(savedTheme || 'light-mode');

if (themeCheckbox) {
  themeCheckbox.addEventListener('change', () => {
    const next = themeCheckbox.checked ? 'light-mode' : 'dark-mode';
    applyTheme(next);
  });
}

const fileInput = document.getElementById('fileInput');
const instructionEl = document.getElementById('instruction');
const uploadBtn = document.getElementById('uploadBtn');
const uploadNote = document.getElementById('uploadNote');
const chooseFileBtn = document.getElementById('chooseFileBtn');
const fileNameLabel = document.getElementById('fileNameLabel');
const fileSizeLabel = document.getElementById('fileSizeLabel');
const dropZone = document.getElementById('dropZone');
const uploadProgress = document.getElementById('uploadProgress');
const downloadsPanel = document.getElementById('downloadsPanel');
const uploadStep = document.getElementById('uploadStep');
let droppedFile = null;

if (chooseFileBtn) {
  chooseFileBtn.onclick = () => fileInput?.click();
}

if (fileInput) {
  fileInput.onchange = () => {
    try {
      const f = fileInput.files?.[0];
      fileNameLabel.textContent = f ? 'Selected: ' + f.name : '';
      droppedFile = null;
      if (f) {
        fileSizeLabel.textContent = (Math.round(f.size / 1024) / 1024).toFixed(2) + ' MB';
      } else {
        fileSizeLabel.textContent = '';
      }
    } catch (e) {
      /* no-op */
    }
  };
}

if (dropZone) {
  ['dragenter', 'dragover'].forEach((ev) =>
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    })
  );
  ['dragleave', 'drop'].forEach((ev) =>
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
    })
  );
  dropZone.addEventListener('drop', (e) => {
    const f = e.dataTransfer?.files?.[0];
    if (f) {
      droppedFile = f;
      fileNameLabel.textContent = 'Selected (dropped): ' + f.name;
      fileSizeLabel.textContent = (Math.round(f.size / 1024) / 1024).toFixed(2) + ' MB';
    }
  });
}

if (uploadBtn) {
  uploadBtn.onclick = async () => {
    uploadNote.textContent = 'Processing...';
    hideError();
    setBusy(true);
    if (uploadStep) uploadStep.textContent = 'Uploading…';
    const f = fileInput?.files?.[0] || droppedFile;
    if (!f) {
      uploadNote.textContent = 'Please choose a file.';
      setBusy(false);
      return;
    }
    const fd = new FormData();
    fd.append('file', f);
    fd.append('instruction', (instructionEl?.value || '').trim());
    try {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload_process');
      if (uploadProgress) uploadProgress.style.display = 'block';
      const bar = uploadProgress?.querySelector('span');
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && bar) {
          const pct = Math.min(100, Math.round((e.loaded / e.total) * 100));
          bar.style.width = pct + '%';
        }
      };
      xhr.onload = () => {
        if (uploadProgress) uploadProgress.style.display = 'none';
        if (uploadProgress?.querySelector('span')) uploadProgress.querySelector('span').style.width = '0%';
        try {
          if (uploadStep) uploadStep.textContent = 'Processing…';
          const j = JSON.parse(xhr.responseText || '{}');
          if (!j.ok) {
            uploadNote.textContent = 'Error: ' + (j.error || 'failed');
            return;
          }
          let msg = '';
          if (j.summary) msg += 'Summary:\n' + j.summary + '\n';
          if (j.text) msg += 'Text:\n' + j.text + '\n';
          appendItem(msg || 'Processed.', 'bot');
          saveMemory('Draco: ' + (msg || 'Processed.'));
          if (j.doc) {
            const a = document.createElement('a');
            a.href = j.doc;
            a.target = '_blank';
            a.textContent = 'Download processed file';
            uploadNote.innerHTML = '';
            uploadNote.appendChild(a);
            if (downloadsPanel) {
              const li = document.createElement('div');
              const when = new Date().toLocaleString();
              li.innerHTML = `<a href="${j.doc}" target="_blank">${when} - ${f.name}</a>`;
              downloadsPanel.prepend(li);
            }
          } else {
            uploadNote.textContent = 'Done.';
          }
          if (uploadStep) uploadStep.textContent = '';
        } catch (e) {
          if (uploadStep) uploadStep.textContent = '';
          showError('Upload failed.', () => uploadBtn.click());
          uploadNote.textContent = 'Upload failed.';
        } finally {
          setBusy(false);
        }
      };
      xhr.onerror = () => {
        if (uploadProgress) uploadProgress.style.display = 'none';
        if (uploadStep) uploadStep.textContent = '';
        setBusy(false);
        showError('Upload failed.', () => uploadBtn.click());
        uploadNote.textContent = 'Upload failed.';
      };
      xhr.send(fd);
    } catch (e) {
      if (uploadProgress) uploadProgress.style.display = 'none';
      if (uploadStep) uploadStep.textContent = '';
      setBusy(false);
      showError('Upload failed.', () => uploadBtn.click());
      uploadNote.textContent = 'Upload failed.';
    }
  };
}

function spawnFlames(container) {
  for (let i = 0; i < 6; i++) {
    const p = document.createElement('div');
    p.className = 'flame-particle';
    p.style.left = 20 + Math.random() * 60 + '%';
    p.style.bottom = Math.random() * 6 + 'px';
    p.style.animationDelay = Math.random() * 1.5 + 's';
    p.style.opacity = 0.6 + Math.random() * 0.4;
    container.style.overflow = 'visible';
    container.appendChild(p);
  }
}

document.querySelectorAll('.button-container').forEach(spawnFlames);

const genTopicSide = document.getElementById('genTopicSide');
const genPPTSide = document.getElementById('genPPTSide');
const genDOCSide = document.getElementById('genDOCSide');
const genPDFSide = document.getElementById('genPDFSide');

if (genPPTSide) {
  genPPTSide.onclick = () => {
    const t = (genTopicSide?.value || '').trim();
    if (!t) return;
    sendCommand('generate ppt on ' + t);
  };
}

if (genDOCSide) {
  genDOCSide.onclick = () => {
    const t = (genTopicSide?.value || '').trim();
    if (!t) return;
    sendCommand('generate doc on ' + t);
  };
}

if (genPDFSide) {
  genPDFSide.onclick = () => {
    const t = (genTopicSide?.value || '').trim();
    if (!t) return;
    sendCommand('generate pdf on ' + t);
  };
}

const editInfoBtn = document.getElementById('editInfoBtn');
const forgetMeBtn = document.getElementById('forgetMeBtn');

if (editInfoBtn) {
  editInfoBtn.onclick = async () => {
    try {
      const cur = user?.profile || {};
      const name = prompt('Your name?', cur.name || '');
      const hobbies = prompt('Your hobbies (comma-separated)?', Array.isArray(cur.hobbies) ? cur.hobbies.join(', ') : (cur.hobbies || ''));
      const fav = prompt('Favorite subject?', cur.favorite_subject || '');
      const body = {};
      if (name !== null) body.name = name.trim();
      if (hobbies !== null) body.hobbies = hobbies.split(',').map((s) => s.trim()).filter(Boolean);
      if (fav !== null) body.favorite_subject = fav.trim();
      const url = user?.logged_in ? '/api/profile' : '/api/guest_profile';
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const d = await r.json();
      if (d?.ok) {
        user.profile = d.profile || {};
        renderProfile();
        appendItem('Profile updated.', 'bot');
      } else {
        appendItem('Failed to update profile.', 'bot');
      }
    } catch (e) {
      appendItem('Error updating profile.', 'bot');
    }
  };
}

if (forgetMeBtn) {
  forgetMeBtn.onclick = async () => {
    try {
      const yes = confirm('This will clear your stored profile. Continue?');
      if (!yes) return;
      const url = user?.logged_in ? '/api/profile/clear' : '/api/guest_profile/clear';
      const r = await fetch(url, { method: 'POST' });
      const d = await r.json();
      if (d?.ok) {
        user.profile = {};
        renderProfile();
        appendItem('Your profile has been cleared.', 'bot');
      } else {
        appendItem('Failed to clear profile.', 'bot');
      }
    } catch (e) {
      appendItem('Error clearing profile.', 'bot');
    }
  };
}

const fileChips = document.getElementById('fileChips');
if (fileChips) {
  fileChips.addEventListener('click', (e) => {
    const t = e.target.closest('.chip');
    if (!t) return;
    const instr = t.getAttribute('data-instruction') || '';
    if (instructionEl) instructionEl.value = instr;
    const f = fileInput?.files?.[0];
    if (!f) {
      uploadNote.textContent = 'Please choose a file first.';
      try {
        chooseFileBtn?.focus();
      } catch (err) {
        /* no-op */
      }
      return;
    }
    uploadBtn?.click();
  });
}

const summaryChips = document.getElementById('summaryChips');
if (summaryChips) {
  summaryChips.addEventListener('click', (e) => {
    const t = e.target.closest('.chip');
    if (!t) return;
    const kind = t.getAttribute('data-summary');
    if (instructionEl) instructionEl.value = `summarize:${kind}`;
    const f = fileInput?.files?.[0] || droppedFile;
    if (!f) {
      uploadNote.textContent = 'Please choose a file first.';
      return;
    }
    uploadBtn?.click();
  });
}

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    try {
      document.getElementById('input').focus();
    } catch (err) {
      /* no-op */
    }
  }
  if (e.altKey && e.key.toLowerCase() === 'u') {
    e.preventDefault();
    chooseFileBtn?.click();
  }
  if (e.altKey && e.key.toLowerCase() === 's') {
    e.preventDefault();
    if (instructionEl) instructionEl.value = 'summarize:short';
    uploadBtn?.click();
  }
  if (e.altKey && e.key.toLowerCase() === 'p') {
    e.preventDefault();
    const t = (document.getElementById('genTopicSide')?.value || '').trim();
    if (t) sendCommand('generate pdf on ' + t);
  }
  if (e.altKey && e.key.toLowerCase() === 'd') {
    e.preventDefault();
    const t = (document.getElementById('genTopicSide')?.value || '').trim();
    if (t) sendCommand('generate doc on ' + t);
  }
  if (e.altKey && e.key.toLowerCase() === 'f') {
    e.preventDefault();
    if (instructionEl) instructionEl.value = 'flashcards';
    uploadBtn?.click();
  }
});

if (clearMemory) {
  clearMemory.addEventListener('click', () => {
    try {
      localStorage.removeItem('draco_memory_v2');
    } catch (e) {
      /* no-op */
    }
    renderMemory();
  });
}

appendItem('Draco Dashboard ready. Type or speak to start.', 'bot');
saveMemory('Draco: Draco Dashboard ready. Type or speak to start.');

renderMemory();
