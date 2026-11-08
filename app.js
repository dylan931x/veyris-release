"use strict";
const TOKEN = document.querySelector('meta[name="veyris-token"]').content;
const $ = id => document.getElementById(id);
const messages = $("messages");
let currentMode = "ai";
const conversation = [];
function setMode(mode) {
  currentMode = mode;
  $("mode-ai").classList.toggle("selected", mode === "ai");
  $("mode-command").classList.toggle("selected", mode === "commands");
  $("command-input").placeholder = mode === "ai" ? "Ask your local AI anything..." : "Run an approved local command...";
  document.querySelectorAll("[data-command]").forEach(b => b.hidden = mode === "ai" ? b.dataset.ai === "false" : b.dataset.ai !== "false");
  $("command-input").focus();
}
async function checkBrain() {
  try {
    const s = await api("/api/brain-status");
    $("brain-status").textContent = s.ready ? "● AI ONLINE: " + s.model + "  //  CODE: " + (s.coder || "NOT INSTALLED") : "● AI MODEL NOT READY  //  " + s.message;
    $("brain-status").classList.toggle("offline", !s.ready);
  } catch {
    $("brain-status").textContent = "● LOCAL AI OFFLINE // CHECK OLLAMA";
    $("brain-status").classList.add("offline");
  }
}
$("mode-ai").addEventListener("click", () => setMode("ai"));
$("mode-command").addEventListener("click", () => setMode("commands"));
const fmtSize = n => {
  if (!Number.isFinite(Number(n))) return "—";
  const x = Number(n);
  return x >= 1073741824 ? (x / 1073741824).toFixed(2) + " GB" : (x / 1048576).toFixed(1) + " MB";
};
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function appendMessage(role, label, message) {
  const bubble = el("div", "bubble " + role);
  bubble.appendChild(el("span", "message-label", label));
  bubble.appendChild(el("p", "", message));
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}
function addRows(bubble, rows) {
  if (!rows.length) return;
  const list = el("ul", "results");
  rows.forEach(row => {
    const item = el("li");
    item.appendChild(el("strong", "", String(row[0])));
    item.appendChild(el("span", "mono", String(row[1])));
    list.appendChild(item);
  });
  bubble.appendChild(list);
  messages.scrollTop = messages.scrollHeight;
}
async function api(path, data) {
  const cfg = data === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-VEYRIS-Token": TOKEN},
    body: JSON.stringify(data)
  };
  const res = await fetch(path, cfg);
  const value = await res.json();
  if (!res.ok) throw new Error(value.error || "Request failed");
  return value;
}
function applyStatus(s) {
  $("hostname").textContent = s.host || "WINDOWS";
  $("cpu").textContent = s.cpu_percent == null ? "—" : Math.round(s.cpu_percent);
  $("ram").textContent = s.ram.percent;
  const diskPct = Math.round(100 * s.disk.used / s.disk.total);
  $("disk").textContent = diskPct;
  $("uptime").textContent = s.uptime_hours;
  $("threads").textContent = s.cpu_threads + " logical CPU processors";
  $("ram-caption").textContent = fmtSize(s.ram.used) + " of " + fmtSize(s.ram.total) + " in use";
  $("disk-caption").textContent = fmtSize(s.disk.free) + " available";
  [["cpu-bar", s.cpu_percent || 0], ["ram-bar", s.ram.percent], ["disk-bar", diskPct]]
    .forEach(([id, val]) => $(id).style.width = Math.max(0, Math.min(100, val)) + "%");
}
async function refreshStatus() {
  try { applyStatus(await api("/api/status")); }
  catch { $("threads").textContent = "Connection unavailable"; }
}
function showSecurity(data, bubble = null) {
  if (!data.available) {
    $("security-summary").textContent = data.error || "Unavailable";
    if (bubble) bubble.appendChild(el("p", "", data.error || "Defender status unavailable"));
    return;
  }
  const healthy = Boolean(data.enabled) && Boolean(data.realtime);
  $("security-summary").textContent =
    (healthy ? "● REAL-TIME PROTECTION ACTIVE" : "● CHECK PROTECTION SETTINGS") +
    "\nSignatures: " + (data.signatures || "unknown") +
    "\nBehavior monitoring: " + (data.behavior ? "enabled" : "disabled") +
    "\nTamper protection: " + (data.tamper ? "enabled" : "disabled");
  $("security-summary").style.whiteSpace = "pre-line";
  if (bubble) addRows(bubble, [
    ["Antivirus", data.enabled ? "Enabled" : "Disabled"],
    ["Real-time protection", data.realtime ? "Enabled" : "Disabled"],
    ["Behavior monitor", data.behavior ? "Enabled" : "Disabled"],
    ["Tamper protection", data.tamper ? "Enabled" : "Disabled"],
    ["Detected threat records", Array.isArray(data.threats) ? String(data.threats.length) : "Unknown"]
  ]);
}
function showFileItems(data, bubble = null) {
  if (data.error) {
    if (bubble) bubble.appendChild(el("p", "", data.error));
    $("file-result").textContent = data.error;
    return;
  }
  const rows = (data.items || []).map(f => [f.name, fmtSize(f.bytes)]);
  if (bubble) addRows(bubble, rows);
  const box = $("file-result");
  box.replaceChildren();
  box.appendChild(el("p", "", String(data.checked_files || 0) + " files checked; names and sizes only. Results may be limited."));
  const ul = el("ul");
  rows.slice(0, 12).forEach(([name, size]) => {
    const item = el("li");
    item.appendChild(el("div", "", name));
    item.appendChild(el("span", "", size));
    ul.appendChild(item);
  });
  box.appendChild(ul);
}
async function launch(action) {
  if (!window.confirm("Allow VEYRIS to launch " + action + " on this PC?")) return;
  try {
    const reply = await api("/api/action", {action});
    appendMessage(reply.ok ? "veyris" : "error", "VEYRIS // ACTION", reply.message || "Done");
  } catch (err) {
    appendMessage("error", "VEYRIS // ERROR", err.message);
  }
}
function renderAIAnswer(bubble, answer) {
  const paragraphs = bubble.querySelectorAll("p");
  paragraphs.forEach(p => p.remove());
  const delimiter = String.fromCharCode(96).repeat(3);
  const sections = answer.split(delimiter);
  sections.forEach((s, index) => {
    if (index % 2 === 0) {
      if (s.trim()) bubble.appendChild(el("p", "", s));
    } else {
      const langMatch = s.match(/^([^\r\n]*)[\r\n]/);
      const code = langMatch ? s.slice(langMatch[0].length) : s;
      const actions = el("div", "code-actions");
      actions.appendChild(el("span", "", langMatch ? langMatch[1] : "CODE"));
      const copy = el("button", "copy-code", "COPY CODE");
      copy.addEventListener("click", () => navigator.clipboard.writeText(code).then(() => {copy.textContent = "COPIED";}).catch(() => {copy.textContent = "SELECT CODE TO COPY";}));
      actions.appendChild(copy);
      const save = el("button", "copy-code", "SAVE .PINE");
      save.addEventListener("click", () => {
        const blob = new Blob([code], {type:"text/plain"});
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = langMatch && /pine/i.test(langMatch[1]) ? "VEYRIS_Indicator.pine" : "VEYRIS_Code.txt"; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1200);
      });
      actions.appendChild(save);
      bubble.appendChild(actions);
      const pre = el("pre", "generated-code");
      pre.appendChild(el("code", "", code));
      bubble.appendChild(pre);
    }
  });
}
function displayResponse(r) {
  const bubble = appendMessage("veyris", "VEYRIS // RESPONSE", r.message || "Completed");
  if (r.kind === "status" && r.data) {
    applyStatus(r.data);
    addRows(bubble, [
      ["CPU", (r.data.cpu_percent ?? "—") + "%"],
      ["Memory", r.data.ram.percent + "%"],
      ["Disk free", fmtSize(r.data.disk.free)],
      ["Uptime", r.data.uptime_hours + " hours"]
    ]);
  } else if (r.kind === "security") {
    showSecurity(r.data, bubble);
  } else if (r.kind === "files") {
    showFileItems(r.data, bubble);
  } else if (r.kind === "confirm") {
    const button = el("button", "inline-confirm", "CONFIRM LAUNCH ↗");
    button.addEventListener("click", () => launch(r.action), {once: true});
    bubble.appendChild(button);
  }
}
async function sendCommand(text) {
  if (!text.trim()) return;
  appendMessage("user", "YOU // REQUEST", text);
  const input = $("command-input");
  input.disabled = true;
  try {
    if (currentMode === "ai") {
      const thinking = appendMessage("veyris", "VEYRIS // PROCESSING", "Thinking on your local AI model...");
      try {
        const response = await api("/api/ai", {text, history: conversation.slice(-12)});
        thinking.remove();
        if (!response.ok) {
          appendMessage("error", "VEYRIS // AI NOT READY", response.error || "Model unavailable");
        } else {
          const bubble = appendMessage("veyris", "VEYRIS // " + response.model, "");
          renderAIAnswer(bubble, response.answer);
          if (response.warning) bubble.appendChild(el("p", "model-warning", response.warning));
          conversation.push({role: "user", content: text});
          conversation.push({role: "assistant", content: response.answer.slice(0, 14000)});
          while (conversation.length > 12) conversation.shift();
        }
      } catch (err) {
        thinking.remove();
        throw err;
      }
    } else {
      displayResponse(await api("/api/command", {text}));
    }
  } catch (err) {
    appendMessage("error", "VEYRIS // ERROR", err.message);
  } finally {
    input.disabled = false;
    input.focus();
  }
}
$("command-form").addEventListener("submit", e => {
  e.preventDefault();
  const text = $("command-input").value;
  $("command-input").value = "";
  sendCommand(text);
});
document.querySelectorAll("[data-command]").forEach(btn =>
  btn.addEventListener("click", () => sendCommand(btn.dataset.command)));
