from loguru import logger
"""
回测结果管理器

功能：
1. 存储、管理和分发回测结果
2. 支持内存存储、DuckDB存储和JSON文件存储
3. 提供添加、获取、删除回测结果的方法
4. 支持事件通知机制
5. 支持文件 I/O 线程安全
6. DuckDB 优先，JSON 作为后备
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from threading import Lock
from contextlib import contextmanager
from filelock import FileLock

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
    """回测结果管理器 - DuckDB优先存储"""
    
    _TABLE_NAME = "backtest_results"
    _DB_FILE = "data/factorweave_backtest.duckdb"
    
    def __init__(self, event_bus: Optional[EventBus] = None, cache_service: Optional[CacheService] = None):
        """初始化回测结果管理器
        
        Args:
            event_bus: 事件总线实例，用于发布回测结果更新事件
            cache_service: 缓存服务实例，用于持久化存储
        """
        self._event_bus = event_bus or get_event_bus()
        self._cache_service = cache_service
        
        self._results: Dict[str, List[BacktestResult]] = {}
        self._lock = Lock()
        
        self._duckdb_available = False
        self._duckdb_ops = None
        
        self._persistence_enabled = True
        self._persistence_dir = os.path.join("data", "backtest_results")
        
        self._init_duckdb()
        self._init_persistence_dir()
        self.load_results()
        
        logger.info("BacktestResultManager初始化完成")
    
    def _init_duckdb(self) -> None:
        """初始化 DuckDB 连接和表结构"""
        try:
            from core.database.duckdb_manager import get_connection_manager
            self._connection_manager = get_connection_manager()
            self._db_path = self._DB_FILE
            self._duckdb_available = True
            self._ensure_table_exists()
            logger.info("BacktestResultManager DuckDB 初始化成功")
        except Exception as e:
            logger.warning(f"BacktestResultManager DuckDB 初始化失败，将使用 JSON 存储: {e}")
            self._duckdb_available = False
    
    def _get_duckdb_connection(self):
        """获取 DuckDB 连接"""
        if not self._duckdb_available:
            return None
        
        try:
            ctx = self._connection_manager.get_connection(self._db_path)
            conn = ctx.__enter__()
            return conn
        except Exception as e:
            logger.warning(f"获取 DuckDB 连接失败: {e}")
            return None
    
    def _release_duckdb_connection(self, conn):
        """释放 DuckDB 连接"""
        if conn:
            try:
                ctx = self._connection_manager.get_connection(self._db_path)
                ctx.__exit__(None, None, None)
            except:
                pass
    
    def _execute_sql(self, sql: str, params: list = None) -> Any:
        """执行 SQL 并返回结果"""
        conn = self._get_duckdb_connection()
        if not conn:
            return None, None
        
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            if sql.strip().upper().startswith('SELECT'):
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                result = (columns, data)
            else:
                conn.commit()
                result = (None, None)
            return result
        except Exception as e:
            logger.error(f"SQL执行失败: {sql[:100]}... 错误: {e}")
            try:
                conn.rollback()
            except:
                pass
            raise
        finally:
            self._release_duckdb_connection(conn)
    
    def _ensure_table_exists(self) -> None:
        """确保回测结果表存在"""
        if not self._duckdb_available:
            return
        
        try:
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {self._TABLE_NAME} (
                id BIGINT,
                stock_code VARCHAR(10),
                stock_name VARCHAR(50),
                strategy_name VARCHAR(100),
                backtest_time TIMESTAMP,
                backtest_results JSON,
                trades JSON,
                duration DOUBLE,
                is_professional BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            self._execute_sql(create_sql)
            
            index_sql_list = [
                f"CREATE INDEX IF NOT EXISTS idx_backtest_stock_code ON {self._TABLE_NAME}(stock_code)",
                f"CREATE INDEX IF NOT EXISTS idx_backtest_strategy ON {self._TABLE_NAME}(strategy_name)",
                f"CREATE INDEX IF NOT EXISTS idx_backtest_time ON {self._TABLE_NAME}(backtest_time)"
            ]
            for index_sql in index_sql_list:
                self._execute_sql(index_sql)
            logger.debug(f"回测结果表 {self._TABLE_NAME} 已确保存在")
        except Exception as e:
            logger.error(f"创建回测结果表失败: {e}")
            self._duckdb_available = False
    
    def _init_persistence_dir(self) -> None:
        """初始化持久化目录（JSON 后备）"""
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
            if result.stock_code not in self._results:
                self._results[result.stock_code] = []
            
            self._results[result.stock_code].append(result)
            
            if len(self._results[result.stock_code]) > 10:
                self._results[result.stock_code] = self._results[result.stock_code][-10:]
            
            self._save_to_db(result)
        
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
    
    def _save_to_db(self, result: BacktestResult) -> None:
        """保存单条结果到 DuckDB"""
        if not self._duckdb_available:
            self._save_to_json(result.stock_code)
            return
        
        try:
            import datetime
            insert_sql = f"""
            INSERT INTO {self._TABLE_NAME} 
            (stock_code, stock_name, strategy_name, backtest_time, 
             backtest_results, trades, duration, is_professional)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                result.stock_code,
                result.stock_name,
                result.strategy_name,
                datetime.datetime.fromtimestamp(result.backtest_time),
                json.dumps(result.backtest_results, default=str),
                json.dumps(result.trades, default=str),
                result.duration,
                result.is_professional
            ]
            self._execute_sql(insert_sql, params)
            logger.debug(f"保存回测结果到 DuckDB: {result.stock_code}")
        except Exception as e:
            logger.warning(f"保存到 DuckDB 失败，回退到 JSON: {e}")
            self._save_to_json(result.stock_code)
    
    def _save_to_json(self, stock_code: str) -> None:
        """保存到 JSON 文件（后备方案）"""
        try:
            file_path = os.path.join(self._persistence_dir, f"{stock_code}.json")
            lock_path = file_path + ".lock"
            
            lock = FileLock(lock_path, timeout=10)
            with lock:
                with self._lock:
                    results = self._results.get(stock_code, [])
                    results_dict = [result.to_dict() for result in results]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(results_dict, f, ensure_ascii=False, indent=2, default=str)
            
            logger.debug(f"保存回测结果到文件: {file_path}")
        except Exception as e:
            logger.error(f"保存回测结果失败: {e}")
    
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
                    self._delete_from_db(stock_code)
                    self._delete_persistence_file(stock_code)
            else:
                self._results.clear()
                self._delete_all_from_db()
                self._delete_all_persistence_files()
        
        logger.info(f"清空回测结果: {stock_code if stock_code else '所有'}")
    
    def _delete_from_db(self, stock_code: str) -> None:
        """从 DuckDB 删除指定股票的结果"""
        if not self._duckdb_available:
            return
        try:
            delete_sql = f"DELETE FROM {self._TABLE_NAME} WHERE stock_code = ?"
            self._execute_sql(delete_sql, [stock_code])
        except Exception as e:
            logger.warning(f"从 DuckDB 删除失败: {e}")
    
    def _delete_all_from_db(self) -> None:
        """从 DuckDB 删除所有结果"""
        if not self._duckdb_available:
            return
        try:
            delete_sql = f"DELETE FROM {self._TABLE_NAME}"
            self._execute_sql(delete_sql)
        except Exception as e:
            logger.warning(f"从 DuckDB 清空失败: {e}")
    
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
                self._save_to_json(stock_code)
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
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        if page_size > 1000:
            page_size = 1000
        
        if self._duckdb_available:
            return self._get_filtered_from_db(
                stock_code, strategy_name, start_time, end_time,
                min_return, max_return, min_success_rate, max_success_rate,
                page, page_size
            )
        else:
            return self._get_filtered_from_memory(
                stock_code, strategy_name, start_time, end_time,
                min_return, max_return, min_success_rate, max_success_rate,
                page, page_size
            )
    
    def _get_filtered_from_db(self, stock_code: Optional[str], strategy_name: Optional[str],
                              start_time: Optional[float], end_time: Optional[float],
                              min_return: Optional[float], max_return: Optional[float],
                              min_success_rate: Optional[float], max_success_rate: Optional[float],
                              page: int, page_size: int) -> Tuple[List[BacktestResult], int]:
        """从 DuckDB 获取过滤后的结果"""
        try:
            import datetime
            
            conditions = []
            params = []
            
            if stock_code:
                conditions.append("stock_code = ?")
                params.append(stock_code)
            
            if strategy_name:
                conditions.append("strategy_name LIKE ?")
                params.append(f"%{strategy_name}%")
            
            if start_time:
                conditions.append("backtest_time >= ?")
                params.append(datetime.datetime.fromtimestamp(start_time))
            
            if end_time:
                conditions.append("backtest_time <= ?")
                params.append(datetime.datetime.fromtimestamp(end_time))
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            count_sql = f"SELECT COUNT(*) as cnt FROM {self._TABLE_NAME} WHERE {where_clause}"
            count_columns, count_data = self._execute_sql(count_sql, params)
            total = int(count_data[0][0]) if count_data and count_data[0] else 0
            
            offset = (page - 1) * page_size
            select_sql = f"""
                SELECT * FROM {self._TABLE_NAME}
                WHERE {where_clause}
                ORDER BY backtest_time DESC
                LIMIT {page_size} OFFSET {offset}
            """
            columns, data = self._execute_sql(select_sql, params)
            
            results = []
            if columns and data:
                for row in data:
                    row_dict = dict(zip(columns, row))
                    backtest_results = json.loads(row_dict['backtest_results']) if row_dict.get('backtest_results') else {}
                    trades = json.loads(row_dict['trades']) if row_dict.get('trades') else []
                    
                    bt_time = row_dict['backtest_time']
                    if isinstance(bt_time, datetime.datetime):
                        bt_timestamp = bt_time.timestamp()
                    else:
                        bt_timestamp = float(bt_time)
                    
                    results.append(BacktestResult(
                        stock_code=row_dict['stock_code'],
                        stock_name=row_dict.get('stock_name', ''),
                        strategy_name=row_dict.get('strategy_name', ''),
                        backtest_time=bt_timestamp,
                        backtest_results=backtest_results,
                        trades=trades,
                        duration=float(row_dict.get('duration', 0)),
                        is_professional=bool(row_dict.get('is_professional', False))
                    ))
            
            return results, total
        except Exception as e:
            logger.warning(f"DuckDB 查询失败，回退到内存: {e}")
            return self._get_filtered_from_memory(
                stock_code, strategy_name, start_time, end_time,
                min_return, max_return, min_success_rate, max_success_rate,
                page, page_size
            )
    
    def _get_filtered_from_memory(self, stock_code: Optional[str], strategy_name: Optional[str],
                                   start_time: Optional[float], end_time: Optional[float],
                                   min_return: Optional[float], max_return: Optional[float],
                                   min_success_rate: Optional[float], max_success_rate: Optional[float],
                                   page: int, page_size: int) -> Tuple[List[BacktestResult], int]:
        """从内存获取过滤后的结果"""
        with self._lock:
            all_results = []
            stocks_to_check = [stock_code] if stock_code else self._results.keys()
            
            for sc in stocks_to_check:
                if sc in self._results:
                    for result in self._results[sc]:
                        if strategy_name and strategy_name not in result.strategy_name:
                            continue
                        if start_time and result.backtest_time < start_time:
                            continue
                        if end_time and result.backtest_time > end_time:
                            continue
                        
                        return_value = 0.0
                        if isinstance(result.backtest_results, dict):
                            return_value = result.backtest_results.get('avg_return', 0)
                            if return_value == 0 and 'risk_metrics' in result.backtest_results:
                                return_value = result.backtest_results['risk_metrics'].get('总收益率', 0)
                            elif return_value == 0 and 'performance' in result.backtest_results:
                                return_value = result.backtest_results['performance'].get('total_return', 0)
                        if min_return is not None and return_value < min_return:
                            continue
                        if max_return is not None and return_value > max_return:
                            continue
                        
                        success_rate = 0.0
                        if isinstance(result.backtest_results, dict):
                            success_rate = result.backtest_results.get('success_rate', 0)
                            if success_rate == 0 and 'performance' in result.backtest_results:
                                success_rate = result.backtest_results['performance'].get('win_rate', 0)
                        if min_success_rate is not None and success_rate < min_success_rate:
                            continue
                        if max_success_rate is not None and success_rate > max_success_rate:
                            continue
                        
                        all_results.append(result)
            
            all_results.sort(key=lambda x: x.backtest_time, reverse=True)
            
            total = len(all_results)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_results = all_results[start:end]
            
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
            results, _ = self.get_filtered_results(**filter_params, page=1, page_size=10000)
            
            export_data = [result.to_dict() for result in results]
            
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
            
            logger.info(f"导出回测结果成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出回测结果失败: {e}")
            return False
    
    def load_results(self) -> None:
        """从 DuckDB 加载回测结果到内存"""
        if not self._duckdb_available:
            self._load_from_json()
            return
        
        try:
            import datetime
            select_sql = f"SELECT * FROM {self._TABLE_NAME} ORDER BY backtest_time DESC LIMIT 1000"
            columns, data = self._execute_sql(select_sql)
            
            if columns and data:
                stock_results: Dict[str, List[BacktestResult]] = {}
                
                for row in data:
                    row_dict = dict(zip(columns, row))
                    backtest_results = json.loads(row_dict['backtest_results']) if row_dict.get('backtest_results') else {}
                    trades = json.loads(row_dict['trades']) if row_dict.get('trades') else []
                    
                    bt_time = row_dict['backtest_time']
                    if isinstance(bt_time, datetime.datetime):
                        bt_timestamp = bt_time.timestamp()
                    else:
                        bt_timestamp = float(bt_time)
                    
                    backtest_result = BacktestResult(
                        stock_code=row_dict['stock_code'],
                        stock_name=row_dict.get('stock_name', ''),
                        strategy_name=row_dict.get('strategy_name', ''),
                        backtest_time=bt_timestamp,
                        backtest_results=backtest_results,
                        trades=trades,
                        duration=float(row_dict.get('duration', 0)),
                        is_professional=bool(row_dict.get('is_professional', False))
                    )
                    
                    sc = row_dict['stock_code']
                    if sc not in stock_results:
                        stock_results[sc] = []
                    stock_results[sc].append(backtest_result)
                
                for sc, results_list in stock_results.items():
                    if len(results_list) > 10:
                        stock_results[sc] = results_list[-10:]
                
                with self._lock:
                    self._results = stock_results
                
                logger.info(f"从 DuckDB 加载回测结果: {len(self._results)} 个股票")
        except Exception as e:
            logger.warning(f"从 DuckDB 加载失败，回退到 JSON: {e}")
            self._load_from_json()
    
    def _load_from_json(self) -> None:
        """从 JSON 文件加载回测结果（后备）"""
        try:
            for filename in os.listdir(self._persistence_dir):
                if filename.endswith('.json'):
                    stock_code = filename[:-5]
                    file_path = os.path.join(self._persistence_dir, filename)
                    lock_path = file_path + ".lock"
                    
                    lock = FileLock(lock_path, timeout=10)
                    with lock:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            results_dict = json.load(f)
                            results = [BacktestResult.from_dict(data) for data in results_dict]
                            
                            with self._lock:
                                self._results[stock_code] = results
            
            logger.info(f"从 JSON 加载回测结果: {len(self._results)} 个股票")
        except Exception as e:
            logger.error(f"加载回测结果失败: {e}")
    
    def _delete_persistence_file(self, stock_code: str) -> None:
        """删除指定股票的持久化文件"""
        try:
            file_path = os.path.join(self._persistence_dir, f"{stock_code}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"删除回测结果文件: {file_path}")
                lock_path = file_path + ".lock"
                if os.path.exists(lock_path):
                    os.remove(lock_path)
        except Exception as e:
            logger.error(f"删除回测结果文件失败: {e}")
    
    def _delete_all_persistence_files(self) -> None:
        """删除所有持久化文件"""
        try:
            for filename in os.listdir(self._persistence_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self._persistence_dir, filename)
                    os.remove(file_path)
                    lock_path = file_path + ".lock"
                    if os.path.exists(lock_path):
                        os.remove(lock_path)
            logger.debug("删除所有回测结果文件")
        except Exception as e:
            logger.error(f"删除所有回测结果文件失败: {e}")
