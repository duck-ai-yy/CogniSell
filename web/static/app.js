const AGENT_COLORS = {
  Scout: '#3b82f6', Enricher: '#10b981', Strategist: '#8b5cf6',
  Champion: '#f59e0b', Skeptic: '#ef4444', Closer: '#6366f1',
  Outreach: '#f97316', Digest: '#0d9488', Relationship: '#ec4899',
  'Social Monitor': '#eab308', Copilot: '#6b7280',
};
const PERSON_COLORS = ['#0d9488','#6366f1','#8b5cf6','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444'];
const COMPANY_COLORS = ['#1e293b','#334155','#1f2937','#27272a'];

let cy = null;
let SNAP = { nodes: [], edges: [] };
const CLIENT_CARDS = [];
let contactId = 'n_andreas';
const updatedNodes = new Set();

const $ = id => document.getElementById(id);
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function api(method, path, body) {
  const opt = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opt.body = JSON.stringify(body);
  const resp = await fetch(path, opt);
  if (!resp.ok) {
    let detail = 'HTTP ' + resp.status;
    try { detail = (await resp.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return resp.json();
}

function toast(msg) {
  const t = $('toast');
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.hidden = true; }, 3400);
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
}
function labelize(s) {
  return String(s).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
function relTime(t) {
  const d = (Date.now() / 1000 - t) / 86400;
  if (d < 1) return 'today';
  return Math.round(d) + 'd ago';
}

function nameHash(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return Math.abs(h);
}
function personColor(name) { return PERSON_COLORS[nameHash(name) % PERSON_COLORS.length]; }
function companyColor(name) { return COMPANY_COLORS[nameHash(name) % COMPANY_COLORS.length]; }

function makeAvatarSvg(name, color, size) {
  size = size || 120;
  const initials = name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  return 'data:image/svg+xml,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="'+size+'" height="'+size+'">' +
    '<circle cx="'+size/2+'" cy="'+size/2+'" r="'+size/2+'" fill="'+color+'"/>' +
    '<text x="'+size/2+'" y="'+size/2+'" text-anchor="middle" dy=".35em" ' +
    'font-family="Inter,system-ui,sans-serif" font-size="'+(size*0.38)+'" ' +
    'fill="white" font-weight="600">'+initials+'</text></svg>'
  );
}
function makeCompanySvg(name, color, size) {
  size = size || 100;
  const letter = name[0].toUpperCase();
  return 'data:image/svg+xml,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="'+size+'" height="'+size+'">' +
    '<rect width="'+size+'" height="'+size+'" rx="'+(size*0.2)+'" fill="'+color+'"/>' +
    '<text x="'+size/2+'" y="'+size/2+'" text-anchor="middle" dy=".36em" ' +
    'font-family="Inter,system-ui,sans-serif" font-size="'+(size*0.4)+'" ' +
    'fill="white" font-weight="700">'+letter+'</text></svg>'
  );
}

const CONTACT_PREDICATES = new Set(['works_at', 'met_at', 'has_title']);

function isColdContact(nodeId) {
  const edges = SNAP.edges.filter(e =>
    e.subject === nodeId && e.status !== 'retired' && CONTACT_PREDICATES.has(e.predicate));
  if (edges.length === 0) return false;
  const now = Date.now() / 1000;
  const newest = Math.max(...edges.map(e => e.t));
  return (now - newest) / 86400 > 85;
}

function getContactTemp(nodeId) {
  const edges = SNAP.edges.filter(e =>
    e.subject === nodeId && e.status !== 'retired' && CONTACT_PREDICATES.has(e.predicate));
  if (edges.length === 0) return { label: 'New', cls: 'warm' };
  const now = Date.now() / 1000;
  const days = (now - Math.max(...edges.map(e => e.t))) / 86400;
  if (days > 85) return { label: 'Cold · ' + Math.round(days) + 'd', cls: 'cold' };
  if (days > 30) return { label: 'Warm · ' + Math.round(days) + 'd', cls: 'warm' };
  return { label: 'Hot', cls: 'hot' };
}