document.querySelectorAll("[data-action]").forEach(btn =>
  btn.addEventListener("click", () => launch(btn.dataset.action)));
$("ask-ai-side").addEventListener("click", () => launch("chatgpt"));
$("security-button").addEventListener("click", async () => {
  $("security-summary").textContent = "Checking Microsoft Defender...";
  try { showSecurity(await api("/api/security")); }
  catch (e) { $("security-summary").textContent = "Error: " + e.message; }
});
$("scan-files").addEventListener("click", async () => {
  const scope = $("file-scope").value;
  $("file-result").textContent = "Scanning " + scope + " (read-only)...";
  try { showFileItems(await api("/api/biggest?scope=" + encodeURIComponent(scope))); }
  catch (e) { $("file-result").textContent = "Error: " + e.message; }
});
document.querySelectorAll(".nav").forEach(btn => btn.addEventListener("click", () => {
  document.querySelectorAll(".nav").forEach(x => x.classList.remove("active"));
  btn.classList.add("active");
  $("nav-label").textContent = btn.textContent.trim().toUpperCase();
  const dest = {
    console: $("console-panel"),
    system: document.querySelector(".stats"),
    security: $("security-summary"),
    files: $("file-result")
  }[btn.dataset.nav];
  if (dest) dest.scrollIntoView({behavior: "smooth", block: "center"});
}));
const clock = () => $("clock").textContent = new Date().toLocaleString(undefined, {hour12: false});
clock();
setInterval(clock, 1000);
refreshStatus();
setInterval(refreshStatus, 12000);
setMode("ai");
checkBrain();
setInterval(checkBrain, 20000);

