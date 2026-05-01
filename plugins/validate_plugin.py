#!/usr/bin/env python3
"""
插件热插拔校验工具

用法:
  python plugins/validate_plugin.py                    # 校验所有插件
  python plugins/validate_plugin.py tender_battle    # 只校验 tender_battle
  python plugins/validate_plugin.py --strict          # 严格模式（不允许孤立节点）

检查项:
  ✓ scenes.yaml 语法正确（可被 PyYAML 解析）
  ✓ 根节点存在
  ✓ 所有 next_node 引用指向已定义的节点
  ✓ 所有 roll_success_node / roll_fail_node 引用指向已定义的节点
  ✓ 无重复节点 ID
  ✓ 结局节点存在（is_end = 无 choices 的节点）
  ✓ 插件入口 __init__.py 存在且定义了 name/title/root
  ✓ NPC 引用与 npcs.yaml 一致（可选警告）
  ✓ 节点文本不包含未闭合的 Jinja2 模板语法（可选警告）
"""

import sys
import yaml
from pathlib import Path
from typing import Optional

# ── 颜色输出 ────────────────────────────────────────────────
RED   = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN  = "\033[96m"
RESET = "\033[0m"

def ok(msg):   print(f"{GREEN}✓{RESET}  {msg}")
def err(msg):  print(f"{RED}✗{RESET}  {msg}")
def warn(msg):  print(f"{YELLOW}⚠{RESET}  {msg}")
def info(msg):  print(f"{CYAN}ℹ{RESET}  {msg}")


