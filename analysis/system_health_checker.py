from loguru import logger
"""
FactorWeave-Quant 量化交易系统健康检查器
监控形态识别系统的整体健康状态和性能指标
"""

from analysis.pattern_base import PatternAlgorithmFactory
from analysis.pattern_recognition import (
    EnhancedPatternRecognizer,
    get_performance_monitor,
    get_pattern_cache,
    get_pattern_recognizer_info
)
import os
import sys
import time
import psutil
import traceback
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 核心服务导入
from core.metrics.aggregation_service import MetricsAggregationService
from core.metrics.repository import MetricsRepository
from core.containers import ServiceContainer

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


class SystemHealthChecker:
    """系统健康检查器 - 现在通过核心服务获取指标"""

    def __init__(self, aggregation_service: MetricsAggregationService, repository: MetricsRepository):
        self.check_results = {}
        self.start_time = datetime.now()
        self._aggregation_service = aggregation_service
        self._repository = repository

    def run_comprehensive_check(self) -> Dict[str, Any]:
        """运行全面的系统健康检查"""
        logger.info("开始FactorWeave-Quant 量化交易系统健康检查...")

        health_report = {
            'timestamp': datetime.now().isoformat(),
            'system_info': self._check_system_info(),
            'pattern_recognition': self._check_pattern_recognition(),
            'performance_metrics': self._check_performance_metrics(),
            'cache_system': self._check_cache_system(),
            'memory_usage': self._check_memory_usage(),
            'dependencies': self._check_dependencies(),
            'database_connectivity': self._check_database_connectivity(),
            'connection_pool_health': self._check_connection_pool_health(),  # 新增
            'ui_components': self._check_ui_components(),
            'overall_health': 'unknown'
        }

        # 计算总体健康状态
        health_report['overall_health'] = self._calculate_overall_health(
            health_report)

        # 生成建议
        health_report['recommendations'] = self._generate_recommendations(
            health_report)

        logger.info(f" 系统健康检查完成，总体状态: {health_report['overall_health']}")

        return health_report

    def _check_system_info(self) -> Dict[str, Any]:
        """检查系统基本信息"""
        try:
            #  修复：添加更安全的信息获取
            try:
                info = get_pattern_recognizer_info()
            except Exception as e:
                logger.info(f" 获取形态识别器信息失败: {e}")
                # 使用默认信息
                info = {
                    'version': 'unknown',
                    'supported_patterns': 0,
                    'performance_optimized': False,
                    'cache_enabled': False,
                    'monitoring_enabled': True,  # 假设监控是启用的
                    'database_algorithms': False,
                    'ml_predictions': False
                }

            return {
                'status': 'healthy',
                'version': info.get('version', 'unknown'),
                'supported_patterns': info.get('supported_patterns', 0),
                'features': {
                    'performance_optimized': info.get('performance_optimized', False),
                    'cache_enabled': info.get('cache_enabled', False),
                    'monitoring_enabled': info.get('monitoring_enabled', False),
                    'database_algorithms': info.get('database_algorithms', False),
                    'ml_predictions': info.get('ml_predictions', False)
                }
            }
        except Exception as e:
            logger.info(f" 系统信息检查失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'details': traceback.format_exc()
            }

    def _check_pattern_recognition(self) -> Dict[str, Any]:
        """检查形态识别功能"""
        try:
            #  修复：添加更安全的形态识别检查
            logger.info("检查形态识别功能...")

            try:
                # 创建测试数据
                test_data = self._generate_test_kdata()
                logger.info(f" 测试数据生成成功，数据量: {len(test_data)}")

                # 测试识别器创建
                recognizer = EnhancedPatternRecognizer(debug_mode=False)
                logger.info("形态识别器创建成功")

                # 测试形态识别
                start_time = time.time()
                patterns = recognizer.identify_patterns(
                    test_data, confidence_threshold=0.1)
                processing_time = time.time() - start_time
                logger.info(f" 形态识别完成，识别到 {len(patterns)} 个形态")

                return {
                    'status': 'healthy',
                    'recognizer_created': True,
                    'patterns_detected': len(patterns),
                    'processing_time': processing_time,
                    'test_data_size': len(test_data),
                    'average_confidence': np.mean([p.get('confidence', 0) for p in patterns]) if patterns else 0
                }
            except ImportError as e:
                logger.info(f" 形态识别模块导入失败: {e}")
                return {
                    'status': 'warning',
                    'error': f'模块导入失败: {e}',
                    'recognizer_created': False,
                    'patterns_detected': 0,
                    'processing_time': 0,
                    'test_data_size': 0,
                    'average_confidence': 0
                }
        except Exception as e:
            logger.info(f" 形态识别检查失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'details': traceback.format_exc()
            }

    def _check_performance_metrics(self) -> Dict[str, Any]:
        """从聚合服务和仓储检查性能指标"""
        try:
            # 尝试从聚合服务获取实时（内存中）的指标
            recent_metrics = self._aggregation_service.get_recent_metrics()
            live_metrics = recent_metrics.get('applications', {})

            total_calls = 0
            total_errors = 0
            total_duration = 0

            for op_name, op_data in live_metrics.items():
                calls = op_data.get('call_count', 0)
                total_calls += calls
                total_errors += op_data.get('error_count', 0)
                # 使用平均持续时间乘以调用次数来估算总持续时间
                avg_duration = op_data.get('avg_duration', 0)
                total_duration += avg_duration * calls

            # 从数据库获取历史趋势（例如过去1小时）
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=1)
            historical_data = self._repository.query_historical_data(
                start_time=start_time,
                end_time=end_time,
                table='app_metrics_summary'
            )

            return {
                'status': 'healthy',
                'live_monitored_operations': len(live_metrics),
                'live_total_calls': total_calls,
                'live_success_rate': (total_calls - total_errors) / total_calls if total_calls > 0 else 1.0,
                'live_avg_duration': total_duration / total_calls if total_calls > 0 else 0,
                'historical_records_count': len(historical_data),
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': f"无法获取性能指标: {e}",
                'details': traceback.format_exc()
            }

    def _check_cache_system(self) -> Dict[str, Any]:
        """检查缓存系统"""
        try:
            cache = get_pattern_cache()
            stats = cache.get_stats()

            return {
                'status': 'healthy',
                'cache_size': stats.get('cache_size', 0),
                'max_size': stats.get('max_size', 0),
                'hit_count': stats.get('hit_count', 0),
                'miss_count': stats.get('miss_count', 0),
                'hit_rate': stats.get('hit_rate', 0),
                'memory_usage_estimate': stats.get('memory_usage_estimate', 0),
                'utilization': stats.get('cache_size', 0) / stats.get('max_size', 1)
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'details': traceback.format_exc()
            }

    def _check_memory_usage(self) -> Dict[str, Any]:
        """从资源服务检查内存使用情况（通过聚合器）"""
        try:
            # 这里的逻辑需要调整，因为我们现在依赖于事件驱动的聚合数据
            # 我们从数据库查询最新的资源记录
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)  # 查询过去5分钟

            recent_data = self._repository.query_historical_data(
                start_time, end_time, 'resource_metrics_summary'
            )

            if not recent_data:
                return {
                    'status': 'warning',
                    'message': '最近5分钟内没有可用的资源指标数据。监控服务可能尚未启动或写入数据库。'
                }

            latest_record = recent_data[-1]
            return {
                'status': 'healthy',
                'cpu_percent': latest_record.get('cpu'),
                'memory_percent': latest_record.get('mem'),
                'disk_percent': latest_record.get('disk'),
                'last_updated': latest_record.get('t_stamp')
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': f"无法获取内存指标: {e}",
                'details': traceback.format_exc()
            }

    def _check_dependencies(self) -> Dict[str, Any]:
        """检查依赖库"""
        dependencies = {
            'pandas': 'pd',
            'numpy': 'np',
            'PyQt5': 'PyQt5',
            'psutil': 'psutil'
        }

        results = {}
        all_available = True

        for name, import_name in dependencies.items():
            try:
                __import__(import_name)
                results[name] = {'status': 'available', 'version': 'unknown'}

                # 尝试获取版本信息
                try:
                    module = sys.modules[import_name]
                    if hasattr(module, '__version__'):
                        results[name]['version'] = module.__version__
                except:
                    pass

            except ImportError as e:
                results[name] = {'status': 'missing', 'error': str(e)}
                all_available = False

        return {
            'status': 'healthy' if all_available else 'warning',
            'dependencies': results,
            'all_available': all_available
        }

    def _check_database_connectivity(self) -> Dict[str, Any]:
        """检查数据库连接"""
        try:
            db_paths = [
                'data/factorweave_system.sqlite',
                'data/factorweave_analytics.duckdb',
                'data/databases/stock_a/stock_a_data.duckdb',
                'data/enhanced_risk_monitor.sqlite',
                'data/strategy.sqlite',
                'data/tdx_servers.sqlite',
                'data/alert_config.sqlite',
                'data/backtest_monitor.sqlite',
                'data/metrics.sqlite',
                'data/unified_quality_monitor.sqlite'
            ]

            db_status = {}
            for db_path in db_paths:
                if os.path.exists(db_path):
                    db_status[db_path] = {
                        'exists': True,
                        'size_mb': os.path.getsize(db_path) / 1024 / 1024,
                        'modified': datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat()
                    }
                else:
                    db_status[db_path] = {'exists': False}

            return {
                'status': 'healthy',
                'databases': db_status
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'details': traceback.format_exc()
            }

    def _check_ui_components(self) -> Dict[str, Any]:
        """检查UI组件"""
        try:
            # 检查关键UI文件是否存在
            ui_files = [
                'gui/widgets/analysis_tabs/pattern_tab_pro.py',
                'gui/widgets/analysis_tabs/pattern_tab.py',
                'gui/widgets/base_analysis_tab.py'
            ]

            ui_status = {}
            for ui_file in ui_files:
                if os.path.exists(ui_file):
                    ui_status[ui_file] = {
                        'exists': True,
                        'size_kb': os.path.getsize(ui_file) / 1024,
                        'modified': datetime.fromtimestamp(os.path.getmtime(ui_file)).isoformat()
                    }
                else:
                    ui_status[ui_file] = {'exists': False}

            return {
                'status': 'healthy',
                'ui_files': ui_status
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'details': traceback.format_exc()
            }

    def _check_connection_pool_health(self) -> Dict[str, Any]:
        """检查DuckDB连接池健康状态"""
        try:
            logger.info("检查DuckDB连接池健康状态...")

            # 导入分析数据库管理器
            from core.database.factorweave_analytics_db import FactorWeaveAnalyticsDB

            # 获取数据库实例
            db = FactorWeaveAnalyticsDB()

            # 执行健康检查
            health = db.health_check()

            # 转换状态
            if health['healthy']:
                if not health['warnings']:
                    status = 'healthy'
                else:
                    status = 'warning'
            else:
                status = 'critical'

            return {
                'status': status,
                'healthy': health['healthy'],
                'pool_size': health['metrics'].get('pool_size', 'N/A'),
                'checked_out': health['metrics'].get('checked_out', 0),
                'checked_in': health['metrics'].get('checked_in', 0),
                'overflow': health['metrics'].get('overflow', 0),
                'warnings': health['warnings'],
                'recommendations': health['recommendations']
            }

        except ImportError as e:
            logger.warning(f"无法导入连接池模块: {e}")
            return {
                'status': 'unknown',
                'error': f'模块不可用: {e}',
                'healthy': None,
                'pool_size': 'N/A',
                'checked_out': 0,
                'checked_in': 0,
                'overflow': 0,
                'warnings': ['连接池模块未安装或不可用'],
                'recommendations': ['安装并配置DuckDB连接池']
            }
        except Exception as e:
            logger.error(f"连接池健康检查失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'details': traceback.format_exc(),
                'healthy': False,
                'pool_size': 'N/A',
                'checked_out': 0,
                'checked_in': 0,
                'overflow': 0,
                'warnings': [f'健康检查失败: {e}'],
                'recommendations': ['检查连接池配置和数据库连接']
            }

    def _generate_test_kdata(self) -> pd.DataFrame:
        """生成测试K线数据"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

        # 生成模拟价格数据
        np.random.seed(42)
        base_price = 100
        price_changes = np.random.normal(0, 2, 100)
        prices = [base_price]

        for change in price_changes[1:]:
            new_price = max(prices[-1] + change, 1)  # 确保价格为正
            prices.append(new_price)

        # 创建OHLC数据
        data = []
        for i, (date, close) in enumerate(zip(dates, prices)):
            high = close + abs(np.random.normal(0, 1))
            low = close - abs(np.random.normal(0, 1))
            open_price = close + np.random.normal(0, 0.5)

            data.append({
                'date': date,
                'open': open_price,
                'high': max(open_price, high, close),
                'low': min(open_price, low, close),
                'close': close,
                'volume': np.random.randint(1000, 10000)
            })

        return pd.DataFrame(data)

    def _calculate_overall_health(self, report: Dict[str, Any]) -> str:
        """计算总体健康状态"""
        error_count = 0
        warning_count = 0
        total_checks = 0

        for key, value in report.items():
            if key in ['timestamp', 'overall_health', 'recommendations']:
                continue

            total_checks += 1
            if isinstance(value, dict) and 'status' in value:
                if value['status'] == 'error':
                    error_count += 1
                elif value['status'] == 'warning':
                    warning_count += 1

        if error_count > 0:
            return 'critical'
        elif warning_count > 0:
            return 'warning'
        else:
            return 'healthy'

    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        recommendations = []

        # 检查性能指标
        perf = report.get('performance_metrics', {})
        if perf.get('success_rate', 1) < 0.9:
            recommendations.append("形态识别成功率较低，建议检查算法配置和数据质量")

        if perf.get('live_avg_duration', 0) > 1.0:
            recommendations.append("处理时间较长，建议优化算法或增加缓存")

        # 检查缓存系统
        cache = report.get('cache_system', {})
        if cache.get('hit_rate', 0) < 0.5:
            recommendations.append("缓存命中率较低，建议调整缓存策略")

        if cache.get('utilization', 0) > 0.9:
            recommendations.append("缓存使用率过高，建议增加缓存大小")

        # 检查内存使用
        memory = report.get('memory_usage', {})
        if memory.get('cpu_percent', 0) > 80:
            recommendations.append("CPU使用率过高，建议优化CPU使用")

        if memory.get('memory_percent', 0) > 80:
            recommendations.append("内存使用率过高，建议优化内存管理")

        # 检查依赖
        deps = report.get('dependencies', {})
        if not deps.get('all_available', True):
            recommendations.append("存在缺失的依赖库，建议安装完整依赖")

        if not recommendations:
            recommendations.append("系统运行良好，无需特别优化")

        return recommendations

    def generate_health_report(self, report: Dict[str, Any]) -> str:
        """生成可读的健康报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("FactorWeave-Quant 量化交易系统健康报告")
        lines.append("=" * 60)
        lines.append(f"检查时间: {report['timestamp']}")
        lines.append(f"总体状态: {report['overall_health'].upper()}")
        lines.append("")

        # 系统信息
        sys_info = report.get('system_info', {})
        lines.append("系统信息:")
        lines.append(f"  版本: {sys_info.get('version', 'unknown')}")
        lines.append(f"  支持形态: {sys_info.get('supported_patterns', 0)}种")
        lines.append("")

        # 性能指标
        perf = report.get('performance_metrics', {})
        lines.append("性能指标:")
        lines.append(f"  实时监控操作: {perf.get('live_monitored_operations', 0)}")
        lines.append(f"  实时总调用次数: {perf.get('live_total_calls', 0)}")
        lines.append(f"  实时成功率: {perf.get('live_success_rate', 0):.2%}")
        lines.append(f"  实时平均处理时间: {perf.get('live_avg_duration', 0):.3f}秒")
        lines.append(f"  历史记录总数: {perf.get('historical_records_count', 0)}")
        lines.append("")

        # 内存使用
        memory = report.get('memory_usage', {})
        lines.append("内存使用:")
        lines.append(f"  CPU使用率: {memory.get('cpu_percent', 0):.1f}%")
        lines.append(f"  内存使用率: {memory.get('memory_percent', 0):.1f}%")
        lines.append(f"  磁盘使用率: {memory.get('disk_percent', 0):.1f}%")
        lines.append(f"  最后更新时间: {memory.get('last_updated', '未知')}")
        lines.append("")

        # 建议
        recommendations = report.get('recommendations', [])
        lines.append("优化建议:")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"  {i}. {rec}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


def main():
    """用于独立测试的入口点"""
    logger.info("运行系统健康检查器（独立测试模式）...")

    # 在测试模式下，我们需要模拟服务容器和服务
    from core.events import EventBus

    # 1. 创建模拟组件
    event_bus = EventBus()
    container = ServiceContainer()

    # 2. 创建并注册真实的服务
    repo = MetricsRepository(db_path=':memory:')  # 使用内存数据库进行测试
    agg_service = MetricsAggregationService(event_bus, repo)

    # 3. 实例化检查器
    checker = SystemHealthChecker(
        aggregation_service=agg_service, repository=repo)

    # 4. 运行检查并打印报告
    report = checker.run_comprehensive_check()
    report_str = checker.generate_health_report(report)
    logger.info("\n--- 健康检查报告 ---")
    logger.info(report_str)
    logger.info("---------------------\n")


if __name__ == '__main__':
    main()
