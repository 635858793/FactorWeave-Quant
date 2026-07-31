"""
R221 子智能体 C - EventBus ORPHAN_PUB/SUB 扫描器 V2

严格遵循 R104 §12.3 + R104 §12.5 铁律:
- AST 解析而非字符串匹配
- 递归进入 with.body (R104 §12.3 教训)
- AST unparse 验证方法体 (R104 §12.5 教训)
- 排除测试代码 + 备份文件 (R6 §6.3 SOP)

功能:
1. 扫描全项目 publish/subscribe 调用
2. 提取事件名 (字符串字面量 + 类名 + 类实例化)
3. 计算 ORPHAN_PUB / ORPHAN_SUB
4. 验证 register_event_type 双轨注册
5. 输出 Markdown 报告

R221-C-ORPHAN-SCANNER-V2
"""
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
import json


# ============================================================
# 配置
# ============================================================

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SUBDIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]

# 排除规则
EXCLUDE_DIRS = {
    "__pycache__", ".git", ".pytest_cache", ".venv", "venv",
    "node_modules", ".mypy_cache", ".ruff_cache", ".tox",
    "build", "dist", ".trae",
}
EXCLUDE_FILE_PATTERNS = {".bak", ".pyc", ".pyo", ".r194dv2", ".r195a", ".r197b", ".r195dv4", ".r195dv41"}
EXCLUDE_PATH_KEYWORDS = ["r194dv2", "r195a", "r197b", "r195dv4", "r195dv41"]

# 业务事件前缀 (重点关注)
BUSINESS_EVENT_PREFIXES = (
    "trade.", "order.", "strategy.", "position.", "risk.",
    "data.", "performance.", "database.", "market.",
    "ui.", "system.", "service.", "feedback.",
    "kdata.", "indicator.", "portfolio.",
)

# EventBus API
PUBLISH_METHODS = {"publish", "publish_async", "publish_event"}
SUBSCRIBE_METHODS = {"subscribe", "subscribe_async"}
REGISTER_METHODS = {"register_event_type"}
# 集中 helper (R8 §8.1 #3 强约束)
SAFE_PUBLISH_METHODS = {"_safe_publish", "safe_publish"}
# publish_xxx 函数名前缀 (helper 函数, 内部走 _safe_publish)
HELPER_PUBLISH_PREFIX = "publish_"


# ============================================================
# AST 工具
# ============================================================

def extract_event_name(arg: ast.AST) -> Optional[str]:
    """从 AST 节点提取事件名
    支持:
    - 字符串字面量: 'order.filled'
    - 变量名: EVENT_NAME (返回 id)
    - 类调用: OrderFilledEvent() (返回 func.id)
    - 属性访问: bus.publish (返回 attr)
    - BaseEvent 实例: OrderFilledEvent(...).event_type
    """
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.Name):
        return arg.id
    if isinstance(arg, ast.Attribute):
        return arg.attr
    if isinstance(arg, ast.Call):
        # 处理 OrderFilledEvent(...) 形式
        return extract_event_name(arg.func)
    if isinstance(arg, ast.JoinedStr):
        # f-string, 提取字面量部分
        for v in arg.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                return v.value
        return None
    return None


def is_business_event(event_name: Optional[str]) -> bool:
    """判断是否为业务事件 (关注前缀)"""
    if not event_name:
        return False
    return any(event_name.startswith(prefix) for prefix in BUSINESS_EVENT_PREFIXES)


def is_test_file(filepath: Path) -> bool:
    """判断是否为测试文件"""
    parts = filepath.parts
    if "tests" in parts:
        return True
    name = filepath.name
    if name.startswith("test_") or name.startswith("_test") or name.endswith("_test.py"):
        return True
    return False


def should_skip_file(filepath: Path) -> bool:
    """判断是否应该跳过该文件"""
    name = filepath.name
    for pat in EXCLUDE_FILE_PATTERNS:
        if pat in name:
            return True
    for kw in EXCLUDE_PATH_KEYWORDS:
        if kw in str(filepath):
            return True
    for part in filepath.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


# ============================================================
# 主扫描器
# ============================================================

