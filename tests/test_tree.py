"""test_tree.py — 树状引擎核心逻辑测试

TreeNode / Choice / RollConfig
TreeEngine: navigate_to / choose / get_available_choices
序列化: to_dict / from_dict
"""

import pytest
from engine.tree import TreeEngine, TreeNode, Choice, RollConfig
from engine.systems.combat import Difficulty


class TestTreeNode:
    def test_basic_node(self):
        node = TreeNode(id="test", title="标题", text="内容")
        assert node.id == "test"
        assert len(node.choices) == 0

    def test_node_with_choices(self):
        choice = Choice(text="选项1", next_node="next_node")
        node = TreeNode(id="test", choices=[choice])
        assert len(node.choices) == 1
        assert node.choices[0].text == "选项1"


class TestRollConfig:
    def test_roll_config_defaults(self):
        rc = RollConfig(skill="linac_diagnostics", difficulty="normal")
        assert rc.exp_on_success == 0
        assert rc.exp_on_fail == 0
        assert rc.skill_point_on_success == 0


class TestTreeEngineBasics:
    def test_add_node(self):
        engine = TreeEngine()
        node = TreeNode(id="start", title="Start")
        engine.add_node(node)
        assert "start" in engine.nodes

    def test_duplicate_node_id_raises(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(id="dup"))
        with pytest.raises(ValueError, match="ID 冲突"):
            engine.add_node(TreeNode(id="dup"))

    def test_navigate_to(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(id="start"))
        engine.navigate_to("start")
        assert engine.current_node_id == "start"


class TestChoiceRouting:
    def test_simple_next(self, simple_node_tree):
        engine = simple_node_tree
        engine.navigate_to("start")
        ok, msg, _ = engine.choose(0)  # go to B
        assert ok
        assert engine.current_node_id == "node_b"

    def test_out_of_range_choice(self, simple_node_tree):
        engine = simple_node_tree
        engine.navigate_to("start")
        ok, msg, _ = engine.choose(99)
        assert not ok
        assert "无效选择" in msg

    def test_condition_filtered_choice(self):
        """条件不满足的选项应该被过滤掉，不计入索引"""
        engine = TreeEngine()
        engine.add_node(TreeNode(
            id="start",
            choices=[
                Choice(text="永远看不到", next_node="end",
                       conditions=[{"check": "attr", "attr": "never", "op": ">=", "value": 999}]),
                Choice(text="永远看得到", next_node="end"),
            ]
        ))
        engine.add_node(TreeNode(id="end"))
        engine.navigate_to("start")
        available = engine.get_available_choices()
        assert len(available) == 1
        assert available[0].text == "永远看得到"
        # choose(1) 应该报错（因为 available 只有 1 项，索引 1 越界）
        ok, msg, _ = engine.choose(1)
        assert not ok


class TestNavigateToEffects:
    def test_on_enter_effects_fire(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(
            id="start",
            on_enter=[{"effect": "set_flag", "flag": "visited_start"}],
        ))
        engine.navigate_to("start")
        assert engine.state.has_flag("visited_start")

    def test_visited_nodes_tracked(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(id="a"))
        engine.add_node(TreeNode(id="b"))
        engine.navigate_to("a")
        engine.navigate_to("b")
        assert "a" in engine.state.visited_nodes
        assert "b" in engine.state.visited_nodes


class TestNodeRoll:
    def test_node_roll_sets_last_roll_result(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(
            id="start",
            roll=RollConfig(skill="linac_diagnostics", difficulty="easy", label="诊断"),
        ))
        engine.navigate_to("start")
        # roll 执行了
        assert engine.last_roll_result is not None
        # RollResult 有这些字段
        r = engine.last_roll_result
        assert hasattr(r, "success")
        assert hasattr(r, "roll")
        assert hasattr(r, "skill_name")


class TestSerialization:
    def test_to_dict_roundtrip(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(id="start", title="开始"))
        engine.add_node(TreeNode(id="end", choices=[]))
        engine.navigate_to("start")

        data = engine.to_dict()
        restored = TreeEngine.from_dict(data)

        assert "start" in restored.nodes
        assert "end" in restored.nodes
        assert restored.current_node_id == "start"

    def test_visited_nodes_serialized(self):
        engine = TreeEngine()
        engine.add_node(TreeNode(id="start"))
        engine.add_node(TreeNode(id="next"))
        engine.navigate_to("start")
        engine.navigate_to("next")

        data = engine.to_dict()
        restored = TreeEngine.from_dict(data)

        assert "start" in restored.state.visited_nodes
        assert "next" in restored.state.visited_nodes


class TestEndNodeDetection:
    def test_is_end_true_when_no_choices(self, simple_node_tree):
        engine = simple_node_tree
        engine.navigate_to("node_c")
        node = engine.get_current_node()
        assert len(node.choices) == 0

    def test_is_end_false_when_has_choices(self, simple_node_tree):
        engine = simple_node_tree
        engine.navigate_to("start")
        node = engine.get_current_node()
        assert len(node.choices) > 0
