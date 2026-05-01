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
    next_node: str                     # 下一节点 ID（无 roll 时使用）
    conditions: list[dict] = field(default_factory=list)   # 前置条件
    effects: list[dict] = field(default_factory=list)      # 选择后效果
    tags: list[str] = field(default_factory=list)          # 标签（UI 用）
    # 判定分支（可选 — 有值时优先于 next_node）
    roll_success_node: str = ""        # 判定成功跳转此节点
    roll_fail_node: str = ""           # 判定失败跳转此节点


@dataclass
class RollConfig:
    """节点级判定配置"""
    skill: str                          # 技能 ID
    difficulty: str = "normal"           # easy / normal / hard / very_hard / legendary
    label: str = ""                     # 显示用描述，如 "诊断 MLC 故障"
    # 判定后自动加经验（可选）
    exp_on_success: float = 0
    exp_on_fail: float = 0
    # 判定后自动加技能点（可选）
    skill_point_on_success: int = 0


@dataclass
class TreeNode:
    """剧情树节点"""
    id: str
    title: str = ""
    speaker: str = ""                  # 说话人（空=旁白）
    text: str = ""                     # 叙述文本（支持多行）
    choices: list[Choice] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # 节点级判定（可选 — 有值时进入节点自动触发）
    roll: RollConfig | None = None

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
    # 最近一次判定结果（供 UI 显示）
    last_roll_result: Any = field(default=None, repr=False)

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

        # ── 节点级判定 ─────────────────────────
        self.last_roll_result = None
        if node.roll:
            self._execute_node_roll(node)

    def _execute_node_roll(self, node: TreeNode) -> Any:
        """执行节点级判定，结果存 last_roll_result"""
        from .systems.skills import check_skill
        from .systems.combat import roll_against_difficulty, Difficulty
        from .effects import effect_add_skill_point, effect_gain_exp

        roll_cfg = node.roll
        skill_result = check_skill(self.state, roll_cfg.skill)
        difficulty = Difficulty.from_str(roll_cfg.difficulty)
        result = roll_against_difficulty(skill_result, difficulty, self.state)
        self.last_roll_result = result

        # 经验奖励
        if result.success and roll_cfg.exp_on_success > 0:
            ss = getattr(self.state, "_skill_system", None)
            if ss:
                sl = ss.skills.get(roll_cfg.skill)
                if sl:
                    sl.add_exp(roll_cfg.exp_on_success)
        if not result.success and roll_cfg.exp_on_fail > 0:
            ss = getattr(self.state, "_skill_system", None)
            if ss:
                sl = ss.skills.get(roll_cfg.skill)
                if sl:
                    sl.add_exp(roll_cfg.exp_on_fail)

        # 技能点点奖励（大成功）
        if result.success and result.margin >= 3 and roll_cfg.skill_point_on_success > 0:
            effect_add_skill_point(self.state, roll_cfg.skill_point_on_success, "大成功奖励")

        return result

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

        # 应用选项自带效果
        logs = apply_effects(self.state, choice.effects)

        # ── 选项级判定分支 ─────────────────────────
        # 格式：roll_success_node = 成功跳转节点，roll_fail_node = 失败跳转节点
        # roll_success_node 的内容同时决定了技能 ID（用 choice_tag 传）
        target_node: str = ""
        roll_result: Any = None

        if choice.roll_success_node or choice.roll_fail_node:
            # roll_success_node 格式："node_id|skill_id" 或纯 node_id（技能 ID 从 tag 取）
            # 为简化：roll_success_node = 成功节点，技能 ID 从 choice.tags 取（如 "roll:linac_diagnostics"）
            skill_id = ""
            success_node = choice.roll_success_node
            fail_node = choice.roll_fail_node

            # 从 tags 中找 "roll:skill_id" 格式
            for tag in choice.tags:
                if tag.startswith("roll:"):
                    skill_id = tag[5:]
                    break

            if not skill_id:
                logs.append("[警告] 选项有 roll 分支但未指定技能标签（格式: roll:skill_id）")
                target_node = choice.next_node
            else:
                from .systems.skills import check_skill
                from .systems.combat import roll_against_difficulty, Difficulty

                skill_result = check_skill(self.state, skill_id)
                # 用 roll_success_node 字段值解析难度（格式："node_id:difficulty"）
                parts = success_node.rsplit(":", 1)
                node_id_part = parts[0]
                difficulty_str = parts[1] if len(parts) == 2 else "normal"
                difficulty = Difficulty.from_str(difficulty_str)

                roll_result = roll_against_difficulty(skill_result, difficulty, self.state)
                logs.append(str(roll_result))

                # 经验奖励
                from .effects import effect_gain_exp
                if roll_result.success and roll_result.margin >= 3:
                    exp_msg = effect_gain_exp.__wrapped__(self.state, skill_id, 50) \
                        if hasattr(effect_gain_exp, "__wrapped__") else ""
                    if exp_msg:
                        logs.append(exp_msg)

                target_node = node_id_part if roll_result.success else fail_node
        else:
            target_node = choice.next_node

        # 跳转
        try:
            self.navigate_to(target_node)
            return True, f"→ {target_node}", logs
        except ValueError as e:
            return False, str(e), logs

    def to_dict(self) -> dict:
        """序列化（存档用）"""
        from dataclasses import asdict
        import copy
        state_copy = copy.deepcopy(self.state)
        # _skill_system 不是 asdict 能序列化的，手动处理
        ss = state_copy._skill_system
        ss_data = None
        if ss is not None:
            from dataclasses import asdict as ai
            # SkillSystem → dict
            ss_data = {
                "skill_points": ss.skill_points,
                "skills": {k: ai(v) for k, v in ss.skills.items()},
            }
            state_copy._skill_system = None
        result = {
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "state": asdict(state_copy),
            "current_node_id": self.current_node_id,
        }
        if ss_data is not None:
            result["state"]["_skill_system"] = ss_data
        return result

    @classmethod
    def from_dict(cls, data: dict) -> TreeEngine:
        """反序列化"""
        engine = cls()
        for node_data in data["nodes"].values():
            choices = [Choice(**c) for c in node_data.pop("choices", [])]
            # 处理 roll 字段反序列化
            roll_data = node_data.pop("roll", None)
            roll_config = None
            if roll_data:
                roll_config = RollConfig(**roll_data)
            node = TreeNode(**node_data, choices=choices, roll=roll_config)
            engine.add_node(node)

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
        gs_val = state_data.get("game_start", "")
        if isinstance(gs_val, datetime):
            game_start = gs_val
        else:
            game_start = datetime.fromisoformat(gs_val) if gs_val else datetime.now()
        engine.state = GameState(
            attrs=state_data.get("attrs", {}),
            npcs=npcs,
            items=items,
            flags=set(state_data.get("flags", [])),
            visited_nodes=set(state_data.get("visited_nodes", [])),
            history=state_data.get("history", []),
            hour=state_data.get("hour", 9),
            day=state_data.get("day", 1),
            game_start=game_start,
            current_plugin=state_data.get("current_plugin", ""),
            current_node=state_data.get("current_node", ""),
        )

        # 恢复 _skill_system
        ss_data = state_data.get("_skill_system")
        if ss_data:
            from engine.systems.skills import SkillSystem, SkillLevel
            ss = SkillSystem()
            ss.skill_points = ss_data.get("skill_points", 0)
            for sid, sd in ss_data.get("skills", {}).items():
                sl = SkillLevel(skill_id=sid, level=sd.get("level", 0),
                                exp=sd.get("exp", 0.0), points_spent=sd.get("points_spent", 0))
                ss.skills[sid] = sl
            engine.state._skill_system = ss
        engine.current_node_id = data.get("current_node_id", "")
        return engine