async function refreshUpdateStatus() {
  try {
    const s = await api("/api/update-status");
    const health = s.health ? (s.health.ok ? "PASS" : "NEEDS ATTENTION") : "NOT TESTED";
    const check = s.last_check ? new Date(s.last_check).toLocaleString() : "Not yet checked";
    const models = s.last_model_sync ? new Date(s.last_model_sync).toLocaleString() : "Not yet refreshed";
    $("update-summary").textContent =
      "● SYSTEM HEALTH: " + health +
      "\n● BACKUPS: " + s.backups +
      "\n● LAST CHECK: " + check +
      "\n● AI MODEL REFRESH: " + models +
      "\n● STATUS: " + (s.maintenance_running ? "WORKING..." : s.last_result) +
      "\n● APP CODE: approval required (no trusted release source)";
    $("update-summary").style.whiteSpace = "pre-line";
  } catch (err) {
    $("update-summary").textContent = "Updater unavailable: " + err.message;
  }
}
$("update-check").addEventListener("click", async () => {
  if (!window.confirm("Run VEYRIS code checks and create a backup? No code or models will be replaced.")) return;
  $("update-summary").textContent = "Checking files and creating backup...";
  try {
    const result = await api("/api/update-check", {});
    appendMessage(result.ok ? "veyris" : "error", "VEYRIS // MAINTENANCE", result.message);
  } catch (err) {
    appendMessage("error", "VEYRIS // MAINTENANCE", err.message);
  }
  refreshUpdateStatus();
});
$("update-sync").addEventListener("click", async () => {
  if (!window.confirm("Refresh the two installed Ollama models? This may download several gigabytes and temporarily use your CPU/GPU. VEYRIS will retain rollback copies.")) return;
  try {
    const result = await api("/api/update-sync", {});
    appendMessage(result.ok ? "veyris" : "error", "VEYRIS // MODEL UPDATER", result.message);
  } catch (err) {
    appendMessage("error", "VEYRIS // MODEL UPDATER", err.message);
  }
  refreshUpdateStatus();
});
refreshUpdateStatus();
setInterval(refreshUpdateStatus, 30000);

