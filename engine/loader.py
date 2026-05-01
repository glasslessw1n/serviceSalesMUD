"""插件加载器 —— 扫描 plugins/ 目录，解析 YAML 场景/NPC 定义。

插件规范：
  plugins/<plugin_name>/
    __init__.py          # 可空，标记为 Python 包即可
    scenes.yaml          # [必需] 场景节点列表
    npcs.yaml            # [可选] NPC 初始定义

scenes.yaml 格式见 engine/tree.py 中的 TreeNode/Choice 数据结构。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .tree import TreeNode, Choice, TreeEngine
from .state import NPCState

if TYPE_CHECKING:
    from .state import GameState


def _find_plugins(root: Path) -> list[Path]:
    """扫描插件目录，返回所有含 scenes.yaml 的子目录"""
    plugins = []
    if not root.exists():
        return plugins
    for entry in root.iterdir():
        if entry.is_dir() and not entry.name.startswith("_"):
            scene_file = entry / "scenes.yaml"
            if scene_file.exists():
                plugins.append(entry)
    return plugins


def _parse_scene_node(data: dict, plugin_name: str) -> TreeNode:
    """从 YAML dict 解析单个场景节点"""
    from .tree import RollConfig

    choices = []
    for cdata in data.get("choices", []):
        choices.append(Choice(
            text=cdata["text"],
            next_node=cdata.get("next", "__END__"),
            conditions=cdata.get("conditions", []),
            effects=cdata.get("effects", []),
            tags=cdata.get("tags", []),
            roll_success_node=cdata.get("roll_success_node", ""),
            roll_fail_node=cdata.get("roll_fail_node", ""),
        ))

    # 合并 effects 和 on_enter：YAML 中 effects 是 on_enter 的简写
    on_enter = data.get("on_enter", [])
    node_effects = data.get("effects", [])
    if node_effects:
        on_enter = on_enter + node_effects

    # 解析节点级 roll
    roll_config = None
    roll_data = data.get("roll")
    if roll_data:
        roll_config = RollConfig(
            skill=roll_data.get("skill", ""),
            difficulty=roll_data.get("difficulty", "normal"),
            label=roll_data.get("label", ""),
            exp_on_success=roll_data.get("exp_on_success", 0),
            exp_on_fail=roll_data.get("exp_on_fail", 0),
            skill_point_on_success=roll_data.get("skill_point_on_success", 0),
        )

    return TreeNode(
        id=data["id"],
        title=data.get("title", ""),
        speaker=data.get("speaker", ""),
        text=data.get("text", ""),
        choices=choices,
        tags=data.get("tags", []),
        plugin=plugin_name,
        roll=roll_config,
        on_enter=on_enter,
        on_exit=data.get("on_exit", []),
    )


def _parse_npcs(data: list[dict]) -> dict[str, NPCState]:
    """解析 NPC 定义列表"""
    npcs = {}
    for nd in data:
        npcs[nd["name"]] = NPCState(
            name=nd["name"],
            role=nd.get("role", ""),
            relationship=nd.get("relationship", 0),
            trust=nd.get("trust", 0),
            flags=set(nd.get("flags", [])),
        )
    return npcs


def validate_tree(nodes: dict[str, TreeNode], root_id: str) -> list[str]:
    """基础校验：无悬挂引用、根节点存在"""
    errors = []

    if root_id not in nodes:
        errors.append(f"根节点 '{root_id}' 不存在")
        return errors

    # 检查所有 choice.next_node 在 nodes 中（允许特殊值 __END__）
    for node in nodes.values():
        for choice in node.choices:
            next_id = choice.next_node
            if next_id == "__END__":
                continue
            if next_id not in nodes:
                errors.append(
                    f"节点 '{node.id}' 的选项 '{choice.text}' "
                    f"指向不存在的节点 '{next_id}'"
                )

    return errors


def load_plugins(
    engine: TreeEngine,
    plugins_dir: str | Path,
    root_node_id: str = "start",
) -> list[str]:
    """
    加载所有插件，合并节点到引擎。
    返回加载日志。

    约定：第一个插件的 start 节点（或显式指定的 root_node_id）为根节点。
    如果没有找到根节点，取第一个加载的节点。
    """
    plugins_dir = Path(plugins_dir)
    plugin_paths = _find_plugins(plugins_dir)
    logs = []

    for pp in plugin_paths:
        plugin_name = pp.name
        logs.append(f"📦 加载插件: {plugin_name}")

        # 动态添加插件目录到 sys.path（允许 __init__.py 做复杂初始化）
        if str(pp.parent) not in sys.path:
            sys.path.insert(0, str(pp.parent))

        # 加载场景
        scene_file = pp / "scenes.yaml"
        with open(scene_file) as f:
            scenes_data = yaml.safe_load(f)

        if not scenes_data:
            logs.append(f"  ⚠ scenes.yaml 为空，跳过")
            continue

        for sd in scenes_data:
            node = _parse_scene_node(sd, plugin_name)
            engine.add_node(node)
            logs.append(f"  ✓ 节点: {node.id} ({node.title or '无标题'})")

        # 加载 NPC（可选）
        npc_file = pp / "npcs.yaml"
        if npc_file.exists():
            with open(npc_file) as f:
                npcs_data = yaml.safe_load(f)
            if npcs_data:
                npcs = _parse_npcs(npcs_data)
                for name, ns in npcs.items():
                    engine.state.npcs[name] = ns
                    logs.append(f"  ✓ NPC: {name} ({ns.role})")

    # 选择根节点
    if root_node_id in engine.nodes:
        engine.navigate_to(root_node_id)
    elif engine.nodes:
        first_id = next(iter(engine.nodes))
        engine.navigate_to(first_id)
        logs.append(f"⚠ 根节点 '{root_node_id}' 未找到，使用 '{first_id}'")
    else:
        raise RuntimeError("没有加载到任何节点")

    # 校验
    errors = validate_tree(engine.nodes, engine.current_node_id)
    if errors:
        logs.append("❌ 校验错误:")
        for e in errors:
            logs.append(f"  - {e}")

    return logs
