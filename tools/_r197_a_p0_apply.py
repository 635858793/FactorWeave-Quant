"""
R197-A v5 P0 静默失败修复器
=========================================================================
基于 R195-A v5 多行 logger 修复器 + R196-B 经验 + R194-D v3/v4.1 升级

修复策略:
- 物理修复 P0 真违规 (except Exception + logger.error 缺 exc_info=True)
- R118 ImportError/ValueError 业务警告路径保留
- R75-DEV-4 持久化失败保留 (traceback.format_exc 已有堆栈)
- 1-stmt Assign 模式不修改 (已是 R194-D 设计)
- 跳过测试代码 (tests/)、工具代码 (tools/)、utils 目录
- 添加 R197-A P0 修复注释

强制度:
- R51 §7.1 #5 严禁静默失败铁律
- R174 §12 v2.1 AST 严格扫描器
- R196-B v2.1 模式
- R194-D v3/v4.1 修复器经验
- R118 ImportError 豁免
- R110-C 时序竞态防御
- R176 死缓存防御兼容期保留
"""
import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# R197-A 业务核心 P0 真违规修复目标 (10 项物理修复, 跨 4 子目录业务核心)
# 保留项 (3 个): database_writer L329/L367 已有 traceback.format_exc() 保留堆栈
#                 intelligent_cache L308 已有 R75-DEV-4 持久化失败设计模式
# 来源: tools/_r197_a_p0_scan.json P0 真违规清单 (R195-A 报告 4 子目录核心)
# 注意: 行号是 logger.X( 所在的实际行 (非 except 行)
R197_A_P0_FIXES = [
    # core/importdata/ (2 项物理修复, 数据写入核心)
    # 保留: L329/L367 已有 traceback.format_exc() 保留堆栈 (R75-DEV-4 兼容)
    ("core/importdata/database_writer.py", 107, "放入写入任务失败"),
    ("core/importdata/unified_data_import_engine.py", 211, "异步任务执行失败"),
    # core/webgpu/ (4 项物理修复, 渲染核心)
    ("core/webgpu/webgpu_renderer.py", 153, "WebGPU上下文初始化失败"),
    ("core/webgpu/memory_manager.py", 206, "内存池初始化失败"),
    ("core/webgpu/memory_manager.py", 233, "内存块预分配失败"),  # L233 才是 logger 行
    ("core/webgpu/pipeline_optimizer.py", 191, "提交渲染命令失败"),
    # core/advanced_optimization/ (2 项物理修复, 性能监控核心)
    # 保留: L308 已有 R75-DEV-4 设计 (持久化失败仅 warning 不抛)
    ("core/advanced_optimization/cache/intelligent_cache.py", 419, "写入缓存失败"),
    ("core/advanced_optimization/performance/thread_monitor.py", 248, "线程泄漏检测失败"),
    # core/ui/ (2 项物理修复, UI 生命周期核心)
    ("core/ui/panels/base_panel.py", 186, "BasePanel 错误处理"),
    ("core/ui/panels/base_panel.py", 473, "Error disposing"),  # L473 才是 logger 行
]


