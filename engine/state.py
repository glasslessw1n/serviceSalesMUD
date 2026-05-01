"""GameState — 玩家状态容器，贯穿整棵游戏树。

所有状态修改通过 Effects 系统进行，保证可追踪、可回滚。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional


class Attr(StrEnum):
    """核心属性（医科达售后销售三围）"""
    TECH = "技术能力"          # 懂 linac 型号差异、故障诊断、升级路径
    RELATION = "关系值"        # 与科室主任/物理师/设备科/院领导的关系
    BUSINESS = "商务敏感度"    # 预算周期、招标规则、竞品动态
    REPUTATION = "声望"        # 行业口碑
    FUNDS = "资金"


@dataclass
class NPCState:
    """单个 NPC 的状态"""
    name: str
    role: str               # 科室主任 / 物理师 / 设备科长 / 院领导
    relationship: int = 0   # 0~100 关系值
    trust: int = 0          # 0~100 信任度（影响信息透露深度）
    flags: set[str] = field(default_factory=set)  # 剧情标记


@dataclass
class Item:
    """物品"""
    id: str
    name: str
    description: str
    quantity: int = 1
    flags: dict[str, Any] = field(default_factory=dict)


@dataclass
class GameState:
    """玩家全局状态"""

    # 核心属性
    attrs: dict[str, int] = field(default_factory=lambda: {
        Attr.TECH: 20,
        Attr.RELATION: 20,
        Attr.BUSINESS: 20,
        Attr.REPUTATION: 0,
        Attr.FUNDS: 0,
        # 竞品好感度（50=中立，<50=玩家占优，>50=竞品占优）
        "competitor_zhuoya": 50,
        "competitor_hongyang": 50,
        "competitor_zhongtaihe": 50,
    })

    # 技能系统（动态属性，不在 dataclass 构造参数里，
    # 通过 getattr/setattr 访问，避免 pickle 问题）
    _skill_system: Optional[Any] = field(default=None, repr=False)

    # NPC 关系
    npcs: dict[str, NPCState] = field(default_factory=dict)

    # 物品栏
    items: list[Item] = field(default_factory=list)

    # 全局标记（剧情分支用）
    flags: set[str] = field(default_factory=set)

    # 已访问过的节点 ID（防止重复、解锁回溯）
    visited_nodes: set[str] = field(default_factory=set)

    # 对话历史（最近 N 条）
    history: list[dict[str, str]] = field(default_factory=list)

    # 游戏时间
    hour: int = 9          # 0-23
    day: int = 1
    game_start: datetime = field(default_factory=datetime.now)

    # 元数据
    current_plugin: str = ""
    current_node: str = ""

    def get_attr(self, name: str) -> int:
        return self.attrs.get(name, 0)

    def set_attr(self, name: str, value: int):
        """带钳位写入"""
        self.attrs[name] = max(0, min(100, value))

    def mod_attr(self, name: str, delta: int):
        self.set_attr(name, self.get_attr(name) + delta)

    def get_npc(self, name: str) -> NPCState | None:
        return self.npcs.get(name)

    def ensure_npc(self, name: str, role: str = "") -> NPCState:
        if name not in self.npcs:
            self.npcs[name] = NPCState(name=name, role=role)
        return self.npcs[name]

    def has_flag(self, flag: str) -> bool:
        return flag in self.flags

    def set_flag(self, flag: str):
        self.flags.add(flag)

    def has_item(self, item_id: str) -> bool:
        return any(i.id == item_id and i.quantity > 0 for i in self.items)

    def add_item(self, item: Item):
        existing = next((i for i in self.items if i.id == item.id), None)
        if existing:
            existing.quantity += item.quantity
        else:
            self.items.append(item)

    def advance_time(self, hours: int):
        self.hour += hours
        while self.hour >= 24:
            self.hour -= 24
            self.day += 1
