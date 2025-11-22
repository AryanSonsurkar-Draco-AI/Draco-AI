/* draco.js
   - Connects to ws://localhost:8765
   - Provides voice input (Web Speech API) + typed input support
   - Displays chat messages and keeps Memory in localStorage
*/

const socket = io({
  transports: ["websocket"],
});

socket.on("connect", () => {
  addMessage("bot", "Connected to Draco bridge ✅");
});

socket.on("draco_response", (data) => {
  hideTyping();
  if (!data) return;
  if (data.text) {
    addMessage("bot", data.text);
    saveMemory("Draco: " + data.text);
    setMode("speaking");
    setTimeout(() => setMode("idle"), 700);
  }
  if (data.action === "open_url" && data.url) {
    window.open(data.url, "_blank");
  }
  if (Array.isArray(data.sources_labeled) && data.sources_labeled.length) {
    const src = data.sources_labeled
      .map((s) => `🔗 <a href="${s.url}" target="_blank">${s.label}</a>`)
      .join("<br>");
    addMessage("bot", "Sources:<br>" + src);
  }
  if (data.doc) {
    addMessage(
      "bot",
      `Document ready: <a href="${data.doc}" target="_blank">Download</a>`
    );
  }
});

function sendCommand(text) {
  if (!text) return;
  addMessage("user", text);
  saveMemory("You: " + text);
  showTyping();
  if (socket && socket.connected) {
    socket.emit("user_command", { text });
    return;
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "command", text }));
  } else {
    addMessage("bot", "Bridge not connected. Start python_bridge.py first.");
    hideTyping();
  }
}

let ws = null;
let recognizing = false;
let recognition = null;
const chatWindow = document.getElementById("chatWindow");
const cmdInput = document.getElementById("cmdInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");
const memoryList = document.getElementById("memoryList");
const clearMemory = document.getElementById("clearMemory");
const modeBadge = document.getElementById("modeBadge");
const clientStatus = document.getElementById("clientStatus");
const typingIndicator = document.getElementById("typing");

const MEMORY_KEY = "draco_memory_v2";
const MAX_MEMORY = 40;

// helpers
function addMessage(who, text) {
  if (!chatWindow) return;
  const role = who === "user" ? "user" : "bot";
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  if (role === "user") {
    el.textContent = text;
  } else {
    const safe = typeof text === "string" ? text : String(text ?? "");
    el.innerHTML = safe.replace(/\n/g, "<br>");
  }
  chatWindow.appendChild(el);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function showTyping() {
  if (typingIndicator) typingIndicator.classList.remove("hidden");
}

function hideTyping() {
  if (typingIndicator) typingIndicator.classList.add("hidden");
}

function setMode(mode) {
  modeBadge.className = "mode " + (mode || "idle");
  modeBadge.innerText = mode ? mode.charAt(0).toUpperCase() + mode.slice(1) : "Idle";
}

function saveMemory(item) {
  let mem = JSON.parse(localStorage.getItem(MEMORY_KEY) || "[]");
  mem.unshift({ time: new Date().toISOString(), text: item });
  mem = mem.slice(0, MAX_MEMORY);
  localStorage.setItem(MEMORY_KEY, JSON.stringify(mem));
  renderMemory();
}

function renderMemory() {
  const mem = JSON.parse(localStorage.getItem(MEMORY_KEY) || "[]");
  memoryList.innerHTML = "";
  mem.forEach(m => {
    const li = document.createElement("li");
    li.innerText = `${new Date(m.time).toLocaleString()} — ${m.text}`;
    memoryList.appendChild(li);
  });
}

// WebSocket connection
function connectWS() {
  ws = new WebSocket(WS_URL);
  clientStatus.innerText = "Connecting...";
  ws.onopen = () => {
    clientStatus.innerText = "Connected";
    addMessage("bot", "Dashboard connected to Draco bridge.");
  };
  ws.onclose = () => {
    clientStatus.innerText = "Disconnected";
    addMessage("bot", "Disconnected from Draco bridge. Reconnecting in 3s...");
    setTimeout(connectWS, 3000);
  };
  ws.onerror = (e) => {
    console.error("WS error", e);
  };
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      hideTyping();
      if (data.type === "speak") {
        // Draco said something
        addMessage("bot", data.text);
        saveMemory("Draco: " + data.text);
        setMode("speaking");
        setTimeout(()=> setMode("idle"), 700);
      } else if (data.type === "status") {
        setMode(data.mode);
      } else if (data.type === "info") {
        addMessage("bot", data.text);
      } else if (data.type === "raw") {
        addMessage("bot", data.text);
      }
      if (data.doc) {
        addMessage(
          "bot",
          `Document ready: <a href="${data.doc}" target="_blank">Download</a>`
        );
      }
    } catch (err) {
      console.log("ws msg", ev.data);
      hideTyping();
      addMessage("bot", ev.data);
    }
  };
}

connectWS();
renderMemory();
window.addEventListener("load", loadHistory);

// send button
sendBtn.addEventListener("click", () => {
  const t = cmdInput.value.trim();
  if (!t) return;
  sendCommand(t);
  cmdInput.value = "";
});

// enter key
cmdInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendBtn.click();
  }
});

// mic (Web Speech API)
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = "en-IN";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    recognizing = true;
    micBtn.innerText = "🎙️ (on)";
    setMode("listening");
  };
  recognition.onend = () => {
    recognizing = false;
    micBtn.innerText = "🎙️";
    setMode("idle");
  };
  recognition.onresult = (evt) => {
    const text = evt.results[0][0].transcript;
    sendCommand(text);
  };
  micBtn.addEventListener("click", () => {
    if (recognizing) {
      recognition.stop();
    } else {
      try { recognition.start(); } catch (e) { console.log(e); }
    }
  });
} else {
  micBtn.style.display = "none";
  addMessage("bot", "Voice recognition not supported in this browser.");
}

// clear memory
clearMemory.addEventListener("click", () => {
  localStorage.removeItem(MEMORY_KEY);
  renderMemory();
});

// small startup message
addMessage("bot", "Draco Dashboard ready. Connect bridge and speak to Draco.");

async function loadHistory() {
  try {
    const res = await fetch("/api/chat_history");
    if (!res.ok) return;
    const data = await res.json();
    if (!data || !Array.isArray(data.items)) return;
    data.items.forEach((m) => addMessage(m.who === "user" ? "user" : "bot", m.text));
  } catch (err) {
    console.error("Failed to load history", err);
  }
}
