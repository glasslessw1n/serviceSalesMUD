#!/usr/bin/env python3
"""
医科达直线加速器售后服务销售 MUD
树状游戏引擎 + 插件式模块

用法:
    python main.py                  # 新游戏
    python main.py --load 存档名    # 读档
    python main.py --list           # 列出现有存档
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from engine import (
    TreeEngine, load_plugins,
    render_scene, render_status, render_logs,
    render_roll_result,
    clear_screen, console,
)

# ── 路径 ──────────────────────────────────────────

BASE_DIR = Path(__file__).parent
PLUGINS_DIR = BASE_DIR / "plugins"
SAVES_DIR = BASE_DIR / "saves"


# ── 存档 ──────────────────────────────────────────

def save_game(engine: TreeEngine, name: str = ""):
    """保存游戏"""
    SAVES_DIR.mkdir(exist_ok=True)
    if not name:
        name = datetime.now().strftime("save_%Y%m%d_%H%M%S")
    path = SAVES_DIR / f"{name}.json"

    data = engine.to_dict()
    # 处理 datetime 序列化
    data["state"]["game_start"] = data["state"]["game_start"].isoformat() \
        if hasattr(data["state"]["game_start"], "isoformat") \
        else data["state"]["game_start"]
    # 处理 sets
    data["state"]["flags"] = list(data["state"]["flags"])
    data["state"]["visited_nodes"] = list(data["state"]["visited_nodes"])
    for npc_data in data["state"]["npcs"].values():
        npc_data["flags"] = list(npc_data.get("flags", []))

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    console.print(f"\n💾 已保存至: {path.name}", style="bold green")
    return path


def load_game(name: str) -> TreeEngine | None:
    """加载存档"""
    path = SAVES_DIR / f"{name}.json"
    if not path.exists():
        # 尝试加上 .json
        path = SAVES_DIR / name
        if not path.exists():
            console.print(f"❌ 存档不存在: {name}", style="bold red")
            return None

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # 恢复 sets
    data["state"]["flags"] = set(data["state"].get("flags", []))
    data["state"]["visited_nodes"] = set(data["state"].get("visited_nodes", []))
    for npc_data in data["state"].get("npcs", {}).values():
        npc_data["flags"] = set(npc_data.get("flags", []))

    return TreeEngine.from_dict(data)


def list_saves():
    """列出存档"""
    if not SAVES_DIR.exists():
        console.print("[dim]暂无存档[/dim]")
        return []

    saves = sorted(SAVES_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    if not saves:
        console.print("[dim]暂无存档[/dim]")
        return []

    console.print("\n📁 存档列表:\n")
    for i, sp in enumerate(saves, 1):
        mtime = datetime.fromtimestamp(sp.stat().st_mtime)
        size = sp.stat().st_size
        console.print(
            f"  [{i}] {sp.stem}  "
            f"[dim]{mtime.strftime('%Y-%m-%d %H:%M')}  "
            f"({size}B)[/dim]"
        )
    return saves


# ── 主循环 ──────────────────────────────────────────

def game_loop(engine: TreeEngine):
    """主游戏循环"""
    roll_result = None  # 本轮要显示的 roll 判定结果

    while True:
        clear_screen()

        node = engine.get_current_node()
        if node is None:
            console.print("[bold red]致命错误：当前节点不存在[/bold red]")
            break

        # 渲染场景（显示上一轮遗留的 roll 结果）
        render_scene(engine, roll_result=roll_result)
        roll_result = None  # 已消费，重置

        available = engine.get_available_choices()

        # 检查是否游戏结束
        if node.id == "__END__":
            console.print("[bold yellow]游戏结束。[/bold yellow]")
            action = _end_menu(engine)
            if action == "restart":
                return "restart"
            elif action == "quit":
                break
            continue

        if not available:
            console.print("[bold red]（无可用选项 — 可能走向了死胡同）[/bold red]")
            action = _end_menu(engine)
            if action == "restart":
                return "restart"
            elif action == "quit":
                break
            continue

        # 状态面板（含技能点）
        render_status(engine.state, engine)

        # 特殊命令提示
        console.print(
            "\n[dim]输入 0=查看状态 | s=存档 | q=退出[/dim]"
        )

        # 获取玩家选择
        try:
            raw_input = input(f"\n请选择 [1-{len(available)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n👋 再见！")
            break

        if raw_input.lower() == "q":
            save_game(engine)
            break

        if raw_input.lower() == "s":
            save_game(engine)
            continue

        if raw_input.lower() == "0":
            clear_screen()
            render_status(engine.state)
            input("\n按 Enter 继续...")
            continue

        if raw_input == "":
            continue

        try:
            choice_idx = int(raw_input)
        except ValueError:
            console.print("[red]请输入数字[/red]")
            input("按 Enter 继续...")
            continue

        if choice_idx < 1 or choice_idx > len(available):
            console.print(f"[red]请输入 1-{len(available)}[/red]")
            input("按 Enter 继续...")
            continue

        # 执行选择
        success, msg, logs = engine.choose(choice_idx - 1)
        if not success:
            console.print(f"[red]{msg}[/red]")
            input("按 Enter 继续...")
            continue

        # 暂存 roll_result，下一轮渲染场景时显示
        roll_result = engine.last_roll_result

        # 显示效果日志
        render_logs(logs)

        if logs:
            input("\n按 Enter 继续...")

    return "quit"


def _end_menu(engine: TreeEngine) -> str:
    """游戏结束/死胡同时的菜单"""
    console.print("\n[R] 重新开始  [Q] 退出  [S] 存档")
    choice = input("> ").strip().lower()
    if choice == "r":
        return "restart"
    elif choice == "s":
        save_game(engine)
        return "quit"
    else:
        return "quit"


# ── 启动 ──────────────────────────────────────────

def main():
    console.print(
        "\n[bold cyan]⚡ 医科达直线加速器售后服务销售 MUD[/bold cyan]",
        "\n[dim]树状游戏引擎 v0.1 | 插件式模块[/dim]\n",
    )

    # 解析参数
    if "--list" in sys.argv:
        list_saves()
        return

    engine = TreeEngine()

    if "--load" in sys.argv:
        idx = sys.argv.index("--load")
        if idx + 1 < len(sys.argv):
            save_name = sys.argv[idx + 1]
            loaded = load_game(save_name)
            if loaded is None:
                return
            engine = loaded
            console.print(f"\n📂 读档: {save_name}\n")
        else:
            saves = list_saves()
            if not saves:
                return
            # 交互式选择
            try:
                choice = int(input("选择存档编号: ").strip())
                if 1 <= choice <= len(saves):
                    loaded = load_game(saves[choice - 1].name)
                    if loaded:
                        engine = loaded
                        console.print(f"\n📂 读档: {saves[choice - 1].name}\n")
                    else:
                        return
            except ValueError:
                console.print("[red]无效选择[/red]")
                return
    else:
        # 新游戏
        logs = load_plugins(engine, PLUGINS_DIR, root_node_id="start")
        console.print("\n".join(f"  {log}" for log in logs))
        console.print("\n[bold green]🎮 新游戏开始！[/bold green]\n")
        input("按 Enter 开始...")

    while True:
        result = game_loop(engine)
        if result == "restart":
            engine = TreeEngine()
            logs = load_plugins(engine, PLUGINS_DIR, root_node_id="start")
            console.print("\n".join(f"  {log}" for log in logs))
            console.print("\n[bold green]🔄 重新开始！[/bold green]\n")
            input("按 Enter 开始...")
            continue
        break

    console.print("\n[bold cyan]感谢试玩！[/bold cyan]\n")


if __name__ == "__main__":
    main()