function literalId(edge) {
  // Use a hash-like or encoded ID based on the literal value so identical literals map to the same node
  let str = String(edge.object);
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = Math.imul(31, hash) + str.charCodeAt(i) | 0;
  return 'lit_' + Math.abs(hash).toString(16);
}

function buildElements(snap) {
  const nodeIds = new Set(snap.nodes.map(n => n.id));
  const nodes = [];
  for (const n of snap.nodes) {
    const d = { id: n.id, label: n.label, ntype: n.type, ...n.props };
    if (n.type === 'person') {
      const cold = isColdContact(n.id);
      d.avatar = makeAvatarSvg(n.label, cold ? '#9ca3af' : personColor(n.label));
      if (cold) d.isCold = true;
      if (updatedNodes.has(n.id)) d.hasUpdate = true;
    } else if (n.type === 'company') {
      d.avatar = makeCompanySvg(n.label, companyColor(n.label));
    }
    nodes.push({ data: d });
  }
  const edges = [];
  const edgeMap = new Map();
  const statusWeight = { confirmed: 4, corrected: 3, proposed: 2, retired: 1 };

  for (const e of snap.edges) {
    if (!nodeIds.has(e.subject)) continue;
    let target = e.object;
    if (!nodeIds.has(e.object)) {
      target = literalId(e);
      nodes.push({ data: {
        id: target, label: String(e.object), ntype: 'literal',
      }});
    }
    const key = `${e.subject}__${target}`;
    const newEdge = { data: {
      id: e.id, source: e.subject, target,
      label: e.predicate.replace(/_/g, ' '),
      status: e.status, confidence: e.confidence,
      extractor: e.extractor, esource: e.source, t: e.t,
    }};
    
    if (!edgeMap.has(key)) {
      edgeMap.set(key, newEdge);
    } else {
      const existing = edgeMap.get(key);
      const wExisting = statusWeight[existing.data.status] || 0;
      const wNew = statusWeight[newEdge.data.status] || 0;
      if (wNew > wExisting || (wNew === wExisting && newEdge.data.t > existing.data.t)) {
         edgeMap.set(key, newEdge);
      }
    }
  }
  
  for (const edge of edgeMap.values()) {
    edges.push(edge);
  }
  return { nodes, edges };
}

const CY_STYLE = [
  { selector: 'node', style: {
    label: 'data(label)', color: '#52525b', 'font-size': '11px', 'font-weight': 500,
    'font-family': 'Inter, system-ui, sans-serif',
    'text-valign': 'bottom', 'text-margin-y': 8,
    'text-max-width': '100px', 'text-wrap': 'wrap',
    width: 44, height: 44,
    'background-color': '#d4d4d8',
    'border-width': 2, 'border-color': '#ffffff',
  }},
  { selector: 'node[ntype="person"]', style: {
    'background-image': 'data(avatar)', 'background-fit': 'cover',
    'background-color': '#e5e5e5',
    shape: 'ellipse', width: 52, height: 52,
  }},
  { selector: 'node[ntype="company"]', style: {
    'background-image': 'data(avatar)', 'background-fit': 'cover',
    'background-color': '#334155',
    shape: 'round-rectangle', width: 44, height: 44,
    'font-size': '10px',
  }},
  { selector: 'node[ntype="topic"]', style: {
    'background-color': '#f59e0b', shape: 'ellipse',
    width: 26, height: 26, 'font-size': '10px', color: '#a1a1aa',
  }},
  { selector: 'node[ntype="literal"]', style: {
    'background-color': '#f0f0ee', shape: 'round-rectangle',
    width: 14, height: 14, 'font-size': '10px', color: '#a1a1aa',
    'border-width': 1, 'border-color': '#e5e5e3',
  }},
  { selector: 'node[?isCold]', style: { opacity: 0.5 } },
  { selector: 'node:selected', style: {
    'border-color': '#0d9488', 'border-width': 3,
  }},
  { selector: 'node[?hasUpdate]', style: {
    'border-color': '#ef4444', 'border-width': 3, 'border-opacity': 1,
  }},
  { selector: 'edge', style: {
    'curve-style': 'bezier', 'target-arrow-shape': 'triangle',
    label: 'data(label)', 'font-size': '9px', color: '#a1a1aa',
    'font-family': 'Inter, system-ui, sans-serif',
    'text-rotation': 'autorotate',
    'text-background-color': '#f7f7f5', 'text-background-opacity': 0.9,
    'text-background-padding': '2px',
    width: 'mapData(confidence, 0, 1, 1, 4)',
  }},
  { selector: 'edge[status="proposed"]', style: {
    'line-style': 'dashed', 'line-color': '#a1a1aa',
    'target-arrow-color': '#a1a1aa', opacity: 0.55,
  }},
  { selector: 'edge[status="confirmed"]', style: {
    'line-style': 'solid', 'line-color': '#0d9488',
    'target-arrow-color': '#0d9488', opacity: 1,
  }},
  { selector: 'edge[status="corrected"]', style: {
    'line-style': 'solid', 'line-color': '#d97706',
    'target-arrow-color': '#d97706', opacity: 1,
  }},
  { selector: 'edge[status="retired"]', style: {
    'line-style': 'dotted', 'line-color': '#d4d4d8',
    'target-arrow-color': '#d4d4d8', opacity: 0.3,
  }},
];

