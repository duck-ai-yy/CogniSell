// Frontend shell: customer data assets on the left, agent confirmation cards on the right.
// It stays API-only; GraphCore remains the SSOT behind /api/*.

const STATE_LABEL = {
  proposed: "Proposed",
  confirmed: "Confirmed",
  corrected: "Corrected",
  retired: "Retired",
};

let graphSnapshot = { nodes: [], edges: [] };
let selectedCustomerId = null;

let _toastTimer = null;
function toast(msg, isError) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.toggle("toast-error", !!isError);
  el.hidden = false;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.hidden = true; }, 4200);
}

async function api(path, opts) {
  try {
    const resp = await fetch(path, opts);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const detail = data.detail || data.error || ("HTTP " + resp.status);
      toast("Error: " + detail, true);
      return null;
    }
    return data;
  } catch (err) {
    toast("Network error: " + err.message + " (server running?)", true);
    return null;
  }
}

async function loadGraph() {
  const snapshot = await api("/api/graph");
  if (!snapshot) return;
  graphSnapshot = snapshot;
  if (!selectedCustomerId) {
    const primary = customers()[0];
    selectedCustomerId = primary ? primary.id : null;
  }
  renderAssets();
}

function nodesById() {
  return new Map(graphSnapshot.nodes.map((n) => [n.id, n]));
}

function customers() {
  return graphSnapshot.nodes
    .filter((n) => n.type === "person" || n.type === "company")
    .sort((a, b) => customerScore(b) - customerScore(a) || a.label.localeCompare(b.label));
}

function customerScore(node) {
  return relatedEdges(node.id).length + (node.id === "n_andreas" ? 100 : 0);
}

function relatedEdges(nodeId) {
  return graphSnapshot.edges.filter((e) => e.subject === nodeId || e.object === nodeId);
}

function trustedEdges(nodeId) {
  return relatedEdges(nodeId).filter((e) => e.status !== "retired");
}

function resolveObject(edge) {
  const node = nodesById().get(edge.object);
  return node ? node.label : String(edge.object);
}

function resolveSubject(edge) {
  const node = nodesById().get(edge.subject);
  return node ? node.label : edge.subject;
}

function companyForPerson(personId) {
  const map = nodesById();
  const edge = graphSnapshot.edges.find((e) =>
    e.subject === personId && e.predicate === "works_at" && e.status !== "retired");
  return edge && map.get(edge.object) ? map.get(edge.object).label : "";
}

function titleForPerson(personId) {
  const titleEdges = graphSnapshot.edges.filter((e) =>
    e.subject === personId && e.predicate === "has_title" && e.status !== "retired");
  const corrected = titleEdges.find((e) => e.status === "corrected");
  return (corrected || titleEdges[0])?.object || nodesById().get(personId)?.props?.title || "";
}

function renderAssets() {
  renderCustomerList();
  renderCustomerDetail();
  renderAssetSummary();
}

function renderAssetSummary() {
  const activeEdges = graphSnapshot.edges.filter((e) => e.status !== "retired");
  const pending = graphSnapshot.edges.filter((e) => e.status === "proposed").length;
  document.getElementById("asset-summary").textContent =
    `${graphSnapshot.nodes.length} nodes · ${activeEdges.length} active facts · ${pending} proposed`;
}

function renderCustomerList() {
  const list = document.getElementById("customer-list");
  const cs = customers();
  list.innerHTML = "";
  for (const customer of cs) {
    const facts = trustedEdges(customer.id);
    const proposed = facts.filter((e) => e.status === "proposed").length;
    const btn = document.createElement("button");
    btn.className = "customer-row" + (customer.id === selectedCustomerId ? " selected" : "");
    btn.type = "button";
    btn.innerHTML = `
      <span class="avatar ${customer.type}">${customer.type === "person" ? "P" : "C"}</span>
      <span class="customer-main">
        <span class="customer-name">${escapeHtml(customer.label)}</span>
        <span class="customer-meta">${escapeHtml(customerSubtitle(customer))}</span>
      </span>
      <span class="customer-badge">${facts.length}${proposed ? `/${proposed}` : ""}</span>
    `;
    btn.addEventListener("click", () => {
      selectedCustomerId = customer.id;
      renderAssets();
    });
    list.appendChild(btn);
  }
}

function customerSubtitle(node) {
  if (node.type === "person") {
    return [titleForPerson(node.id), companyForPerson(node.id)].filter(Boolean).join(" · ") || "Person";
  }
  return node.props?.industry || node.props?.domain || "Company";
}

