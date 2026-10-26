// ── SkipMan UI ──────────────────────────────────────────────────────────────
// Talks to Python through window.pywebview.api (see skipman/api.py).
// Python pushes the whole queue state via SM.state(...) whenever it changes.

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let S = { rows: [] };          // latest state from Python
let selId = null;              // song shown in the tag panel
let userPicked = false;        // user clicked a row (don't auto-jump)
const edits = {};              // id -> {title, artist, album} typed locally
const albumEdits = {};         // album id -> {title, artist}
let clipLink = null;

const SM = (window.SM = {
  state(s) { S = s; render(); },
});

// ── Helpers ─────────────────────────────────────────────────────────────────
function songs() {
  const out = [];
  for (const r of S.rows) {
    if (r.type === "album") r.tracks.forEach((t) => out.push({ ...t, albumRow: r }));
    else out.push(r);
  }
  return out;
}
const byId = (id) => songs().find((s) => s.id === id);
const editable = (s) => s && ["identifying", "queued", "downloading", "ready",
  "error-send"].includes(s.status) && !(s.albumRow && s.albumRow.status === "confirm");

function statusHtml(r) {
  switch (r.status) {
    case "probing": return `<span class="stat amb">CHECKING…</span>`;
    case "identifying": return `<span class="stat amb">IDENTIFYING…</span>`;
    case "waiting": return r.dupe ? `<span class="stat amb">DUPE</span>` : `<span class="stat">—</span>`;
    case "queued": return `<span class="stat">WAITING</span>`;
    case "downloading": {
      const on = Math.round((r.progress || 0) / 10);
      let bar = "";
      for (let i = 0; i < 10; i++) bar += `<i class="${i < on ? "on" : ""}"></i>`;
      return `<span class="stat"><span class="mini">${bar}</span>${r.progress || 0}%</span>`;
    }
    case "ready": return `<span class="stat ready">READY</span>`;
    case "sending": return `<span class="stat amb">SENDING…</span>`;
    case "sent": return `<span class="stat ready">✓ SENT</span>`;
    case "dupe": return `<span class="stat amb">DUPE <button class="btn small inline-btn" data-act="skip" data-id="${r.id}">SKIP</button><button class="btn small inline-btn" data-act="anyway" data-id="${r.id}">GET IT ANYWAY</button></span>`;
    case "error": case "error-send":
      return `<span class="stat err" title="${esc(r.error)}">ERROR <button class="btn small inline-btn" data-act="retry" data-id="${r.id}">RETRY</button></span>`;
    default: return `<span class="stat">${esc(r.status)}</span>`;
  }
}

function label(s) {
  const e = edits[s.id] || s;
  const t = e.title || s.title || s.url;
  return e.artist ? `${esc(e.artist)} <span class="muted">—</span> ${esc(t)}` : esc(t);
}

function songRow(s, inAlbum, draggable) {
  const dot = s.confidence || "none";
  const num = inAlbum ? `<span class="num">${String(s.track_no || "").padStart(2, "0")}.</span>` : "";
  const extra = s.dupe && s.status !== "dupe" && inAlbum ? ` <span class="stat amb">[DUPE]</span>` : "";
  return `<div class="item ${s.id === selId ? "sel" : ""} ${s.status === "sent" ? "sent" : ""}"
      data-id="${s.id}" ${draggable ? 'draggable="true"' : ""}
      title="${esc(s.dupe || s.error || s.source || "")}">
    <span class="dot ${dot}"></span>
    <span class="name">${num}${label(s)}${extra}</span>
    ${statusHtml(s)}
    <span class="x" data-act="remove" data-id="${s.id}" title="Remove">×</span>
  </div>`;
}

