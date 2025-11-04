/* draco.js
   - Connects to ws://localhost:8765
   - Provides voice input (Web Speech API) + typed input support
   - Displays chat messages and keeps Memory in localStorage
*/

const socket = io.connect("http://localhost:5000");

socket.on("connect", () => {
  appendMessage("draco", "Connected to Draco bridge ✅");
});

socket.on("draco_response", (data) => {
  appendMessage("draco", data.text);
  saveMemory("Draco: " + data.text);
  setMode("speaking");
  setTimeout(()=> setMode("idle"), 700);
});

function sendCommand(text) {
  appendMessage("user", text);
  saveMemory("You: " + text);
  socket.emit("user_command", { text });
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

const MEMORY_KEY = "draco_memory_v2";
const MAX_MEMORY = 40;

// helpers
function appendMessage(who, text) {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerText = text;
  el.appendChild(bubble);
  chatWindow.appendChild(el);
  chatWindow.scrollTop = chatWindow.scrollHeight;
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
    appendMessage("draco", "Dashboard connected to Draco bridge.");
  };
  ws.onclose = () => {
    clientStatus.innerText = "Disconnected";
    appendMessage("draco", "Disconnected from Draco bridge. Reconnecting in 3s...");
    setTimeout(connectWS, 3000);
  };
  ws.onerror = (e) => {
    console.error("WS error", e);
  };
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "speak") {
        // Draco said something
        appendMessage("draco", data.text);
        saveMemory("Draco: " + data.text);
        setMode("speaking");
        setTimeout(()=> setMode("idle"), 700);
      } else if (data.type === "status") {
        setMode(data.mode);
      } else if (data.type === "info") {
        appendMessage("draco", data.text);
      } else if (data.type === "raw") {
        appendMessage("draco", data.text);
      }
    } catch (err) {
      console.log("ws msg", ev.data);
      appendMessage("draco", ev.data);
    }
  };
}

connectWS();
renderMemory();

// send typed command
function sendCommand(text) {
  if (!text) return;
  appendMessage("user", text);
  saveMemory("You: " + text);
  // send to server
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "command", text }));
  } else {
    appendMessage("draco", "Bridge not connected. Start python_bridge.py first.");
  }
  setMode("listening");
  setTimeout(()=> setMode("idle"), 400);
}

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
  appendMessage("draco", "Voice recognition not supported in this browser.");
}

// clear memory
clearMemory.addEventListener("click", () => {
  localStorage.removeItem(MEMORY_KEY);
  renderMemory();
});

// small startup message
appendMessage("draco", "Draco Dashboard ready. Connect bridge and speak to Draco.");