function runLayout() {
  cy.layout({
    name: 'cose', animate: true, animationDuration: 500,
    padding: 50, nodeRepulsion: () => 10000, idealEdgeLength: () => 100, fit: true,
  }).run();
}

async function loadGraph() {
  let snap;
  try { snap = await api('GET', '/api/graph'); }
  catch (err) { toast('Could not load graph: ' + err.message); return; }
  SNAP = snap;
  const els = buildElements(snap);
  const wantIds = new Set(els.nodes.map(n => n.data.id));

  if (!cy) {
    cy = cytoscape({
      container: $('cy'),
      elements: [...els.nodes, ...els.edges],
      style: CY_STYLE,
      minZoom: 0.3, maxZoom: 2.4, wheelSensitivity: 0.18,
    });
    cy.on('tap', 'node', ev => {
      const ntype = ev.target.data('ntype');
      if (ntype === 'person' || ntype === 'company') openDetail(ev.target.id());
    });
    cy.on('tap', 'edge', ev => openEdgeEditor(ev.target.data()));
    runLayout();
    updateRelCount();
    return;
  }

  let added = 0;
  cy.nodes().forEach(n => { if (!wantIds.has(n.id())) n.remove(); });
  els.nodes.forEach(ne => {
    const existing = cy.getElementById(ne.data.id);
    if (existing.empty()) {
      cy.add(ne); added++;
    } else {
      Object.entries(ne.data).forEach(([k, v]) => existing.data(k, v));
    }
  });
  cy.edges().remove();
  cy.add(els.edges);
  if (added > 0) runLayout();
  updateRelCount();
}

function updateRelCount() {
  const people = SNAP.nodes.filter(n => n.type === 'person').length;
  $('rel-count').textContent = people;
}

function focusNode(nodeId) {
  if (!cy) return;
  const n = cy.getElementById(nodeId);
  if (n.empty()) return;
  cy.animate({ center: { eles: n }, zoom: 1.5 }, { duration: 400 });
  n.select();
}

