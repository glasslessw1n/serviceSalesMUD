"""Rich 终端 UI —— 渲染当前场景、选项、状态面板。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED, DOUBLE
from rich.rule import Rule

if TYPE_CHECKING:
    from .tree import TreeEngine, Choice
    from .state import GameState


console = Console()


# ── 颜色常量（暗色主题）─────────────────────────────────────────

C_TITLE   = "bold cyan"
C_SPEAKER = "bold yellow"
C_TEXT    = "white"
C_CHOICE  = "bold green"
C_CHOICE_HL = "bold bright_green"
C_CHOICE_DISABLED = "dim red"
C_CHOICE_ROLL  = "bold bright_magenta"
C_RECOMMEND    = "bold bright_yellow"
C_ATTR    = "magenta"
C_NPC     = "blue"
C_TAG     = "dim yellow"
C_LOG     = "dim green"
C_WARN    = "bold red"
C_SUCCESS = "bold bright_green"
C_FAIL    = "bold red"
C_INFO    = "cyan"
C_DIVIDER = "cyan"
C_SKILL_PTS = "bold bright_red"
C_SKILL_BAR = "bright_blue"


# ── 渲染函数 ──────────────────────────────────────────

def render_roll_result(result, live_display: bool = True) -> bool:
    """
    渲染一次 roll 判定结果。
    返回 True 如果成功，返回 False 如果失败。
    """
    if result is None:
        return True

    success = result.success
    icon = "✅" if success else "❌"
    label = result.narrative or result.skill_name or "判定"
    dc_val = result.difficulty.value
    roll_str = f"🎲 {result.roll} = {result.final}"
    dc_str = f"DC {dc_val}"

    skill_str = f" [{result.skill_name}]" if result.skill_name else ""
    margin_str = f" (±{result.margin:+d})" if result.margin != 0 else ""

    verdict = "成功" if success else "失败"
    verdict_color = C_SUCCESS if success else C_FAIL

    panel = Panel(
        Text.assemble(
            (f"{icon} {label}", verdict_color),
            (f"{skill_str}{margin_str}\n", C_INFO),
            (f"{roll_str}  vs  {dc_str}\n", "white"),
            (f"→ {verdict}", verdict_color),
            (f"  {'⭐ 大成功！' if result.crit else '💀 大失败…' if result.fumble else ''}", "bold yellow"),
        ),
        title="🎲 技能判定",
        border_style=verdict_color,
        box=ROUNDED,
        padding=(1, 2),
        width=52,
    )
    console.print(panel)
    return success


def render_scene(engine: TreeEngine, roll_result=None):
    """渲染当前游戏场景

    Args:
        engine: 引擎实例
        roll_result: 要显示的 roll 结果（从外部传入，不从 engine 读）
    """
    node = engine.get_current_node()
    if node is None:
        console.print(Panel("⚠ 当前节点不存在", style=C_WARN))
        return

    # ── 分隔线 ──
    console.print(Rule(title=f" {node.title} ", style=C_DIVIDER, characters="─"))

    # ── 说话人 + 标签 ──
    if node.speaker:
        console.print(f"  🗣  [ {node.speaker} ]", style=C_SPEAKER)

    tag_str = "  ".join(f"[{t}]" for t in node.tags) if node.tags else ""
    if tag_str:
        console.print(f"  {tag_str}", style=C_TAG)

    # ── 正文 ──
    body = Text(node.text.strip(), style=C_TEXT)
    console.print(Panel(body, border_style="cyan", box=ROUNDED, padding=(1, 2)))

    # ── Roll 结果（节点级） ──
    if roll_result is not None:
        render_roll_result(roll_result)

    # ── 选项列表 ──
    available = engine.get_available_choices()
    all_choices = node.choices

    if not available and all_choices:
        # 所有选项都被条件禁用 → 游戏死胡同
        console.print()
        console.print("[bold red]⚠ 所有选项均未满足条件，走向了死胡同。[/bold red]")
        return

    if not available:
        console.print("[dim]（无可用选项）[/dim]")
        return

    console.print()

    # 可用选项
    for i, choice in enumerate(available, 1):
        tags = choice.tags or []
        is_roll = "roll_success_node" in tags or any(t.startswith("roll:") for t in tags)
        is_recommended = "推荐" in tags

        tag_parts = []
        if is_roll:
            tag_parts.append("[bold magenta]🎲[/bold magenta]")
        if is_recommended:
            tag_parts.append("[bold yellow]⭐ 推荐[/bold yellow]")
        tag_hint = "  ".join(tag_parts)

        # 选项文字
        if is_recommended and not is_roll:
            choice_text = f"✨ {choice.text}"
            text_style = C_RECOMMEND
        elif is_roll:
            choice_text = f"🎯 {choice.text}"
            text_style = C_CHOICE_ROLL
        else:
            choice_text = choice.text
            text_style = C_CHOICE

        if tag_hint:
            console.print(f"  [bold cyan][{i}][/bold cyan]  {choice_text}  {tag_hint}")
        else:
            console.print(f"  [bold cyan][{i}][/bold cyan]  {choice_text}")

    # 已禁用选项
    disabled = [c for c in all_choices if c not in available]
    if disabled:
        console.print()
        console.print("[dim]─ 以下选项条件不足 ─[/dim]")
        for c in disabled:
            console.print(f"  [dim]✗ {c.text}[/dim]")

    console.print()


def render_status(state: GameState, engine=None):
    """渲染状态面板（左侧/顶部小面板）"""
    # ── 属性 ──
    attr_lines = []
    for a, v in [
        ("技术能力", state.get_attr("技术能力")),
        ("关系值",   state.get_attr("关系值")),
        ("商务敏感", state.get_attr("商务敏感度")),
        ("声望",     state.get_attr("声望")),
        ("资金",     state.get_attr("资金")),
    ]:
        bar = _bar(v, width=14)
        attr_lines.append(f"  {a:<8} {bar} [cyan]{v:>3}[/cyan]")
    attr_text = "\n".join(attr_lines)

    # ── 技能系统 ──
    skill_lines = []
    if engine and engine.state._skill_system:
        ss = engine.state._skill_system
        skill_lines.append(f"  技能点: [bold red]{ss.skill_points}[/bold red]")
        for sid, sl in ss.skills.items():
            bar = _bar(sl.exp / max(sl.level * 100, 1), width=10)
            skill_lines.append(f"  {sid:<20} Lv.{sl.level} {bar}")
    skill_text = "\n".join(skill_lines) if skill_lines else "  [dim]暂无[/dim]"

    # ── NPC ──
    npc_lines = []
    if state.npcs:
        for name, ns in list(state.npcs.items())[:5]:
            rel = ns.relationship
            trust = ns.trust
            npc_lines.append(
                f"  [{C_NPC}]{name}[/{C_NPC}] "
                f"[dim]关系[/dim][cyan]{rel}[/cyan] "
                f"[dim]信任[/dim][cyan]{trust}[/cyan]"
            )
    npc_text = "\n".join(npc_lines) if npc_lines else "  [dim]暂无[/dim]"

    # ── 标记（取前6个） ──
    flags = sorted(state.flags)
    flag_preview = ", ".join(flags[:6])
    if len(flags) > 6:
        flag_preview += f" … (+{len(flags)-6})"

    # ── 时间 ──
    time_str = f"[bold]⏰ Day {state.day}, {state.hour:02d}:00[/bold]"
    if engine and engine.state._skill_system:
        sp = engine.state._skill_system.skill_points
        if sp > 0:
            time_str += f"    [bold red]✨ {sp}[/bold red]"

    content = Text.assemble(
        f"{time_str}\n\n",
        "[bold white]── 属性 ──[/bold white]\n",
        Text(attr_text),
        "\n\n[bold white]── 技能 ──[/bold white]\n",
        Text(skill_text),
        "\n\n[bold white]── NPC 关系 ──[/bold white]\n",
        Text(npc_text),
        "\n\n[bold white]── 标记 ──[/bold white]\n",
        Text(f"  {flag_preview}") if flag_preview else Text("  [dim]无[/dim]"),
    )

    console.print(Panel(
        content,
        title="📊 状态面板",
        border_style="blue",
        box=DOUBLE,
        width=52,
    ))


def render_logs(logs: list[str]):
    """渲染效果日志"""
    if not logs:
        return
    console.print()
    for log in logs:
        console.print(f"  {C_LOG}▸ {log}{C_LOG}")
    console.print()


def _bar(value: int, width: int = 10) -> str:
    """简单进度条（基于 0-100）"""
    value = max(0, min(100, value))
    filled = int(value / 100 * width)
    return f"[cyan]{'█' * filled}[/cyan][dim]{'░' * (width - filled)}[/dim]"


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
