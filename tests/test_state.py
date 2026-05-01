"""test_state.py — GameState 测试"""

import pytest
from engine.state import GameState, NPCState, Item


class TestGameStateBasics:
    def test_default_attrs(self):
        s = GameState()
        # 有一些默认 attrs
        assert isinstance(s.attrs, dict)

    def test_get_set_attr(self):
        s = GameState()
        s.set_attr("声望", 50)
        assert s.get_attr("声望") == 50

    def test_get_attr_default(self):
        s = GameState()
        val = s.get_attr("不存在")
        assert val == 0  # default is 0

    def test_competitor_attrs_initialized(self):
        s = GameState()
        # 竞品好感度应该初始化为 50（中立）
        assert s.attrs.get("competitor_zhuoya") == 50
        assert s.attrs.get("competitor_hongyang") == 50
        assert s.attrs.get("competitor_zhongtaihe") == 50


class TestNPCState:
    def test_npc_creation(self):
        npc = NPCState(name="陈主任", role="设备科主任", relationship=60, trust=40)
        assert npc.name == "陈主任"
        assert npc.relationship == 60
        assert "friendly" not in npc.flags

    def test_npc_flags(self):
        npc = NPCState(name="测试", role="临时")
        npc.flags.add("visited")
        assert "visited" in npc.flags


class TestItems:
    def test_item_creation(self):
        item = Item(id="report", name="检测报告", description="", quantity=1)
        assert item.id == "report"
        assert item.quantity == 1

    def test_item_quantity_default(self):
        item = Item(id="x", name="X", description="")
        assert item.quantity == 1


class TestGameStateMethods:
    def test_set_flag(self):
        s = GameState()
        s.set_flag("test")
        assert s.has_flag("test")

    def test_advance_time(self):
        s = GameState()
        s.hour = 10
        s.advance_time(5)
        assert s.hour == 15

    def test_advance_time_next_day(self):
        s = GameState()
        s.hour = 22
        s.advance_time(4)
        assert s.hour == 2
        assert s.day == 2

    def test_history_append(self):
        s = GameState()
        s.history.append({"node": "a", "choice": "go to b", "next": "b"})
        assert len(s.history) == 1

    def test_ensure_npc_creates_if_missing(self):
        s = GameState()
        npc = s.ensure_npc("新NPC")
        assert "新NPC" in s.npcs
        assert npc.relationship == 0


class TestSerialization:
    def test_game_state_attrs_serializable(self):
        s = GameState()
        s.set_attr("声望", 88)
        # dataclass asdict 应该可以序列化（set 需要手动处理）
        from dataclasses import asdict
        data = asdict(s)
        assert data["attrs"]["声望"] == 88

    def test_set_not_json_serializable_but_list_is(self):
        import json
        s = GameState()
        s.flags.add("test_flag")
        s.visited_nodes.add("node_x")
        data = {
            "flags": list(s.flags),
            "visited_nodes": list(s.visited_nodes),
        }
        # 不应该抛异常
        json.dumps(data)