function openDetail(nodeId) {
  const node = SNAP.nodes.find(n => n.id === nodeId);
  if (!node) return;

  if (updatedNodes.has(nodeId)) {
    updatedNodes.delete(nodeId);
    const cyNode = cy.getElementById(nodeId);
    if (!cyNode.empty()) cyNode.data('hasUpdate', undefined);
  }

  const props = node.props || {};
  const activeEdges = SNAP.edges.filter(e => e.subject === nodeId && e.status !== 'retired');
  const retiredEdges = SNAP.edges.filter(e => e.subject === nodeId && e.status === 'retired');
  const cold = isColdContact(nodeId);
  const temp = getContactTemp(nodeId);
  const hasUp = updatedNodes.has(nodeId);
  const color = node.type === 'person' ? personColor(node.label) : companyColor(node.label);
  const avatarSvg = node.type === 'person'
    ? makeAvatarSvg(node.label, cold ? '#9ca3af' : color, 120)
    : makeCompanySvg(node.label, color, 120);

  const companyEdge = activeEdges.find(e => e.predicate === 'works_at');
  const companyNode = companyEdge ? SNAP.nodes.find(n => n.id === companyEdge.object) : null;

  let html = '';
  html += '<div class="detail-avatar' + (cold ? ' cold' : '') + (hasUp ? ' has-update' : '') + '">';
  html += '<img src="' + avatarSvg + '" alt="' + esc(node.label) + '" /></div>';
  html += '<div class="detail-name">' + esc(node.label) + '</div>';
  if (props.title) html += '<div class="detail-role">' + esc(props.title) + '</div>';
  if (companyNode) html += '<div class="detail-company">' + esc(companyNode.label) + '</div>';
  if (node.type === 'person') {
    html += '<div class="detail-temp ' + temp.cls + '">' + temp.label + '</div>';
  }

  const attrKeys = Object.entries(props).filter(([k]) => k !== 'title');
  if (attrKeys.length) {
    html += '<div class="detail-section"><div class="detail-section-title">Details</div>';
    for (const [k, v] of attrKeys) {
      if (!v) continue;
      html += '<div class="detail-attr"><span class="k">' + labelize(k) + '</span><span class="v">' + esc(v) + '</span></div>';
    }
    html += '</div>';
  }

  if (activeEdges.length) {
    html += '<div class="detail-section"><div class="detail-section-title">Knowledge</div>';
    for (const e of activeEdges) {
      const objNode = SNAP.nodes.find(n => n.id === e.object);
      const obj = objNode ? objNode.label : e.object;
      const isNew = e.source === 'social_monitor';
      html += '<div class="detail-edge' + (isNew ? ' change-highlight' : '') + '">';
      html += '<div class="rel">' + labelize(e.predicate) + ' &rarr; <b>' + esc(obj) + '</b></div>';
      html += '<div class="meta"><span class="status-chip ' + e.status + '">' + e.status + '</span>';
      html += '<span>' + Math.round(e.confidence * 100) + '%</span>';
      html += '<span>&middot; ' + e.extractor + '</span>';
      html += '<span>&middot; ' + relTime(e.t) + '</span></div></div>';
    }
    html += '</div>';
  }

  if (retiredEdges.length) {
    html += '<div class="detail-section"><div class="detail-section-title">History (superseded)</div>';
    for (const e of retiredEdges) {
      const objNode = SNAP.nodes.find(n => n.id === e.object);
      html += '<div class="detail-edge" style="opacity:.55">';
      html += '<div class="rel">' + labelize(e.predicate) + ' &rarr; ' + esc(objNode ? objNode.label : e.object) + '</div>';
      html += '<div class="meta"><span class="status-chip retired">retired</span><span>superseded</span></div></div>';
    }
    html += '</div>';
  }

  $('detail-content').innerHTML = html;
  $('detail-panel').hidden = false;
}

$('detail-close').addEventListener('click', () => { $('detail-panel').hidden = true; });

function openEdgeEditor(d) {
  const objNode = SNAP.nodes.find(n => n.id === d.target);
  const objLabel = objNode ? objNode.label : (d.target.startsWith('lit_') ? d.label : d.target);

  let html = '';
  html += '<div class="detail-section-title">Edit belief</div>';
  html += '<div class="detail-name">' + labelize(d.label) + '</div>';
  html += '<div class="meta" style="display:flex;gap:6px;margin:8px 0;font-size:11px;color:#a1a1aa">';
  html += '<span class="status-chip ' + d.status + '">' + d.status + '</span>';
  html += '<span>' + Math.round(d.confidence * 100) + '% &middot; ' + d.extractor + '</span></div>';
  html += '<div class="edge-edit-row">';
  html += '<input class="edge-edit-input" id="edge-edit-val" value="' + esc(objLabel) + '" />';
  html += '<button class="edge-edit-btn" id="edge-save-btn">Correct</button></div>';
  html += '<div class="card-hint" style="margin-top:10px">Correcting retires the old belief and records a new one that supersedes it.</div>';

  $('detail-content').innerHTML = html;
  $('detail-panel').hidden = false;

  $('edge-save-btn').onclick = async () => {
    const val = $('edge-edit-val').value.trim();
    if (!val) return;
    try {
      const res = await api('POST', '/api/edge/' + d.id + '/correct', { new_object: val });
      $('detail-panel').hidden = true;
      await loadGraph();
      toast(res.recomputed_catchup
        ? 'Belief corrected · catch-up suggestion recomputed.'
        : 'Belief corrected · old retired, new edge supersedes it.');
    } catch (err) { toast('Could not correct: ' + err.message); }
  };
}

