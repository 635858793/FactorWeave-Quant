#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FactorWeave-Quant 传统数据源依赖关系分析器

该模块提供传统数据源迁移过程中的依赖关系分析功能，包括：
- 代码库扫描和AST分析
- 直接和间接依赖关系识别
- 依赖关系图生成
- 影响分析报告

注意：传统数据源已迁移到TET+Plugin架构，此分析器主要用于历史依赖检查。
- 迁移优先级建议

作者: FactorWeave-Quant Migration Team
日期: 2025-09-20
"""

import os
import sys
import ast
import json
import time
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import re
import importlib.util

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from core.loguru_interface import get_logger
except ImportError:
    # 备用日志记录
    from loguru import logger

    def get_logger(name):
        return logger


class DependencyType(Enum):
    """依赖类型枚举"""
    IMPORT = "import"
    FUNCTION_CALL = "function_call"
    CLASS_INSTANTIATION = "class_instantiation"
    ATTRIBUTE_ACCESS = "attribute_access"
    INHERITANCE = "inheritance"
    CONFIGURATION = "configuration"
    STRING_REFERENCE = "string_reference"


class ImpactLevel(Enum):
    """影响级别枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DependencyReference:
    """依赖引用"""
    file_path: str
    line_number: int
    column_number: int
    dependency_type: DependencyType
    source_name: str  # 传统数据源名称
    reference_text: str  # 引用的具体文本
    context: str  # 上下文代码
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    impact_level: ImpactLevel = ImpactLevel.MEDIUM

    def __post_init__(self):
        # 根据依赖类型自动评估影响级别
        if self.dependency_type == DependencyType.IMPORT:
            self.impact_level = ImpactLevel.HIGH
        elif self.dependency_type == DependencyType.CLASS_INSTANTIATION:
            self.impact_level = ImpactLevel.HIGH
        elif self.dependency_type == DependencyType.INHERITANCE:
            self.impact_level = ImpactLevel.CRITICAL
        elif self.dependency_type == DependencyType.FUNCTION_CALL:
            self.impact_level = ImpactLevel.MEDIUM
        elif self.dependency_type == DependencyType.ATTRIBUTE_ACCESS:
            self.impact_level = ImpactLevel.MEDIUM
        elif self.dependency_type == DependencyType.CONFIGURATION:
            self.impact_level = ImpactLevel.LOW
        elif self.dependency_type == DependencyType.STRING_REFERENCE:
            self.impact_level = ImpactLevel.LOW


@dataclass
class FileAnalysisResult:
    """文件分析结果"""
    file_path: str
    total_references: int
    dependencies: List[DependencyReference]
    imports: List[str]
    classes: List[str]
    functions: List[str]
    analysis_time: float
    has_legacy_dependencies: bool = False

    def __post_init__(self):
        self.has_legacy_dependencies = len(self.dependencies) > 0


@dataclass
class DependencyGraph:
    """依赖关系图"""
    nodes: Dict[str, Dict[str, Any]]  # 节点信息
    edges: List[Dict[str, Any]]  # 边信息
    legacy_sources: Set[str]  # 传统数据源集合
    affected_files: Set[str]  # 受影响的文件
    dependency_chains: List[List[str]]  # 依赖链


