"""技能系统 —— 技能点积累与加点机制。

技能独立于属性（Attr）运作：
  - Attr 是"角色三维"，出生固定，通过剧情选择缓慢成长
  - Skill 是"专项技能"，可花费技能点自由加点，影响特定判定

技能检查（check_skill）返回一个元组：
  (是否成功, 投骰结果, 技能加成, 最终值, 难度描述)
供 combat.py 的 roll_against_difficulty 使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.state import GameState


# ── 技能定义 ──────────────────────────────────────────────

SKILL_DEFINITIONS: dict[str, dict] = {
    # 医疗设备知识
    "linac_diagnostics": {
        "name": "直线加速器诊断",
        "name_en": "Linac Diagnostics",
        "desc": "根据日志和报警判断故障根源",
        "category": "技术",
        "base_bonus": 0,      # 点进技能后每次检查的固定加值
    },
    "tps_operation": {
        "name": "TPS 操作",
        "name_en": "TPS Operation",
        "desc": "熟练使用 Monaco/XiO 等治疗计划系统",
        "category": "技术",
        "base_bonus": 0,
    },
    "negotiation": {
        "name": "商务谈判",
        "name_en": "Negotiation",
        "desc": "在商务场合影响对方决策",
        "category": "商务",
        "base_bonus": 0,
    },
    "hospital_network": {
        "name": "院内关系网",
        "name_en": "Hospital Network",
        "desc": "了解院内人事关系和决策链",
        "category": "关系",
        "base_bonus": 0,
    },
    "crisis_management": {
        "name": "危机处理",
        "name_en": "Crisis Management",
        "desc": "高压环境下快速决策",
        "category": "通用",
        "base_bonus": 0,
    },
    "data_analysis": {
        "name": "数据分析",
        "name_en": "Data Analysis",
        "desc": "从维修记录和性能数据中提炼商业洞察",
        "category": "商务",
        "base_bonus": 0,
    },
}


@dataclass
class SkillLevel:
    """单个技能的当前等级和经验"""
    skill_id: str
    level: int = 0          # 0 = 未学习，最高 5
    exp: float = 0.0        # 当前经验值（达到阈值升级）
    points_spent: int = 0   # 累计投入的技能点

    EXP_TO_LEVEL = [0, 100, 300, 700, 1500, 3000]  # 升到 N 级所需总经验

    def add_exp(self, amount: float) -> bool:
        """加经验，可能升级。返回是否升级了。"""
        if self.level >= 5:
            return False
        self.exp += amount
        leveled_up = False
        while self.level < 5 and self.exp >= self.EXP_TO_LEVEL[self.level + 1]:
            self.level += 1
            leveled_up = True
        return leveled_up

    def bonus(self) -> int:
        """该等级的技能加值：0/2/5/9/14/20（每级递增）"""
        BONUSES = [0, 2, 5, 9, 14, 20]
        return BONUSES[self.level]


@dataclass
class SkillSystem:
    """角色全部技能的状态"""

    # 技能点：每升一级获得 1 点；剧情某些选择也会奖励
    skill_points: int = 0

    # 各技能等级
    skills: dict[str, SkillLevel] = field(default_factory=dict)

    def learn_or_level(self, skill_id: str) -> tuple[bool, str]:
        """
        投入 1 点技能点学习或升级一个技能。
        返回 (是否成功, 消息)
        """
        if skill_id not in SKILL_DEFINITIONS:
            return False, f"未知技能: {skill_id}"

        if self.skill_points <= 0:
            return False, "没有可用的技能点"

        sl = self.skills.get(skill_id)
        if sl is None:
            sl = SkillLevel(skill_id=skill_id, level=0)
            self.skills[skill_id] = sl

        if sl.level >= 5:
            return False, f"{SKILL_DEFINITIONS[skill_id]['name']} 已满级"

        self.skill_points -= 1
        sl.points_spent += 1
        old_level = sl.level
        sl.level += 1
        bonus = sl.bonus()
        name = SKILL_DEFINITIONS[skill_id]["name"]
        return True, f"习得 {name} Lv.{sl.level}（+{bonus} 加值）"

    def add_skill_points(self, n: int, reason: str = ""):
        self.skill_points += n
        msg = f"+{n} 技能点"
        if reason:
            msg += f"（{reason}）"
        return msg

    def get_bonus(self, skill_id: str) -> int:
        sl = self.skills.get(skill_id)
        return sl.bonus() if sl else 0

    def is_learned(self, skill_id: str) -> bool:
        sl = self.skills.get(skill_id)
        return sl is not None and sl.level > 0

    def all_skills_summary(self) -> list[tuple[str, int, int]]:
        """返回 [(skill_id, level, bonus)]，未学习的技能 level=0"""
        result = []
        for sid in SKILL_DEFINITIONS:
            sl = self.skills.get(sid)
            result.append((sid, sl.level if sl else 0, sl.bonus() if sl else 0))
        return result


# ── 效果函数（供 effects.py 调用）─────────────────────────

def effect_add_skill_point(state: GameState, amount: int, reason: str = "") -> str:
    """剧情效果：奖励技能点"""
    # 延迟导入避免循环引用
    from engine.systems.skills import SkillSystem
    ss = getattr(state, "_skill_system", None)
    if ss is None:
        ss = SkillSystem()
        state._skill_system = ss
    ss.add_skill_points(amount, reason)
    msg = f"+{amount} 技能点"
    if reason:
        msg += f"（{reason}）"
    return f"【技能点】{msg}"


def effect_learn_skill(state: GameState, skill_id: str) -> str:
    """剧情效果：强制学会某技能（不消耗技能点）"""
    from engine.systems.skills import SkillSystem, SkillLevel, SKILL_DEFINITIONS
    ss = getattr(state, "_skill_system", None)
    if ss is None:
        ss = SkillSystem()
        state._skill_system = ss
    if skill_id not in SKILL_DEFINITIONS:
        return f"【错误】未知技能: {skill_id}"
    sl = ss.skills.get(skill_id)
    if sl is None:
        sl = SkillLevel(skill_id=skill_id, level=1, points_spent=0)
        ss.skills[skill_id] = sl
    elif sl.level < 5:
        sl.level += 1
    name = SKILL_DEFINITIONS[skill_id]["name"]
    return f"【技能习得】{name} Lv.{sl.level}（+{sl.bonus()} 加值）"


def effect_gain_exp(state: GameState, skill_id: str, amount: float) -> str:
    """剧情效果：给某技能加经验（可能触发升级）"""
    from engine.systems.skills import SKILL_DEFINITIONS
    ss = getattr(state, "_skill_system", None)
    if ss is None:
        return ""
    sl = ss.skills.get(skill_id)
    if sl is None:
        return ""
    leveled = sl.add_exp(amount)
    msg = f"+{amount:.0f} 经验 → {SKILL_DEFINITIONS.get(skill_id, {}).get('name', skill_id)}"
    if leveled:
        msg += f" ⬆ 升到 Lv.{sl.level}！"
    return msg


# ── 技能检查（供 combat.py 调用）───────────────────────────

def check_skill(
    state: GameState,
    skill_id: str,
) -> tuple[int, int, str]:
    """
    技能检查。

    返回 (final_value, bonus, skill_name)
      - final_value: 投骰结果 + 技能加成
      - bonus: 加成数值
      - skill_name: 技能名称（显示用）

    使用 state._skill_system 读取技能数据。
    """
    ss: Optional[SkillSystem] = getattr(state, "_skill_system", None)
    bonus = ss.get_bonus(skill_id) if ss else 0
    roll = roll_d66()
    final = roll + bonus

    skill_name = SKILL_DEFINITIONS.get(skill_id, {}).get("name", skill_id)
    return final, bonus, skill_name


def roll_d66() -> int:
    """投两个 d6，返回 2~12（模拟技能相关随机性）"""
    import random
    return random.randint(1, 6) + random.randint(1, 6)


# ── 效果注册到 effects.py 的辅助 ──────────────────────────

EFFECT_DISPATCH_SKILLS = {
    "add_skill_point": effect_add_skill_point,
    "learn_skill":     effect_learn_skill,
    "gain_exp":        effect_gain_exp,
}