// ── Agent Activity Stream ──

function showActivity() {
  $('activity-stream').hidden = false;
  $('empty-state').style.display = 'none';
}

let _typeCancel = new WeakMap();

async function typeText(el, text, speed) {
  speed = speed || 16;
  const token = {};
  _typeCancel.set(el, token);
  el.textContent = '';
  for (let i = 0; i < text.length; i++) {
    if (_typeCancel.get(el) !== token) return;
    el.textContent += text[i];
    if (i % 3 === 0) await sleep(speed);
  }
}

function actStream(agent, text) {
  showActivity();
  const row = document.createElement('div');
  row.className = 'stream-item';
  const color = AGENT_COLORS[agent] || '#6b7280';
  row.innerHTML =
    '<span class="agent-dot" style="background:' + color + '"></span>' +
    '<span class="agent-label">' + agent + '</span>' +
    '<span class="agent-text"></span>' +
    '<span class="agent-status"><span class="spinner-sm"></span></span>';
  $('stream-items').appendChild(row);
  scrollRight();
  typeText(row.querySelector('.agent-text'), text);
  return row;
}

function actDone(row, result) {
  const textEl = row.querySelector('.agent-text');
  _typeCancel.set(textEl, null);
  row.querySelector('.agent-status').innerHTML = '<span class="check-mark">✓</span>';
  if (result) textEl.textContent = result;
}

function scrollRight() {
  const s = $('right-scroll');
  s.scrollTop = s.scrollHeight;
}

// ── Decision Cards ──

function pushCard(card) {
  CLIENT_CARDS.push(card);
  renderCards();
}
function removeCard(id) {
  const i = CLIENT_CARDS.findIndex(c => c.id === id);
  if (i >= 0) CLIENT_CARDS.splice(i, 1);
  renderCards();
}

async function refreshServerCards() {
  let serverCards = [];
  try { serverCards = (await api('GET', '/api/inbox')).cards || []; } catch (_) {}
  return serverCards.filter(c => c.node_type !== 'N2' && c.node_type !== 'N3');
}

async function renderCards() {
  const server = await refreshServerCards();
  const all = [...CLIENT_CARDS, ...server];
  const area = $('cards-area');
  area.innerHTML = '';
  for (const c of all) area.appendChild(buildCardEl(c));
  scrollRight();
}

const BADGE_MAP = {
  FLOW_CONFIRM: ['Confirm', 'confirm'],
  FLOW_MEET: ['Details', 'details'],
  N3: ['Strategy', 'strategy'],
  N4: ['Draft', 'draft'],
  N6: ['Warm-up', 'warmup'],
  N8: ['Signal', 'signal'],
};