class DependencyAnalyzer:
    """依赖关系分析器"""

    def __init__(self, project_root: str = None):
        """
        初始化依赖分析器

        Args:
            project_root: 项目根目录
        """
        self.logger = get_logger("DependencyAnalyzer")

        if project_root:
            self.project_root = Path(project_root)
        else:
            self.project_root = project_root

        # 传统数据源定义
        self.legacy_sources = {
            "eastmoney": {
                "module_names": ["eastmoney_source", "EastmoneySource"],
                "file_patterns": ["*eastmoney*", "*east_money*"],
                "class_names": ["EastmoneySource", "EastMoneySource"],
                "function_patterns": ["eastmoney_", "east_money_"],
                "config_keys": ["eastmoney", "EASTMONEY"]
            },
            "sina": {
                "module_names": ["sina_source", "SinaSource"],
                "file_patterns": ["*sina*"],
                "class_names": ["SinaSource"],
                "function_patterns": ["sina_"],
                "config_keys": ["sina", "SINA"]
            },
            "tonghuashun": {
                "module_names": ["tonghuashun_source", "TonghuashunSource"],
                "file_patterns": ["*tonghuashun*", "*ths*"],
                "class_names": ["TonghuashunSource", "THSSource"],
                "function_patterns": ["tonghuashun_", "ths_"],
                "config_keys": ["tonghuashun", "THS", "TONGHUASHUN"]
            }
        }

        # 排除的目录和文件
        self.exclude_patterns = [
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".git",
            ".pytest_cache",
            "logs",
            "cache",
            "temp",
            "tmp",
            "backups",
            "node_modules",
            ".spec-workflow"
        ]

        # 分析结果
        self.file_results: Dict[str, FileAnalysisResult] = {}
        self.dependency_graph: Optional[DependencyGraph] = None

        self.logger.info("依赖关系分析器初始化完成")

    def analyze_project(self) -> Dict[str, Any]:
        """分析整个项目的依赖关系"""
        self.logger.info("开始分析项目依赖关系...")
        start_time = time.time()

        # 扫描Python文件
        python_files = self._find_python_files()
        self.logger.info(f"找到 {len(python_files)} 个Python文件")

        # 分析每个文件
        total_references = 0
        for file_path in python_files:
            try:
                result = self._analyze_file(file_path)
                self.file_results[str(file_path)] = result
                total_references += result.total_references

                if result.has_legacy_dependencies:
                    self.logger.debug(f"发现依赖: {file_path} ({result.total_references} 个引用)")

            except Exception as e:
                self.logger.error(f"分析文件失败 {file_path}: {e}")

        # 构建依赖关系图
        self.dependency_graph = self._build_dependency_graph()

        analysis_time = time.time() - start_time
        self.logger.info(f"依赖分析完成，耗时: {analysis_time:.2f}秒，总引用数: {total_references}")

        return self._generate_analysis_summary()

    def _find_python_files(self) -> List[Path]:
        """查找所有Python文件"""
        python_files = []

        for pattern in ["**/*.py"]:
            for file_path in self.project_root.glob(pattern):
                # 检查是否应该排除
                should_exclude = False
                for exclude_pattern in self.exclude_patterns:
                    if exclude_pattern in str(file_path):
                        should_exclude = True
                        break

                if not should_exclude and file_path.is_file():
                    python_files.append(file_path)

        return python_files

    def _analyze_file(self, file_path: Path) -> FileAnalysisResult:
        """分析单个文件的依赖关系"""
        start_time = time.time()
        dependencies = []
        imports = []
        classes = []
        functions = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析AST
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError as e:
                self.logger.warning(f"语法错误，跳过文件 {file_path}: {e}")
                return FileAnalysisResult(
                    file_path=str(file_path),
                    total_references=0,
                    dependencies=[],
                    imports=[],
                    classes=[],
                    functions=[],
                    analysis_time=time.time() - start_time
                )

            # AST遍历分析
            visitor = DependencyVisitor(self.legacy_sources, str(file_path), content)
            visitor.visit(tree)

            dependencies = visitor.dependencies
            imports = visitor.imports
            classes = visitor.classes
            functions = visitor.functions

        except Exception as e:
            self.logger.error(f"分析文件内容失败 {file_path}: {e}")

        analysis_time = time.time() - start_time

        return FileAnalysisResult(
            file_path=str(file_path),
            total_references=len(dependencies),
            dependencies=dependencies,
            imports=imports,
            classes=classes,
            functions=functions,
            analysis_time=analysis_time
        )

    def _build_dependency_graph(self) -> DependencyGraph:
        """构建依赖关系图"""
        nodes = {}
        edges = []
        legacy_sources = set()
        affected_files = set()

        # 构建节点
        for file_path, result in self.file_results.items():
            if result.has_legacy_dependencies:
                affected_files.add(file_path)

                nodes[file_path] = {
                    "type": "file",
                    "name": Path(file_path).name,
                    "path": file_path,
                    "reference_count": result.total_references,
                    "impact_level": self._calculate_file_impact_level(result)
                }

                # 添加依赖的传统数据源
                for dep in result.dependencies:
                    legacy_sources.add(dep.source_name)

                    source_node_id = f"legacy_{dep.source_name}"
                    if source_node_id not in nodes:
                        nodes[source_node_id] = {
                            "type": "legacy_source",
                            "name": dep.source_name,
                            "source": dep.source_name
                        }

                    # 添加边
                    edges.append({
                        "from": file_path,
                        "to": source_node_id,
                        "type": dep.dependency_type.value,
                        "impact": dep.impact_level.value,
                        "references": len([d for d in result.dependencies if d.source_name == dep.source_name])
                    })

        # 分析依赖链
        dependency_chains = self._find_dependency_chains(nodes, edges)

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            legacy_sources=legacy_sources,
            affected_files=affected_files,
            dependency_chains=dependency_chains
        )

    def _calculate_file_impact_level(self, result: FileAnalysisResult) -> str:
        """计算文件的影响级别"""
        critical_count = sum(1 for dep in result.dependencies if dep.impact_level == ImpactLevel.CRITICAL)
        high_count = sum(1 for dep in result.dependencies if dep.impact_level == ImpactLevel.HIGH)

        if critical_count > 0:
            return ImpactLevel.CRITICAL.value
        elif high_count > 2:
            return ImpactLevel.HIGH.value
        elif result.total_references > 5:
            return ImpactLevel.MEDIUM.value
        else:
            return ImpactLevel.LOW.value

    def _find_dependency_chains(self, nodes: Dict[str, Any], edges: List[Dict[str, Any]]) -> List[List[str]]:
        """查找依赖链"""
        chains = []

        # 简单的依赖链分析（可以扩展为更复杂的图算法）
        file_nodes = [node_id for node_id, node in nodes.items() if node["type"] == "file"]
        legacy_nodes = [node_id for node_id, node in nodes.items() if node["type"] == "legacy_source"]

        for legacy_node in legacy_nodes:
            dependent_files = [edge["from"] for edge in edges if edge["to"] == legacy_node]
            if len(dependent_files) > 1:
                chains.append([legacy_node] + dependent_files)

        return chains

    def _generate_analysis_summary(self) -> Dict[str, Any]:
        """生成分析摘要"""
        total_files = len(self.file_results)
        affected_files = sum(1 for result in self.file_results.values() if result.has_legacy_dependencies)
        total_references = sum(result.total_references for result in self.file_results.values())

        # 按数据源统计
        source_stats = {}
        for source_name in self.legacy_sources.keys():
            source_refs = []
            for result in self.file_results.values():
                source_refs.extend([dep for dep in result.dependencies if dep.source_name == source_name])

            source_stats[source_name] = {
                "total_references": len(source_refs),
                "affected_files": len(set(dep.file_path for dep in source_refs)),
                "impact_levels": {
                    level.value: len([dep for dep in source_refs if dep.impact_level == level])
                    for level in ImpactLevel
                }
            }

        # 按依赖类型统计
        type_stats = {}
        for dep_type in DependencyType:
            type_refs = []
            for result in self.file_results.values():
                type_refs.extend([dep for dep in result.dependencies if dep.dependency_type == dep_type])

            type_stats[dep_type.value] = len(type_refs)

        # 影响级别统计
        impact_stats = {}
        for impact_level in ImpactLevel:
            level_refs = []
            for result in self.file_results.values():
                level_refs.extend([dep for dep in result.dependencies if dep.impact_level == impact_level])

            impact_stats[impact_level.value] = len(level_refs)

        return {
            "summary": {
                "total_files_scanned": total_files,
                "affected_files": affected_files,
                "total_references": total_references,
                "legacy_sources_found": len(self.dependency_graph.legacy_sources) if self.dependency_graph else 0
            },
            "by_source": source_stats,
            "by_type": type_stats,
            "by_impact": impact_stats,
            "dependency_chains": len(self.dependency_graph.dependency_chains) if self.dependency_graph else 0,
            "migration_complexity": self._assess_migration_complexity()
        }

    def _assess_migration_complexity(self) -> str:
        """评估迁移复杂度"""
        if not self.dependency_graph:
            return "unknown"

        total_refs = sum(result.total_references for result in self.file_results.values())
        affected_files = len(self.dependency_graph.affected_files)
        critical_refs = sum(
            len([dep for dep in result.dependencies if dep.impact_level == ImpactLevel.CRITICAL])
            for result in self.file_results.values()
        )

        if critical_refs > 10 or affected_files > 50:
            return "high"
        elif critical_refs > 5 or affected_files > 20:
            return "medium"
        else:
            return "low"

    def get_migration_plan(self) -> Dict[str, Any]:
        """生成迁移计划建议"""
        if not self.dependency_graph:
            return {"error": "需要先运行依赖分析"}

        # 按影响级别排序文件
        files_by_impact = {level.value: [] for level in ImpactLevel}
        for file_path, result in self.file_results.items():
            if result.has_legacy_dependencies:
                impact_level = self._calculate_file_impact_level(result)
                files_by_impact[impact_level].append({
                    "file": file_path,
                    "references": result.total_references,
                    "dependencies": len(result.dependencies)
                })

        # 迁移阶段建议
        migration_phases = []

        # 阶段1：低影响文件
        if files_by_impact[ImpactLevel.LOW.value]:
            migration_phases.append({
                "phase": 1,
                "name": "低影响文件迁移",
                "description": "迁移配置引用和字符串引用",
                "files": files_by_impact[ImpactLevel.LOW.value],
                "estimated_effort": "低",
                "risk_level": "低"
            })

        # 阶段2：中等影响文件
        if files_by_impact[ImpactLevel.MEDIUM.value]:
            migration_phases.append({
                "phase": 2,
                "name": "中等影响文件迁移",
                "description": "迁移函数调用和属性访问",
                "files": files_by_impact[ImpactLevel.MEDIUM.value],
                "estimated_effort": "中等",
                "risk_level": "中等"
            })

        # 阶段3：高影响文件
        if files_by_impact[ImpactLevel.HIGH.value]:
            migration_phases.append({
                "phase": 3,
                "name": "高影响文件迁移",
                "description": "迁移导入和类实例化",
                "files": files_by_impact[ImpactLevel.HIGH.value],
                "estimated_effort": "高",
                "risk_level": "高"
            })

        # 阶段4：关键文件
        if files_by_impact[ImpactLevel.CRITICAL.value]:
            migration_phases.append({
                "phase": 4,
                "name": "关键文件迁移",
                "description": "迁移继承关系和核心组件",
                "files": files_by_impact[ImpactLevel.CRITICAL.value],
                "estimated_effort": "很高",
                "risk_level": "关键"
            })

        return {
            "migration_phases": migration_phases,
            "total_phases": len(migration_phases),
            "recommended_order": "按阶段顺序执行，每个阶段完成后进行测试",
            "risk_mitigation": [
                "在每个阶段前创建备份",
                "逐步迁移，每次只处理一个文件",
                "在每个阶段后运行完整测试",
                "保留传统数据源作为备用，直到迁移完全完成"
            ]
        }

    def save_analysis_report(self, file_path: str = None) -> str:
        """保存分析报告"""
        if not file_path:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = self.project_root / "reports" / f"dependency_analysis_{timestamp}.json"

        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        report_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "analysis_summary": self._generate_analysis_summary(),
            "migration_plan": self.get_migration_plan(),
            "dependency_graph": {
                "nodes": self.dependency_graph.nodes if self.dependency_graph else {},
                "edges": self.dependency_graph.edges if self.dependency_graph else [],
                "legacy_sources": list(self.dependency_graph.legacy_sources) if self.dependency_graph else [],
                "affected_files": list(self.dependency_graph.affected_files) if self.dependency_graph else []
            },
            "detailed_results": {
                file_path: {
                    "total_references": result.total_references,
                    "has_legacy_dependencies": result.has_legacy_dependencies,
                    "analysis_time": result.analysis_time,
                    "dependencies": [
                        {
                            "line_number": dep.line_number,
                            "dependency_type": dep.dependency_type.value,
                            "source_name": dep.source_name,
                            "reference_text": dep.reference_text,
                            "impact_level": dep.impact_level.value,
                            "function_name": dep.function_name,
                            "class_name": dep.class_name
                        }
                        for dep in result.dependencies
                    ]
                }
                for file_path, result in self.file_results.items()
                if result.has_legacy_dependencies
            }
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"依赖分析报告已保存: {file_path}")
        return str(file_path)


