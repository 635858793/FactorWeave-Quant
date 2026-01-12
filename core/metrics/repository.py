# core/metrics/repository.py
import sqlite3
import threading
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import datetime
import json
import time
from threading import Lock
from loguru import logger


# 获取项目根目录的绝对路径
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
except IndexError:
    PROJECT_ROOT = Path.cwd()

DB_FILE = PROJECT_ROOT / "db" / "metrics.sqlite"
DB_FILE.parent.mkdir(parents=True, exist_ok=True)

class MetricsRepository:
    """
    指标数据仓储

    负责存储和检索系统性能指标数据，支持内存缓存和数据库持久化。
    """

    def __init__(self, db_path: str = "data/metrics.sqlite", cache_size: int = 1000):
        """
        初始化指标数据仓储

        Args:
            db_path: 数据库文件路径
            cache_size: 内存缓存大小
        """
        self.db_path = db_path
        self.cache_size = cache_size
        self.cache = {}
        self.lock = Lock()
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 创建指标数据表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_name TEXT NOT NULL,
                        value REAL NOT NULL,
                        timestamp INTEGER NOT NULL,
                        category TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 创建索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON metrics(metric_name, timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(category)')

                conn.commit()
                logger.info("数据库初始化完成")

        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    def store_metric(self, metric_name: str, value: float, category: str = None, metadata: Dict = None):
        """存储单个指标"""
        try:
            timestamp = int(time.time())
            metadata_json = json.dumps(metadata) if metadata else None

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO metrics (metric_name, value, timestamp, category, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (metric_name, value, timestamp, category, metadata_json))
                conn.commit()

        except Exception as e:
            logger.error(f"存储指标失败: {e}")

    def update_metric(self, metric_id: int, value: float, metadata: Dict = None) -> bool:
        """更新单个指标"""
        try:
            timestamp = int(time.time())
            metadata_json = json.dumps(metadata) if metadata else None

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE metrics
                    SET value = ?, timestamp = ?, metadata = ?
                    WHERE id = ?
                ''', (value, timestamp, metadata_json, metric_id))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.debug(f"指标更新成功: id={metric_id}, value={value}")
                    return True
                else:
                    logger.warning(f"指标未找到: id={metric_id}")
                    return False

        except Exception as e:
            logger.error(f"更新指标失败: {e}")
            return False

    def delete_metric(self, metric_id: int) -> bool:
        """删除单个指标"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM metrics WHERE id = ?", (metric_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.debug(f"指标删除成功: id={metric_id}")
                    return True
                else:
                    logger.warning(f"指标未找到: id={metric_id}")
                    return False

        except Exception as e:
            logger.error(f"删除指标失败: {e}")
            return False

    def query_metrics(self,
                      metric_name: str,
                      start_time: Optional[int] = None,
                      end_time: Optional[int] = None,
                      category: Optional[str] = None,
                      limit: int = 1000) -> List[Dict[str, Any]]:
        """
        查询指标数据

        Args:
            metric_name: 指标名称
            start_time: 开始时间戳
            end_time: 结束时间戳
            category: 指标分类
            limit: 返回记录数限制

        Returns:
            指标数据列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM metrics WHERE metric_name = ?"
                params = [metric_name]

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time)

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time)

                if category:
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"查询指标失败: {e}")
            return []

    def query_historical_data(self,
                              start_time: datetime.datetime,
                              end_time: datetime.datetime,
                              table: str = "resource_metrics_summary",
                              operation_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询历史数据

        Args:
            start_time: 开始时间
            end_time: 结束时间
            table: 数据表名
            operation_name: 操作名称

        Returns:
            历史数据列表
        """
        try:
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())

            if table == "resource_metrics_summary":
                # 查询系统资源数据
                cpu_data = self.query_metrics("cpu_usage", start_timestamp, end_timestamp, "system")
                memory_data = self.query_metrics("memory_usage", start_timestamp, end_timestamp, "system")
                disk_data = self.query_metrics("disk_usage", start_timestamp, end_timestamp, "system")

                # 合并数据
                result = []
                for cpu_item in cpu_data:
                    timestamp = cpu_item['timestamp']

                    # 查找对应时间的内存和磁盘数据
                    memory_value = next((m['value'] for m in memory_data if abs(m['timestamp'] - timestamp) < 60), 0)
                    disk_value = next((d['value'] for d in disk_data if abs(d['timestamp'] - timestamp) < 60), 0)

                    result.append({
                        'id': cpu_item['id'],
                        't_stamp': datetime.datetime.fromtimestamp(timestamp).isoformat(),
                        'cpu': cpu_item['value'],
                        'mem': memory_value,
                        'disk': disk_value
                    })

                return result

            elif table == "app_metrics_summary":
                # 查询应用性能数据
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    query = '''
                        SELECT id, timestamp, metric_name, value, metadata
                        FROM metrics 
                        WHERE timestamp BETWEEN ? AND ?
                        AND category = 'application'
                    '''
                    params = [start_timestamp, end_timestamp]

                    if operation_name:
                        query += " AND metric_name LIKE ?"
                        params.append(f"%{operation_name}%")

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    result = []
                    for row in rows:
                        result.append({
                            'id': row[0],
                            't_stamp': datetime.datetime.fromtimestamp(row[1]).isoformat(),
                            'operation': row[2],
                            'avg_duration': row[3],
                            'max_duration': row[3] * 1.5,  # 模拟最大耗时
                            'call_count': 1,
                            'error_count': 0
                        })

                    return result

            return []

        except Exception as e:
            logger.error(f"查询历史数据失败: {e}")
            return []

    def get_latest_metric(self, metric_name: str, category: str = None) -> Optional[Dict[str, Any]]:
        """获取最新的指标值"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM metrics WHERE metric_name = ?"
                params = [metric_name]

                if category:
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY timestamp DESC LIMIT 1"

                cursor.execute(query, params)
                row = cursor.fetchone()

                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))

                return None

        except Exception as e:
            logger.error(f"获取最新指标失败: {e}")
            return None

    def cleanup_old_data(self, days: int = 30):
        """清理旧数据"""
        try:
            cutoff_time = int(time.time()) - (days * 24 * 3600)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff_time,))
                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(f"清理了 {deleted_count} 条旧数据")

        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
