#!/usr/bin/env python3
"""
数据导入配置管理器

管理各种数据源的导入配置、调度策略和任务管理
对标专业软件的配置管理功能
"""

import json
import os
from loguru import logger
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor



class ImportMode(Enum):
    """导入模式"""
    REAL_TIME = "real_time"      # 实时导入
    BATCH = "batch"              # 批量导入
    SCHEDULED = "scheduled"      # 定时导入
    MANUAL = "manual"            # 手动导入


class DataFrequency(Enum):
    """数据频率"""
    TICK = "tick"                # 逐笔数据
    MINUTE_1 = "1min"           # 1分钟
    MINUTE_5 = "5min"           # 5分钟
    MINUTE_15 = "15min"         # 15分钟
    MINUTE_30 = "30min"         # 30分钟
    HOUR_1 = "1h"               # 1小时
    DAILY = "daily"             # 日线
    WEEKLY = "weekly"           # 周线
    MONTHLY = "monthly"         # 月线


class ImportStatus(Enum):
    """导入状态"""
    PENDING = "pending"         # 等待中
    RUNNING = "running"         # 运行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    PAUSED = "paused"          # 暂停
    CANCELLED = "cancelled"     # 已取消


@dataclass
class DataSourceConfig:
    """数据源配置"""
    name: str                           # 数据源名称
    plugin_name: str                    # 插件名称
    enabled: bool = True                # 是否启用
    priority: int = 1                   # 优先级 (1-10)
    timeout: int = 30                   # 超时时间(秒)
    retry_count: int = 3                # 重试次数
    retry_delay: int = 5                # 重试延迟(秒)
    rate_limit: int = 100               # 速率限制(请求/分钟)
    api_key: Optional[str] = None       # API密钥
    api_secret: Optional[str] = None    # API密钥
    base_url: Optional[str] = None      # 基础URL
    extra_params: Dict[str, Any] = field(default_factory=dict)  # 额外参数

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataSourceConfig':
        """从字典创建（容错处理）"""
        try:
            valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in valid_fields}
            return cls(**filtered_data)
        except Exception as e:
            logger.error(f"从字典创建DataSourceConfig失败: {e}")
            raise


@dataclass
class ImportTaskConfig:
    """导入任务配置"""
    task_id: str                                # 任务ID
    name: str                                   # 任务名称
    data_source: str                            # 数据源名称
    asset_type: str                             # 资产类型
    data_type: str                              # 数据类型
    symbols: List[str]                          # 股票代码列表
    frequency: DataFrequency                    # 数据频率
    mode: ImportMode                            # 导入模式
    description: Optional[str] = None           # 任务描述
    data_usage: str = "general"                 # 数据用途
    start_date: Optional[str] = None            # 开始日期
    end_date: Optional[str] = None              # 结束日期
    schedule_cron: Optional[str] = None         # 定时任务表达式
    enabled: bool = True                        # 是否启用
    max_workers: int = os.cpu_count() * 2         # 最大工作线程数
    batch_size: int = 790                      # 批处理大小
    retry_count: int = 3                        # 失败重试次数
    error_strategy: str = "重试"                # 错误处理策略
    memory_limit: int = 2048                    # 内存限制(MB)
    timeout: int = 300                          # 超时时间(秒)
    progress_interval: int = 5                  # 进度更新间隔(秒)
    validate_data: bool = True                  # 是否验证数据
    # 增量更新配置
    enable_incremental: bool = True    # 是否启用增量更新
    incremental_days: int = 7  # 增量更新的天数阈值
    force_full_update: bool = False    # 强制全量更新
    check_completeness: bool = True  # 数据完整性检查
    skip_latest_data: bool = True  # 跳过最新数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['frequency'] = self.frequency.value
        data['mode'] = self.mode.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImportTaskConfig':
        """从字典创建（容错处理）"""
        try:
            # 获取dataclass的字段名，过滤掉不存在的参数
            valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in valid_fields}

            # 处理frequency字段（可能是字符串或枚举值）
            freq_value = filtered_data.get('frequency')
            if isinstance(freq_value, str):
                try:
                    filtered_data['frequency'] = DataFrequency(freq_value)
                except (ValueError, KeyError):
                    logger.warning(f"无效的频率值 '{freq_value}'，使用默认值 DAILY")
                    filtered_data['frequency'] = DataFrequency.DAILY
            elif freq_value and not isinstance(freq_value, DataFrequency):
                filtered_data['frequency'] = DataFrequency.DAILY

            # 处理mode字段（可能是字符串或枚举值）
            mode_value = filtered_data.get('mode')
            if isinstance(mode_value, str):
                try:
                    filtered_data['mode'] = ImportMode(mode_value)
                except (ValueError, KeyError):
                    logger.warning(f"无效的导入模式 '{mode_value}'，使用默认值 MANUAL")
                    filtered_data['mode'] = ImportMode.MANUAL
            elif mode_value and not isinstance(mode_value, ImportMode):
                filtered_data['mode'] = ImportMode.MANUAL

            return cls(**filtered_data)
        except Exception as e:
            logger.error(f"从字典创建ImportTaskConfig失败: {e}")
            raise


