#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
算法版本管理器
支持算法版本的保存、回滚、比较和自动清理
"""

from loguru import logger

from core.database.unified_sqlite_access import UnifiedSQLiteAccess
from core.strategy_extensions import PerformanceMetrics, TradingPerformanceMetrics
from optimization.database_schema import OptimizationDatabaseManager
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class AlgorithmVersion:
    """算法版本数据类"""
    id: int
    pattern_id: int
    pattern_name: str
    version_number: int
    algorithm_code: str
    parameters: Dict[str, Any]
    created_time: str
    created_by: str
    description: str
    is_active: bool
    parent_version_id: Optional[int]
    optimization_method: str
    performance_metrics: Optional[TradingPerformanceMetrics] = None


class VersionManager:
    """算法版本管理器"""

    def __init__(self, db_path: str = 'data/factorweave_system.sqlite'):
        self.db_manager = OptimizationDatabaseManager(db_path)
        self.max_versions_per_pattern = 10  # 每个形态最多保留10个版本

    def save_version(self, pattern_id: int, pattern_name: str,
                     algorithm_code: str, parameters: Dict[str, Any],
                     description: str = "", optimization_method: str = "manual",
                     parent_version_id: Optional[int] = None,
                     performance_metrics: Optional[TradingPerformanceMetrics] = None,
                     created_by: str = "system") -> int:
        """
        保存新的算法版本

        Args:
            pattern_id: 形态ID
            pattern_name: 形态名称
            algorithm_code: 算法代码
            parameters: 算法参数
            description: 版本描述
            optimization_method: 优化方法
            parent_version_id: 父版本ID
            performance_metrics: 性能指标
            created_by: 创建者

        Returns:
            新版本的ID
        """
        logger.info(f" 保存算法版本: {pattern_name}")

        # 保存算法版本
        version_id = self.db_manager.save_algorithm_version(
            pattern_id=pattern_id,
            pattern_name=pattern_name,
            algorithm_code=algorithm_code,
            parameters=parameters,
            description=description,
            optimization_method=optimization_method,
            parent_version_id=parent_version_id,
            created_by=created_by
        )

        # 保存性能指标（如果有）
        if performance_metrics:
            metrics_dict = asdict(performance_metrics)
            self.db_manager.save_performance_metrics(
                version_id=version_id,
                pattern_name=pattern_name,
                metrics=metrics_dict
            )

        # 自动清理旧版本
        self._cleanup_old_versions(pattern_name)

        logger.info(f" 版本保存成功，版本ID: {version_id}")
        return version_id

    def get_versions(self, pattern_name: str, limit: int = 10) -> List[AlgorithmVersion]:
        """获取算法版本列表"""
        versions_data = self.db_manager.get_algorithm_versions(
            pattern_name, limit)
        versions = []

        for data in versions_data:
            # 获取性能指标
            performance_metrics = self._get_version_performance(data['id'])

            version = AlgorithmVersion(
                id=data['id'],
                pattern_id=0,  # 需要从数据库获取
                pattern_name=pattern_name,
                version_number=data['version_number'],
                algorithm_code=data['algorithm_code'],
                parameters=data['parameters'],
                created_time=data['created_time'],
                created_by=data.get('created_by', 'system'),
                description=data['description'],
                is_active=data['is_active'],
                parent_version_id=None,
                optimization_method=data['optimization_method'],
                performance_metrics=performance_metrics
            )
            versions.append(version)

        return versions

    def get_version_by_id(self, version_id: int) -> Optional[AlgorithmVersion]:
        db = UnifiedSQLiteAccess.get_instance(self.db_manager.db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, pattern_id, pattern_name, version_number, algorithm_code, 
                       parameters, created_time, created_by, description, is_active,
                       parent_version_id, optimization_method
                FROM algorithm_versions 
                WHERE id = ?
            ''', (version_id,))

            row = cursor.fetchone()

            if not row:
                return None

            performance_metrics = self._get_version_performance(version_id)

            return AlgorithmVersion(
                id=row[0],
                pattern_id=row[1],
                pattern_name=row[2],
                version_number=row[3],
                algorithm_code=row[4],
                parameters=json.loads(row[5]) if row[5] else {},
                created_time=row[6],
                created_by=row[7],
                description=row[8],
                is_active=bool(row[9]),
                parent_version_id=row[10],
                optimization_method=row[11],
                performance_metrics=performance_metrics
            )

    def activate_version(self, version_id: int) -> bool:
        version = self.get_version_by_id(version_id)
        if not version:
            return False

        db = UnifiedSQLiteAccess.get_instance(self.db_manager.db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute('''
                    UPDATE algorithm_versions 
                    SET is_active = 0 
                    WHERE pattern_name = ?
                ''', (version.pattern_name,))

                cursor.execute('''
                    UPDATE algorithm_versions 
                    SET is_active = 1 
                    WHERE id = ?
                ''', (version_id,))

                cursor.execute('''
                    UPDATE pattern_types 
                    SET algorithm_code = ?, parameters = ?
                    WHERE name = ?
                ''', (version.algorithm_code, json.dumps(version.parameters), version.pattern_name))

                logger.info(f" 版本 {version.version_number} 已激活: {version.pattern_name}")
                return True

            except Exception as e:
                logger.info(f" 激活版本失败: {e}")
                return False

    def rollback_to_version(self, pattern_name: str, version_number: int) -> bool:
        """回滚到指定版本"""
        logger.info(f"回滚 {pattern_name} 到版本 {version_number}")

        # 获取指定版本
        versions = self.get_versions(pattern_name)
        target_version = None

        for version in versions:
            if version.version_number == version_number:
                target_version = version
                break

        if not target_version:
            logger.info(f" 未找到版本 {version_number}")
            return False

        # 激活该版本
        return self.activate_version(target_version.id)

    def compare_versions(self, version_id1: int, version_id2: int) -> Dict[str, Any]:
        """比较两个版本"""
        version1 = self.get_version_by_id(version_id1)
        version2 = self.get_version_by_id(version_id2)

        if not version1 or not version2:
            return {"error": "版本不存在"}

        comparison = {
            "version1": {
                "id": version1.id,
                "version_number": version1.version_number,
                "created_time": version1.created_time,
                "optimization_method": version1.optimization_method,
                "description": version1.description
            },
            "version2": {
                "id": version2.id,
                "version_number": version2.version_number,
                "created_time": version2.created_time,
                "optimization_method": version2.optimization_method,
                "description": version2.description
            },
            "code_diff": self._compare_code(version1.algorithm_code, version2.algorithm_code),
            "parameter_diff": self._compare_parameters(version1.parameters, version2.parameters),
            "performance_diff": self._compare_performance(
                version1.performance_metrics, version2.performance_metrics
            )
        }

        return comparison

    def get_version_history(self, pattern_name: str) -> List[Dict[str, Any]]:
        """获取版本历史记录"""
        versions = self.get_versions(pattern_name, limit=50)

        history = []
        for version in versions:
            record = {
                "id": version.id,
                "version_number": version.version_number,
                "created_time": version.created_time,
                "optimization_method": version.optimization_method,
                "description": version.description,
                "is_active": version.is_active,
                "performance_summary": self._get_performance_summary(version.performance_metrics)
            }
            history.append(record)

        return history

    def delete_version(self, version_id: int) -> bool:
        version = self.get_version_by_id(version_id)
        if not version:
            return False

        if version.is_active:
            logger.info("不能删除激活的版本")
            return False

        db = UnifiedSQLiteAccess.get_instance(self.db_manager.db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute(
                    'DELETE FROM performance_metrics WHERE version_id = ?', (version_id,))

                cursor.execute(
                    'DELETE FROM algorithm_versions WHERE id = ?', (version_id,))

                logger.info(f" 版本 {version.version_number} 已删除")
                return True

            except Exception as e:
                logger.info(f" 删除版本失败: {e}")
                return False

    def get_best_version(self, pattern_name: str) -> Optional[AlgorithmVersion]:
        """获取性能最佳的版本"""
        versions = self.get_versions(pattern_name)

        best_version = None
        best_score = -1

        for version in versions:
            if version.performance_metrics and version.performance_metrics.overall_score > best_score:
                best_score = version.performance_metrics.overall_score
                best_version = version

        return best_version

    def create_branch(self, base_version_id: int, branch_description: str) -> int:
        """基于现有版本创建分支"""
        base_version = self.get_version_by_id(base_version_id)
        if not base_version:
            raise ValueError("基础版本不存在")

        # 创建新版本作为分支
        branch_version_id = self.save_version(
            pattern_id=base_version.pattern_id,
            pattern_name=base_version.pattern_name,
            algorithm_code=base_version.algorithm_code,
            parameters=base_version.parameters,
            description=f"分支: {branch_description}",
            optimization_method="branch",
            parent_version_id=base_version_id,
            created_by="branch"
        )

        return branch_version_id

    def _get_version_performance(self, version_id: int) -> Optional[TradingPerformanceMetrics]:
        db = UnifiedSQLiteAccess.get_instance(self.db_manager.db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM performance_metrics 
                WHERE version_id = ? 
                ORDER BY test_time DESC 
                LIMIT 1
            ''', (version_id,))

            row = cursor.fetchone()

            if not row:
                return None

            columns = [
                'id', 'version_id', 'pattern_name', 'test_dataset_id',
                'true_positives', 'false_positives', 'true_negatives', 'false_negatives',
                'precision', 'recall', 'f1_score', 'accuracy',
                'execution_time', 'memory_usage', 'cpu_usage',
                'signal_quality', 'confidence_avg', 'confidence_std', 'patterns_found',
                'robustness_score', 'parameter_sensitivity', 'overall_score',
                'test_time', 'test_conditions'
            ]

            data = dict(zip(columns, row))

            return TradingPerformanceMetrics(
                true_positives=data.get('true_positives', 0),
                false_positives=data.get('false_positives', 0),
                true_negatives=data.get('true_negatives', 0),
                false_negatives=data.get('false_negatives', 0),
                precision=data.get('precision', 0.0),
                recall=data.get('recall', 0.0),
                f1_score=data.get('f1_score', 0.0),
                accuracy=data.get('accuracy', 0.0),
                execution_time=data.get('execution_time', 0.0),
                memory_usage=data.get('memory_usage', 0.0),
                cpu_usage=data.get('cpu_usage', 0.0),
                signal_quality=data.get('signal_quality', 0.0),
                confidence_avg=data.get('confidence_avg', 0.0),
                confidence_std=data.get('confidence_std', 0.0),
                patterns_found=data.get('patterns_found', 0),
                robustness_score=data.get('robustness_score', 0.0),
                parameter_sensitivity=data.get('parameter_sensitivity', 0.0),
                overall_score=data.get('overall_score', 0.0)
            )

    def _cleanup_old_versions(self, pattern_name: str):
        """清理旧版本"""
        self.db_manager.cleanup_old_versions(
            pattern_name, self.max_versions_per_pattern)

    def _compare_code(self, code1: str, code2: str) -> Dict[str, Any]:
        """比较代码差异"""
        import difflib

        lines1 = code1.splitlines()
        lines2 = code2.splitlines()

        diff = list(difflib.unified_diff(lines1, lines2, lineterm=''))

        return {
            "has_changes": len(diff) > 0,
            "diff_lines": diff,
            "similarity": difflib.SequenceMatcher(None, code1, code2).ratio()
        }

    def _compare_parameters(self, params1: Dict[str, Any], params2: Dict[str, Any]) -> Dict[str, Any]:
        """比较参数差异"""
        all_keys = set(params1.keys()) | set(params2.keys())

        changes = {}
        for key in all_keys:
            val1 = params1.get(key)
            val2 = params2.get(key)

            if val1 != val2:
                changes[key] = {
                    "old_value": val1,
                    "new_value": val2
                }

        return {
            "has_changes": len(changes) > 0,
            "changes": changes
        }

    def _compare_performance(self, metrics1: Optional[TradingPerformanceMetrics],
                             metrics2: Optional[TradingPerformanceMetrics]) -> Dict[str, Any]:
        """比较性能差异"""
        if not metrics1 or not metrics2:
            return {"error": "缺少性能数据"}

        comparisons = {}

        # 比较关键指标
        key_metrics = [
            'overall_score', 'signal_quality', 'confidence_avg',
            'execution_time', 'robustness_score', 'patterns_found'
        ]

        for metric in key_metrics:
            val1 = getattr(metrics1, metric, 0)
            val2 = getattr(metrics2, metric, 0)

            if val1 > 0:
                improvement = (val2 - val1) / val1 * 100
            else:
                improvement = 0

            comparisons[metric] = {
                "old_value": val1,
                "new_value": val2,
                "improvement_percent": improvement
            }

        return comparisons

    def _get_performance_summary(self, metrics: Optional[TradingPerformanceMetrics]) -> Dict[str, Any]:
        """获取性能摘要"""
        if not metrics:
            return {"status": "无性能数据"}

        return {
            "overall_score": metrics.overall_score,
            "signal_quality": metrics.signal_quality,
            "confidence_avg": metrics.confidence_avg,
            "execution_time": metrics.execution_time,
            "patterns_found": metrics.patterns_found
        }

    def export_version(self, version_id: int, export_path: str) -> bool:
        """导出版本到文件"""
        version = self.get_version_by_id(version_id)
        if not version:
            return False

        try:
            export_data = {
                "version_info": asdict(version),
                "export_time": datetime.now().isoformat(),
                "export_format_version": "1.0"
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f" 版本已导出到: {export_path}")
            return True

        except Exception as e:
            logger.info(f" 导出失败: {e}")
            return False

    def import_version(self, import_path: str, pattern_name: str) -> Optional[int]:
        """从文件导入版本"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            version_info = import_data['version_info']

            # 保存导入的版本
            version_id = self.save_version(
                pattern_id=0,  # 需要查找正确的pattern_id
                pattern_name=pattern_name,
                algorithm_code=version_info['algorithm_code'],
                parameters=version_info['parameters'],
                description=f"导入版本: {version_info.get('description', '')}",
                optimization_method="import",
                created_by="import"
            )

            logger.info(f" 版本已导入，新版本ID: {version_id}")
            return version_id

        except Exception as e:
            logger.info(f" 导入失败: {e}")
            return None


def create_version_manager(db_path: str = 'data/factorweave_system.sqlite') -> VersionManager:
    """创建版本管理器实例"""
    return VersionManager(db_path)


if __name__ == "__main__":
    # 测试版本管理器
    manager = create_version_manager()

    # 获取锤头线的版本历史
    history = manager.get_version_history("hammer")
    logger.info(f"锤头线版本历史: {len(history)} 个版本")

    for record in history[:3]:  # 显示前3个版本
        logger.info(f"  版本 {record['version_number']}: {record['description']}")
        logger.info(f"    创建时间: {record['created_time']}")
        logger.info(f"    优化方法: {record['optimization_method']}")
        logger.info(f"    是否激活: {record['is_active']}")
        logger.info("")
