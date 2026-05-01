/* ═══════════════════════════════════════════════
   医科达 MUD — 前端逻辑 (v0.3)
   ═══════════════════════════════════════════════ */

// 剧本列表
const SCRIPTS = [
  {
    id: "start",
    name: "第一剧本：维保合同攻防战",
    desc: "某医院放疗中心维保合同即将到期，卓亚虎视眈眈。医科达售后服务销售深入客户三线，争夺合同。",
    plugin: "elekta_service",
  },
  {
    id: "contract_start",
    name: "第二剧本：新危机",
    desc: "东州市人民医院放疗中心维保合同争夺战——医科达 vs 卓亚。",
    plugin: "tender_battle",
  },
];

// ── 初始化 ──────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadGame();

  document.getElementById('btn-new').addEventListener('click', showScriptModal);
  document.getElementById('btn-save').addEventListener('click', saveGame);
  document.getElementById('btn-load').addEventListener('click', showLoadModal);
  document.getElementById('btn-status').addEventListener('click', toggleStatus);
});

// ── 剧本选择 ────────────────────────────────────

function showScriptModal() {
  const modal = document.getElementById('script-modal');
  const list = document.getElementById('script-list');

  list.innerHTML = SCRIPTS.map(s => `
    <div class="save-entry" data-root="${s.id}" onclick="startScript('${s.id}')">
      <span class="save-name">${s.name}</span>
      <span class="save-meta">${s.desc}</span>
    </div>
  `).join('');

  modal.classList.remove('hidden');
}

async function startScript(rootNodeId) {
  closeModal('script-modal');
  const resp = await fetch('/api/new', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root_node_id: rootNodeId }),
  });
  const data = await resp.json();
  renderGame(data);
}

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
  renderRollResult(data.roll_result);
  renderVisitedNodes(data.visited_nodes || []);

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

  // 建立 text → 可用索引的映射
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
      <div class="attr-bar"><div class="attr-bar-fill" style="width:${Math.min(100, a.pct)}%"></div></div>
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

  // 技能系统
  renderSkills(data.skill_data);

  // 路径历史
  // (由 renderVisitedNodes 单独处理)
}

function renderSkills(skillData) {
  const el = document.getElementById('status-skills');
  if (!skillData || !skillData.skills || skillData.skills.length === 0) {
    el.innerHTML = '<span style="color:var(--text-dim)">暂无技能</span>';
    return;
  }
  const points = skillData.skill_points;
  el.innerHTML = `
    <div style="margin-bottom:6px;font-size:12px;color:var(--yellow)">
      技能点: <strong>${points}</strong>
    </div>
    ${skillData.skills.map(s => `
      <div class="skill-row">
        <span class="skill-name">${s.name}</span>
        <span class="skill-level">Lv${s.level}</span>
      </div>
    `).join('')}
  `;
}

function renderVisitedNodes(visited) {
  const el = document.getElementById('status-history');
  if (!visited || visited.length === 0) {
    el.innerHTML = '<span style="color:var(--text-dim)">无</span>';
    return;
  }
  // 只显示最近20个
  const recent = visited.slice(-20);
  el.innerHTML = recent.map(n =>
    `<span class="flag-tag" style="cursor:default">${n}</span>`
  ).join('');
}

function renderRollResult(rr) {
  const el = document.getElementById('roll-result');
  if (!rr) {
    el.innerHTML = '';
    el.classList.add('hidden');
    return;
  }

  const color = rr.success ? 'var(--green)' : 'var(--red)';
  const label = rr.success ? '✅ 成功' : '❌ 失败';
  const critLabel = rr.crit ? ' <span style="color:var(--yellow)">★ CRIT!</span>' : '';
  const fumbleLabel = rr.fumble ? ' <span style="color:var(--red)">☆ FUMBLE!</span>' : '';
  const skillLabel = rr.skill_name ? `<span style="color:var(--purple)">[${rr.skill_name}]</span>` : '';

  el.innerHTML = `
    <div style="color:${color};font-weight:bold;margin-bottom:4px">${label}${critLabel}${fumbleLabel}</div>
    ${skillLabel}
    <div style="font-size:13px;color:var(--text-dim)">
      投掷: <span style="color:var(--cyan)">${rr.roll}</span>
      + <span style="color:var(--cyan)">${rr.bonus}</span>
      = <strong>${rr.final}</strong>
      ${rr.margin >= 0 ? '+' : ''}${rr.margin}
    </div>
    ${rr.narrative ? `<div style="margin-top:4px;font-size:12px;color:var(--text)">${rr.narrative}</div>` : ''}
  `;
  el.classList.remove('hidden');
}

function flashLog(logs) {
  const area = document.getElementById('log-area');
  area.innerHTML = logs.map(l => `<div class="log-entry">▸ ${l}</div>`).join('');
  area.classList.remove('hidden');

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