function renderCustomerDetail() {
  const node = nodesById().get(selectedCustomerId);
  const empty = document.getElementById("detail-empty");
  const content = document.getElementById("detail-content");
  if (!node) {
    empty.hidden = false;
    content.hidden = true;
    return;
  }

  empty.hidden = true;
  content.hidden = false;
  document.getElementById("customer-kind").textContent = node.type;
  document.getElementById("customer-title").textContent = node.label;
  document.getElementById("customer-subtitle").textContent = customerSubtitle(node);

  const facts = trustedEdges(node.id);
  const avg = facts.length
    ? Math.round((facts.reduce((sum, e) => sum + Number(e.confidence || 0), 0) / facts.length) * 100)
    : 0;
  const stale = facts.filter((e) => isStale(e)).length;
  const proposed = facts.filter((e) => e.status === "proposed").length;

  document.getElementById("metric-facts").textContent = String(facts.length);
  document.getElementById("metric-confidence").textContent = `${avg}%`;
  document.getElementById("metric-stale").textContent = String(stale);
  document.getElementById("metric-proposed").textContent = String(proposed);
  renderStatePills(facts);
  renderFactList(node.id);
  renderAuditList(node.id);
}

function renderStatePills(facts) {
  const counts = { proposed: 0, confirmed: 0, corrected: 0, retired: 0 };
  for (const e of relatedEdges(selectedCustomerId)) counts[e.status] = (counts[e.status] || 0) + 1;
  const wrap = document.getElementById("state-pills");
  wrap.innerHTML = Object.entries(counts)
    .filter(([, count]) => count > 0)
    .map(([state, count]) => `<span class="pill ${state}">${STATE_LABEL[state]} ${count}</span>`)
    .join("");
}

function renderFactList(nodeId) {
  const list = document.getElementById("fact-list");
  const facts = trustedEdges(nodeId).sort((a, b) => statusRank(a.status) - statusRank(b.status));
  if (!facts.length) {
    list.innerHTML = `<div class="empty-inline">No active facts.</div>`;
    return;
  }
  list.innerHTML = "";
  for (const edge of facts) {
    const item = document.createElement("div");
    item.className = `fact-row ${edge.status}`;
    item.innerHTML = `
      <div class="fact-status"></div>
      <div class="fact-copy">
        <div class="fact-line">
          <strong>${escapeHtml(resolveSubject(edge))}</strong>
          <span>${escapeHtml(edge.predicate)}</span>
          <strong>${escapeHtml(resolveObject(edge))}</strong>
        </div>
        <div class="fact-meta">
          ${STATE_LABEL[edge.status]} · ${Math.round(edge.confidence * 100)}% · ${escapeHtml(edge.source)}
        </div>
      </div>
      <div class="fact-actions">
        ${edge.status === "proposed" ? `<button class="mini-btn" data-edge-confirm="${edge.id}">Confirm</button>` : ""}
      </div>
    `;
    list.appendChild(item);
  }
  list.querySelectorAll("[data-edge-confirm]").forEach((btn) => {
    btn.addEventListener("click", () => confirmFact(btn.dataset.edgeConfirm));
  });
}

function renderAuditList(nodeId) {
  const list = document.getElementById("audit-list");
  const edges = relatedEdges(nodeId).sort((a, b) => Number(b.t) - Number(a.t));
  if (!edges.length) {
    list.innerHTML = `<div class="empty-inline">No audit events.</div>`;
    return;
  }
  list.innerHTML = edges.map((edge) => `
    <div class="audit-row">
      <span class="audit-dot ${edge.status}"></span>
      <span class="audit-main">
        <strong>${escapeHtml(edge.predicate)}</strong>
        <span>${escapeHtml(resolveObject(edge))}</span>
      </span>
      <span class="audit-meta">
        ${escapeHtml(edge.extractor)} · ${escapeHtml(edge.source)}${edge.supersedes ? ` · supersedes ${escapeHtml(edge.supersedes)}` : ""}
      </span>
    </div>
  `).join("");
}

function statusRank(status) {
  return { proposed: 0, corrected: 1, confirmed: 2, retired: 3 }[status] ?? 9;
}

function isStale(edge) {
  return edge.status !== "retired" && (Date.now() / 1000 - Number(edge.t || 0)) > 90 * 86400;
}

async function confirmFact(edgeId) {
  const data = await api(`/api/edge/${edgeId}/confirm`, jsonPost({}));
  if (!data) return;
  toast("Fact confirmed.");
  await loadGraph();
  await refreshInbox();
}

// ---- inbox waterfall ----------------------------------------------------