def backup_file(file_path: Path) -> Path:
    """备份文件"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(file_path.suffix + f".r197a.{ts}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def find_logger_call_end(source: str, logger_lineno: int) -> Optional[Tuple[int, int]]:
    """找到 logger.X( 调用的结束位置 (返回 (行号, 字符位置))"""
    lines = source.split("\n")
    if logger_lineno < 1 or logger_lineno > len(lines):
        return None
    start_line = logger_lineno - 1
    start_line_content = lines[start_line]
    m = re.search(r'(self\.)?logger\.(warning|error|debug|info|critical|exception|warn)\(', start_line_content)
    if not m:
        return None
    paren_pos = m.end() - 1
    paren_depth = 1
    current_line = start_line
    current_pos = paren_pos + 1
    while current_line < len(lines):
        line = lines[current_line]
        while current_pos < len(line):
            ch = line[current_pos]
            if ch == '(':
                paren_depth += 1
            elif ch == ')':
                paren_depth -= 1
                if paren_depth == 0:
                    return (current_line + 1, current_pos)
            current_pos += 1
        current_line += 1
        current_pos = 0
    return None


def add_exc_info(file_path: Path, logger_lineno: int, fix_desc: str = "") -> bool:
    """
    物理修复: 在 logger.X(...) 调用的 ) 前插入 , exc_info=True
    R197-A P0 修复 (R51 §7.1 #5 严禁静默失败)
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception:
        return False

    # 幂等性检查: 如果已经含 exc_info, 跳过
    if "exc_info" in source.split("\n")[logger_lineno - 1] if logger_lineno - 1 < len(source.split("\n")) else False:
        return True  # 已修复

    end_pos = find_logger_call_end(source, logger_lineno)
    if not end_pos:
        return False
    end_line, end_col = end_pos
    end_line_idx = end_line - 1

    lines = source.split("\n")
    end_line_content = lines[end_line_idx]

    # 在 ) 前插入 , exc_info=True
    if end_line_content[end_col] != ')':
        return False

    after_paren = end_line_content[end_col + 1:].rstrip()
    if "#" in after_paren:
        # 注释放外面
        comment_match = re.search(r'(#.*)', end_line_content[end_col + 1:])
        if comment_match:
            comment = comment_match.group(1)
            new_end_line = (end_line_content[:end_col]
                            + ", exc_info=True"
                            + ")"
                            + "  "
                            + comment)
        else:
            new_end_line = end_line_content[:end_col] + ", exc_info=True)" + end_line_content[end_col + 1:]
    else:
        new_end_line = end_line_content[:end_col] + ", exc_info=True)" + end_line_content[end_col + 1:]

    lines[end_line_idx] = new_end_line

    # 在 logger 行前添加 R197-A 修复注释
    start_line_idx = logger_lineno - 1
    if start_line_idx < len(lines):
        start_line = lines[start_line_idx]
        if "R197-A P0 修复" not in start_line:
            # 缩进与 logger 行一致
            indent_match = re.match(r"^(\s*)", start_line)
            indent = indent_match.group(1) if indent_match else ""
            comment_line = f"{indent}# R197-A P0 修复: exc_info=True 保留堆栈 (R51 §7.1 #5 严禁静默失败)"
            # 检查前一行是否已有注释
            if start_line_idx > 0 and "R197-A P0 修复" not in lines[start_line_idx - 1]:
                lines.insert(start_line_idx, comment_line)
            else:
                # 已有注释, 不重复
                pass

    new_source = "\n".join(lines)

    # 验证语法
    try:
        ast.parse(new_source)
    except SyntaxError:
        return False

    file_path.write_text(new_source, encoding="utf-8")
    return True


def main():
    print("=" * 80)
    print("R197-A v5 P0 静默失败修复器 (12 项业务核心)")
    print("=" * 80)
    print()
    print("强制度: R51 §7.1 #5 + R174 §12 v2.1 + R196-B v2.1 + R194-D v3 + R118 豁免")
    print()

    # 按文件分组
    by_file: Dict[str, List[Tuple[int, str]]] = {}
    for f, ln, desc in R197_A_P0_FIXES:
        by_file.setdefault(f, []).append((ln, desc))

    grand_fixed = 0
    grand_skipped = 0
    backed_up = set()
    apply_log = []

    for rel_path, fixes in by_file.items():
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"  [MISSING] {rel_path}")
            continue
        # 备份
        if rel_path not in backed_up:
            backup_file(file_path)
            backed_up.add(rel_path)
        file_fixed = 0
        file_skipped = 0
        for ln, desc in fixes:
            if add_exc_info(file_path, ln, desc):
                file_fixed += 1
                apply_log.append({
                    "file": rel_path,
                    "line": ln,
                    "description": desc,
                    "status": "FIXED",
                })
            else:
                file_skipped += 1
                apply_log.append({
                    "file": rel_path,
                    "line": ln,
                    "description": desc,
                    "status": "SKIPPED_OR_IDEMPOTENT",
                })
        grand_fixed += file_fixed
        grand_skipped += file_skipped
        print(f"  [{file_fixed}/{len(fixes)}] {rel_path}")

    print()
    print(f"总计: 修复 {grand_fixed} / 跳过 {grand_skipped} / 总计 {len(R197_A_P0_FIXES)}")

    # 写修复日志
    log_file = PROJECT_ROOT / "tools" / "_r197_a_p0_apply.json"
    log_file.write_text(
        json.dumps({
            "fix_count": grand_fixed,
            "skip_count": grand_skipped,
            "total": len(R197_A_P0_FIXES),
            "fixes": apply_log,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"修复日志: {log_file}")


if __name__ == "__main__":
    main()
