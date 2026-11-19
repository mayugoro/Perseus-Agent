(() => {
  const chat = document.getElementById("chat");
  const input = document.getElementById("input");
  const form = document.getElementById("composer");
  const modelEl = document.getElementById("model");
  const statusEl = document.getElementById("status");
  const sessionsEl = document.getElementById("sessions");
  let busy = false;

  const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  function render(text) {
    let h = esc(text);
    h = h.replace(/```([\s\S]*?)```/g, (_, c) => `<pre>${c}</pre>`);
    h = h.replace(/`([^`]+)`/g, "<code>$1</code>");
    h = h.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    return h;
  }

  function bubble(who, text, cls = "") {
    const d = document.createElement("div");
    d.className = `msg ${who === "you" ? "user" : "bot"} ${cls}`;
    d.innerHTML = `<div class="who">${who === "you" ? "YOU" : "PERSEUS"}</div><div class="body">${render(text)}</div>`;
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
    return d;
  }

  async function status() {
    try {
      const r = await fetch("/api/status");
      const s = await r.json();
      modelEl.textContent = `☤ ${s.model}`;
      const pct = s.ctx_limit ? (100 * s.ctx_tokens / s.ctx_limit).toFixed(1) : "0";
      statusEl.textContent = `${s.mode} · ${s.reasoning || "-"} · ctx ${pct}% (${s.ctx_tokens}/${Math.round((s.ctx_limit || 0) / 1000)}k)`;
    } catch { statusEl.textContent = "offline"; }
  }

  async function sessions() {
    try {
      const r = await fetch("/api/sessions");
      const j = await r.json();
      sessionsEl.innerHTML = "";
      for (const s of j.sessions || []) {
        const d = document.createElement("div");
        d.className = "sess";
        d.innerHTML = `<div class="t">${esc(s.title || s.id)}</div><div class="m">${esc(s.rel || "")} · ${s.turns || 0} turns</div>`;
        d.onclick = () => resume(s.id);
        sessionsEl.appendChild(d);
      }
    } catch {}
  }

  async function resume(id) {
    const r = await fetch("/api/resume", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ id }) });
    const j = await r.json();
    if (j.error) return bubble("perseus", "resume: " + j.error);
    chat.innerHTML = "";
    for (const m of j.messages || []) {
      if (m.role === "user") bubble("you", m.content || "");
      else if (m.role === "assistant") bubble("perseus", m.content || "");
    }
    status();
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (busy) return;
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    input.style.height = "auto";
    bubble("you", text);
    const t = bubble("perseus", "⠋ thinking…", "thinking");
    busy = true;
    try {
      const r = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }) });
      const j = await r.json();
      t.classList.remove("thinking");
      t.querySelector(".body").innerHTML = render(j.text || j.error || "(empty)");
    } catch (err) {
      t.querySelector(".body").textContent = "error: " + err;
    } finally {
      busy = false;
      chat.scrollTop = chat.scrollHeight;
      status();
      sessions();
    }
  });

  document.getElementById("stopBtn").onclick = () => fetch("/api/stop", { method: "POST" });
  document.getElementById("newBtn").onclick = async () => { await fetch("/api/new", { method: "POST" }); chat.innerHTML = ""; status(); sessions(); };

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(160, input.scrollHeight) + "px"; });

  status(); sessions(); setInterval(status, 4000);
})();