function albumBlock(a) {
  const ae = albumEdits[a.id] || {};
  const confirm = a.status === "confirm";
  const ready = a.tracks.filter((t) => t.status === "ready").length;
  const dupes = a.tracks.filter((t) => t.dupe).length;
  const head = `<div class="album-head">
    <div class="top">
      <span><span class="tag">${a.as === "songs" ? "PLAYLIST → SONGS" : "ALBUM"}</span>
        · ${a.tracks.length} tracks ${a.status === "done" ? '<span class="stat ready">✓ DONE</span>' : ""}</span>
      <span class="row">
        ${confirm ? `<span class="seg">
            <button class="btn ${a.as !== "songs" ? "on" : ""}" data-act="as-album" data-id="${a.id}">ALBUM</button>
            <button class="btn ${a.as === "songs" ? "on" : ""}" data-act="as-songs" data-id="${a.id}">SEPARATE SONGS</button>
          </span>` : ""}
        ${confirm && dupes ? `<button class="btn small" data-act="drop-dupes" data-id="${a.id}">DROP DUPES (${dupes})</button>` : ""}
        ${confirm ? `<button class="btn accent small" data-act="album-go" data-id="${a.id}">DOWNLOAD ▶</button>` : ""}
        ${!confirm && ready ? `<button class="btn accent small" data-act="send-album" data-id="${a.id}">SEND ${ready} READY ♫</button>` : ""}
        <span class="x" data-act="remove" data-id="${a.id}" title="Remove album">×</span>
      </span>
    </div>
    ${a.as !== "songs" ? `<div class="album-fields">
      <input class="field" id="alb-t-${a.id}" data-album="${a.id}" data-k="title" placeholder="Album name" value="${esc(ae.title ?? a.title)}">
      <input class="field" id="alb-a-${a.id}" data-album="${a.id}" data-k="artist" placeholder="Album artist" value="${esc(ae.artist ?? a.artist)}">
    </div>` : ""}
    ${confirm ? `<div class="hint">Drag tracks to set the order. Nothing downloads until you hit DOWNLOAD.</div>` : ""}
  </div>`;
  const tracks = a.tracks.map((t) => songRow(t, true, confirm)).join("");
  return `<div class="album" data-album-id="${a.id}">${head}${tracks}</div>`;
}

// ── Render ──────────────────────────────────────────────────────────────────
function render() {
  $("ver").textContent = S.version ? "v" + S.version : "";
  const all = songs();
  $("queueLbl").textContent = `QUEUE (${all.filter((s) => s.status !== "sent").length})`;

  autoSelect();
  // Keep focus/caret in album fields across re-renders
  const ae = document.activeElement;
  const keep = ae && ae.dataset && ae.dataset.album ? [ae.id, ae.selectionStart, ae.selectionEnd] : null;
  $("list").innerHTML = S.rows.map((r) => (r.type === "album" ? albumBlock(r) : songRow(r))).join("");
  if (keep) {
    const el = $(keep[0]);
    if (el) { el.focus(); el.setSelectionRange(keep[1], keep[2]); }
  }

  // Status bar
  const st = $("status");
  st.textContent = S.status || "";
  st.className = "st " + (S.statusColor || "");
  const ready = all.filter((s) => s.status === "ready").length;
  const bits = [];
  if (S.downloading) bits.push(`⬇ ${S.downloading} downloading`);
  if (ready) bits.push(`${ready} ready`);
  $("counts").textContent = bits.join("  ·  ");

  // Update banner
  if (S.update) { $("updateMsg").textContent = S.update.message; $("updateBar").classList.remove("hidden"); }

  renderPanel();
}

function autoSelect() {
  const cur = byId(selId);
  const typing = ["fTitle", "fArtist", "fAlbum"].includes(document.activeElement.id);
  if (cur && editable(cur) && (typing || userPicked || cur.status === "ready" ||
      cur.status === "error-send")) return;
  const list = songs().filter(editable);
  const next = list.find((s) => s.status === "ready") || (cur && editable(cur) ? cur : list[0]);
  selId = next ? next.id : null;
  if (next && next.status === "ready") userPicked = false;
}

