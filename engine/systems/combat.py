"""判定引擎 —— 骰点 + 技能修正 vs 难度等级。

核心函数：roll_against_difficulty(skill_check_result, difficulty)
  - skill_check_result: check_skill() 的返回值
  - difficulty: Difficulty 枚举（EASY / NORMAL / HARD / VERY_HARD / Legendary）
  - 返回 RollResult（含成功/失败、叙事文本）

难度等级：
  EASY       (DC 8)  — 新人也能过
  NORMAL     (DC 11) — 有一定技能的人
  HARD       (DC 14) — 需要经验和技能等级
  VERY_HARD  (DC 17) — 只有高水平才可能过
  Legendary  (DC 20) — 极少数情况
"""

from __future__ import annotations

import random
from enum import IntEnum

from engine.state import GameState
from .skills import check_skill, roll_d66


class Difficulty(IntEnum):
    EASY      = 8
    NORMAL    = 11
    HARD      = 14
    VERY_HARD = 17
    LEGENDARY = 20

    @classmethod
    def from_str(cls, name: str) -> "Difficulty":
        mapping = {
            "easy": cls.EASY,
            "normal": cls.NORMAL,
            "hard": cls.HARD,
            "very_hard": cls.VERY_HARD,
            "legendary": cls.LEGENDARY,
            "极简单": cls.EASY,
            "普通": cls.NORMAL,
            "困难": cls.HARD,
            "极困难": cls.VERY_HARD,
            "传奇": cls.LEGENDARY,
        }
        return cls(mapping.get(name.lower(), cls.NORMAL))

    def label(self) -> str:
        labels = {
            Difficulty.EASY:      "☺ 简单",
            Difficulty.NORMAL:    "⚖ 普通",
            Difficulty.HARD:      "😓 困难",
            Difficulty.VERY_HARD: "😰 极困难",
            Difficulty.LEGENDARY: "� legendary 传奇",
        }
        return labels[self]


# ── 判定结果 ──────────────────────────────────────────────


class RollResult:
    def __init__(
        self,
        success: bool,
        roll: int,
        bonus: int,
        final: int,
        difficulty: Difficulty,
        skill_name: str,
        margin: int,        # 超出或不足 DC 的数值（正值=成功溢出，负值=失败缺口）
        crit: bool = False, # 是否大成功（骰出 12 且成功）
        fumble: bool = False,  # 是否大失败（骰出 2 且失败）
        narrative: str = "",
    ):
        self.success   = success
        self.roll      = roll
        self.bonus     = bonus
        self.final     = final
        self.difficulty = difficulty
        self.skill_name = skill_name
        self.margin    = margin
        self.crit      = crit
        self.fumble    = fumble
        self.narrative = narrative

    def __str__(self) -> str:
        roll_str = f"{self.roll}" + ("⭐" if self.crit else "")
        bonus_str = f"+{self.bonus}" if self.bonus else ""
        dc_str = f"DC {self.difficulty.value}"

        result_icon = "✅" if self.success else "❌"
        margin_str = f"(超出 {self.margin})" if self.success else f"(差 {abs(self.margin)})"

        header = (
            f"{result_icon} 判定: {self.skill_name}\n"
            f"  🎲 {roll_str}{bonus_str} = {self.final}  vs  {dc_str}\n"
        )

        if self.crit:
            header += f"  🌟 大成功！{self.narrative}\n"
        elif self.fumble:
            header += f"  💀 大失败…… {self.narrative}\n"
        elif self.success:
            header += f"  成功 {margin_str}。{self.narrative}\n"
        else:
            header += f"  失败 {margin_str}。{self.narrative}\n"

        return header


# ── 判定主函数 ─────────────────────────────────────────────


def roll_against_difficulty(
    skill_check_result: tuple[int, int, str],
    difficulty: Difficulty | str,
    state: GameState | None = None,
) -> RollResult:
    """
    执行一次技能判定。

    skill_check_result: (final_value, bonus, skill_name)
      由 check_skill() 返回。
    difficulty: Difficulty 枚举或字符串。

    state: 可选，传入了可获得额外修正（如物品加成）。

    返回 RollResult。
    """
    if isinstance(difficulty, str):
        difficulty = Difficulty.from_str(difficulty)

    final, bonus, skill_name = skill_check_result
    roll  = final - bonus   # 反推骰值（用于显示）
    crit  = (roll == 12)
    fumble = (roll == 2)

    margin = final - difficulty.value
    success = margin >= 0

    # 大成功：骰出12且成功
    if crit and success:
        success = True
        margin = max(margin, 3)   # 至少算超出3
        narrative = _crit_success_narrative(skill_name)
    # 大失败：骰出2且失败
    elif fumble and not success:
        success = False
        margin = min(margin, -3)  # 至少算差3
        narrative = _fumble_narrative(skill_name)
    else:
        narrative = _normal_narrative(skill_name, success, margin, difficulty)

    return RollResult(
        success=success,
        roll=roll,
        bonus=bonus,
        final=final,
        difficulty=difficulty,
        skill_name=skill_name,
        margin=margin,
        crit=crit,
        fumble=fumble,
        narrative=narrative,
    )


def roll_d66_narrative(skill_name: str, final: int, difficulty: Difficulty) -> str:
    """生成人类可读的判定描述（由 UI 层在渲染 RollResult 时调用）"""
    margin = final - difficulty.value
    if margin >= 5:
        return "大获成功。"
    elif margin >= 0:
        return "险胜。"
    elif margin >= -3:
        return "惜败。"
    else:
        return "彻底失败。"


# ── 叙事文本库 ─────────────────────────────────────────────

def _crit_success_narrative(skill_name: str) -> str:
    pool = {
        "linac_diagnostics": "你精准定位了故障根源，连资深工程师都惊讶不已。",
        "negotiation": "你的话术完美击中对方心理，对方当场松口。",
        "hospital_network": "你利用关系网找到了关键决策人，局面瞬间打开。",
        "crisis_management": "高压之下你反而超常发挥，所有人对你刮目相看。",
        "data_analysis": "你的分析报告让院长眼前一亮，数据自己会说话。",
    }
    return pool.get(skill_name, "这次判定达到了难以置信的结果。")


def _fumble_narrative(skill_name: str) -> str:
    pool = {
        "linac_diagnostics": "你误判了故障原因，方向完全走偏了。",
        "negotiation": "你说错了话，场面陷入尴尬。",
        "hospital_network": "你找错了人，反而引起了对方的警觉。",
        "crisis_management": "压力下你做出冲动决策，情况更糟了。",
        "data_analysis": "你的数据引用有误，被对方当场质疑。",
    }
    return pool.get(skill_name, "最糟糕的情况发生了。")


def _normal_narrative(
    skill_name: str,
    success: bool,
    margin: int,
    difficulty: Difficulty,
) -> str:
    if success:
        if margin >= 5:
            return "干净利落地成功了。"
        else:
            return "勉强成功，但结果是好的。"
    else:
        if margin >= -2:
            return "差一点点就成功了。"
        else:
            return "结果令人失望。"
