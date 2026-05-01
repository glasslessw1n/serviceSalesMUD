"""pytest fixtures — 所有测试共享"""

import sys
from pathlib import Path

# 确保 engine/ 可以 import
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from engine.tree import TreeEngine, TreeNode, Choice
from engine.state import GameState
from engine.loader import load_plugins
from engine.systems.skills import SkillSystem


@pytest.fixture
def fresh_engine():
    """干净的 TreeEngine"""
    return TreeEngine()


@pytest.fixture
def fresh_state():
    """干净的 GameState"""
    return GameState()


@pytest.fixture
def simple_node_tree():
    """一个简单的小树，用于快速测试"""
    engine = TreeEngine()

    # A → B → C（结局）
    engine.add_node(TreeNode(
        id="start",
        title="开始",
        text="这是开始",
        choices=[
            Choice(text="去B", next_node="node_b"),
            Choice(text="直接结局", next_node="end"),
        ],
    ))
    engine.add_node(TreeNode(
        id="node_b",
        title="B节点",
        text="这是B",
        choices=[Choice(text="去C", next_node="node_c")],
    ))
    engine.add_node(TreeNode(
        id="node_c",
        title="C节点",
        text="这是C",
        choices=[],  # 结局
    ))
    engine.add_node(TreeNode(
        id="end",
        title="结局",
        text="游戏结束",
        choices=[],
    ))

    engine.navigate_to("start")
    return engine


@pytest.fixture
def multi_plugin_engine():
    """加载真实插件（elekta_service）"""
    engine = TreeEngine()
    logs = load_plugins(
        engine,
        plugins_dir=Path(__file__).parent.parent / "plugins",
        root_node_id="start",
    )
    return engine, logs


@pytest.fixture
def skill_system_state():
    """带技能系统的 GameState"""
    state = GameState()
    ss = SkillSystem()
    ss.skill_points = 3
    state._skill_system = ss
    return state