function buildCardEl(c) {
  const el = document.createElement('div');
  el.className = 'decision-card';
  const [badgeText, badgeCls] = BADGE_MAP[c.node_type] || ['Review', 'details'];

  let body = '';
  let actions = '';

  if (c.node_type === 'FLOW_CONFIRM') {
    body = '<div class="card-body">' + esc(c.body) + '</div>';
    actions = '<button class="btn btn-primary" data-act="confirm-contact">Confirm &amp; file</button>' +
              '<button class="btn btn-ghost" data-act="dismiss">Not now</button>';
  } else if (c.node_type === 'FLOW_MEET') {
    body = '<div class="card-field-row">' +
      '<input class="card-input" id="meet-when" placeholder="When? e.g. Hannover Messe, April" />' +
      '<input class="card-input" id="meet-where" placeholder="Where? e.g. Hall 6, Booth C24" /></div>';
    actions = '<button class="btn btn-primary" data-act="save-meet">Save to record</button>';
  } else if (c.node_type === 'N4') {
    body = '<textarea class="card-textarea" id="mail-' + c.id + '">' + esc(c.body) + '</textarea>';
    actions = '<button class="btn btn-primary" data-act="send">Approve &amp; send</button>' +
              '<button class="btn btn-ghost" data-act="dismiss">Discard</button>';
  } else if (c.node_type === 'N6') {
    body = '<div class="card-body">' + esc(c.body) + '</div>';
    actions = '<button class="btn btn-primary" data-act="approve-warmup">Approve warm-up</button>' +
              '<button class="btn btn-ghost" data-act="dismiss">Dismiss</button>';
  } else if (c.node_type === 'N8') {
    body = '<div class="card-body">' + esc(c.body) + '</div>';
    actions = '<button class="btn btn-primary" data-act="approve-signal">Follow up</button>' +
              '<button class="btn btn-ghost" data-act="dismiss">Dismiss</button>';
  } else {
    body = '<div class="card-body">' + esc(c.body || '') + '</div>';
    actions = '<button class="btn btn-primary" data-act="approve">Approve</button>' +
              '<button class="btn btn-ghost" data-act="dismiss">Dismiss</button>';
  }

  el.innerHTML =
    '<div class="card-header"><span class="card-badge ' + badgeCls + '">' + badgeText + '</span>' +
    '<span class="card-title">' + esc(c.title) + '</span></div>' +
    body +
    (c.why ? '<div class="card-hint">' + esc(c.why) + '</div>' : '') +
    '<div class="card-actions">' + actions + '</div>';

  el.querySelectorAll('button[data-act]').forEach(b =>
    b.addEventListener('click', () => onCardAction(c, b.dataset.act)));
  return el;
}

async function onCardAction(card, act) {
  try {
    if (act === 'dismiss') { removeCard(card.id); return; }
    if (act === 'confirm-contact') return confirmContact(card);
    if (act === 'save-meet') return saveMeet();
    if (act === 'send') {
      const textarea = document.getElementById('mail-' + card.id);
      return sendMail(card, textarea ? textarea.value : card.body);
    }
    if (act === 'approve-warmup' || act === 'approve-signal' || act === 'approve') {
      await api('POST', '/api/inbox/' + card.id + '/resolve', { action: 'approve', payload: {} });
      toast('Approved.');
      await loadGraph();
      await renderCards();
    }
  } catch (err) { toast('Action failed: ' + err.message); }
}

// ── Complete Demo Flow ──