@dataclass
class ImportProgress:
    """导入进度"""
    task_id: str                       # 任务ID
    status: ImportStatus               # 状态
    total_symbols: int = 0             # 总股票数
    processed_symbols: int = 0         # 已处理股票数
    total_records: int = 0             # 总记录数
    imported_records: int = 0          # 已导入记录数
    error_count: int = 0               # 错误数量
    start_time: Optional[str] = None   # 开始时间
    end_time: Optional[str] = None     # 结束时间
    error_message: Optional[str] = None  # 错误信息
    processed_symbols_list: List[str] = field(default_factory=list)  # 修复：已处理的股票列表（用于恢复）

    @property
    def progress_percentage(self) -> float:
        """进度百分比"""
        if self.total_symbols == 0:
            return 0.0
        return (self.processed_symbols / self.total_symbols) * 100

    @property
    def duration(self) -> Optional[float]:
        """持续时间(秒)"""
        if not self.start_time:
            return None

        end_time = self.end_time or datetime.now().isoformat()
        start_dt = datetime.fromisoformat(self.start_time)
        end_dt = datetime.fromisoformat(end_time)
        return (end_dt - start_dt).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImportProgress':
        """从字典创建（容错处理）"""
        try:
            valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in valid_fields}

            if 'status' in filtered_data:
                if isinstance(filtered_data['status'], str):
                    filtered_data['status'] = ImportStatus(filtered_data['status'])
            return cls(**filtered_data)
        except Exception as e:
            logger.error(f"从字典创建ImportProgress失败: {e}")
            raise


