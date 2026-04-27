/* ═══════════════════════════════════════════════
   医科达 MUD — 前端逻辑
   ═══════════════════════════════════════════════ */

// ── 初始化 ──────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadGame();

  document.getElementById('btn-new').addEventListener('click', newGame);
  document.getElementById('btn-save').addEventListener('click', saveGame);
  document.getElementById('btn-load').addEventListener('click', showLoadModal);
  document.getElementById('btn-status').addEventListener('click', toggleStatus);
});

// ── API 调用 ────────────────────────────────────

async function loadGame() {
  const resp = await fetch('/api/game');
  const data = await resp.json();
  renderGame(data);
}

async function makeChoice(index) {
  const resp = await fetch('/api/choose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ choice: index }),
  });
  const data = await resp.json();
  renderGame(data);
}

async function newGame() {
  const resp = await fetch('/api/new', { method: 'POST' });
  const data = await resp.json();
  renderGame(data);
}

async function saveGame() {
  const resp = await fetch('/api/save', { method: 'POST' });
  const data = await resp.json();
  flashLog([`💾 已保存: ${data.name}`]);
}

async function loadSave(name) {
  const resp = await fetch('/api/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!resp.ok) {
    flashLog(['❌ 读档失败']);
    return;
  }
  const data = await resp.json();
  closeModal('save-modal');
  renderGame(data);
}

let savesCache = null;
async function showLoadModal() {
  const modal = document.getElementById('save-modal');
  const list = document.getElementById('save-list');

  modal.classList.remove('hidden');
  list.innerHTML = '<p style="color:var(--text-dim)">加载中…</p>';

  const resp = await fetch('/api/saves');
  savesCache = await resp.json();

  if (savesCache.length === 0) {
    list.innerHTML = '<p style="color:var(--text-dim)">暂无存档</p>';
    return;
  }

  list.innerHTML = savesCache.map(s => `
    <div class="save-entry" data-name="${s.name}" onclick="loadSave('${s.name}')">
      <span class="save-name">📄 ${s.name}</span>
      <span class="save-meta">${s.time} · ${(s.size / 1024).toFixed(1)} KB</span>
    </div>
  `).join('');
}

// ── 渲染 ────────────────────────────────────────

function renderGame(data) {
  if (data.error) {
    document.getElementById('scene-text').textContent = '⚠ ' + data.error;
    return;
  }

  renderScene(data);
  renderChoices(data);
  renderStatus(data);

  // 效果日志
  if (data.result && data.result.logs && data.result.logs.length > 0) {
    flashLog(data.result.logs);
  }

  // 结束画面
  if (data.is_end) {
    document.getElementById('end-screen').classList.remove('hidden');
    document.getElementById('end-text').textContent = data.text;
    document.getElementById('choices-area').classList.add('hidden');
  } else {
    document.getElementById('end-screen').classList.add('hidden');
    document.getElementById('choices-area').classList.remove('hidden');
  }
}

function renderScene(data) {
  document.getElementById('scene-title').textContent = data.title ? '📌 ' + data.title : '';

  // 标签
  const tagsEl = document.getElementById('scene-tags');
  tagsEl.innerHTML = (data.tags || []).map(t =>
    `<span class="tag">[${t}]</span>`
  ).join('');

  // 说话人
  const speakerEl = document.getElementById('scene-speaker');
  speakerEl.textContent = data.speaker ? '🗣 ' + data.speaker : '';

  // 正文
  document.getElementById('scene-text').textContent = data.text;
}

function renderChoices(data) {
  const list = document.getElementById('choices-list');
  const all = data.all_choices || [];

  if (all.length === 0) {
    list.innerHTML = '<p style="color:var(--text-dim)">（无可用选项）</p>';
    return;
  }

  // 找到可用的索引映射
  const availableMap = {};
  (data.choices || []).forEach((c, i) => {
    availableMap[c.text] = i;
  });

  list.innerHTML = all.map((c, i) => {
    const isAvail = c.available;
    const availIdx = availableMap[c.text];

    let tags = '';
    if (c.tags && c.tags.length > 0) {
      const recTag = c.tags.includes('推荐') ? '<span class="choice-recommend">⭐推荐</span>' : '';
      const otherTags = c.tags.filter(t => t !== '推荐').map(t => `[${t}]`).join(' ');
      tags = `<span class="choice-tags">${recTag} ${otherTags}</span>`;
    }

    if (isAvail) {
      return `
        <button class="choice-btn" onclick="makeChoice(${availIdx})">
          <span style="color:var(--green)">[${availIdx + 1}]</span> ${c.text}${tags}
        </button>
      `;
    } else {
      return `
        <button class="choice-btn disabled" disabled>
          <span style="color:var(--text-dim)">[✗]</span> ${c.text} (条件不足)
        </button>
      `;
    }
  }).join('');
}

function renderStatus(data) {
  // 时间
  document.getElementById('status-time').innerHTML =
    `Day ${data.day}, ${String(data.hour).padStart(2, '0')}:00`;

  // 属性
  document.getElementById('status-attrs').innerHTML = (data.attrs || []).map(a => `
    <div class="attr-row">
      <span class="attr-name">${a.name}</span>
      <div class="attr-bar"><div class="attr-bar-fill" style="width:${a.pct}%"></div></div>
      <span class="attr-value">${a.value}</span>
    </div>
  `).join('');

  // NPC
  document.getElementById('status-npcs').innerHTML = (data.npcs || []).map(n => `
    <div class="npc-row">
      <div><span class="npc-name">${n.name}</span> <span class="npc-role">${n.role}</span></div>
      <div class="npc-bars">
        <div>
          <span class="npc-bar-label">关系</span>
          <span class="npc-bar-val">${n.relationship}</span>
        </div>
        <div>
          <span class="npc-bar-label">信任</span>
          <span class="npc-bar-val">${n.trust}</span>
        </div>
      </div>
    </div>
  `).join('') || '<span style="color:var(--text-dim)">暂无</span>';

  // 物品
  document.getElementById('status-items').innerHTML = (data.items || []).map(i =>
    `<div>📦 ${i.name} ×${i.quantity}</div>`
  ).join('') || '<span style="color:var(--text-dim)">空</span>';

  // 标记
  document.getElementById('status-flags').innerHTML = (data.flags || []).map(f =>
    `<span class="flag-tag">${f}</span>`
  ).join('') || '<span style="color:var(--text-dim)">无</span>';
}

function flashLog(logs) {
  const area = document.getElementById('log-area');
  area.innerHTML = logs.map(l => `<div class="log-entry">▸ ${l}</div>`).join('');
  area.classList.remove('hidden');

  // 3 秒后自动消失
  clearTimeout(area._timeout);
  area._timeout = setTimeout(() => {
    area.classList.add('hidden');
  }, 4000);
}

// ── UI 辅助 ──────────────────────────────────────

function toggleStatus() {
  const panel = document.getElementById('status-panel');
  panel.classList.toggle('hidden');
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

// 点击弹窗背景关闭
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal')) {
    e.target.classList.add('hidden');
  }
});