class DependencyVisitor(ast.NodeVisitor):
    """AST访问器，用于分析依赖关系"""

    def __init__(self, legacy_sources: Dict[str, Any], file_path: str, content: str):
        self.legacy_sources = legacy_sources
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')

        self.dependencies: List[DependencyReference] = []
        self.imports: List[str] = []
        self.classes: List[str] = []
        self.functions: List[str] = []

        self.current_class = None
        self.current_function = None

    def visit_Import(self, node):
        """访问import语句"""
        for alias in node.names:
            self.imports.append(alias.name)

            # 检查是否导入传统数据源
            for source_name, source_info in self.legacy_sources.items():
                if any(module in alias.name for module in source_info["module_names"]):
                    self._add_dependency(
                        node, DependencyType.IMPORT, source_name,
                        f"import {alias.name}"
                    )

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """访问from...import语句"""
        if node.module:
            module_name = node.module

            for alias in node.names:
                import_name = f"{module_name}.{alias.name}"
                self.imports.append(import_name)

                # 检查是否导入传统数据源
                for source_name, source_info in self.legacy_sources.items():
                    if (any(module in module_name for module in source_info["module_names"]) or
                            any(cls in alias.name for cls in source_info["class_names"])):
                        self._add_dependency(
                            node, DependencyType.IMPORT, source_name,
                            f"from {module_name} import {alias.name}"
                        )

        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """访问类定义"""
        self.classes.append(node.name)
        old_class = self.current_class
        self.current_class = node.name

        # 检查继承
        for base in node.bases:
            if isinstance(base, ast.Name):
                for source_name, source_info in self.legacy_sources.items():
                    if base.id in source_info["class_names"]:
                        self._add_dependency(
                            node, DependencyType.INHERITANCE, source_name,
                            f"class {node.name}({base.id})"
                        )

        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        """访问函数定义"""
        self.functions.append(node.name)
        old_function = self.current_function
        self.current_function = node.name

        self.generic_visit(node)
        self.current_function = old_function

    def visit_Call(self, node):
        """访问函数调用"""
        # 检查类实例化
        if isinstance(node.func, ast.Name):
            for source_name, source_info in self.legacy_sources.items():
                if node.func.id in source_info["class_names"]:
                    self._add_dependency(
                        node, DependencyType.CLASS_INSTANTIATION, source_name,
                        f"{node.func.id}()"
                    )

        # 检查函数调用
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            for source_name, source_info in self.legacy_sources.items():
                if any(pattern in attr_name for pattern in source_info["function_patterns"]):
                    self._add_dependency(
                        node, DependencyType.FUNCTION_CALL, source_name,
                        f"*.{attr_name}()"
                    )

        self.generic_visit(node)

    def visit_Attribute(self, node):
        """访问属性访问"""
        if isinstance(node.value, ast.Name):
            for source_name, source_info in self.legacy_sources.items():
                if (node.value.id in source_info["class_names"] or
                        any(pattern in node.attr for pattern in source_info["function_patterns"])):
                    self._add_dependency(
                        node, DependencyType.ATTRIBUTE_ACCESS, source_name,
                        f"{node.value.id}.{node.attr}"
                    )

        self.generic_visit(node)

    def visit_Str(self, node):
        """访问字符串字面量"""
        # 检查字符串中的配置引用
        for source_name, source_info in self.legacy_sources.items():
            for config_key in source_info["config_keys"]:
                if config_key.lower() in node.s.lower():
                    self._add_dependency(
                        node, DependencyType.STRING_REFERENCE, source_name,
                        f'"{node.s}"'
                    )

        self.generic_visit(node)

    def _add_dependency(self, node, dep_type: DependencyType, source_name: str, reference_text: str):
        """添加依赖引用"""
        # 获取上下文
        context_lines = []
        start_line = max(0, node.lineno - 3)
        end_line = min(len(self.lines), node.lineno + 2)

        for i in range(start_line, end_line):
            prefix = ">>> " if i == node.lineno - 1 else "    "
            context_lines.append(f"{prefix}{self.lines[i]}")

        context = "\n".join(context_lines)

        dependency = DependencyReference(
            file_path=self.file_path,
            line_number=node.lineno,
            column_number=getattr(node, 'col_offset', 0),
            dependency_type=dep_type,
            source_name=source_name,
            reference_text=reference_text,
            context=context,
            function_name=self.current_function,
            class_name=self.current_class
        )

        self.dependencies.append(dependency)


def analyze_project_dependencies(project_root: str = None) -> Tuple[Dict[str, Any], str]:
    """分析项目依赖关系的便捷函数"""
    analyzer = DependencyAnalyzer(project_root)
    summary = analyzer.analyze_project()
    report_file = analyzer.save_analysis_report()

    return summary, report_file


if __name__ == "__main__":
    # 测试代码
    print("开始分析传统数据源依赖关系...")

    analyzer = DependencyAnalyzer()
    summary = analyzer.analyze_project()

    print(f"\n依赖分析摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # 生成迁移计划
    migration_plan = analyzer.get_migration_plan()
    print(f"\n迁移计划:")
    print(json.dumps(migration_plan, indent=2, ensure_ascii=False))

    # 保存报告
    report_file = analyzer.save_analysis_report()
    print(f"\n详细报告已保存到: {report_file}")
