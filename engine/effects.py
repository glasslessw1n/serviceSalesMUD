"""效果执行器 —— 选择分支后修改 GameState。

统一签名：(state, params) -> str (简短日志)
"""

from __future__ import annotations

from typing import Any

from .state import GameState, Item, NPCState


def effect_mod_attr(state: GameState, attr: str, op: str, value: int) -> str:
    """修改属性：op in ('+', '-', '=', '*')"""
    current = state.get_attr(attr)
    ops = {
        "+": lambda a, b: a + b,
        "-": lambda a, b: a - b,
        "=": lambda a, b: b,
        "*": lambda a, b: int(a * b),
    }
    new_val = ops[op](current, value)
    state.set_attr(attr, new_val)
    direction = "↑" if new_val > current else "↓" if new_val < current else "→"
    return f"{attr} {current} → {new_val} {direction}{abs(new_val - current)}"


def effect_mod_npc_relation(state: GameState, npc: str, op: str, value: int) -> str:
    """修改 NPC 关系值"""
    ns = state.ensure_npc(npc)
    old = ns.relationship
    ops = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "=": lambda a, b: b}
    ns.relationship = max(0, min(100, ops[op](old, value)))
    direction = "↑" if ns.relationship > old else "↓" if ns.relationship < old else "→"
    return f"与 {npc} 关系 {old} → {ns.relationship} {direction}"


def effect_mod_npc_trust(state: GameState, npc: str, op: str, value: int) -> str:
    """修改 NPC 信任度"""
    ns = state.ensure_npc(npc)
    old = ns.trust
    ops = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "=": lambda a, b: b}
    ns.trust = max(0, min(100, ops[op](old, value)))
    direction = "↑" if ns.trust > old else "↓" if ns.trust < old else "→"
    return f"对 {npc} 信任度 {old} → {ns.trust} {direction}"


def effect_set_flag(state: GameState, flag: str) -> str:
    """设置标记"""
    existed = state.has_flag(flag)
    state.set_flag(flag)
    return f"【标记】{flag}" if not existed else f"【标记】{flag} (已存在)"


def effect_clear_flag(state: GameState, flag: str) -> str:
    """清除标记"""
    if flag in state.flags:
        state.flags.discard(flag)
        return f"【清除标记】{flag}"
    return ""


def effect_add_item(state: GameState, item_id: str, name: str,
                    description: str = "", quantity: int = 1) -> str:
    """添加物品"""
    item = Item(id=item_id, name=name, description=description, quantity=quantity)
    state.add_item(item)
    return f"【获得物品】{name} ×{quantity}"


def effect_remove_item(state: GameState, item_id: str, quantity: int = 1) -> str:
    """移除物品"""
    for item in state.items:
        if item.id == item_id:
            removed = min(item.quantity, quantity)
            item.quantity -= removed
            if item.quantity <= 0:
                state.items.remove(item)
            return f"【失去物品】{item.name} ×{removed}"
    return f"【错误】没有物品 {item_id}"


def effect_set_npc_flag(state: GameState, npc: str, flag: str) -> str:
    """给 NPC 打标记"""
    ns = state.ensure_npc(npc)
    ns.flags.add(flag)
    return f"【NPC 标记】{npc}.{flag}"


def effect_advance_time(state: GameState, hours: int) -> str:
    """推进游戏时间"""
    old_hour = state.hour
    old_day = state.day
    state.advance_time(hours)
    return f"时间推进 {hours}h → Day {state.day}, {state.hour:02d}:00"


def effect_log(state: GameState, message: str) -> str:
    """纯文本日志"""
    return message


# 效果分发映射
EFFECT_DISPATCH = {
    "mod_attr":           effect_mod_attr,
    "mod_npc_relation":   effect_mod_npc_relation,
    "mod_npc_trust":      effect_mod_npc_trust,
    "set_flag":           effect_set_flag,
    "clear_flag":         effect_clear_flag,
    "add_item":           effect_add_item,
    "remove_item":        effect_remove_item,
    "set_npc_flag":       effect_set_npc_flag,
    "advance_time":       effect_advance_time,
    "log":                effect_log,
}


def apply_effects(state: GameState, effects: list[dict]) -> list[str]:
    """执行一组效果，返回日志列表"""
    logs = []
    for eff in effects:
        eff_type = eff["effect"]
        handler = EFFECT_DISPATCH.get(eff_type)
        if handler is None:
            logs.append(f"[警告] 未知效果类型: {eff_type}")
            continue
        kwargs = {k: v for k, v in eff.items() if k != "effect"}
        try:
            result = handler(state, **kwargs)
            if result:
                logs.append(result)
        except Exception as e:
            logs.append(f"[错误] {eff_type}: {e}")
    return logs