class ImportConfigManager:
    """
    数据导入配置管理器

    管理数据源配置、导入任务配置和进度跟踪
    """

    def __init__(self, db_path: str = "data/factorweave_system.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._data_sources: Dict[str, DataSourceConfig] = {}
        self._tasks: Dict[str, ImportTaskConfig] = {}
        self._progress: Dict[str, ImportProgress] = {}

        self._init_database()
        self._load_configs()

        logger.info(f"导入配置管理器初始化完成: {self.db_path}")

    def _init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 数据源配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_sources (
                    name TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 导入任务配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_tasks (
                    task_id TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 导入进度表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_progress (
                    task_id TEXT PRIMARY KEY,
                    progress TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 导入历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_records INTEGER,
                    imported_records INTEGER,
                    error_count INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            conn.commit()

    def _load_configs(self):
        """加载配置"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 加载数据源配置
            cursor.execute("SELECT name, config FROM data_sources")
            for name, config_json in cursor.fetchall():
                try:
                    config_data = json.loads(config_json)
                    self._data_sources[name] = DataSourceConfig.from_dict(config_data)
                except Exception as e:
                    logger.error(f"加载数据源配置失败 {name}: {e}")

            # 加载任务配置
            cursor.execute("SELECT task_id, config FROM import_tasks")
            for task_id, config_json in cursor.fetchall():
                try:
                    config_data = json.loads(config_json)
                    logger.debug(f"加载任务配置: {task_id}, 数据: {config_data.get('name', 'Unknown')}")
                    self._tasks[task_id] = ImportTaskConfig.from_dict(config_data)
                    logger.info(f"成功加载任务: {task_id} - {self._tasks[task_id].name}")
                except Exception as e:
                    logger.error(f"加载任务配置失败 {task_id}: {e}")
                    import traceback
                    logger.error(f"详细错误: {traceback.format_exc()}")

            # 加载进度信息
            cursor.execute("SELECT task_id, progress FROM import_progress")
            for task_id, progress_json in cursor.fetchall():
                try:
                    progress_data = json.loads(progress_json)
                    self._progress[task_id] = ImportProgress.from_dict(progress_data)
                except Exception as e:
                    logger.error(f"加载进度信息失败 {task_id}: {e}")

            # 输出加载统计
            logger.info(f"配置加载完成 - 数据源: {len(self._data_sources)}, 任务: {len(self._tasks)}, 进度: {len(self._progress)}")

    # 数据源配置管理
    def add_data_source(self, config: DataSourceConfig) -> bool:
        """添加数据源配置"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    now = datetime.now().isoformat()

                    cursor.execute("""
                        INSERT OR REPLACE INTO data_sources 
                        (name, config, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        config.name,
                        json.dumps(config.to_dict(), ensure_ascii=False),
                        now,
                        now
                    ))

                    conn.commit()
                    self._data_sources[config.name] = config

                logger.info(f"添加数据源配置: {config.name}")
                return True

        except Exception as e:
            logger.error(f"添加数据源配置失败 {config.name}: {e}")
            return False

    def get_data_source(self, name: str) -> Optional[DataSourceConfig]:
        """获取数据源配置"""
        return self._data_sources.get(name)

    def get_all_data_sources(self) -> Dict[str, DataSourceConfig]:
        """获取所有数据源配置"""
        return self._data_sources.copy()

    def update_data_source(self, name: str, **kwargs) -> bool:
        """更新数据源配置"""
        try:
            with self._lock:
                config = self._data_sources.get(name)
                if not config:
                    logger.error(f"数据源不存在: {name}")
                    return False

                # 更新配置
                for key, value in kwargs.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

                # 保存到数据库
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE data_sources 
                        SET config = ?, updated_at = ?
                        WHERE name = ?
                    """, (
                        json.dumps(config.to_dict(), ensure_ascii=False),
                        datetime.now().isoformat(),
                        name
                    ))
                    conn.commit()

                logger.info(f"更新数据源配置: {name}")
                return True

        except Exception as e:
            logger.error(f"更新数据源配置失败 {name}: {e}")
            return False

    def remove_data_source(self, name: str) -> bool:
        """删除数据源配置"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM data_sources WHERE name = ?", (name,))
                    conn.commit()

                if name in self._data_sources:
                    del self._data_sources[name]

                logger.info(f"删除数据源配置: {name}")
                return True

        except Exception as e:
            logger.error(f"删除数据源配置失败 {name}: {e}")
            return False

    # 导入任务配置管理
    def add_import_task(self, config: ImportTaskConfig) -> bool:
        """添加导入任务配置"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    now = datetime.now().isoformat()
                    config.updated_at = now

                    cursor.execute("""
                        INSERT OR REPLACE INTO import_tasks 
                        (task_id, config, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        config.task_id,
                        json.dumps(config.to_dict(), ensure_ascii=False),
                        config.created_at,
                        now
                    ))

                    conn.commit()
                    self._tasks[config.task_id] = config

                logger.info(f"添加导入任务: {config.task_id}")
                return True

        except Exception as e:
            logger.error(f"添加导入任务失败 {config.task_id}: {e}")
            return False

    def get_import_task(self, task_id: str) -> Optional[ImportTaskConfig]:
        """获取导入任务配置"""
        return self._tasks.get(task_id)

    def get_all_import_tasks(self) -> Dict[str, ImportTaskConfig]:
        """获取所有导入任务配置"""
        return self._tasks.copy()

    def get_import_tasks(self) -> List[ImportTaskConfig]:
        """获取导入任务配置列表（别名方法）"""
        return list(self._tasks.values())

    def get_tasks_by_data_source(self, data_source: str) -> List[ImportTaskConfig]:
        """根据数据源获取任务"""
        return [task for task in self._tasks.values()
                if task.data_source == data_source]

    def get_enabled_tasks(self) -> List[ImportTaskConfig]:
        """获取启用的任务"""
        return [task for task in self._tasks.values() if task.enabled]

    def update_import_task(self, task_id: str, **kwargs) -> bool:
        """更新导入任务配置"""
        try:
            with self._lock:
                task = self._tasks.get(task_id)
                if not task:
                    logger.error(f"导入任务不存在: {task_id}")
                    return False

                # 更新配置
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)

                task.updated_at = datetime.now().isoformat()

                # 保存到数据库
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE import_tasks 
                        SET config = ?, updated_at = ?
                        WHERE task_id = ?
                    """, (
                        json.dumps(task.to_dict(), ensure_ascii=False),
                        task.updated_at,
                        task_id
                    ))
                    conn.commit()

                logger.info(f"更新导入任务: {task_id}")
                return True

        except Exception as e:
            logger.error(f"更新导入任务失败 {task_id}: {e}")
            return False

    def remove_import_task(self, task_id: str) -> bool:
        """删除导入任务配置"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM import_tasks WHERE task_id = ?", (task_id,))
                    cursor.execute("DELETE FROM import_progress WHERE task_id = ?", (task_id,))
                    conn.commit()

                if task_id in self._tasks:
                    del self._tasks[task_id]
                if task_id in self._progress:
                    del self._progress[task_id]

                logger.info(f"删除导入任务: {task_id}")
                return True

        except Exception as e:
            logger.error(f"删除导入任务失败 {task_id}: {e}")
            return False

    # 进度管理
    def update_progress(self, progress: ImportProgress) -> bool:
        """更新导入进度"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    now = datetime.now().isoformat()

                    cursor.execute("""
                        INSERT OR REPLACE INTO import_progress 
                        (task_id, progress, updated_at)
                        VALUES (?, ?, ?)
                    """, (
                        progress.task_id,
                        json.dumps(progress.to_dict(), ensure_ascii=False),
                        now
                    ))

                    conn.commit()
                    self._progress[progress.task_id] = progress

                return True

        except Exception as e:
            logger.error(f"更新导入进度失败 {progress.task_id}: {e}")
            return False

    def get_progress(self, task_id: str) -> Optional[ImportProgress]:
        """获取导入进度"""
        return self._progress.get(task_id)

    def get_all_progress(self) -> Dict[str, ImportProgress]:
        """获取所有导入进度"""
        return self._progress.copy()

    def get_running_tasks(self) -> List[str]:
        """获取运行中的任务"""
        return [task_id for task_id, progress in self._progress.items()
                if progress.status == ImportStatus.RUNNING]

    def save_history(self, progress: ImportProgress) -> bool:
        """保存导入历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO import_history 
                    (task_id, status, total_records, imported_records, error_count,
                     start_time, end_time, error_message, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    progress.task_id,
                    progress.status.value,
                    progress.total_records,
                    progress.imported_records,
                    progress.error_count,
                    progress.start_time,
                    progress.end_time,
                    progress.error_message,
                    datetime.now().isoformat()
                ))
                conn.commit()

            logger.info(f"保存导入历史: {progress.task_id}")
            return True

        except Exception as e:
            logger.error(f"保存导入历史失败 {progress.task_id}: {e}")
            return False

    def get_history(self, task_id: Optional[str] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """获取导入历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if task_id:
                    cursor.execute("""
                        SELECT * FROM import_history 
                        WHERE task_id = ?
                        ORDER BY created_at DESC 
                        LIMIT ?
                    """, (task_id, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM import_history 
                        ORDER BY created_at DESC 
                        LIMIT ?
                    """, (limit,))

                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"获取导入历史失败: {e}")
            return []

    # 统计信息
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 任务统计
                total_tasks = len(self._tasks)
                enabled_tasks = len([t for t in self._tasks.values() if t.enabled])
                running_tasks = len(self.get_running_tasks())

                # 数据源统计
                total_sources = len(self._data_sources)
                enabled_sources = len([s for s in self._data_sources.values() if s.enabled])

                # 历史统计
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_runs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                        SUM(imported_records) as total_imported
                    FROM import_history
                    WHERE created_at >= date('now', '-30 days')
                """)

                history_stats = cursor.fetchone()

                return {
                    'tasks': {
                        'total': total_tasks,
                        'enabled': enabled_tasks,
                        'running': running_tasks
                    },
                    'data_sources': {
                        'total': total_sources,
                        'enabled': enabled_sources
                    },
                    'history_30_days': {
                        'total_runs': history_stats[0] or 0,
                        'successful_runs': history_stats[1] or 0,
                        'failed_runs': history_stats[2] or 0,
                        'total_imported': history_stats[3] or 0
                    }
                }

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def export_config(self, file_path: str) -> bool:
        """导出配置"""
        try:
            config_data = {
                'data_sources': {name: config.to_dict()
                                 for name, config in self._data_sources.items()},
                'import_tasks': {task_id: config.to_dict()
                                 for task_id, config in self._tasks.items()},
                'exported_at': datetime.now().isoformat()
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            logger.info(f"配置导出成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"配置导出失败: {e}")
            return False

    def import_config(self, file_path: str) -> bool:
        """导入配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 导入数据源配置
            for name, data in config_data.get('data_sources', {}).items():
                config = DataSourceConfig.from_dict(data)
                self.add_data_source(config)

            # 导入任务配置
            for task_id, data in config_data.get('import_tasks', {}).items():
                config = ImportTaskConfig.from_dict(data)
                self.add_import_task(config)

            logger.info(f"配置导入成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"配置导入失败: {e}")
            return False


def main():
    """测试函数"""
    # 创建配置管理器
    manager = ImportConfigManager()

    # 添加数据源配置
    wind_config = DataSourceConfig(
        name="Wind万得",
        plugin_name="wind_plugin",
        priority=1,
        timeout=30,
        api_key="your_api_key",
        base_url="https://api.wind.com.cn"
    )
    manager.add_data_source(wind_config)

    # 添加导入任务
    task_config = ImportTaskConfig(
        task_id="stock_daily_import",
        name="A股日线数据导入",
        data_source="Wind万得",
        asset_type="stock",
        data_type="kline",
        symbols=["000001.SZ", "000002.SZ"],
        frequency=DataFrequency.DAILY,
        mode=ImportMode.SCHEDULED,
        schedule_cron="0 18 * * 1-5"  # 工作日18点
    )
    manager.add_import_task(task_config)

    # 更新进度
    progress = ImportProgress(
        task_id="stock_daily_import",
        status=ImportStatus.RUNNING,
        total_symbols=2,
        processed_symbols=1,
        total_records=1000,
        imported_records=500,
        start_time=datetime.now().isoformat()
    )
    manager.update_progress(progress)

    # 获取统计信息
    stats = manager.get_statistics()
    logger.info(f"统计信息: {json.dumps(stats, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
