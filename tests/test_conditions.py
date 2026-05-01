"""test_conditions.py — 条件系统测试

覆盖全部 9 种条件类型：
attr / npc_relation / npc_trust / flag / not_flag /
has_item / visited / time / competitor_favor
"""

import pytest
from engine.conditions import (
    check_attr, check_npc_relation, check_npc_trust,
    check_flag, check_not_flag, check_has_item,
    check_visited, check_time, check_competitor_favor,
    evaluate_conditions,
)
from engine.state import GameState, NPCState, Item


@pytest.fixture
def state():
    s = GameState()
    s.attrs = {
        "技术能力": 60,
        "声望": 30,
        "competitor_zhuoya": 65,
    }
    s.npcs["陈主任"] = NPCState(name="陈主任", role="科室主任", relationship=70, trust=50)
    s.flags.add("met_director")
    s.visited_nodes.add("node_x")
    s.hour = 10
    s.day = 2
    s.items = [Item(id="report", name="报告", description="", quantity=1)]
    return s


class TestCheckAttr:
    def test_gte_pass(self, state):
        assert check_attr(state, "技术能力", ">=", 50)

    def test_gte_fail(self, state):
        assert not check_attr(state, "技术能力", ">=", 70)

    def test_lt_pass(self, state):
        assert check_attr(state, "声望", "<", 40)

    def test_eq_pass(self, state):
        assert check_attr(state, "技术能力", "==", 60)

    def test_neq_pass(self, state):
        assert check_attr(state, "声望", "!=", 60)


class TestCheckNpcRelation:
    def test_gte_pass(self, state):
        assert check_npc_relation(state, "陈主任", ">=", 60)

    def test_gte_fail(self, state):
        assert not check_npc_relation(state, "陈主任", ">=", 80)

    def test_unknown_npc(self, state):
        assert not check_npc_relation(state, "不存在的NPC", ">=", 0)


class TestCheckNpcTrust:
    def test_gte_pass(self, state):
        assert check_npc_trust(state, "陈主任", ">=", 40)

    def test_unknown_npc(self, state):
        assert not check_npc_trust(state, "不存在", ">=", 0)


class TestCheckFlag:
    def test_flag_exists(self, state):
        assert check_flag(state, "met_director")

    def test_flag_missing(self, state):
        assert not check_flag(state, "not_exist_flag")


class TestCheckNotFlag:
    def test_not_flag_pass(self, state):
        assert check_not_flag(state, "not_exist_flag")

    def test_not_flag_fail(self, state):
        assert not check_not_flag(state, "met_director")


class TestCheckHasItem:
    def test_has_item_pass(self, state):
        assert check_has_item(state, "report", 1)

    def test_has_item_insufficient_qty(self, state):
        assert not check_has_item(state, "report", 99)

    def test_missing_item(self, state):
        assert not check_has_item(state, "不存在的物品", 1)


class TestCheckVisited:
    def test_visited_pass(self, state):
        assert check_visited(state, "node_x")

    def test_visited_fail(self, state):
        assert not check_visited(state, "never_visited_node")


class TestCheckTime:
    def test_gte_pass(self, state):
        assert check_time(state, ">=", 9)

    def test_lt_pass(self, state):
        assert check_time(state, "<", 15)

    def test_eq_pass(self, state):
        assert check_time(state, "==", 10)


class TestCompetitorFavor:
    def test_zhuoya_gte_pass(self, state):
        assert check_competitor_favor(state, "zhuoya", ">=", 60)

    def test_zhuoya_gte_fail(self, state):
        assert not check_competitor_favor(state, "zhuoya", ">=", 70)

    def test_unknown_competitor_defaults_to_zero(self, state):
        # 未知竞品返回 0，默认好感度 0
        assert not check_competitor_favor(state, "unknown", ">=", 1)


class TestEvaluateConditions:
    def test_empty_conditions(self, state):
        assert evaluate_conditions(state, []) is True

    def test_single_condition_pass(self, state):
        cond = [{"check": "attr", "attr": "技术能力", "op": ">=", "value": 50}]
        assert evaluate_conditions(state, cond) is True

    def test_single_condition_fail(self, state):
        cond = [{"check": "attr", "attr": "技术能力", "op": ">=", "value": 99}]
        assert evaluate_conditions(state, cond) is False

    def test_and_logic_all_pass(self, state):
        cond = [
            {"check": "attr", "attr": "技术能力", "op": ">=", "value": 50},
            {"check": "flag", "flag": "met_director"},
        ]
        assert evaluate_conditions(state, cond) is True

    def test_and_logic_one_fail(self, state):
        cond = [
            {"check": "attr", "attr": "技术能力", "op": ">=", "value": 99},
            {"check": "flag", "flag": "met_director"},
        ]
        assert evaluate_conditions(state, cond) is False

    def test_unknown_condition_type_raises(self, state):
        cond = [{"check": "nonexistent_type", "foo": "bar"}]
        with pytest.raises(ValueError, match="未知条件类型"):
            evaluate_conditions(state, cond)