let panelFor = null;
function renderPanel() {
  const s = byId(selId);
  const show = !!s && editable(s);
  $("panel").classList.toggle("hidden", !show);
  $("idle").classList.toggle("hidden", show || songs().length > 0);
  if (!show) { panelFor = null; return; }

  const e = edits[s.id] || {};
  if (panelFor !== s.id) {           // switched song: load fields
    $("fTitle").value = e.title ?? s.title ?? "";
    $("fArtist").value = e.artist ?? s.artist ?? "";
    $("fAlbum").value = e.album ?? (s.albumRow ? s.albumRow.title : s.album) ?? "";
    panelFor = s.id;
  } else if (!edits[s.id]) {         // fresh identify result arrived
    for (const [k, id] of [["title", "fTitle"], ["artist", "fArtist"], ["album", "fAlbum"]]) {
      if (document.activeElement !== $(id)) $(id).value = (k === "album" && s.albumRow) ? s.albumRow.title : (s[k] || "");
    }
  }
  $("fAlbum").disabled = !!s.albumRow;
  $("fAlbum").title = s.albumRow ? "Set the album name on the album row above" : "";

  const why = $("whyLine");
  const word = { matched: "MATCHED", guess: "BEST GUESS", check: "CHECK ME" }[s.confidence] || "";
  why.className = "why " + (s.confidence || "");
  why.innerHTML = word ? `<span class="dot ${s.confidence}"></span>${word} · ${esc(s.source)}` : "";

  const art = $("art");
  if (s.art) { art.style.backgroundImage = `url("${s.art}")`; art.firstElementChild.textContent = ""; }
  else { art.style.backgroundImage = "none"; art.firstElementChild.textContent = "NO ART"; }

  const btn = $("sendBtn");
  if (s.status === "ready" || s.status === "error-send") { btn.disabled = false; btn.textContent = "♫ SEND TO APPLE MUSIC ↵"; }
  else if (s.status === "sending") { btn.disabled = true; btn.textContent = "SENDING…"; }
  else { btn.disabled = true; btn.textContent = "DOWNLOADING… (edit away)"; }
}

// ── Actions ─────────────────────────────────────────────────────────────────
function addFromBox() {
  const v = $("url").value.trim();
  if (!v) return;
  api().add_text(v);
  $("url").value = "";
}

let editTimer = null;
function onEdit() {
  const s = byId(selId);
  if (!s) return;
  edits[s.id] = { title: $("fTitle").value, artist: $("fArtist").value, album: $("fAlbum").value };
  clearTimeout(editTimer);
  editTimer = setTimeout(() => api().save_edit(s.id, edits[s.id].title, edits[s.id].artist, edits[s.id].album), 250);
}

function send() {
  const s = byId(selId);
  if (!s || $("sendBtn").disabled) return;
  const album = s.albumRow ? (albumEdits[s.albumRow.id]?.title ?? s.albumRow.title) : $("fAlbum").value;
  api().send(s.id, $("fTitle").value, $("fArtist").value, album);
  delete edits[s.id];
  userPicked = false;
  // Jump to the next ready song right away
  const nxt = songs().find((x) => x.id !== s.id && x.status === "ready");
  selId = nxt ? nxt.id : null;
  panelFor = null;
  renderPanel();
  if (nxt) $("fTitle").focus();
}

function skip() {
  const s = byId(selId);
  if (!s) return;
  api().remove(s.id);
  delete edits[s.id];
  selId = null; userPicked = false; panelFor = null;
}

$("addBtn").onclick = addFromBox;
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") addFromBox(); });
$("sendBtn").onclick = send;
$("skipBtn").onclick = skip;
$("clearBtn").onclick = () => api().clear_finished();
$("artBtn").onclick = () => selId && api().choose_art(selId);
$("noArtBtn").onclick = () => selId && api().set_art_none(selId);
$("restartBtn").onclick = () => api().restart();
for (const id of ["fTitle", "fArtist", "fAlbum"]) {
  $(id).addEventListener("input", onEdit);
  $(id).addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !acOpen()) { e.preventDefault(); send(); }
  });
}

