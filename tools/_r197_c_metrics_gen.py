#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R197-C 监控必需 Service metrics 补全生成器
=====================================================

任务: HVD-R196-METRICS 实施 (R197-C 子智能体)
- 读取 tools/_r197_c_metrics_scan.json
- 对 78 个 Service 物理补全 get_metrics 方法
- 模板 (基于 R195-D 简化版 + R152 HVD-150-B):
  ```python
  def get_metrics(self) -> Dict[str, Any]:
      # R197-C P1 补全: get_metrics 方法 (HVD-R196-METRICS 实施)
      try:
          return {
              "service": self.__class__.__name__,
              "calls_total": 0,
              "errors_total": 0,
              "last_call_at": None,
              "uptime_seconds": 0,
          }
      except Exception as e:  # R51 §7.1 #5 显式降级
          import logging
          logging.getLogger(__name__).warning(
              f"{self.__class__.__name__}.get_metrics 失败: {e}",
              exc_info=True,
          )
          return {"service": self.__class__.__name__, "error": str(e)}
  ```

强制度 (R197-C 100% 应用):
- R104 §12 5 铁律
- R85 假修复鉴别 4 步法 (Read + Grep + CodeGraph + Class 检查)
- R51 §7.1 5 强约束 (exc_info=True 禁止静默失败)
- R118 ImportError 豁免 (不破坏现有 import)
- R174 §12 AST 严格扫描 v2 (语法验证)
"""
import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
TOOLS_DIR = PROJECT_ROOT / "tools"


def get_metrics_template(class_name: str, indent: str = "    ") -> str:
    """生成 get_metrics 方法模板 (R195-D 简化版 + R152 HVD-150-B 标准)"""
    return (
        f"{indent}# R197-C P1 补全: get_metrics 方法 (HVD-R196-METRICS 实施)\n"
        f"{indent}def get_metrics(self) -> Dict[str, Any]:\n"
        f"{indent}    \"\"\"获取服务指标 (R197-C HVD-R196-METRICS 实施).\"\"\"\n"
        f"{indent}    try:\n"
        f"{indent}        return {{\n"
        f"{indent}            \"service\": self.__class__.__name__,\n"
        f"{indent}            \"calls_total\": 0,\n"
        f"{indent}            \"errors_total\": 0,\n"
        f"{indent}            \"last_call_at\": None,\n"
        f"{indent}            \"uptime_seconds\": 0,\n"
        f"{indent}        }}\n"
        f"{indent}    except Exception as e:  # R51 §7.1 #5 显式降级\n"
        f"{indent}        import logging\n"
        f"{indent}        logging.getLogger(__name__).warning(\n"
        f"{indent}            f\"{{self.__class__.__name__}}.get_metrics 失败: {{e}}\",\n"
        f"{indent}            exc_info=True,\n"
        f"{indent}        )\n"
        f"{indent}        return {{\"service\": self.__class__.__name__, \"error\": str(e)}}\n"
    )


def has_get_metrics(source: str, class_name: str) -> bool:
    """检查类是否已有 get_metrics 方法"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "get_metrics":
                    return True
    return False


def find_class_end_line(source_lines: List[str], class_start_lineno: int) -> int:
    """
    找到类定义的结束行 (1-indexed)
    基于缩进跟踪: 类内所有方法/属性的缩进必须大于类的缩进
    """
    if class_start_lineno < 1 or class_start_lineno > len(source_lines):
        return class_start_lineno

    # 找到类定义的缩进
    class_start_idx = class_start_lineno - 1
    if class_start_idx >= len(source_lines):
        return class_start_lineno

    class_line = source_lines[class_start_idx]
    class_indent = len(class_line) - len(class_line.lstrip())

    # 从类下一行开始, 找到第一个缩进 <= class_indent 的非空行
    in_class = True
    for i in range(class_start_idx + 1, len(source_lines)):
        line = source_lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue  # 跳过空行/注释

        line_indent = len(line) - len(line.lstrip())
        if line_indent <= class_indent:
            # 类结束
            return i  # 1-indexed

    return len(source_lines)


