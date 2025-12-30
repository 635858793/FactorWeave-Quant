from loguru import logger
"""
回测结果管理器

功能：
1. 存储、管理和分发回测结果
2. 支持内存存储和持久化存储
3. 提供添加、获取、删除回测结果的方法
4. 支持事件通知机制
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from threading import Lock

from core.events import EventBus, get_event_bus, AnalysisCompleteEvent
from core.services.cache_service import CacheService

@dataclass
class BacktestResult:
    """回测结果数据类"""
    stock_code: str  # 股票代码
    stock_name: str  # 股票名称
    strategy_name: str  # 策略名称
    backtest_time: float  # 回测时间戳
    backtest_results: Dict[str, Any]  # 回测结果
    trades: List[Dict[str, Any]]  # 交易记录
    duration: float  # 回测耗时（秒）
    is_professional: bool = False  # 是否为专业回测
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestResult':
        """从字典创建实例"""
        return cls(**data)

class BacktestResultManager:
    """回测结果管理器"""
    
    def __init__(self, event_bus: Optional[EventBus] = None, cache_service: Optional[CacheService] = None):
        """初始化回测结果管理器
        
        Args:
            event_bus: 事件总线实例，用于发布回测结果更新事件
            cache_service: 缓存服务实例，用于持久化存储
        """
        self._event_bus = event_bus or get_event_bus()
        self._cache_service = cache_service
        
        # 内存存储：股票代码 -> 回测结果列表
        self._results: Dict[str, List[BacktestResult]] = {}
        self._lock = Lock()  # 线程安全锁
        
        # 持久化配置
        self._persistence_enabled = True
        self._persistence_dir = os.path.join("data", "backtest_results")
        
        # 初始化持久化目录
        self._init_persistence_dir()
        
        # 加载历史回测结果
        self.load_results()
        
        logger.info("BacktestResultManager初始化完成")
    
    def _init_persistence_dir(self) -> None:
        """初始化持久化目录"""
        try:
            if not os.path.exists(self._persistence_dir):
                os.makedirs(self._persistence_dir)
        except Exception as e:
            logger.error(f"初始化持久化目录失败: {e}")
    
    def add_result(self, result: BacktestResult) -> None:
        """添加回测结果
        
        Args:
            result: 回测结果实例
        """
        with self._lock:
            # 确保股票代码对应的列表存在
            if result.stock_code not in self._results:
                self._results[result.stock_code] = []
            
            # 添加回测结果
            self._results[result.stock_code].append(result)
            
            # 限制每个股票的回测结果数量（保留最新10个）
            if len(self._results[result.stock_code]) > 10:
                self._results[result.stock_code] = self._results[result.stock_code][-10:]
            
            # 保存回测结果
            self.save_results(result.stock_code)
            
        # 发布回测完成事件
        self._event_bus.publish(AnalysisCompleteEvent(
            stock_code=result.stock_code,
            analysis_type="backtest",
            results={
                "backtest": {
                    "is_professional": result.is_professional,
                    "results": result.backtest_results,
                    "trades": result.trades
                }
            }
        ))
        
        logger.info(f"添加回测结果: {result.stock_code} - {result.strategy_name}")
    
    def get_latest_result(self, stock_code: str) -> Optional[BacktestResult]:
        """获取最新的回测结果
        
        Args:
            stock_code: 股票代码
            
        Returns:
            最新的回测结果，如果没有则返回None
        """
        with self._lock:
            if stock_code in self._results and self._results[stock_code]:
                return self._results[stock_code][-1]
            return None
    
    def get_results(self, stock_code: str) -> List[BacktestResult]:
        """获取指定股票的所有回测结果
        
        Args:
            stock_code: 股票代码
            
        Returns:
            回测结果列表
        """
        with self._lock:
            return self._results.get(stock_code, [])
    
    def clear_results(self, stock_code: Optional[str] = None) -> None:
        """清空回测结果
        
        Args:
            stock_code: 股票代码，如果为None则清空所有结果
        """
        with self._lock:
            if stock_code:
                if stock_code in self._results:
                    del self._results[stock_code]
                    # 删除持久化文件
                    self._delete_persistence_file(stock_code)
            else:
                # 清空所有结果
                self._results.clear()
                # 删除所有持久化文件
                self._delete_all_persistence_files()
        
        logger.info(f"清空回测结果: {stock_code if stock_code else '所有'}")
    
    def delete_result(self, stock_code: str, result_index: int) -> bool:
        """删除指定股票的指定回测结果
        
        Args:
            stock_code: 股票代码
            result_index: 回测结果索引
            
        Returns:
            是否删除成功
        """
        with self._lock:
            if stock_code in self._results and 0 <= result_index < len(self._results[stock_code]):
                del self._results[stock_code][result_index]
                self.save_results(stock_code)
                logger.info(f"删除回测结果: {stock_code} 第{result_index}条")
                return True
            logger.warning(f"删除回测结果失败: {stock_code} 索引{result_index}无效")
            return False
    
    def get_filtered_results(self, stock_code: Optional[str] = None, 
                          strategy_name: Optional[str] = None, 
                          start_time: Optional[float] = None, 
                          end_time: Optional[float] = None,
                          min_return: Optional[float] = None,
                          max_return: Optional[float] = None,
                          min_success_rate: Optional[float] = None,
                          max_success_rate: Optional[float] = None,
                          page: int = 1,
                          page_size: int = 10) -> Tuple[List[BacktestResult], int]:
        """获取过滤后的回测结果，支持分页
        
        Args:
            stock_code: 股票代码，None表示所有股票
            strategy_name: 策略名称，支持模糊匹配
            start_time: 开始时间戳
            end_time: 结束时间戳
            min_return: 最小收益率
            max_return: 最大收益率
            min_success_rate: 最小成功率
            max_success_rate: 最大成功率
            page: 页码，从1开始
            page_size: 每页大小
            
        Returns:
            (过滤后的回测结果列表, 总结果数)
        """
        with self._lock:
            # 收集所有符合条件的结果
            all_results = []
            stocks_to_check = [stock_code] if stock_code else self._results.keys()
            
            for sc in stocks_to_check:
                if sc in self._results:
                    for result in self._results[sc]:
                        # 应用过滤条件
                        if strategy_name and strategy_name not in result.strategy_name:
                            continue
                        if start_time and result.backtest_time < start_time:
                            continue
                        if end_time and result.backtest_time > end_time:
                            continue
                        
                        # 收益率过滤
                        return_value = 0.0
                        if isinstance(result.backtest_results, dict):
                            return_value = result.backtest_results.get('avg_return', 0)
                            # 兼容不同的回测结果格式
                            if return_value == 0 and 'risk_metrics' in result.backtest_results:
                                return_value = result.backtest_results['risk_metrics'].get('总收益率', 0)
                            elif return_value == 0 and 'performance' in result.backtest_results:
                                return_value = result.backtest_results['performance'].get('total_return', 0)
                        if min_return is not None and return_value < min_return:
                            continue
                        if max_return is not None and return_value > max_return:
                            continue
                        
                        # 成功率过滤
                        success_rate = 0.0
                        if isinstance(result.backtest_results, dict):
                            success_rate = result.backtest_results.get('success_rate', 0)
                            # 兼容不同的回测结果格式
                            if success_rate == 0 and 'performance' in result.backtest_results:
                                success_rate = result.backtest_results['performance'].get('win_rate', 0)
                        if min_success_rate is not None and success_rate < min_success_rate:
                            continue
                        if max_success_rate is not None and success_rate > max_success_rate:
                            continue
                        
                        all_results.append(result)
            
            # 按时间倒序排序
            all_results.sort(key=lambda x: x.backtest_time, reverse=True)
            
            # 分页处理
            total = len(all_results)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_results = all_results[start:end]
            
            logger.info(f"过滤回测结果: 共{total}条，返回{len(paginated_results)}条")
            return paginated_results, total
    
    def export_results(self, 
                    file_path: str, 
                    file_format: str = 'json',
                    **filter_params) -> bool:
        """导出回测结果
        
        Args:
            file_path: 文件路径
            file_format: 文件格式，支持json、csv、excel
            **filter_params: 过滤参数
            
        Returns:
            是否导出成功
        """
        try:
            # 获取过滤后的结果
            results, _ = self.get_filtered_results(**filter_params, page=1, page_size=10000)  # 最大导出10000条
            
            # 转换为可导出格式
            export_data = [result.to_dict() for result in results]
            
            # 导出到文件
            if file_format == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            elif file_format == 'csv':
                import pandas as pd
                df = pd.json_normalize(export_data)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif file_format == 'excel':
                import pandas as pd
                df = pd.json_normalize(export_data)
                df.to_excel(file_path, index=False)
            else:
                logger.error(f"不支持的导出格式: {file_format}")
                return False
            
            logger.info(f"导出回测结果成功: {file_path}，共{len(export_data)}条")
            return True
        except Exception as e:
            logger.error(f"导出回测结果失败: {e}")
            return False
    
    def save_results(self, stock_code: str) -> None:
        """保存回测结果到文件
        
        Args:
            stock_code: 股票代码
        """
        if not self._persistence_enabled:
            return
        
        try:
            file_path = os.path.join(self._persistence_dir, f"{stock_code}.json")
            # 先获取结果，在锁内完成
            with self._lock:
                results = self._results.get(stock_code, [])
                # 转换为字典列表
                results_dict = [result.to_dict() for result in results]
            
            # 然后写入文件，不需要锁
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results_dict, f, ensure_ascii=False, indent=2, default=str)
            
            logger.debug(f"保存回测结果到文件: {file_path}")
        except Exception as e:
            logger.error(f"保存回测结果失败: {e}")
    
    def load_results(self) -> None:
        """从文件加载回测结果"""
        if not self._persistence_enabled:
            return
        
        try:
            # 遍历持久化目录下的所有文件
            for filename in os.listdir(self._persistence_dir):
                if filename.endswith('.json'):
                    stock_code = filename[:-5]  # 移除.json后缀
                    file_path = os.path.join(self._persistence_dir, filename)
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        results_dict = json.load(f)
                        # 转换为BacktestResult实例
                        results = [BacktestResult.from_dict(data) for data in results_dict]
                        
                        with self._lock:
                            self._results[stock_code] = results
            
            logger.info(f"加载回测结果: {len(self._results)} 个股票")
        except Exception as e:
            logger.error(f"加载回测结果失败: {e}")
    
    def _delete_persistence_file(self, stock_code: str) -> None:
        """删除指定股票的持久化文件
        
        Args:
            stock_code: 股票代码
        """
        try:
            file_path = os.path.join(self._persistence_dir, f"{stock_code}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"删除回测结果文件: {file_path}")
        except Exception as e:
            logger.error(f"删除回测结果文件失败: {e}")
    
    def _delete_all_persistence_files(self) -> None:
        """删除所有持久化文件"""
        try:
            for filename in os.listdir(self._persistence_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self._persistence_dir, filename)
                    os.remove(file_path)
            logger.debug("删除所有回测结果文件")
        except Exception as e:
            logger.error(f"删除所有回测结果文件失败: {e}")
    
    def enable_persistence(self, enable: bool) -> None:
        """启用或禁用持久化
        
        Args:
            enable: 是否启用持久化
        """
        self._persistence_enabled = enable
        logger.info(f"{'启用' if enable else '禁用'}回测结果持久化")