// List clicks (rows + inline buttons)
$("list").addEventListener("click", (e) => {
  const act = e.target.closest("[data-act]");
  if (act) {
    const id = Number(act.dataset.id);
    e.stopPropagation();
    ({
      remove: () => api().remove(id),
      skip: () => api().remove(id),
      anyway: () => api().get_anyway(id),
      retry: () => api().retry(id),
      "as-album": () => api().album_set_kind(id, "album"),
      "as-songs": () => api().album_set_kind(id, "songs"),
      "drop-dupes": () => api().album_drop_dupes(id),
      "album-go": () => { flushAlbum(id); api().album_go(id); },
      "send-album": () => { flushAlbum(id); api().send_album(id); },
    }[act.dataset.act] || (() => {}))();
    return;
  }
  const row = e.target.closest(".item");
  if (row) {
    selId = Number(row.dataset.id); userPicked = true; panelFor = null;
    render();
  }
});

// Album name / artist fields
const albumTimers = {};
$("list").addEventListener("input", (e) => {
  const aid = e.target.dataset.album;
  if (!aid) return;
  const id = Number(aid);
  albumEdits[id] = albumEdits[id] || {};
  albumEdits[id][e.target.dataset.k] = e.target.value;
  clearTimeout(albumTimers[id]);
  albumTimers[id] = setTimeout(() => flushAlbum(id), 300);
});
function flushAlbum(id) {
  const ed = albumEdits[id];
  if (ed) api().album_update(id, ed.title ?? null, ed.artist ?? null);
}

// Drag to reorder album tracks
let dragId = null;
$("list").addEventListener("dragstart", (e) => {
  const row = e.target.closest(".item[draggable]");
  if (!row) return;
  dragId = Number(row.dataset.id);
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("application/x-skipman", String(dragId));
});
$("list").addEventListener("dragover", (e) => {
  if (dragId == null) return;
  const row = e.target.closest(".item[draggable]");
  document.querySelectorAll(".drag-over").forEach((x) => x.classList.remove("drag-over"));
  if (row) { e.preventDefault(); row.classList.add("drag-over"); }
});
$("list").addEventListener("drop", (e) => {
  if (dragId == null) return;
  e.preventDefault(); e.stopPropagation();
  const row = e.target.closest(".item[draggable]");
  const block = e.target.closest(".album");
  if (row && block) {
    const aid = Number(block.dataset.albumId);
    const ids = [...block.querySelectorAll(".item")].map((x) => Number(x.dataset.id));
    const from = ids.indexOf(dragId), to = ids.indexOf(Number(row.dataset.id));
    if (from >= 0 && to >= 0 && from !== to) {
      ids.splice(to, 0, ids.splice(from, 1)[0]);
      api().album_reorder(aid, ids);
    }
  }
  dragId = null;
  document.querySelectorAll(".drag-over").forEach((x) => x.classList.remove("drag-over"));
});
$("list").addEventListener("dragend", () => { dragId = null; });

// ── Drop links anywhere on the window ───────────────────────────────────────
let dragDepth = 0;
window.addEventListener("dragenter", (e) => { if (dragId == null) { dragDepth++; $("dropHint").classList.remove("hidden"); } });
window.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("dropHint").classList.add("hidden"); } });
window.addEventListener("dragover", (e) => { if (dragId == null) e.preventDefault(); });
window.addEventListener("drop", (e) => {
  dragDepth = 0; $("dropHint").classList.add("hidden");
  if (dragId != null) return;
  e.preventDefault();
  const dt = e.dataTransfer;
  const text = [dt.getData("text/uri-list"), dt.getData("text/plain"), dt.getData("URL")]
    .filter(Boolean).join("\n");
  if (text) api().add_text(text);
});

