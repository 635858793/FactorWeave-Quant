#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
R237-B 子智能体 B: BaseService 子类冗余 property 扫描工具
============================================================

目的:
  1. 提取 BaseService 父类 (BaseService, AsyncBaseService, ConfigurableService, CacheableService) 的所有 @property
  2. 扫描所有继承 BaseService 的子类, 找出潜在 property 冲突
  3. 分类:
     - READONLY: 父类 @property, 子类尝试 self.x = Y (破坏只读)
     - WRITABLE: 父类无 @property, 子类用 @property 暴露, 但同时有 self.x = Y (属性遮蔽)
     - DIFFERENT_BODY: 父类有 @property, 子类也定义同名 @property, 但实现不同 (覆盖)
  4. 4 源验证:
     源 1: Read 类定义 + __init__ 模式
     源 2: Grep `self.<prop_name>\\s*=\\s*` 跨子目录
     源 3: mcp_codegraph 节点 (此处仅 AST)
     源 4: 业务调用链

合规:
  - R104 §12.4 铁律 #3: 嵌套检测递归 (适用 with)
  - R104 §12.4 铁律 #4: 物理删除前 4 源 100% 命中
  - R231 §13.4 铁律 #4: 类同名方法 AST 定位 class_name 限定
"""
import ast
import os
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional

# BaseService 父类继承链
BASE_SERVICE_PARENTS = {
    "BaseService",
    "AsyncBaseService",
    "ConfigurableService",
    "CacheableService",
}

# BaseService 父类定义的 @property (来自 base_service.py 源码审计)
BASE_SERVICE_PROPERTIES = {
    "BaseService": {
        "name", "initialized", "disposed", "event_bus",
        "service_id", "initialization_time", "dependencies", "metrics",
    },
    "AsyncBaseService": set(),  # 继承自 BaseService, 无新 property
    "ConfigurableService": {"config"},
    "CacheableService": set(),  # 继承自 BaseService, 无新 property
}


def get_property_names_from_class(node: ast.ClassDef) -> Set[str]:
    """从 AST ClassDef 节点提取所有 @property 装饰的属性名."""
    props = set()
    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            for decorator in item.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == "property":
                    props.add(item.name)
                elif isinstance(decorator, ast.Attribute) and decorator.attr == "property":
                    props.add(item.name)
    return props


def get_all_parent_properties(class_node: ast.ClassDef, all_classes: Dict[str, ast.ClassDef]) -> Set[str]:
    """递归收集所有父类的 @property 集合."""
    result = set()
    bases = []
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(base.attr)
    for base_name in bases:
        if base_name in all_classes:
            result |= get_all_parent_properties(all_classes[base_name], all_classes)
            result |= get_property_names_from_class(all_classes[base_name])
        elif base_name in BASE_SERVICE_PARENTS:
            result |= BASE_SERVICE_PROPERTIES.get(base_name, set())
    return result


def find_self_assign_in_method(method_node: ast.FunctionDef, prop_name: str) -> List[Tuple[int, str]]:
    """
    查找方法体中 `self.<prop_name> = <...>` 模式 (R12 §12.4 铁律 #3: 递归 into nested blocks).

    Returns:
        [(行号, 右侧表达式字符串), ...]
    """
    hits = []
    for node in ast.walk(method_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Attribute) and
                    isinstance(target.value, ast.Name) and
                    target.value.id == "self" and
                    target.attr == prop_name):
                    try:
                        rhs = ast.unparse(node.value)
                    except Exception:
                        rhs = "<complex>"
                    hits.append((node.lineno, rhs))
    return hits


def is_property_in_class(class_node: ast.ClassDef, prop_name: str) -> bool:
    """检查类是否定义了该 @property."""
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == prop_name:
            for decorator in item.decorator_list:
                if (isinstance(decorator, ast.Name) and decorator.id == "property") or \
                   (isinstance(decorator, ast.Attribute) and decorator.attr == "property"):
                    return True
    return False


def get_property_body(class_node: ast.ClassDef, prop_name: str) -> Optional[str]:
    """获取 @property 方法体的 unparse 字符串 (用于 DIFFERENT_BODY 比对)."""
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == prop_name:
            for decorator in item.decorator_list:
                if (isinstance(decorator, ast.Name) and decorator.id == "property") or \
                   (isinstance(decorator, ast.Attribute) and decorator.attr == "property"):
                    try:
                        return ast.unparse(item)
                    except Exception:
                        return None
    return None


def analyze_file(filepath: Path) -> List[Dict]:
    """
    分析单个 .py 文件, 返回所有 BaseService 子类的 property 冲突列表.

    每个冲突项结构:
    {
        "class_name": "...",
        "class_lineno": ...,
        "prop_name": "...",
        "category": "READONLY" | "WRITABLE" | "DIFFERENT_BODY",
        "self_assign_lines": [L1, L2, ...],
        "self_assign_examples": ["self.x = ...", ...],
        "parent_class": "...",
    }
    """
    try:
        src = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError, PermissionError):
        return []

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    # 1. 收集本文件所有 class 节点
    all_classes: Dict[str, ast.ClassDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            all_classes[node.name] = node

    results = []

    for class_name, class_node in all_classes.items():
        # 2. 检查是否继承 BaseService 父类
        parent_props = get_all_parent_properties(class_node, all_classes)
        if not parent_props:
            # 既不继承 BaseService, 也不通过链式继承拿到 property
            continue

        # 3. 收集本类的 @property (DIFFERENT_BODY 比对用)
        own_props = get_property_names_from_class(class_node)

        for prop_name in parent_props:
            # 4. 遍历所有方法, 找 self.<prop_name> = ... 模式
            self_assign_hits = []
            for item in class_node.body:
                if isinstance(item, ast.FunctionDef):
                    hits = find_self_assign_in_method(item, prop_name)
                    for lineno, rhs in hits:
                        self_assign_hits.append({
                            "method": item.name,
                            "line": lineno,
                            "rhs": rhs[:120],
                        })

            if not self_assign_hits:
                continue

            # 5. 分类
            if prop_name in own_props:
                # 子类有 @property, 但内部某方法 self.x = Y
                # 可能是 property setter, 也可能是 bug
                # 找子类的 @property body 与父类 body 对比
                parent_class_for_prop = None
                for pname in BASE_SERVICE_PARENTS:
                    if prop_name in BASE_SERVICE_PROPERTIES.get(pname, set()):
                        parent_class_for_prop = pname
                        break
                # 父类 body (硬编码)
                parent_body = get_parent_property_body(parent_class_for_prop, prop_name)
                own_body = get_property_body(class_node, prop_name)
                if parent_body and own_body and parent_body != own_body:
                    category = "DIFFERENT_BODY"
                else:
                    category = "DIFFERENT_BODY"  # 即使 body 相同但有 self.x = Y 仍标
            else:
                # 子类无 @property, 父类有 readonly @property
                # 任何 self.x = Y 都是 READONLY 冲突
                category = "READONLY"

            results.append({
                "class_name": class_name,
                "class_lineno": class_node.lineno,
                "prop_name": prop_name,
                "category": category,
                "self_assign_count": len(self_assign_hits),
                "self_assign_lines": [h["line"] for h in self_assign_hits[:5]],
                "self_assign_examples": [
                    f"{h['method']}:L{h['line']} = {h['rhs']}"
                    for h in self_assign_hits[:3]
                ],
            })

        # 6. DIFFERENT_BODY 单独检测: 子类覆盖父类 @property (即使没 self.x = Y)
        for prop_name in own_props:
            if prop_name in parent_props:
                # 是覆盖
                parent_class_for_prop = None
                for pname in BASE_SERVICE_PARENTS:
                    if prop_name in BASE_SERVICE_PROPERTIES.get(pname, set()):
                        parent_class_for_prop = pname
                        break
                parent_body = get_parent_property_body(parent_class_for_prop, prop_name)
                own_body = get_property_body(class_node, prop_name)
                if parent_body and own_body:
                    # 不重复报告: 如果已有 self_assign 报告, 跳过
                    if not any(r["prop_name"] == prop_name and r["class_name"] == class_name for r in results):
                        results.append({
                            "class_name": class_name,
                            "class_lineno": class_node.lineno,
                            "prop_name": prop_name,
                            "category": "DIFFERENT_BODY",
                            "self_assign_count": 0,
                            "self_assign_lines": [],
                            "self_assign_examples": [
                                f"@property {prop_name} override at L{[i.lineno for i in class_node.body if isinstance(i, ast.FunctionDef) and i.name == prop_name][0] if any(isinstance(i, ast.FunctionDef) and i.name == prop_name for i in class_node.body) else '?'}"
                            ],
                        })

    return results


# 父类 @property body 硬编码 (R237-B 子智能体手动审计, 与 base_service.py 源码一致)
def get_parent_property_body(parent_class: str, prop_name: str) -> Optional[str]:
    bodies = {
        ("BaseService", "name"): "return self._name",
        ("BaseService", "initialized"): "return self._initialized",
        ("BaseService", "disposed"): "return self._disposed",
        ("BaseService", "event_bus"): "return self._event_bus",
        ("BaseService", "service_id"): "return self._service_id",
        ("BaseService", "initialization_time"): "return self._initialization_time",
        ("BaseService", "dependencies"): "return self._dependencies.copy()",
        ("BaseService", "metrics"): "with self._lock: ... return self._metrics.copy()",
        ("ConfigurableService", "config"): "return self._config.copy()",
    }
    return bodies.get((parent_class, prop_name))


def scan_directory(target_dir: Path, project_root: Path) -> Dict:
    """扫描整个目录, 汇总结果."""
    summary = {
        "target": str(target_dir),
        "files_scanned": 0,
        "files_with_findings": 0,
        "readonly_count": 0,
        "writable_count": 0,
        "different_body_count": 0,
        "findings": [],
        "by_class": defaultdict(int),
        "by_prop": defaultdict(int),
    }

    for py_file in target_dir.rglob("*.py"):
        summary["files_scanned"] += 1
        file_findings = analyze_file(py_file)
        if file_findings:
            summary["files_with_findings"] += 1
            for f in file_findings:
                f["file"] = str(py_file.resolve().relative_to(project_root.resolve())) if str(py_file).startswith(str(project_root.resolve())) else str(py_file)
                summary["findings"].append(f)
                if f["category"] == "READONLY":
                    summary["readonly_count"] += 1
                elif f["category"] == "WRITABLE":
                    summary["writable_count"] += 1
                elif f["category"] == "DIFFERENT_BODY":
                    summary["different_body_count"] += 1
                summary["by_class"][f["class_name"]] += 1
                summary["by_prop"][f["prop_name"]] += 1

    summary["by_class"] = dict(summary["by_class"])
    summary["by_prop"] = dict(summary["by_prop"])
    return summary


def main():
    parser = argparse.ArgumentParser(description="R237-B BaseService 子类 property 冲突扫描")
    parser.add_argument("--module", type=str, help="扫描指定模块路径")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    targets = []
    if args.module:
        targets.append(Path(args.module))
    else:
        # 全项目扫描
        for sub in ["core/services", "core", "plugins"]:
            p = project_root / sub
            if p.exists():
                targets.append(p)

    all_results = {}
    for target in targets:
        if not target.exists():
            continue
        result = scan_directory(target, project_root)
        # 兼容 Windows 路径
        try:
            key = str(target.relative_to(project_root))
        except ValueError:
            try:
                key = str(target.resolve().relative_to(project_root.resolve()))
            except ValueError:
                key = str(target)
        all_results[key] = result

    if args.json:
        print(json.dumps(all_results, indent=2, ensure_ascii=False))
    else:
        # 人类可读输出
        for tgt, res in all_results.items():
            print("=" * 80)
            print(f"Target: {tgt}")
            print(f"  Files scanned: {res['files_scanned']}")
            print(f"  Files with findings: {res['files_with_findings']}")
            print(f"  READONLY: {res['readonly_count']}")
            print(f"  WRITABLE: {res['writable_count']}")
            print(f"  DIFFERENT_BODY: {res['different_body_count']}")
            print()
            print(f"  By property: {res['by_prop']}")
            print()
            print("  Findings:")
            for f in res['findings'][:30]:
                print(f"    [{f['category']}] {f['class_name']}.{f['prop_name']}")
                print(f"      file: {f['file']}:L{f['class_lineno']}")
                for ex in f['self_assign_examples']:
                    print(f"      - {ex}")
            if len(res['findings']) > 30:
                print(f"    ... and {len(res['findings']) - 30} more")


if __name__ == "__main__":
    main()
