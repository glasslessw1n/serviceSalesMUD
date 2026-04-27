"""TreeNode + TreeEngine —— 树状剧情引擎核心。

设计原则：
- 节点 = 场景（一段叙述 + 一组选项）
- 选项 = 分支（下一节点 ID + 前置条件 + 后果效果）
- 引擎只负责：展示当前节点 → 收玩家选择 → 检查条件 → 应用效果 → 跳转下一节点
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from .state import GameState
from .conditions import evaluate_conditions
from .effects import apply_effects

if TYPE_CHECKING:
    from .ui import UI


@dataclass
class Choice:
    """一个可选项"""
    text: str                          # 显示文本
    next_node: str                     # 下一节点 ID
    conditions: list[dict] = field(default_factory=list)   # 前置条件
    effects: list[dict] = field(default_factory=list)      # 选择后效果
    tags: list[str] = field(default_factory=list)          # 标签（UI 用）


@dataclass
class TreeNode:
    """剧情树节点"""
    id: str
    title: str = ""
    speaker: str = ""                  # 说话人（空=旁白）
    text: str = ""                     # 叙述文本（支持多行）
    choices: list[Choice] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # 元数据
    plugin: str = ""

    # 进/出节点回调（暂留扩展口）
    on_enter: list[dict] = field(default_factory=list)
    on_exit: list[dict] = field(default_factory=list)


@dataclass
class TreeEngine:
    """树状剧情引擎"""

    nodes: dict[str, TreeNode] = field(default_factory=dict)
    state: GameState = field(default_factory=GameState)
    current_node_id: str = ""

    def add_node(self, node: TreeNode):
        """注册节点（插件加载时调用）"""
        if node.id in self.nodes:
            raise ValueError(f"节点 ID 冲突: {node.id}")
        self.nodes[node.id] = node

    def add_nodes(self, nodes: list[TreeNode]):
        for node in nodes:
            self.add_node(node)

    def get_current_node(self) -> TreeNode | None:
        return self.nodes.get(self.current_node_id)

    def navigate_to(self, node_id: str):
        """强行跳转到指定节点"""
        if node_id not in self.nodes:
            raise ValueError(f"节点不存在: {node_id}")
        self.current_node_id = node_id
        self.state.current_node = node_id

        # 记录访问
        self.state.visited_nodes.add(node_id)

        # 执行 on_enter 效果
        node = self.nodes[node_id]
        if node.on_enter:
            apply_effects(self.state, node.on_enter)

    def get_available_choices(self) -> list[Choice]:
        """获取当前节点所有可用的选项（过滤条件不满足的）"""
        node = self.get_current_node()
        if node is None:
            return []

        available = []
        for choice in node.choices:
            if evaluate_conditions(self.state, choice.conditions):
                available.append(choice)
        return available

    def choose(self, choice_index: int) -> tuple[bool, str, list[str]]:
        """
        玩家做出选择。
        返回: (成功?, 消息, 效果日志列表)
        """
        available = self.get_available_choices()

        if choice_index < 0 or choice_index >= len(available):
            return False, f"无效选择 (0-{len(available)-1})", []

        choice = available[choice_index]

        # 记录历史
        node = self.get_current_node()
        self.state.history.append({
            "node": node.id if node else "?",
            "choice": choice.text,
            "next": choice.next_node,
        })

        # 应用效果
        logs = apply_effects(self.state, choice.effects)

        # 跳转
        try:
            self.navigate_to(choice.next_node)
            return True, f"→ {choice.next_node}", logs
        except ValueError as e:
            return False, str(e), logs

    def to_dict(self) -> dict:
        """序列化（存档用）"""
        from dataclasses import asdict
        return {
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "state": asdict(self.state),
            "current_node_id": self.current_node_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TreeEngine:
        """反序列化"""
        engine = cls()
        for node_data in data["nodes"].values():
            choices = [Choice(**c) for c in node_data.pop("choices", [])]
            engine.add_node(TreeNode(**node_data, choices=choices))

        state_data = data["state"]
        # 处理 npcs dict
        from .state import NPCState
        npcs = {}
        for name, nsd in state_data.get("npcs", {}).items():
            npcs[name] = NPCState(
                name=nsd["name"],
                role=nsd.get("role", ""),
                relationship=nsd.get("relationship", 0),
                trust=nsd.get("trust", 0),
                flags=set(nsd.get("flags", [])),
            )

        from .state import Item
        items = [Item(**it) for it in state_data.get("items", [])]

        from datetime import datetime
        engine.state = GameState(
            attrs=state_data.get("attrs", {}),
            npcs=npcs,
            items=items,
            flags=set(state_data.get("flags", [])),
            visited_nodes=set(state_data.get("visited_nodes", [])),
            history=state_data.get("history", []),
            hour=state_data.get("hour", 9),
            day=state_data.get("day", 1),
            game_start=datetime.fromisoformat(state_data.get("game_start", datetime.now().isoformat())),
            current_plugin=state_data.get("current_plugin", ""),
            current_node=state_data.get("current_node", ""),
        )
        engine.current_node_id = data.get("current_node_id", "")
        return engine