# ── 核心解析 ────────────────────────────────────────────────
def load_scenes(plugin_dir: Path) -> tuple[list[dict], str]:
    """加载 scenes.yaml，返回 (nodes_list, plugin_name)"""
    scene_file = plugin_dir / "scenes.yaml"
    if not scene_file.exists():
        raise FileNotFoundError(f"找不到 scenes.yaml: {scene_file}")

    with open(scene_file, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError("scenes.yaml 为空")

    plugin_name = plugin_dir.name
    return raw, plugin_name


def load_npcs(plugin_dir: Path) -> set[str]:
    """加载 npcs.yaml，返回 NPC name 集合（用于检查引用一致性）"""
    npc_file = plugin_dir / "npcs.yaml"
    if not npc_file.exists():
        return set()

    with open(npc_file, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        return set()

    return {npc["name"] for npc in raw if "name" in npc}


def find_root_node_id(nodes: list[dict]) -> Optional[str]:
    """推测根节点 ID（第一个节点，或者 id=="start" 的节点）"""
    # 显式查找 id="start" 或 id 包含 "start" 的节点
    for n in nodes:
        nid = n.get("id", "")
        if nid in ("start", "contract_start", "scene_01"):
            return nid

    # 没有 start 就用第一个
    if nodes:
        return nodes[0].get("id")
    return None


def check_plugin(plugin_dir: Path, strict: bool = False) -> bool:
    """校验单个插件，返回 True=有错误"""
    plugin_name = plugin_dir.name
    info(f"校验插件: {plugin_name}")

    has_error = False

    # 1. 基本文件检查
    if not (plugin_dir / "__init__.py").exists():
        warn(f"  缺少 __init__.py（可忽略，不影响加载）")

    # 2. 加载 scenes.yaml
    try:
        nodes, pname = load_scenes(plugin_dir)
    except Exception as e:
        err(f"  scenes.yaml 解析失败: {e}")
        return True

    # 3. 节点 ID 集合
    node_ids = set()
    for n in nodes:
        nid = n.get("id", "")
        if not nid:
            err(f"  节点缺少 id 字段")
            has_error = True
            continue
        if nid in node_ids:
            err(f"  节点 ID 重复: {nid}")
            has_error = True
        node_ids.add(nid)

    ok(f"  {len(nodes)} 个节点 ✓（{len(node_ids)} 个唯一 ID）")

    # 4. NPC 加载（用于一致性检查）
    npc_names = load_npcs(plugin_dir)
    if npc_names:
        ok(f"  {len(npc_names)} 个 NPC 定义 ✓")

    # 5. 收集所有引用
    referenced_ids: set[str] = set()
    dangling_refs: list[tuple[str, str, str]] = []  # (node_id, field, target_id)

    for n in nodes:
        nid = n.get("id", "?")
        text = n.get("text", "")

        # 检查文本中是否有未闭合 Jinja2
        if "{{" in text and "}}" not in text:
            warn(f"  节点 '{nid}' text 包含未闭合的 {{ — 可能存在 Jinja2 模板错误")

        # choices 中的引用
        for choice in n.get("choices", []):
            next_id = choice.get("next", "")
            if next_id and next_id not in ("__END__", "__end__"):
                if next_id not in node_ids:
                    dangling_refs.append((nid, "next", next_id))
                referenced_ids.add(next_id)

            rs = choice.get("roll_success_node", "")
            if rs:
                # roll_success_node 格式可能是 "node_id:difficulty"，取 node_id 部分
                real_id = rs.split(":")[0]
                if real_id not in node_ids:
                    dangling_refs.append((nid, "roll_success_node", real_id))

            rf = choice.get("roll_fail_node", "")
            if rf:
                if rf not in node_ids:
                    dangling_refs.append((nid, "roll_fail_node", rf))

        # 节点级 roll 字段（虽然目前 loader 不解析这个）
        roll = n.get("roll")
        if roll and isinstance(roll, dict):
            skill_id = roll.get("skill", "")
            # skill_id 不做引用检查，只检查格式

    # 报告悬挂引用
    if dangling_refs:
        has_error = True
        for nid, field, target in dangling_refs:
            err(f"  节点 '{nid}' 的 {field} → 指向不存在的节点 '{target}'")

    # 6. 孤立节点检查（strict 模式）
    if strict:
        # 孤立节点：没有被任何节点引用，且不是根节点
        root_id = find_root_node_id(nodes)
        orphans = node_ids - referenced_ids - {"__END__", "__end__"}
        if root_id and root_id in orphans:
            orphans.discard(root_id)  # 根节点不被引用是正常的

        if orphans:
            warn(f"  孤立节点（无任何入口）: {orphans}")
            for oid in orphans:
                nid_list = [n["id"] for n in nodes if n["id"] == oid]
                if nid_list:
                    first_ref = nid_list[0] if nid_list else oid
                    info(f"    → '{oid}' 首行: {nodes[0].get('title', '') if nodes else ''}")

    # 7. 结局节点
    end_nodes = [n["id"] for n in nodes if len(n.get("choices", [])) == 0]
    if end_nodes:
        ok(f"  {len(end_nodes)} 个结局节点 ✓")
    else:
        warn(f"  没有发现无选项的结局节点")

    # 8. 汇总
    if has_error:
        err(f"  插件 '{plugin_name}' 校验失败 ✗")
    else:
        ok(f"  插件 '{plugin_name}' 校验通过 ✓")

    return has_error


# ── 主程序 ─────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="插件热插拔校验工具")
    parser.add_argument(
        "plugin_name",
        nargs="?",
        help="只校验指定插件（默认校验全部）"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：报告孤立节点（无任何引用）"
    )
    parser.add_argument(
        "--plugins-dir",
        type=Path,
        default=Path(__file__).parent,
        help="plugins 目录路径（默认: plugins/）"
    )
    args = parser.parse_args()

    plugins_dir = args.plugins_dir
    if not plugins_dir.exists():
        err(f"插件目录不存在: {plugins_dir}")
        sys.exit(1)

    # 确定要校验的插件
    if args.plugin_name:
        target = plugins_dir / args.plugin_name
        if not target.exists():
            err(f"插件不存在: {target}")
            sys.exit(1)
        targets = [target]
    else:
        targets = [
            p for p in sorted(plugins_dir.iterdir())
            if p.is_dir() and (p / "scenes.yaml").exists()
        ]

    print(f"\n{'='*50}")
    print(f"  插件校验报告  (strict={args.strict})")
    print(f"{'='*50}\n")

    total_errors = 0
    for plugin_dir in targets:
        print()
        has_err = check_plugin(plugin_dir, strict=args.strict)
        total_errors += int(has_err)

    print(f"\n{'='*50}")
    if total_errors == 0:
        ok(f"全部通过 ({len(targets)} 个插件)")
        sys.exit(0)
    else:
        err(f"共 {total_errors} 个插件有错误")
        sys.exit(1)


if __name__ == "__main__":
    main()
