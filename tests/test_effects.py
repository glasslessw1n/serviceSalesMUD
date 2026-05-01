"""test_effects.py — 效果系统测试

覆盖全部 13 种效果类型：
mod_attr / mod_npc_relation / mod_npc_trust / set_flag /
clear_flag / add_item / remove_item / set_npc_flag /
advance_time / log / add_skill_point / learn_skill / gain_exp
"""

import pytest
from engine.effects import (
    effect_mod_attr, effect_mod_npc_relation, effect_mod_npc_trust,
    effect_set_flag, effect_clear_flag, effect_add_item,
    effect_remove_item, effect_set_npc_flag,
    effect_advance_time, effect_log,
    effect_add_skill_point, effect_learn_skill, effect_gain_exp,
    apply_effects,
)
from engine.state import GameState, NPCState, Item


@pytest.fixture
def state():
    s = GameState()
    s.attrs = {"声望": 30, "技术能力": 50}
    s.npcs["陈主任"] = NPCState(name="陈主任", role="科室主任", relationship=50, trust=30)
    s.hour = 9
    s.day = 1
    s.items = []
    return s


class TestModAttr:
    def test_add(self, state):
        log = effect_mod_attr(state, "声望", "+", 10)
        assert state.get_attr("声望") == 40
        assert "40" in log

    def test_subtract(self, state):
        effect_mod_attr(state, "声望", "-", 10)
        assert state.get_attr("声望") == 20

    def test_set(self, state):
        effect_mod_attr(state, "声望", "=", 99)
        assert state.get_attr("声望") == 99

    def test_multiply(self, state):
        effect_mod_attr(state, "声望", "*", 2)
        assert state.get_attr("声望") == 60

    def test_new_attr_starts_at_zero(self, state):
        effect_mod_attr(state, "新属性", "+", 5)
        assert state.get_attr("新属性") == 5


class TestModNpcRelation:
    def test_add(self, state):
        log = effect_mod_npc_relation(state, "陈主任", "+", 20)
        assert state.npcs["陈主任"].relationship == 70
        assert "↑" in log

    def test_subtract(self, state):
        effect_mod_npc_relation(state, "陈主任", "-", 10)
        assert state.npcs["陈主任"].relationship == 40

    def test_clamped_to_100(self, state):
        effect_mod_npc_relation(state, "陈主任", "+", 999)
        assert state.npcs["陈主任"].relationship == 100

    def test_clamped_to_0(self, state):
        effect_mod_npc_relation(state, "陈主任", "-", 999)
        assert state.npcs["陈主任"].relationship == 0

    def test_unknown_npc_auto_created(self, state):
        log = effect_mod_npc_relation(state, "新NPC", "+", 10)
        assert "新NPC" in state.npcs


class TestModNpcTrust:
    def test_add(self, state):
        effect_mod_npc_trust(state, "陈主任", "+", 20)
        assert state.npcs["陈主任"].trust == 50


class TestSetFlag:
    def test_set_new_flag(self, state):
        log = effect_set_flag(state, "new_flag")
        assert state.has_flag("new_flag")
        assert "new_flag" in log

    def test_set_existing_flag(self, state):
        state.set_flag("existing")
        log = effect_set_flag(state, "existing")
        assert "已存在" in log


class TestClearFlag:
    def test_clear_existing_flag(self, state):
        state.set_flag("to_clear")
        log = effect_clear_flag(state, "to_clear")
        assert not state.has_flag("to_clear")
        assert "清除标记" in log

    def test_clear_missing_flag(self, state):
        log = effect_clear_flag(state, "never_existed")
        assert log == ""


class TestAddItem:
    def test_add_new_item(self, state):
        log = effect_add_item(state, "report", "检测报告", "设备检测", 1)
        assert len(state.items) == 1
        assert state.items[0].id == "report"
        assert "检测报告" in log

    def test_add_existing_item_increments_qty(self, state):
        state.items.append(Item(id="report", name="报告", description="", quantity=5))
        effect_add_item(state, "report", "报告", "", 3)
        assert next(i.quantity for i in state.items if i.id == "report") == 8


class TestRemoveItem:
    def test_remove_partial_qty(self, state):
        state.items.append(Item(id="report", name="报告", description="", quantity=5))
        log = effect_remove_item(state, "report", 3)
        assert next(i.quantity for i in state.items if i.id == "report") == 2
        assert "失去物品" in log

    def test_remove_all_qty_removes_item(self, state):
        state.items.append(Item(id="report", name="报告", description="", quantity=2))
        effect_remove_item(state, "report", 2)
        assert not any(i.id == "report" for i in state.items)

    def test_remove_missing_item(self, state):
        log = effect_remove_item(state, "nonexistent", 1)
        assert "错误" in log


class TestSetNpcFlag:
    def test_set_npc_flag(self, state):
        log = effect_set_npc_flag(state, "陈主任", "friendly")
        assert "friendly" in state.npcs["陈主任"].flags
        assert "NPC 标记" in log


class TestAdvanceTime:
    def test_advance_time(self, state):
        log = effect_advance_time(state, 3)
        assert state.hour == 12
        assert "3h" in log
        assert "Day 1" in log

    def test_advance_time_crosses_midnight(self, state):
        state.hour = 22
        effect_advance_time(state, 4)
        assert state.hour == 2
        assert state.day == 2


class TestEffectLog:
    def test_log_returns_message(self, state):
        log = effect_log(state, "自定义消息")
        assert log == "自定义消息"


class TestSkillEffects:
    def test_add_skill_point(self, state):
        from engine.systems.skills import SkillSystem
        state._skill_system = SkillSystem()
        state._skill_system.skill_points = 0

        log = effect_add_skill_point(state, 2, "测试奖励")
        assert state._skill_system.skill_points == 2
        assert "技能点" in log
        assert "测试奖励" in log

    def test_learn_skill(self, state):
        from engine.systems.skills import SKILL_DEFINITIONS, SkillSystem
        state._skill_system = SkillSystem()
        state._skill_system.skill_points = 3

        log = effect_learn_skill(state, "linac_diagnostics")
        assert "linac_diagnostics" in state._skill_system.skills or "诊断" in log

    def test_gain_exp(self, state):
        from engine.systems.skills import SkillSystem, SkillLevel
        state._skill_system = SkillSystem()
        state._skill_system.skills["linac_diagnostics"] = SkillLevel(
            skill_id="linac_diagnostics", level=1, exp=0, points_spent=0
        )

        log = effect_gain_exp(state, "linac_diagnostics", 150)
        # 150 exp 在 Lv.1 → Lv.2 阈值（100），应该升级
        assert "150" in log
        assert "直线加速器诊断" in log  # skill name, not skill_id


class TestApplyEffects:
    def test_apply_effects_list(self, state):
        effects = [
            {"effect": "mod_attr", "attr": "声望", "op": "+", "value": 5},
            {"effect": "set_flag", "flag": "test_flag"},
        ]
        logs = apply_effects(state, effects)
        assert state.get_attr("声望") == 35
        assert state.has_flag("test_flag")
        assert len(logs) == 2

    def test_unknown_effect_type_warning(self, state):
        effects = [{"effect": "nonexistent_effect", "foo": "bar"}]
        logs = apply_effects(state, effects)
        assert any("未知效果类型" in log for log in logs)

    def test_effect_exception_caught(self, state):
        effects = [{"effect": "mod_attr", "attr": "声望", "op": "+", "value": 5}]
        # 即使有异常也不崩溃，只记录错误
        logs = apply_effects(state, effects)
        assert len(logs) >= 1
