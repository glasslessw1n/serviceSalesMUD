"""test_loader.py — 插件加载和校验测试"""

import pytest
from pathlib import Path
from engine.tree import TreeEngine, TreeNode, Choice
from engine.loader import (
    load_plugins, validate_tree, _find_plugins, _parse_scene_node
)


class TestFindPlugins:
    def test_finds_plugins(self):
        plugins_dir = Path(__file__).parent.parent / "plugins"
        found = _find_plugins(plugins_dir)
        names = [p.name for p in found]
        assert "elekta_service" in names or "tender_battle" in names


class TestLoadPlugins:
    def test_loads_real_plugins(self):
        engine = TreeEngine()
        logs = load_plugins(
            engine,
            plugins_dir=Path(__file__).parent.parent / "plugins",
            root_node_id="start",
        )
        # 应该没有错误级别的日志
        error_logs = [l for l in logs if "❌" in l or "错误" in l]
        assert len(error_logs) == 0, f"加载有错误: {error_logs}"
        # 至少加载了 40+ 节点
        assert len(engine.nodes) >= 40

    def test_load_with_contract_start(self):
        engine = TreeEngine()
        logs = load_plugins(
            engine,
            plugins_dir=Path(__file__).parent.parent / "plugins",
            root_node_id="contract_start",
        )
        error_logs = [l for l in logs if "❌" in l]
        assert len(error_logs) == 0


class TestValidateTree:
    def test_valid_tree_passes(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(id="start", choices=[
            Choice(text="go", next_node="end")
        ]))
        engine.add_node(TreeNode(id="end"))
        errors = validate_tree(engine.nodes, "start")
        assert len(errors) == 0

    def test_dangling_reference_caught(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(id="start", choices=[
            Choice(text="go", next_node="does_not_exist")
        ]))
        errors = validate_tree(engine.nodes, "start")
        assert len(errors) == 1
        assert "不存在" in errors[0]

    def test_root_not_exist(self):
        errors = validate_tree({}, "nonexistent_root")
        assert len(errors) == 1
        assert "根节点" in errors[0]


class TestParseSceneNode:
    def test_parses_minimal_node(self):
        yaml_data = {
            "id": "test_node",
            "title": "测试节点",
            "text": "这是内容",
            "choices": [],
        }
        node = _parse_scene_node(yaml_data, "test_plugin")
        assert node.id == "test_node"
        assert node.plugin == "test_plugin"
        assert len(node.choices) == 0

    def test_parses_choices(self):
        yaml_data = {
            "id": "test_node",
            "choices": [
                {
                    "text": "选项1",
                    "next": "next_node",
                    "conditions": [{"check": "flag", "flag": "foo"}],
                    "effects": [{"effect": "set_flag", "flag": "bar"}],
                    "tags": ["推荐"],
                }
            ],
        }
        node = _parse_scene_node(yaml_data, "test")
        assert len(node.choices) == 1
        c = node.choices[0]
        assert c.text == "选项1"
        assert c.next_node == "next_node"
        assert len(c.conditions) == 1
        assert len(c.effects) == 1

    def test_parses_node_roll(self):
        yaml_data = {
            "id": "roll_node",
            "roll": {
                "skill": "linac_diagnostics",
                "difficulty": "hard",
                "label": "故障诊断",
                "exp_on_success": 50,
            },
            "choices": [],
        }
        node = _parse_scene_node(yaml_data, "test")
        assert node.roll is not None
        assert node.roll.skill == "linac_diagnostics"
        assert node.roll.difficulty == "hard"
        assert node.roll.exp_on_success == 50

    def test_effects_merged_into_on_enter(self):
        yaml_data = {
            "id": "test",
            "effects": [{"effect": "set_flag", "flag": "from_effects"}],
            "on_enter": [{"effect": "set_flag", "flag": "from_on_enter"}],
            "choices": [],
        }
        node = _parse_scene_node(yaml_data, "test")
        # effects 被追加到 on_enter 后面
        assert len(node.on_enter) == 2
        flag_ids = [e.get("flag") for e in node.on_enter]
        assert "from_effects" in flag_ids
        assert "from_on_enter" in flag_ids