// Paste anywhere (outside a text field) adds links
document.addEventListener("paste", (e) => {
  if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  const text = e.clipboardData.getData("text");
  if (text) { e.preventDefault(); api().add_text(text); }
});

// ── Copied-link detection ───────────────────────────────────────────────────
async function checkClip() {
  try {
    const link = await api().check_clipboard();
    if (link) {
      clipLink = link;
      $("clipUrl").textContent = link.length > 70 ? link.slice(0, 67) + "…" : link;
      $("clipBar").classList.remove("hidden");
    }
  } catch (_) {}
}
$("clipAdd").onclick = () => { if (clipLink) api().add_text(clipLink); $("clipBar").classList.add("hidden"); };
$("clipNo").onclick = () => $("clipBar").classList.add("hidden");
window.addEventListener("focus", checkClip);

// ── Autofill dropdowns (artist / album) ─────────────────────────────────────
let acIdx = -1;
function acBox(input) { return input.parentElement.querySelector(".ac"); }
function acOpen() { return [...document.querySelectorAll(".ac")].some((b) => !b.classList.contains("hidden")); }
async function acShow(input) {
  const box = acBox(input);
  const q = input.value;
  const items = input.id === "fArtist" ? await api().suggest_artists(q)
    : await api().suggest_albums(q, $("fArtist").value);
  const filtered = (items || []).filter((x) => x.toLowerCase() !== q.toLowerCase());
  if (!q || !filtered.length || document.activeElement !== input) { box.classList.add("hidden"); return; }
  acIdx = -1;
  box.innerHTML = filtered.map((x) => `<div>${esc(x)}</div>`).join("");
  box.classList.remove("hidden");
}
function acPick(input, val) {
  input.value = val;
  acBox(input).classList.add("hidden");
  onEdit();
}
for (const id of ["fArtist", "fAlbum"]) {
  const input = $(id);
  input.addEventListener("input", () => acShow(input));
  input.addEventListener("blur", () => setTimeout(() => acBox(input).classList.add("hidden"), 150));
  input.addEventListener("keydown", (e) => {
    const box = acBox(input);
    if (box.classList.contains("hidden")) return;
    const opts = [...box.children];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      acIdx = (acIdx + (e.key === "ArrowDown" ? 1 : -1) + opts.length) % opts.length;
      opts.forEach((o, i) => o.classList.toggle("on", i === acIdx));
    } else if ((e.key === "Enter" || e.key === "Tab") && acIdx >= 0) {
      e.preventDefault(); acPick(input, opts[acIdx].textContent);
    } else if (e.key === "Escape") { box.classList.add("hidden"); }
  });
  acBox(input).addEventListener("mousedown", (e) => {
    if (e.target.parentElement === acBox(input)) acPick(input, e.target.textContent);
  });
}

// ── Settings ────────────────────────────────────────────────────────────────
async function openSettings() {
  const s = await api().get_settings();
  $("sDir").value = s.save_dir;
  $("sKey").value = s.acoustid_key || "";
  $("sKeyNote").textContent = s.acoustid_key
    ? (s.fingerprint_ready ? "Sound matching is ON." : "Key saved. Also needs the fpcalc tool (brew install chromaprint).")
    : "Free key from acoustid.org — lets SkipMan identify badly titled uploads by sound.";
  $("sVer").textContent = "SkipMan v" + s.version + " · updates itself from GitHub on launch";
  $("settings").classList.remove("hidden");
}
$("settingsBtn").onclick = openSettings;
$("setClose").onclick = () => $("settings").classList.add("hidden");
$("sDirBtn").onclick = async () => { $("sDir").value = await api().choose_save_dir(); };
$("sKeyBtn").onclick = async () => { await api().set_acoustid_key($("sKey").value); openSettings(); };

// ── Boot ────────────────────────────────────────────────────────────────────
window.addEventListener("pywebviewready", async () => {
  SM.state(await api().ready());
  checkClip();
  $("url").focus();
});