async function refreshReleaseChannel() {
  try {
    const info = await api("/api/release-status");
    const area = $("release-summary");
    if (!info.configured) {
      area.textContent = "SIGNED SOURCE: NOT CONNECTED\n" +
        info.reason + "\nCode upgrades remain disabled until a trusted GitHub repository and Ed25519 public key are configured.";
      $("release-check").disabled = true;
      $("release-check").title = "Connect an approved GitHub release channel first";
    } else {
      area.textContent =
        "SIGNED SOURCE: " + info.repository +
        "\nCURRENT VERSION: v" + info.current_version +
        "\nSTAGED: " + (info.staged_version || "None") +
        "\nLAST CHECK: " + (info.latest_checked || "Not yet") +
        "\nRESULT: " + (info.last_result || "Ready") +
        "\nINSTALL: Next VEYRIS launch after signature verification";
      $("release-check").disabled = false;
    }
    area.style.whiteSpace = "pre-line";
  } catch (err) {
    $("release-summary").textContent = "Release channel unavailable: " + err.message;
    $("release-check").disabled = true;
  }
}
$("release-check").addEventListener("click", async () => {
  if (!window.confirm("Check the pinned GitHub release channel for a publisher-signed update? Verified updates are only staged until next launch.")) return;
  $("release-summary").textContent = "Checking signed releases...";
  try {
    const answer = await api("/api/release-check", {});
    appendMessage(answer.ok ? "veyris" : "error", "VEYRIS // SIGNED RELEASE", answer.message);
  } catch (e) {
    appendMessage("error", "VEYRIS // SIGNED RELEASE", e.message);
  }
  refreshReleaseChannel();
});
refreshReleaseChannel();
setInterval(refreshReleaseChannel, 60000);