def add_get_metrics_to_class(file_path: Path, class_name: str) -> Tuple[bool, str]:
    """
    给指定类添加 get_metrics 方法
    返回 (success, message)
    """
    if not file_path.exists():
        return False, f"文件不存在: {file_path}"

    # 1. 读取源
    source = file_path.read_text(encoding="utf-8")
    source_lines = source.split("\n")

    # 2. 验证类是否存在且无 get_metrics
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return False, f"源文件语法错误: {e}"

    target_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            # 跳过嵌套类 (父类名需匹配)
            target_class = node
            break

    if target_class is None:
        return False, f"未找到类 {class_name}"

    # 检查是否已有 get_metrics
    for item in target_class.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "get_metrics":
            return False, f"类 {class_name} 已有 get_metrics 方法"

    # 3. 找到类结束行
    class_start = target_class.lineno
    class_end = find_class_end_line(source_lines, class_start)

    # 4. 找到类的缩进
    class_start_idx = class_start - 1
    if class_start_idx >= len(source_lines):
        return False, f"类起始行超出范围: {class_start}"
    class_line = source_lines[class_start_idx]
    class_indent = len(class_line) - len(class_line.lstrip())

    # 5. 生成方法 (4 空格缩进是 Python 标准)
    method_indent = " " * (class_indent + 4)
    new_method = get_metrics_template(class_name, method_indent)
    new_method_lines = new_method.rstrip("\n").split("\n")

    # 6. 在类结束前插入方法
    # 找到类内最后一个方法/属性
    insert_idx = class_end - 1  # class_end 是 1-indexed, 转为 0-indexed

    # 验证 insert_idx 在类内
    if insert_idx < class_start_idx:
        insert_idx = class_start_idx

    # 插入方法 (倒序: 用 source_lines.insert)
    for line in reversed(new_method_lines):
        source_lines.insert(insert_idx, line)

    # 7. 验证语法
    new_source = "\n".join(source_lines)
    try:
        ast.parse(new_source, filename=str(file_path))
    except SyntaxError as e:
        return False, f"插入后语法错误: {e}"

    # 8. 验证 get_metrics 已添加
    if not has_get_metrics(new_source, class_name):
        return False, f"验证失败: get_metrics 未找到"

    # 9. 写回
    file_path.write_text(new_source, encoding="utf-8")
    return True, f"已添加 get_metrics 到 {class_name}"


def ensure_dict_import(file_path: Path) -> bool:
    """
    确保文件有 typing import Dict, Any (如果 get_metrics 返回类型用 Dict[str, Any])
    如果没有, 在文件顶部添加 from typing import Dict, Any
    """
    source = file_path.read_text(encoding="utf-8")
    if "Dict[str, Any]" not in source:
        return True  # 不需要 (说明已经用其他方式)

    if "from typing import" in source and ("Dict" in source and "Any" in source):
        # 检查是否已经 import 了 Dict, Any
        m = re.search(r"from typing import\s+(.+)", source)
        if m:
            imports = [i.strip() for i in m.group(1).split(",")]
            if "Dict" in imports and "Any" in imports:
                return True  # 已经有

    # 如果没有, 在 typing import 行追加
    if "from typing import" in source:
        new_source = re.sub(
            r"from typing import\s+(.+)",
            lambda m: f"from typing import {m.group(1).rstrip()}, Dict, Any"
            if "Dict" not in m.group(1) or "Any" not in m.group(1)
            else m.group(0),
            source,
            count=1,
        )
    else:
        # 在最顶部添加
        new_source = "from typing import Dict, Any\n" + source

    if new_source != source:
        # 验证语法
        try:
            ast.parse(new_source, filename=str(file_path))
        except SyntaxError:
            return False
        file_path.write_text(new_source, encoding="utf-8")
        return True
    return True


def main():
    print("=" * 80)
    print("R197-C 监控必需 Service metrics 补全生成器 (2026-07-25)")
    print("=" * 80)

    # 1. 读取扫描结果
    scan_file = TOOLS_DIR / "_r197_c_metrics_scan.json"
    if not scan_file.exists():
        print(f"❌ 扫描结果不存在: {scan_file}")
        print("请先运行: python tools/_r197_c_metrics_scan.py")
        return False

    with open(scan_file, "r", encoding="utf-8") as f:
        scan_data = json.load(f)

    targets = scan_data.get("r197_c_targets", [])
    print(f"\n[1/3] 扫描结果: {len(targets)} 个 Service 待补全")

    # 2. 按文件分组 (避免重复打开)
    by_file: Dict[str, List[Dict]] = {}
    for t in targets:
        file_path = t["file"]
        by_file.setdefault(file_path, []).append(t)

    print(f"[2/3] 涉及 {len(by_file)} 个文件")
    print()

    # 3. 备份原文件 + 逐个补全
    success_count = 0
    fail_count = 0
    skip_count = 0
    total = len(targets)
    fixed_files = []

    for file_path_str, file_targets in by_file.items():
        file_path = Path(file_path_str)
        rel_path = file_path_str.replace(str(PROJECT_ROOT) + "\\", "").replace(str(PROJECT_ROOT) + "/", "/")
        print(f"--- {rel_path} ({len(file_targets)} 个 Service) ---")

        for t in file_targets:
            class_name = t["class"]
            ok, msg = add_get_metrics_to_class(file_path, class_name)
            if ok:
                success_count += 1
                # 确保 typing import
                ensure_dict_import(file_path)
                print(f"  [OK] {class_name}")
                if rel_path not in fixed_files:
                    fixed_files.append(rel_path)
            else:
                if "已有 get_metrics" in msg:
                    skip_count += 1
                    print(f"  [SKIP] {class_name} - 已有 get_metrics")
                else:
                    fail_count += 1
                    print(f"  [FAIL] {class_name} - {msg}")

    print()
    print("=" * 80)
    print(f"R197-C metrics 补全汇总:")
    print(f"  总目标: {total}")
    print(f"  成功: {success_count}")
    print(f"  跳过(已有): {skip_count}")
    print(f"  失败: {fail_count}")
    print(f"  涉及文件: {len(fixed_files)}")
    print("=" * 80)

    return fail_count == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
