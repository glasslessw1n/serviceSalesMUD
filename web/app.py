"""医科达 MUD — Web 层

Flask 应用，在现有 engine 上提供浏览器可玩的界面。
游戏状态按 session 存储在服务端内存中（server_sessions dict）。
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# 把项目根目录加入 path，让 engine 可导入
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import TreeEngine, load_plugins, apply_effects

# ── 配置 ──────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
PLUGINS_DIR = BASE_DIR / "plugins"
SAVES_DIR = BASE_DIR / "web_saves"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "linac-mud-dev-key-change-me")

# 服务端 session 存储：{session_id: serialized_engine_json}
server_sessions: dict[str, dict] = {}


# ── 辅助函数 ──────────────────────────────────────

def _get_engine() -> TreeEngine:
    """从当前 Flask session 获取/创建游戏引擎"""
    sid = session.get("game_id")
    if not sid or sid not in server_sessions:
        # 没有活跃游戏 → 创建新的
        engine = TreeEngine()
        load_plugins(engine, PLUGINS_DIR, root_node_id="start")
        sid = uuid.uuid4().hex
        session["game_id"] = sid
        server_sessions[sid] = _serialize(engine)
        return engine

    return _deserialize(server_sessions[sid])


def _save_engine(engine: TreeEngine):
    """保存引擎到 session 存储"""
    sid = session.get("game_id")
    if sid:
        server_sessions[sid] = _serialize(engine)


def _serialize(engine: TreeEngine) -> dict:
    """序列化引擎（去掉不可 JSON 化的字段）"""
    data = engine.to_dict()
    # 处理 sets
    data["state"]["flags"] = list(data["state"]["flags"])
    data["state"]["visited_nodes"] = list(data["state"]["visited_nodes"])
    for v in data["state"]["npcs"].values():
        v["flags"] = list(v.get("flags", []))
    # 处理 datetime
    gs = data["state"]["game_start"]
    if hasattr(gs, "isoformat"):
        data["state"]["game_start"] = gs.isoformat()
    return data


def _deserialize(data: dict) -> TreeEngine:
    """反序列化"""
    # 恢复 sets
    data["state"]["flags"] = set(data["state"].get("flags", []))
    data["state"]["visited_nodes"] = set(data["state"].get("visited_nodes", []))
    for v in data["state"].get("npcs", {}).values():
        v["flags"] = set(v.get("flags", []))
    return TreeEngine.from_dict(data)


def _engine_to_game_data(engine: TreeEngine) -> dict:
    """将引擎状态转为前端可用的 game_data"""
    from engine.state import Attr

    node = engine.get_current_node()
    if node is None:
        return {"error": "当前节点不存在"}

    # 可用选项
    available = engine.get_available_choices()
    choices_data = []
    for c in available:
        choices_data.append({
            "text": c.text,
            "tags": c.tags,
            "conditions": bool(c.conditions),
        })

    # 所有选项（含禁用）
    all_choices_data = []
    for c in node.choices:
        all_choices_data.append({
            "text": c.text,
            "available": c in available,
            "tags": c.tags,
        })

    # 属性
    attr_order = [Attr.TECH, Attr.RELATION, Attr.BUSINESS, Attr.REPUTATION, Attr.FUNDS]
    attrs_data = []
    for a in attr_order:
        v = engine.state.get_attr(a)
        attrs_data.append({"name": a, "value": v, "pct": v})

    # NPC
    npcs_data = []
    for name, ns in engine.state.npcs.items():
        npcs_data.append({
            "name": name,
            "role": ns.role,
            "relationship": ns.relationship,
            "trust": ns.trust,
        })

    # 物品
    items_data = []
    for item in engine.state.items:
        if item.quantity > 0:
            items_data.append({
                "name": item.name,
                "quantity": item.quantity,
            })

    # 标记
    flags_data = sorted(engine.state.flags)

    return {
        "node_id": node.id,
        "title": node.title,
        "speaker": node.speaker,
        "text": node.text.strip(),
        "tags": node.tags,
        "choices": choices_data,
        "all_choices": all_choices_data,
        "attrs": attrs_data,
        "npcs": npcs_data,
        "items": items_data,
        "flags": flags_data,
        "day": engine.state.day,
        "hour": engine.state.hour,
        "is_end": node.id == "__END__",
        "game_id": session.get("game_id", ""),
    }


# ── 路由 ──────────────────────────────────────────

@app.route("/")
def index():
    """主游戏页面"""
    return render_template("game.html")


@app.route("/api/game")
def api_game():
    """获取当前游戏状态"""
    engine = _get_engine()
    return jsonify(_engine_to_game_data(engine))


@app.route("/api/choose", methods=["POST"])
def api_choose():
    """玩家做出选择"""
    data = request.get_json()
    choice_index = data.get("choice", -1)

    engine = _get_engine()
    success, msg, logs = engine.choose(choice_index)
    _save_engine(engine)

    game_data = _engine_to_game_data(engine)
    game_data["result"] = {"success": success, "message": msg, "logs": logs}
    return jsonify(game_data)


@app.route("/api/new", methods=["POST"])
def api_new():
    """开始新游戏"""
    sid = session.get("game_id")
    if sid and sid in server_sessions:
        del server_sessions[sid]

    engine = TreeEngine()
    load_plugins(engine, PLUGINS_DIR, root_node_id="start")
    sid = uuid.uuid4().hex
    session["game_id"] = sid
    server_sessions[sid] = _serialize(engine)

    return jsonify(_engine_to_game_data(engine))


@app.route("/api/save", methods=["POST"])
def api_save():
    """保存游戏到文件"""
    engine = _get_engine()
    SAVES_DIR.mkdir(exist_ok=True)

    name = datetime.now().strftime("save_%Y%m%d_%H%M%S")
    path = SAVES_DIR / f"{name}.json"

    data = _serialize(engine)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return jsonify({"success": True, "name": name})


@app.route("/api/saves")
def api_saves():
    """列出存档"""
    if not SAVES_DIR.exists():
        return jsonify([])

    saves = []
    for sp in sorted(SAVES_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        mtime = datetime.fromtimestamp(sp.stat().st_mtime)
        saves.append({
            "name": sp.stem,
            "time": mtime.strftime("%Y-%m-%d %H:%M"),
            "size": sp.stat().st_size,
        })
    return jsonify(saves)


@app.route("/api/load", methods=["POST"])
def api_load():
    """读档"""
    data = request.get_json()
    name = data.get("name", "")

    path = SAVES_DIR / f"{name}.json"
    if not path.exists():
        return jsonify({"error": "存档不存在"}), 404

    with open(path, encoding="utf-8") as f:
        save_data = json.load(f)

    engine = _deserialize(save_data)

    # 绑定到当前 session
    sid = session.get("game_id")
    if sid and sid in server_sessions:
        del server_sessions[sid]

    sid = uuid.uuid4().hex
    session["game_id"] = sid
    server_sessions[sid] = _serialize(engine)

    return jsonify(_engine_to_game_data(engine))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
