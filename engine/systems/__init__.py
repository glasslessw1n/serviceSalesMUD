"""引擎子系统——技能、判定、随机事件、快照回滚。"""

from .skills import SkillSystem, check_skill
from .combat import RollResult, roll_against_difficulty, Difficulty
from .random_events import RandomEventEngine, trigger_time_based_events, RandomEvent
from .snapshot import SnapshotEngine, take_snapshot, rollback_to

__all__ = [
    "SkillSystem", "check_skill",
    "RollResult", "roll_against_difficulty", "Difficulty",
    "RandomEventEngine", "trigger_time_based_events", "RandomEvent",
    "SnapshotEngine", "take_snapshot", "rollback_to",
]