async function refreshInbox() {
  const data = await api("/api/inbox");
  if (!data) return;
  renderInbox(data.cards || []);
}

function renderInbox(cards) {
  const list = document.getElementById("inbox-list");
  const empty = document.getElementById("inbox-empty");
  document.getElementById("inbox-count").textContent = `${cards.length} pending`;
  list.innerHTML = "";
  empty.hidden = cards.length > 0;
  for (const card of cards) list.appendChild(renderCard(card));
}

function renderCard(card) {
  const el = document.createElement("article");
  el.className = "agent-card";
  el.innerHTML = `
    <div class="card-top">
      <span class="card-tag">${escapeHtml(card.node_type)}</span>
      <span class="card-contact">${escapeHtml(contactName(card.contact_id))}</span>
    </div>
    <h3>${escapeHtml(card.title)}</h3>
    ${card.body ? `<div class="card-body"></div>` : ""}
    ${card.why ? `<div class="card-why">${escapeHtml(card.why)}</div>` : ""}
  `;
  if (card.body) {
    const bodyEl = el.querySelector(".card-body");
    if (card.node_type === "N4" && card.payload && card.payload.editable) {
      const ta = document.createElement("textarea");
      ta.className = "card-textarea";
      ta.value = card.body;
      bodyEl.appendChild(ta);
    } else {
      bodyEl.textContent = card.body;
    }
  }
  el.appendChild(cardActions(card, el));
  return el;
}

function contactName(contactId) {
  return contactId && nodesById().get(contactId) ? nodesById().get(contactId).label : "agent";
}

function cardActions(card, cardEl) {
  const wrap = document.createElement("div");
  wrap.className = "card-actions";
  const add = (label, fn, cls) => {
    const b = document.createElement("button");
    b.className = "btn " + (cls || "");
    b.textContent = label;
    b.addEventListener("click", fn);
    wrap.appendChild(b);
  };

  switch (card.node_type) {
    case "N2":
      add("Confirm", () => resolveCard(card.id, "confirm", {}));
      add("Correct", () => {
        const v = prompt("Corrected value:", card.payload.current || "");
        if (v != null && v.trim()) resolveCard(card.id, "correct", { new_object: v.trim() });
      }, "ghost");
      break;
    case "N3":
      (card.options || []).forEach((opt) => {
        add(opt.length > 30 ? opt.slice(0, 30) + "..." : opt,
          () => resolveCard(card.id, "choose", { choice: opt }), "ghost");
      });
      break;
    case "N4":
      add("Send", () => {
        const ta = cardEl.querySelector(".card-textarea");
        sendMail(card.contact_id, ta ? ta.value : card.body);
      });
      break;
    case "N5":
      add("Approve", () => resolveCard(card.id, "approve", {}));
      add("Correct", () => {
        const v = prompt("Corrected value:", card.body || "");
        if (v != null && v.trim()) resolveCard(card.id, "correct", { new_object: v.trim() });
      }, "ghost");
      break;
    case "N6":
      add("Approve", () => resolveCard(card.id, "approve", {}));
      break;
    default:
      add("Confirm", () => resolveCard(card.id, "confirm", {}));
  }
  return wrap;
}

async function resolveCard(cardId, action, payload) {
  const data = await api(`/api/inbox/${cardId}/resolve`, jsonPost({ action, payload }));
  if (!data) return;
  toast(data.note || "Done.");
  await loadGraph();
  await refreshInbox();
}

// ---- agent actions ------------------------------------------------------

async function actScan() {
  const data = await api("/api/scan", jsonPost({}));
  if (!data) return;
  toast(`Scanned ${data.candidates.length} contact; ${data.cards_added} task added.`);
  openCandidateModal(data.candidates);
  await loadGraph();
  await refreshInbox();
}

async function actStrategy() {
  const data = await api("/api/strategy", jsonPost({ contact_id: "n_andreas" }));
  if (!data) return;
  toast("Strategy card added.");
  const draft = await api("/api/mail/compose", jsonPost({ contact_id: "n_andreas" }));
  if (draft) toast("Outreach draft added.");
  await refreshInbox();
}

async function sendMail(contactId, body) {
  const data = await api("/api/mail/send", jsonPost({ contact_id: contactId, body }));
  if (!data) return;
  toast(`${data.receipt} · ${data.cards_added} task(s) added`);
  await loadGraph();
  await refreshInbox();
}

async function actCatchup() {
  const data = await api("/api/catchup/scan", jsonPost({}));
  if (!data) return;
  toast(`Catch-up scan: ${data.stale.length} stale tie(s).`);
  await refreshInbox();
}