async function scanFlow() {
  $('empty-state').style.display = 'none';

  const r1 = actStream('Scout', 'Reading business card via OCR...');
  await sleep(1000);
  let scan;
  try {
    if (useCamera) {
      const video = $('camera-video');
      const canvas = $('camera-canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      
      const blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg', 0.9));
      const formData = new FormData();
      formData.append('file', blob, 'camera_scan.jpg');
      
      const resp = await fetch('/api/scan', { method: 'POST', body: formData });
      if (!resp.ok) {
        let detail = 'HTTP ' + resp.status;
        try { detail = (await resp.json()).detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      scan = await resp.json();
    } else if (uploadedFile) {
      const formData = new FormData();
      formData.append('file', uploadedFile, uploadedFile.name);
      const resp = await fetch('/api/scan', { method: 'POST', body: formData });
      if (!resp.ok) {
        let detail = 'HTTP ' + resp.status;
        try { detail = (await resp.json()).detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      scan = await resp.json();
    } else {
      scan = await api('POST', '/api/scan');
    }
  } catch (err) { actDone(r1, 'Scan failed: ' + err.message); return; }
  const cand = (scan.candidates || [])[0] || {};
  contactId = cand.node_id || contactId;
  actDone(r1, 'Found: ' + (cand.label || 'contact') + ' · ' + (cand.company || ''));
  await loadGraph();
  focusNode(contactId);

  await sleep(400);
  const r2 = actStream('Enricher', 'Matching company & pulling public profiles...');
  await sleep(1100);
  actDone(r2, 'Linked to ' + (cand.company || 'company') + ' · Steel manufacturing');
  await loadGraph();

  await sleep(300);
  pushCard({
    id: 'flow_confirm', node_type: 'FLOW_CONFIRM',
    title: (cand.label || 'New contact') + ' — ' + (cand.company || ''),
    body: 'Scanned the card and created a provisional node on the left. The dashed edge means it\'s proposed — confirm to file it as a trusted contact.',
    why: 'Nothing is trusted until you confirm. The node stays proposed on the graph until then.',
  });
}

async function confirmContact(card) {
  removeCard(card.id);
  const r = actStream('Scout', 'Filing contact & enriching company facts...');
  await api('POST', '/api/scan/select', { ids: [contactId] });
  await sleep(800);
  actDone(r, 'Filed contact & retrieved online data');
  await loadGraph();
  focusNode(contactId);

  await sleep(300);
  pushCard({
    id: 'flow_meet', node_type: 'FLOW_MEET',
    title: 'Add meeting details while they\'re fresh',
    why: 'Where and when you met sharpens every future suggestion.',
  });
}

async function saveMeet() {
  const when = ($('meet-when') ? $('meet-when').value : '') || 'Hannover Messe, April';
  const where = ($('meet-where') ? $('meet-where').value : '') || 'Hall 6, Booth C24';
  removeCard('flow_meet');
  const r = actStream('Copilot', 'Saving meeting context to the record...');
  await api('POST', '/api/contact/' + contactId + '/meet', { when, where });
  await sleep(700);
  actDone(r, 'Recorded: met at ' + where);
  await loadGraph();
  focusNode(contactId);

  await sleep(500);
  draftFollowup();
}

async function draftFollowup() {
  const rs = actStream('Strategist', 'Debating approach — Champion · Skeptic · Closer...');
  let strat;
  try { strat = await api('POST', '/api/strategy', { contact_id: contactId }); }
  catch (err) { actDone(rs, 'Strategy failed'); return; }

  const roles = (strat.debate && strat.debate.roles) || [];
  await sleep(1000);
  actDone(rs, 'Converged: ' + ((strat.debate.strategy_card || {}).approach_angle || '').slice(0, 60) + '...');

  for (const role of roles) {
    const rr = actStream(role.role, role.stance);
    await sleep(500);
    actDone(rr, role.stance);
  }

  await sleep(400);
  const rc = actStream('Outreach', 'Drafting follow-up email using graph context...');
  await api('POST', '/api/mail/compose', { contact_id: contactId });
  await sleep(900);
  actDone(rc, 'Draft ready for your review');
  await renderCards();
}

async function sendMail(card, body) {
  removeCard(card.id);
  const r = actStream('Outreach', 'Sending email & logging the thread...');
  await api('POST', '/api/mail/send', { contact_id: contactId, body });
  await sleep(800);
  actDone(r, 'Sent ✓');

  const rd = actStream('Digest', 'Extracting commitments from the thread...');
  await sleep(900);
  actDone(rd, 'Captured next steps into the graph');
  await loadGraph();
  await renderCards();

  await sleep(800);
  proactiveSweep();
}

async function proactiveSweep() {
  const r1 = actStream('Social Monitor', 'Scanning tracked contacts\' social feeds...');
  await sleep(1200);
  await api('POST', '/api/signals/scan');
  actDone(r1, 'Detected: Nordic Drives AB may be going to tender');
  await renderCards();

  await sleep(600);
  const r2 = actStream('Relationship', 'Scanning your book for cooling relationships...');
  await api('POST', '/api/catchup/scan');
  await sleep(1000);
  actDone(r2, 'Found: Markus Brandt — 92 days since last contact');
  await loadGraph();
  await renderCards();

  toast('Two items may need you — see the cards below.');

  await sleep(2500);
  jobChangeFlow();
}

async function jobChangeFlow() {
  const r1 = actStream('Social Monitor', 'Detected job change: Henrik Sørensen...');
  await sleep(1200);
  try {
    await api('POST', '/api/signals/job-change', {
      contact_id: 'n_noise_p3',
      new_company_name: 'Siemens Energy AG',
    });
  } catch (err) { actDone(r1, 'Job change detection failed'); return; }
  actDone(r1, 'Henrik moved: Aalborg Maskin → Siemens Energy AG');

  updatedNodes.add('n_noise_p3');
  await loadGraph();
  focusNode('n_noise_p3');
  toast('Henrik Sørensen changed jobs — tap the red-bordered node to review.');
}

// ── Voice ──

function setupVoice() {
  const mic = $('mic-btn');
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR) {
    const rec = new SR();
    rec.lang = 'en-US'; rec.interimResults = false;
    mic.addEventListener('click', () => {
      try { rec.start(); mic.classList.add('listening'); } catch (_) {}
    });
    rec.onresult = ev => {
      mic.classList.remove('listening');
      handleVoice(ev.results[0][0].transcript);
    };
    rec.onerror = () => { mic.classList.remove('listening'); toast('Mic unavailable — type the command instead.'); };
    rec.onend = () => mic.classList.remove('listening');
  } else {
    mic.addEventListener('click', () => toast('Voice needs Chrome/Edge — type the command instead.'));
  }
  $('send-btn').addEventListener('click', () => {
    const v = $('input-text').value.trim();
    if (v) handleVoice(v);
  });
  $('input-text').addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.value.trim()) handleVoice(e.target.value);
  });
}

async function handleVoice(transcript) {
  $('input-text').value = '';
  try {
    const res = await api('POST', '/api/voice', { transcript });
    toast(res.result && res.result.message ? res.result.message : 'Done.');
    if (res.result && res.result.graph_changed) await loadGraph();
    await renderCards();
  } catch (err) { toast('Voice failed: ' + err.message); }
}

// ── Camera and Modal ──
let useCamera = false;
let cameraStream = null;
let uploadedFile = null;

async function toggleCamera() {
  useCamera = !useCamera;
  uploadedFile = null; // clear uploaded file if any
  const video = $('camera-video');
  const imgContainer = $('image-preview-container');
  const camContainer = $('camera-container');
  const hint = $('upload-hint');
  const btn = $('toggle-camera-btn');
  
  if (useCamera) {
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      video.srcObject = cameraStream;
      imgContainer.hidden = true;
      camContainer.hidden = false;
      hint.textContent = 'Position card in view and click Start Scan.';
      btn.textContent = 'Use Sample';
      $('preview-img').src = '/static/sample_real.png';
    } catch (err) {
      useCamera = false;
      toast('Camera access denied or unavailable: ' + err.message);
    }
  } else {
    if (cameraStream) {
      cameraStream.getTracks().forEach(t => t.stop());
      cameraStream = null;
    }
    imgContainer.hidden = false;
    camContainer.hidden = true;
    hint.textContent = 'Using sample image. Click \'Use Camera\' or \'Upload Image\' to scan a real card.';
    btn.textContent = 'Use Camera';
    $('preview-img').src = '/static/sample_real.png';
  }
}

// ── Init ──
function openUploadModal() {
  $('upload-modal').hidden = false;
}
$('modal-close').addEventListener('click', () => { 
  $('upload-modal').hidden = true; 
  if (useCamera) toggleCamera();
  uploadedFile = null;
});
$('toggle-camera-btn').addEventListener('click', toggleCamera);

$('upload-btn').addEventListener('click', () => $('file-input').click());
$('file-input').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) {
    uploadedFile = file;
    if (useCamera) toggleCamera(); // switch out of camera mode
    $('camera-container').hidden = true;
    $('image-preview-container').hidden = false;
    const url = URL.createObjectURL(file);
    $('preview-img').src = url;
    $('upload-hint').textContent = 'Using uploaded image: ' + file.name;
    $('toggle-camera-btn').textContent = 'Use Camera';
  }
});

$('start-scan-btn').addEventListener('click', () => {
  $('upload-modal').hidden = true;
  scanFlow();
  if (useCamera) toggleCamera();
});
$('scan-btn').addEventListener('click', openUploadModal);
setupVoice();
loadGraph();
