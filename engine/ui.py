"""Rich 终端 UI —— 渲染当前场景、选项、状态面板。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED

if TYPE_CHECKING:
    from .tree import TreeEngine, Choice
    from .state import GameState


console = Console()


# ── 颜色常量 ──────────────────────────────────────────

COLOR_TITLE = "bold cyan"
COLOR_SPEAKER = "bold yellow"
COLOR_TEXT = "white"
COLOR_CHOICE = "bold green"
COLOR_CHOICE_DISABLED = "dim red"
COLOR_ATTR = "magenta"
COLOR_NPC = "blue"
COLOR_TAG = "dim yellow"
COLOR_LOG = "dim green"
COLOR_WARNING = "bold red"


# ── 渲染函数 ──────────────────────────────────────────

def render_scene(engine: TreeEngine):
    """渲染当前游戏场景"""
    node = engine.get_current_node()
    if node is None:
        console.print(Panel("⚠ 当前节点不存在", style=COLOR_WARNING))
        return

    # 标题栏
    tag_str = " ".join(f"[{t}]" for t in node.tags) if node.tags else ""
    header = Text()
    if node.title:
        header.append(f"📌 {node.title}", style=COLOR_TITLE)
    if tag_str:
        header.append(f"  {tag_str}", style=COLOR_TAG)
    if node.speaker:
        header.append(f"\n🗣 {node.speaker}", style=COLOR_SPEAKER)

    # 叙述文本
    body = Text(node.text.strip(), style=COLOR_TEXT)

    console.print(Panel(
        body,
        title=header,
        border_style="cyan",
        box=ROUNDED,
        padding=(1, 2),
    ))

    # 选项列表
    console.print()
    available = engine.get_available_choices()

    if not available:
        console.print("[bold red]（无可用选项 — 游戏结束）[/bold red]")
        return

    for i, choice in enumerate(available, 1):
        tag_hint = ""
        if choice.tags:
            tag_hint = f" [dim]{' '.join(f'[{t}]' for t in choice.tags)}[/dim]"

        # 标注有条件限制的选项
        cond_hint = ""
        if choice.conditions:
            cond_hint = " [dim italic](条件)[/dim italic]"

        console.print(
            f"  {COLOR_CHOICE}[{i}]{COLOR_CHOICE} {choice.text}{tag_hint}{cond_hint}"
        )

    # 已禁用选项（不满足条件）
    all_choices = node.choices
    disabled = [c for c in all_choices if c not in available]
    if disabled:
        console.print()
        for c in disabled:
            console.print(
                f"  {COLOR_CHOICE_DISABLED}[✗] {c.text} (条件不足){COLOR_CHOICE_DISABLED}"
            )

    console.print()


def render_status(state: GameState):
    """渲染状态面板"""
    # 属性表 — 用简单文本，不用 Rich Table（避免 f-string 嵌入问题）
    from .state import Attr
    attr_order = [Attr.TECH, Attr.RELATION, Attr.BUSINESS, Attr.REPUTATION, Attr.FUNDS]
    attr_lines = []
    for a in attr_order:
        v = state.get_attr(a)
        bar = _bar(v)
        attr_lines.append(f"  {a:<8} {bar} {v:>3}")
    attr_text = "\n".join(attr_lines)

    # NPC 面板
    npc_lines = []
    if state.npcs:
        for name, ns in state.npcs.items():
            rel_bar = _bar(ns.relationship, width=8)
            trust_bar = _bar(ns.trust, width=8)
            npc_lines.append(
                f"[{COLOR_NPC}]{ns.role}[/{COLOR_NPC}] {name}  "
                f"关系{rel_bar} {ns.relationship}  "
                f"信任{trust_bar} {ns.trust}"
            )
    npc_text = "\n".join(npc_lines) if npc_lines else "[dim]暂无 NPC[/dim]"

    # 物品
    item_lines = []
    if state.items:
        for item in state.items:
            if item.quantity > 0:
                item_lines.append(f"  📦 {item.name} ×{item.quantity}")
    item_text = "\n".join(item_lines) if item_lines else "[dim]空[/dim]"

    # 标记
    flag_text = ", ".join(sorted(state.flags)) if state.flags else "[dim]无[/dim]"

    console.print(Panel(
        f"[bold]⏰ Day {state.day}, {state.hour:02d}:00[/bold]\n\n"
        f"{attr_text}\n\n"
        f"[bold]👥 NPC 关系[/bold]\n{npc_text}\n\n"
        f"[bold]🎒 物品[/bold]\n{item_text}\n\n"
        f"[bold]🏷 标记[/bold]\n{flag_text}",
        title="📊 状态面板",
        border_style="blue",
        box=ROUNDED,
        width=50,
    ))


def render_logs(logs: list[str]):
    """渲染效果日志"""
    if not logs:
        return
    console.print()
    for log in logs:
        console.print(f"  {COLOR_LOG}▸ {log}{COLOR_LOG}")
    console.print()


def _bar(value: int, width: int = 10) -> str:
    """简单进度条"""
    filled = int(value / 100 * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


def clear_screen():
    """清屏"""
    console.clear()


def prompt_choice(max_n: int) -> int:
    """提示玩家选择，返回 1-based 索引"""
    from rich.prompt import IntPrompt
    return IntPrompt.ask(
        f"请选择 [1-{max_n}]",
        choices=[str(i) for i in range(1, max_n + 1)],
        show_choices=False,
    )