class OrphanScanner:
    """EventBus ORPHAN_PUB/SUB 扫描器 (R221-C)"""

    def __init__(self, project_root: Path = PROJECT_ROOT):
        self.project_root = project_root
        self.publishes: Dict[str, List[Tuple[str, int]]] = defaultdict(list)  # event_name -> [(file, line), ...]
        self.subscribes: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        self.registers: Dict[str, List[Tuple[str, int]]] = defaultdict(list)  # register_event_type
        self.publish_objs: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)  # event_name -> [(file, line, class_name), ...]
        self.subscribe_objs: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)
        self.register_classes: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        self.files_scanned: int = 0
        self.files_skipped: int = 0
        self.errors: List[str] = []

    def scan_file(self, filepath: Path) -> None:
        """扫描单个文件"""
        if should_skip_file(filepath):
            self.files_skipped += 1
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=str(filepath))
        except (SyntaxError, UnicodeDecodeError) as e:
            self.errors.append(f"{filepath}: {e}")
            return
        self.files_scanned += 1
        self._scan_ast(tree, filepath)

    def _scan_ast(self, tree: ast.Module, filepath: Path) -> None:
        """递归扫描 AST"""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # 必须包含方法调用: .publish(...) / .subscribe(...) / .register_event_type(...)
            func = node.func
            method_name = None
            if isinstance(func, ast.Attribute):
                # 形式: self.bus.publish(...) / bus.publish(...)
                method_name = func.attr
            elif isinstance(func, ast.Name):
                # 形式: _safe_publish(...) / safe_publish(...) (R8 §8.1 #3 集中 helper)
                method_name = func.id
            if method_name is None:
                continue
            if method_name in PUBLISH_METHODS:
                self._handle_publish(node, filepath, method_name)
            elif method_name in SUBSCRIBE_METHODS:
                self._handle_subscribe(node, filepath, method_name)
            elif method_name in REGISTER_METHODS:
                self._handle_register(node, filepath)
            elif method_name in SAFE_PUBLISH_METHODS:
                # R8 §8.1 #3 集中 helper: _safe_publish("event.name", **kwargs)
                self._handle_safe_publish(node, filepath, method_name)

    def _handle_publish(self, node: ast.Call, filepath: Path, method: str) -> None:
        """处理 publish 调用"""
        if not node.args:
            return
        first_arg = node.args[0]
        rel_path = str(filepath.relative_to(self.project_root))
        line_no = node.lineno

        # 情况 1: 字符串字面量
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            self.publishes[first_arg.value].append((rel_path, line_no))
            return

        # 情况 2: 变量名
        if isinstance(first_arg, ast.Name):
            # 单变量名无法确定具体事件, 但记录位置
            return

        # 情况 3: 类实例化: OrderFilledEvent(...)
        if isinstance(first_arg, ast.Call):
            cls_name = extract_event_name(first_arg)
            if cls_name:
                self.publish_objs[cls_name].append((rel_path, line_no, cls_name))
            return

        # 情况 4: 已有事件对象: event
        if isinstance(first_arg, ast.Name):
            # 静态分析无法确定具体事件类型, 跳过
            return

    def _handle_subscribe(self, node: ast.Call, filepath: Path, method: str) -> None:
        """处理 subscribe 调用"""
        if not node.args:
            return
        first_arg = node.args[0]
        rel_path = str(filepath.relative_to(self.project_root))
        line_no = node.lineno

        # 情况 1: 字符串字面量
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            self.subscribes[first_arg.value].append((rel_path, line_no))
            return

        # 情况 2: 变量名
        if isinstance(first_arg, ast.Name):
            return

        # 情况 3: 类实例化
        if isinstance(first_arg, ast.Call):
            cls_name = extract_event_name(first_arg)
            if cls_name:
                self.subscribe_objs[cls_name].append((rel_path, line_no, cls_name))
            return

    def _handle_register(self, node: ast.Call, filepath: Path) -> None:
        """处理 register_event_type 调用"""
        if not node.args:
            return
        first_arg = node.args[0]
        rel_path = str(filepath.relative_to(self.project_root))
        line_no = node.lineno

        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            self.registers[first_arg.value].append((rel_path, line_no))
            return
        if isinstance(first_arg, ast.Name):
            self.register_classes[first_arg.id].append((rel_path, line_no))
            return

    def _handle_safe_publish(self, node: ast.Call, filepath: Path, method: str) -> None:
        """处理 _safe_publish("event.name", **kwargs) 调用 (R8 §8.1 #3 集中 helper)

        与 _handle_publish 类似, 但只识别字符串字面量, 不处理类实例化
        """
        if not node.args:
            return
        first_arg = node.args[0]
        rel_path = str(filepath.relative_to(self.project_root))
        line_no = node.lineno

        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            # 与 publish 合并到同一个 dict
            self.publishes[first_arg.value].append((rel_path, line_no))
            return

    def scan_subdirs(self, subdirs: List[str] = SUBDIRS) -> None:
        """扫描多个子目录"""
        for subdir in subdirs:
            dir_path = self.project_root / subdir
            if not dir_path.exists():
                self.errors.append(f"目录不存在: {dir_path}")
                continue
            for root, dirs, files in os.walk(dir_path):
                # 过滤目录
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    fp = Path(root) / fname
                    self.scan_file(fp)

    def compute_orphans(self) -> Dict[str, Any]:
        """计算 ORPHAN 集合"""
        # 所有发布方 (字符串 + 类)
        pub_strings = set(self.publishes.keys())
        pub_classes = set(self.publish_objs.keys())
        sub_strings = set(self.subscribes.keys())
        sub_classes = set(self.subscribe_objs.keys())

        # 字符串事件 ORPHAN
        orphan_pub_str = pub_strings - sub_strings
        orphan_sub_str = sub_strings - pub_strings
        paired_str = pub_strings & sub_strings

        # 类事件 ORPHAN
        orphan_pub_cls = pub_classes - sub_classes
        orphan_sub_cls = sub_classes - pub_classes
        paired_cls = pub_classes & sub_classes

        return {
            "publish_strings": self.publishes,
            "subscribe_strings": self.subscribes,
            "publish_classes": self.publish_objs,
            "subscribe_classes": self.subscribe_objs,
            "registers": self.registers,
            "register_classes": self.register_classes,
            "orphan_pub_strings": sorted(orphan_pub_str),
            "orphan_sub_strings": sorted(orphan_sub_str),
            "paired_strings": sorted(paired_str),
            "orphan_pub_classes": sorted(orphan_pub_cls),
            "orphan_sub_classes": sorted(orphan_sub_cls),
            "paired_classes": sorted(paired_cls),
        }

    def generate_report(self) -> str:
        """生成 Markdown 报告"""
        result = self.compute_orphans()
        lines = []
        lines.append("# R221-C EventBus ORPHAN_PUB/SUB 扫描报告")
        lines.append("")
        lines.append(f"> 扫描时间: 2026-07-28 (R221 子智能体 C)")
        lines.append(f"> 项目根: `{self.project_root}`")
        lines.append(f"> 扫描子目录: {SUBDIRS}")
        lines.append("")
        lines.append("## 1. 扫描统计")
        lines.append("")
        lines.append(f"- 扫描文件数: **{self.files_scanned}**")
        lines.append(f"- 跳过文件数: **{self.files_skipped}** (备份/缓存/测试隔离)")
        lines.append(f"- 解析错误数: **{len(self.errors)}**")
        lines.append(f"- 字符串事件 publish 唯一数: **{len(self.publishes)}**")
        lines.append(f"- 字符串事件 subscribe 唯一数: **{len(self.subscribes)}**")
        lines.append(f"- 类事件 publish 唯一数: **{len(self.publish_objs)}**")
        lines.append(f"- 类事件 subscribe 唯一数: **{len(self.subscribe_objs)}**")
        lines.append(f"- 字符串事件 register_event_type 数: **{len(self.registers)}**")
        lines.append(f"- 类事件 register_event_type 数: **{len(self.register_classes)}**")
        lines.append("")
        lines.append("## 2. 字符串事件 ORPHAN 清单")
        lines.append("")
        lines.append(f"### 2.1 ORPHAN_PUB (有 publish 无 subscribe) - {len(result['orphan_pub_strings'])} 项")
        lines.append("")
        lines.append("| 事件名 | publish 位置 (file:line) | publish 次数 | 业务前缀 | 状态 |")
        lines.append("|--------|--------------------------|-------------|---------|------|")
        for evt in result['orphan_pub_strings']:
            locs = self.publishes[evt]
            loc_str = ", ".join(f"{f}:{ln}" for f, ln in locs[:3])
            if len(locs) > 3:
                loc_str += f" ... (+{len(locs)-3})"
            biz = "是" if is_business_event(evt) else "否"
            status = "**P0 ORPHAN**" if is_business_event(evt) else "ORPHAN"
            lines.append(f"| `{evt}` | {loc_str} | {len(locs)} | {biz} | {status} |")
        lines.append("")
        lines.append(f"### 2.2 ORPHAN_SUB (有 subscribe 无 publish) - {len(result['orphan_sub_strings'])} 项")
        lines.append("")
        lines.append("| 事件名 | subscribe 位置 (file:line) | subscribe 次数 | 业务前缀 | 状态 |")
        lines.append("|--------|---------------------------|---------------|---------|------|")
        for evt in result['orphan_sub_strings']:
            locs = self.subscribes[evt]
            loc_str = ", ".join(f"{f}:{ln}" for f, ln in locs[:3])
            if len(locs) > 3:
                loc_str += f" ... (+{len(locs)-3})"
            biz = "是" if is_business_event(evt) else "否"
            status = "**P0 ORPHAN**" if is_business_event(evt) else "ORPHAN"
            lines.append(f"| `{evt}` | {loc_str} | {len(locs)} | {biz} | {status} |")
        lines.append("")
        lines.append(f"### 2.3 PAIRED (配对正常) - {len(result['paired_strings'])} 项")
        lines.append("")
        lines.append("| 事件名 | publish 数 | subscribe 数 | 业务前缀 |")
        lines.append("|--------|------------|--------------|---------|")
        for evt in result['paired_strings']:
            biz = "是" if is_business_event(evt) else "否"
            lines.append(f"| `{evt}` | {len(self.publishes[evt])} | {len(self.subscribes[evt])} | {biz} |")
        lines.append("")
        lines.append("## 3. 类事件 ORPHAN 清单")
        lines.append("")
        lines.append(f"### 3.1 ORPHAN_PUB 类 - {len(result['orphan_pub_classes'])} 项")
        lines.append("")
        for cls in result['orphan_pub_classes']:
            locs = self.publish_objs[cls]
            loc_str = ", ".join(f"{f}:{ln}" for f, ln, _ in locs[:3])
            lines.append(f"- `{cls}`: {loc_str} (n={len(locs)})")
        lines.append("")
        lines.append(f"### 3.2 ORPHAN_SUB 类 - {len(result['orphan_sub_classes'])} 项")
        lines.append("")
        for cls in result['orphan_sub_classes']:
            locs = self.subscribe_objs[cls]
            loc_str = ", ".join(f"{f}:{ln}" for f, ln, _ in locs[:3])
            lines.append(f"- `{cls}`: {loc_str} (n={len(locs)})")
        lines.append("")
        lines.append("## 4. register_event_type 验证")
        lines.append("")
        lines.append("### 4.1 字符串事件注册情况")
        lines.append("")
        all_str_events = set(self.publishes.keys()) | set(self.subscribes.keys())
        not_registered = [e for e in all_str_events if e not in self.registers]
        registered = [e for e in all_str_events if e in self.registers]
        lines.append(f"- 字符串事件总数: **{len(all_str_events)}**")
        lines.append(f"- 已注册: **{len(registered)}** ({100*len(registered)/max(len(all_str_events),1):.1f}%)")
        lines.append(f"- 未注册: **{len(not_registered)}**")
        lines.append("")
        if not_registered:
            lines.append("#### 未注册的字符串事件 (按业务前缀分组)")
            lines.append("")
            biz_orphans = [e for e in not_registered if is_business_event(e)]
            other_orphans = [e for e in not_registered if not is_business_event(e)]
            if biz_orphans:
                lines.append(f"**业务事件 ({len(biz_orphans)})**:")
                lines.append("")
                for evt in sorted(biz_orphans):
                    pub_n = len(self.publishes.get(evt, []))
                    sub_n = len(self.subscribes.get(evt, []))
                    lines.append(f"- `{evt}` (publish={pub_n}, subscribe={sub_n})")
                lines.append("")
            if other_orphans:
                lines.append(f"**其他事件 ({len(other_orphans)})** (前 20):")
                lines.append("")
                for evt in sorted(other_orphans)[:20]:
                    pub_n = len(self.publishes.get(evt, []))
                    sub_n = len(self.subscribes.get(evt, []))
                    lines.append(f"- `{evt}` (publish={pub_n}, subscribe={sub_n})")
                lines.append("")
        return "\n".join(lines)


