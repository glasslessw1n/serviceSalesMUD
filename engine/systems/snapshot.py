"""快照与回滚系统 —— 每个节点选择前存档，支持悔棋。

用法：
  snapshots = SnapshotEngine()
  take_snapshot(engine, snapshots, label="进急诊室前")  # 在展示选项前调用
  ...
  success, msg = rollback_to(snapshots, label="进急诊室前")  # 玩家要悔棋时

快照以节点 ID + 选择序号为 key，支持按标签回滚到任意历史状态。
引擎的 state 被完整复制（包括 _skill_system 等动态属性）。
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from engine.tree import TreeEngine


@dataclass
class Snapshot:
    """单次快照"""
    label: str                # 快照描述（如"进急诊室前"）
    node_id: str              # 快照时的节点 ID
    choice_index: int         # 快照时玩家即将做选择的选项序号（-1=刚进入节点）
    engine_state_json: str     # TreeEngine.state 的 JSON 序列化（deepcopy）
    current_node_id: str       # 当前节点 ID
    turn_index: int           # 回合计数器（用于排序）
    timestamp: str            # ISO 时间戳

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "node_id": self.node_id,
            "choice_index": self.choice_index,
            "engine_state_json": self.engine_state_json,
            "current_node_id": self.current_node_id,
            "turn_index": self.turn_index,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Snapshot":
        return cls(
            label=d["label"],
            node_id=d["node_id"],
            choice_index=d["choice_index"],
            engine_state_json=d["engine_state_json"],
            current_node_id=d["current_node_id"],
            turn_index=d["turn_index"],
            timestamp=d["timestamp"],
        )


class SnapshotEngine:
    """
    管理快照历史。
    可以序列化到 JSON 存档文件，也可以在内存中管理。
    """

    MAX_HISTORY = 50   # 内存中最多保留这么多快照

    def __init__(self):
        self.snapshots: list[Snapshot] = []
        self.turn_counter: int = 0

    def take(self, label: str, engine: "TreeEngine", choice_index: int = -1) -> Snapshot:
        """
        给当前引擎状态拍快照。
        choice_index: 玩家即将选择的序号（-1=刚进入节点，还没选）
        """
        self.turn_counter += 1

        import copy
        from dataclasses import asdict
        state_copy = copy.deepcopy(engine.state)

        # 处理 _skill_system（动态属性，手动序列化）
        ss = getattr(state_copy, "_skill_system", None)
        ss_data = None
        if ss is not None:
            ss_data = {
                "skill_points": ss.skill_points,
                "skills": {k: asdict(v) for k, v in ss.skills.items()},
            }
            del state_copy._skill_system

        # 把所有 set 字段转成 list（JSON 不支持 set）
        state_dict = asdict(state_copy)
        # 手动处理 GameState 里已知是 set 的字段
        state_dict["flags"] = list(state_dict.get("flags", []))
        state_dict["visited_nodes"] = list(state_dict.get("visited_nodes", []))
        for npc_data in state_dict.get("npcs", {}).values():
            npc_data["flags"] = list(npc_data.get("flags", []))

        if ss_data is not None:
            state_dict["_skill_system"] = ss_data

        def json_default(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        state_json = json.dumps(state_dict, ensure_ascii=False, default=json_default)

        snap = Snapshot(
            label=label,
            node_id=engine.current_node_id,
            choice_index=choice_index,
            engine_state_json=state_json,
            current_node_id=engine.current_node_id,
            turn_index=self.turn_counter,
            timestamp=__import__("datetime").datetime.now().isoformat(),
        )
        self.snapshots.append(snap)

        # 限制历史长度
        if len(self.snapshots) > self.MAX_HISTORY:
            self.snapshots = self.snapshots[-self.MAX_HISTORY:]

        return snap

    def find_by_label(self, label: str) -> Optional[Snapshot]:
        """按标签找最近的同名快照"""
        for snap in reversed(self.snapshots):
            if snap.label == label:
                return snap
        return None

    def find_nearest_before_turn(self, turn_index: int) -> Optional[Snapshot]:
        """找到最近的一次选择前的快照（在指定回合之前）"""
        candidates = [s for s in self.snapshots if s.turn_index < turn_index]
        return max(candidates, key=lambda s: s.turn_index) if candidates else None

    def list_labels(self) -> list[tuple[str, str, int]]:
        """返回 [(label, node_id, turn_index)]，最近的最前"""
        result = [(s.label, s.node_id, s.turn_index) for s in reversed(self.snapshots)]
        return result

    def save_to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in self.snapshots], f, ensure_ascii=False, indent=2)

    def load_from_file(self, path: str):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.snapshots = [Snapshot.from_dict(d) for d in data]
        if self.snapshots:
            self.turn_counter = max(s.turn_index for s in self.snapshots)


def take_snapshot(
    engine: TreeEngine,
    snapshots: SnapshotEngine,
    label: str | None = None,
) -> Snapshot:
    """
    便捷封装：从当前引擎状态拍快照。
    label 如果为 None，自动生成"节点ID + 回合数"。
    """
    if label is None:
        label = f"{engine.current_node_id} (turn {snapshots.turn_counter + 1})"
    return snapshots.take(label=label, engine=engine, choice_index=-1)


def rollback_to(
    snapshots: SnapshotEngine,
    label: str | None = None,
    turn_index: int | None = None,
) -> tuple[bool, str]:
    """
    执行回滚。
    label 或 turn_index 二选一，都不传则回滚到上一次选择前。

    返回 (是否成功, 消息)
    """
    # 延迟导入避免循环引用
    from engine.tree import TreeEngine
    from engine.state import GameState
    from dataclasses import dataclass, asdict

    target: Optional[Snapshot] = None

    if label:
        target = snapshots.find_by_label(label)
    elif turn_index is not None:
        target = snapshots.find_nearest_before_turn(turn_index)
    else:
        # 找最近一次 choice_index == -1 的快照（即选择前的快照）
        candidates = [s for s in reversed(snapshots.snapshots) if s.choice_index == -1]
        target = candidates[0] if candidates else None

    if target is None:
        return False, "没有找到可回滚的快照"

    # 将快照中的 state_json 反序列化并替换引擎的 state
    from engine.tree import TreeEngine
    from engine.state import GameState
    from dataclasses import dataclass, asdict

    state_dict = json.loads(target.engine_state_json)

    # 重建 GameState（处理 set 转换等）
    from engine.state import NPCState, Item
    npcs = {}
    for name, nsd in state_dict.get("npcs", {}).items():
        npcs[name] = NPCState(
            name=nsd["name"],
            role=nsd.get("role", ""),
            relationship=nsd.get("relationship", 0),
            trust=nsd.get("trust", 0),
            flags=set(nsd.get("flags", [])),
        )
    items = [Item(**it) for it in state_dict.get("items", [])]

    from datetime import datetime
    state = GameState(
        attrs=state_dict.get("attrs", {}),
        npcs=npcs,
        items=items,
        flags=set(state_dict.get("flags", [])),
        visited_nodes=set(state_dict.get("visited_nodes", [])),
        history=state_dict.get("history", []),
        hour=state_dict.get("hour", 9),
        day=state_dict.get("day", 1),
        game_start=datetime.fromisoformat(state_dict.get("game_start", datetime.now().isoformat())),
        current_plugin=state_dict.get("current_plugin", ""),
        current_node=state_dict.get("current_node", ""),
    )
    # 重建 _skill_system（如果有）
    ss_data = state_dict.get("_skill_system")
    if ss_data:
        from engine.systems.skills import SkillSystem
        ss = SkillSystem()
        ss.skill_points = ss_data.get("skill_points", 0)
        for sid, sd in ss_data.get("skills", {}).items():
            from engine.systems.skills import SkillLevel
            sl = SkillLevel(skill_id=sid, level=sd.get("level", 0),
                            exp=sd.get("exp", 0.0), points_spent=sd.get("points_spent", 0))
            ss.skills[sid] = sl
        state._skill_system = ss

    return state, target.label, target.node_id
