"""条件求值器 —— 决定分支是否可见 / 可选。

所有条件函数签名统一：(state, params) -> bool
params 从 YAML 的 conditions 块传入。
"""

from __future__ import annotations

from typing import Any

from .state import GameState


def check_attr(state: GameState, attr: str, op: str, value: int) -> bool:
    """属性比较：op in ('>=', '<=', '>', '<', '==', '!=')"""
    current = state.get_attr(attr)
    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">":  lambda a, b: a > b,
        "<":  lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    return ops[op](current, value)


def check_npc_relation(state: GameState, npc: str, op: str, value: int) -> bool:
    """NPC 关系值比较"""
    npc_state = state.get_npc(npc)
    if npc_state is None:
        return False
    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">":  lambda a, b: a > b,
        "<":  lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    return ops[op](npc_state.relationship, value)


def check_npc_trust(state: GameState, npc: str, op: str, value: int) -> bool:
    """NPC 信任度比较"""
    npc_state = state.get_npc(npc)
    if npc_state is None:
        return False
    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">":  lambda a, b: a > b,
        "<":  lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    return ops[op](npc_state.trust, value)


def check_flag(state: GameState, flag: str) -> bool:
    """检查全局标记"""
    return state.has_flag(flag)


def check_not_flag(state: GameState, flag: str) -> bool:
    """检查标记不存在"""
    return not state.has_flag(flag)


def check_has_item(state: GameState, item_id: str, quantity: int = 1) -> bool:
    """检查物品"""
    for item in state.items:
        if item.id == item_id and item.quantity >= quantity:
            return True
    return False


def check_visited(state: GameState, node_id: str) -> bool:
    """是否访问过某个节点"""
    return node_id in state.visited_nodes


def check_time(state: GameState, op: str, hour: int) -> bool:
    """游戏内时间比较"""
    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">":  lambda a, b: a > b,
        "<":  lambda a, b: a < b,
        "==": lambda a, b: a == b,
    }
    return ops[op](state.hour, hour)


# 条件分发映射


def check_competitor_favor(state: GameState, competitor: str, op: str, value: int) -> bool:
    """竞品好感度比较（attr 中存储：zhuoya / hongyang / zhongtaihe）"""
    attr_key = f"competitor_{competitor}"
    current = state.get_attr(attr_key)
    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">":  lambda a, b: a > b,
        "<":  lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    return ops[op](current, value)

CONDITION_DISPATCH = {
    "attr":          check_attr,
    "npc_relation":  check_npc_relation,
    "npc_trust":     check_npc_trust,
    "flag":          check_flag,
    "not_flag":      check_not_flag,
    "has_item":      check_has_item,
    "visited":       check_visited,
    "time":          check_time,
    "competitor_favor": check_competitor_favor,
}


def evaluate_conditions(state: GameState, conditions: list[dict]) -> bool:
    """求值一组条件。全 AND 逻辑（所有条件都满足才算通过）。

    conditions 格式：
      - check: attr
        attr: 技术能力
        op: ">="
        value: 30
      - check: flag
        flag: met_director
    """
    if not conditions:
        return True

    for cond in conditions:
        check_type = cond["check"]
        handler = CONDITION_DISPATCH.get(check_type)
        if handler is None:
            raise ValueError(f"未知条件类型: {check_type}")

        # 构建参数，去掉 check 字段
        kwargs = {k: v for k, v in cond.items() if k != "check"}

        if not handler(state, **kwargs):
            return False

    return True