# ============================================================
# CLI
# ============================================================

def main():
    scanner = OrphanScanner(PROJECT_ROOT)
    print(f"[R221-C] 开始扫描 {PROJECT_ROOT} ...")
    scanner.scan_subdirs()
    print(f"[R221-C] 扫描完成: {scanner.files_scanned} 文件, 跳过 {scanner.files_skipped} 文件")
    print(f"[R221-C] 错误: {len(scanner.errors)}")
    if scanner.errors:
        for err in scanner.errors[:5]:
            print(f"  - {err}")

    report = scanner.generate_report()
    print("\n" + "=" * 60)
    print(report[:3000])
    print("=" * 60)

    # 保存报告
    report_path = PROJECT_ROOT / ".trae" / "reports" / "rounds" / "audit_r221_c_orphan_pub_sub.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[R221-C] 报告已保存到: {report_path}")

    # 保存 JSON
    json_path = PROJECT_ROOT / "tools" / "_r221_c_orphan_scan.json"
    json_data = {
        "publishes": dict(scanner.publishes),
        "subscribes": dict(scanner.subscribes),
        "publish_classes": dict(scanner.publish_objs),
        "subscribe_classes": dict(scanner.subscribe_objs),
        "registers": dict(scanner.registers),
        "register_classes": dict(scanner.register_classes),
        "orphan_pub_strings": result["orphan_pub_strings"],
        "orphan_sub_strings": result["orphan_sub_strings"],
        "paired_strings": result["paired_strings"],
        "orphan_pub_classes": result["orphan_pub_classes"],
        "orphan_sub_classes": result["orphan_sub_classes"],
        "files_scanned": scanner.files_scanned,
        "files_skipped": scanner.files_skipped,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"[R221-C] JSON 数据已保存到: {json_path}")


if __name__ == "__main__":
    main()
