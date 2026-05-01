"""随机事件引擎 —— 时间推进时触发外部事件。

事件表（EventTable）定义了所有可能的随机事件：
  - 触发条件（时间窗口、必须/禁止持有某标记）
  - 事件内容（描述文本 + 效果 + 后续节点）
  - 权重（影响随机抽中的概率）

用法：
  events = RandomEventEngine(table=MY_EVENTS)
  event = events.roll()       # 按权重随机抽一个
  events.apply(event, state)  # 应用到游戏状态

 YAML 示例（在 scenes.yaml 中定义）：
   events:
     - id: varian_visit
       trigger: time_advance   # 在 advance_time 时触发
       min_hours: 24           # 至少过了24小时才可能触发
       weight: 3
       text: "竞品瓦里安的销售今天拜访了该医院设备科。"
       effects:
         - effect: set_flag
           flag: varian_visited_hospital
       next_node: random_event_varian

     - id: equipment_bonus
       trigger: time_advance
       min_hours: 48
       weight: 1
       condition:
         - check: flag
           flag: contract_signed
       text: "维保合同签订后，院里下发了设备采购奖励。"
       effects:
         - effect: add_skill_point
           amount: 1
           reason: "设备采购奖励"
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from engine.state import GameState


@dataclass
class RandomEvent:
    """单个随机事件"""
    id: str
    text: str                          # 事件描述
    effects: list[dict] = field(default_factory=list)   # 触发后的效果
    next_node: str = ""                # 触发后跳转到这个节点（空=留在当前）
    weight: int = 1                    # 权重，越大约容易抽中
    tags: list[str] = field(default_factory=list)

    # 触发条件
    min_hours_passed: int = 0         # 必须过了多少游戏小时才可能触发
    required_flags: list[str] = field(default_factory=list)   # 必须有这些标记
    forbidden_flags: list[str] = field(default_factory=list)  # 不能有这些标记


class RandomEventEngine:
    """随机事件引擎"""

    def __init__(self, table: list[RandomEvent] | None = None):
        self.table: list[RandomEvent] = table or []
        self.cooldown_ids: set[str] = field(default_factory=set)  # 已触发过的，避免重复
        self._last_roll_hours: int = 0  # 上次roll时的游戏小时数

    def add_event(self, event: RandomEvent):
        self.table.append(event)

    def roll(self, state: GameState) -> Optional[RandomEvent]:
        """
        按权重随机抽一个满足条件的事件。
        返回 None 表示本次时间推进没有触发任何事件（这是正常情况）。
        """
        hours_elapsed = state.hour + (state.day - 1) * 24 - self._last_roll_hours

        candidates = []
        for ev in self.table:
            if ev.id in self.cooldown_ids:
                continue
            if hours_elapsed < ev.min_hours_passed:
                continue
            if not all(f in state.flags for f in ev.required_flags):
                continue
            if any(f in state.flags for f in ev.forbidden_flags):
                continue
            candidates.append(ev)

        if not candidates:
            return None

        total_weight = sum(e.weight for e in candidates)
        r = random.randint(1, total_weight)
        cumulative = 0
        for ev in candidates:
            cumulative += ev.weight
            if r <= cumulative:
                self.cooldown_ids.add(ev.id)
                self._last_roll_hours = state.hour + (state.day - 1) * 24
                return ev

        return None

    def reset_cooldowns(self):
        self.cooldown_ids.clear()

    def apply(self, event: RandomEvent, state: GameState) -> tuple[list[str], Optional[str]]:
        """
        将事件效果应用到游戏状态。
        返回 (日志列表, 跳转目标节点ID)
        """
        from engine.effects import apply_effects

        logs = apply_effects(state, event.effects)
        logs.insert(0, f"📢 突发事件：{event.text}")
        return logs, event.next_node if event.next_node else None


# ── 内置事件表（示例）─────────────────────────────────────

BUILTIN_EVENTS: list[RandomEvent] = [

    RandomEvent(
        id="varian_visit",
        text="竞品瓦里安的销售今天拜访了该医院设备科，带了新的维保报价方案。",
        effects=[
            {"effect": "set_flag", "flag": "varian_visited_hospital"},
        ],
        next_node="",
        weight=3,
        min_hours_passed=24,
        required_flags=["hospital_prospect_active"],
        forbidden_flags=["contract_signed"],
    ),

    RandomEvent(
        id="hospital_news",
        text="该医院的放疗科在《中华放射医学杂志》上发表了一篇论文，研究用的正是 Versa HD。",
        effects=[
            {"effect": "mod_attr", "attr": "声望", "op": "+", "value": 3},
        ],
        next_node="",
        weight=2,
        min_hours_passed=72,
        tags=["正面"],
    ),

    RandomEvent(
        id="director_absent",
        text="孙主任临时出差，这周的会面计划泡汤了。",
        effects=[],
        next_node="",
        weight=4,
        min_hours_passed=12,
        required_flags=["appointment_scheduled"],
        tags=["负面", "时间浪费"],
    ),

    RandomEvent(
        id="eq_failure_forecast",
        text="雨季来临，设备科担心机房湿度。你接到电话：放疗科的空调需要维护。",
        effects=[
            {"effect": "set_flag", "flag": "humidity_concern_active"},
        ],
        next_node="",
        weight=3,
        min_hours_passed=48,
        required_flags=["hospital_prospect_active"],
        tags=["机会"],
    ),
]


def trigger_time_based_events(
    state: GameState,
    hours_elapsed: int,
    extra_events: list[RandomEvent] | None = None,
) -> tuple[list[str], Optional[str]]:
    """
    时间推进后调用此函数检查是否触发随机事件。
    合并内置事件 + 插件自定义事件。

    返回 (事件日志列表, 跳转目标节点)，无事件时日志=[]。
    """
    engine = RandomEventEngine(table=BUILTIN_EVENTS + (extra_events or []))
    engine._last_roll_hours = state.hour + (state.day - 1) * 24 - hours_elapsed
    event = engine.roll(state)
    if event is None:
        return [], None
    return engine.apply(event, state)