// ---- candidate picker ---------------------------------------------------

function openCandidateModal(candidates) {
  const modal = document.getElementById("candidate-modal");
  const list = document.getElementById("candidate-list");
  list.innerHTML = "";
  candidates.forEach((c) => {
    const row = document.createElement("label");
    row.className = "cand-row";
    row.innerHTML = `<input type="checkbox" value="${c.node_id}" checked />
      <span><b>${escapeHtml(c.label)}</b><small>${escapeHtml(c.company)}</small></span>`;
    list.appendChild(row);
  });
  modal.hidden = false;
}

document.getElementById("candidate-cancel").addEventListener("click", () => {
  document.getElementById("candidate-modal").hidden = true;
});

document.getElementById("candidate-confirm").addEventListener("click", async () => {
  const ids = [...document.querySelectorAll("#candidate-list input:checked")].map((i) => i.value);
  document.getElementById("candidate-modal").hidden = true;
  if (ids.length === 0) { toast("No contact selected."); return; }
  const data = await api("/api/scan/select", jsonPost({ ids }));
  if (!data) return;
  selectedCustomerId = ids[0];
  toast(`Kept ${ids.length} contact.`);
  await loadGraph();
  await refreshInbox();
});

// ---- skills -------------------------------------------------------------

async function loadSkills() {
  const data = await api("/api/skills");
  if (!data) return;
  const panel = document.getElementById("skills-panel");
  panel.innerHTML = "";
  data.skills.forEach((s) => {
    const row = document.createElement("div");
    row.className = "skill-row";
    row.innerHTML = `<span class="skill-name">${escapeHtml(s.label)}</span>
      <span class="skill-desc">${escapeHtml(s.desc)}</span>`;
    const btn = document.createElement("button");
    btn.className = "btn ghost skill-toggle " + (s.enabled ? "on" : "off");
    btn.textContent = s.enabled ? "On" : "Off";
    btn.addEventListener("click", async () => {
      const r = await api(`/api/skills/${s.name}/toggle`, jsonPost({}));
      if (r) { toast(`${s.label} ${r.skill.enabled ? "enabled" : "disabled"}.`); loadSkills(); }
    });
    row.appendChild(btn);
    panel.appendChild(row);
  });
}

document.getElementById("skills-btn").addEventListener("click", () => {
  const p = document.getElementById("skills-panel");
  p.hidden = !p.hidden;
  if (!p.hidden) loadSkills();
});

// ---- voice --------------------------------------------------------------

async function sendVoice(transcript) {
  const data = await api("/api/voice", jsonPost({ transcript }));
  if (!data) return;
  const msg = (data.result && data.result.message) || "Done.";
  toast(`Voice: ${msg}`);
  if (data.action === "correct_company" && data.result.needs_input) {
    const v = prompt("Corrected company name:", "");
    if (v != null && v.trim()) {
      const r = await api(`/api/edge/${data.result.edge_id}/correct`, jsonPost({ new_object: v.trim() }));
      if (r) toast("Company corrected.");
    }
  }
  await loadGraph();
  await refreshInbox();
}

function setupVoice() {
  const btn = document.getElementById("voice-btn");
  const fallback = document.getElementById("voice-fallback");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    fallback.hidden = false;
    btn.addEventListener("click", () =>
      toast("Speech recognition unavailable; use text command.", true));
    return;
  }
  const recog = new SR();
  recog.lang = "en-US";
  recog.interimResults = false;
  recog.maxAlternatives = 1;
  btn.addEventListener("click", () => {
    try { recog.start(); toast("Listening..."); }
    catch (e) { fallback.hidden = false; toast("Mic error: " + e.message, true); }
  });
  recog.onresult = (ev) => sendVoice(ev.results[0][0].transcript);
  recog.onerror = (ev) => {
    fallback.hidden = false;
    toast("Voice error: " + ev.error, true);
  };
}

document.getElementById("voice-send").addEventListener("click", () => {
  const input = document.getElementById("voice-text");
  const t = input.value.trim();
  if (t) sendVoice(t);
  input.value = "";
});

// ---- helpers ------------------------------------------------------------

function jsonPost(body) {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

document.querySelectorAll("[data-act]").forEach((b) => {
  b.addEventListener("click", () => {
    const act = b.dataset.act;
    if (act === "scan") actScan();
    else if (act === "strategy") actStrategy();
    else if (act === "catchup") actCatchup();
  });
});

async function init() {
  await loadGraph();
  await refreshInbox();
  setupVoice();
}

init();
