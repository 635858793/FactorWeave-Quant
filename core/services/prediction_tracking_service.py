"""
预测准确性跟踪服务

提供完整的预测结果记录和准确性跟踪功能，包括：
- 预测结果记录
- 准确性计算
- 准确性统计和分析
"""

from loguru import logger
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import threading
from enum import Enum

from .base_service import BaseService
from ..containers import ServiceContainer, get_service_container
from ..events import EventBus, get_event_bus


class PredictionType(Enum):
    """预测类型"""
    PATTERN = "pattern"      # 形态预测
    TREND = "trend"         # 趋势预测
    PRICE = "price"         # 价格预测
    SENTIMENT = "sentiment" # 情绪预测


class PredictionTrackingService(BaseService):
    """预测准确性跟踪服务"""

    def __init__(self, service_container: Optional[ServiceContainer] = None,
                 event_bus: Optional[EventBus] = None):
        """
        初始化预测跟踪服务

        Args:
            service_container: 服务容器
            event_bus: 事件总线
        """
        super().__init__(event_bus)
        self._service_container = service_container or get_service_container()

        # 预测记录管理
        self._prediction_records: Dict[str, Dict[str, Any]] = {}
        self._record_lock = threading.RLock()

        # 准确性统计缓存
        self._accuracy_statistics: Dict[str, Dict[str, Any]] = {}
        self._statistics_lock = threading.RLock()

        # 数据库服务（延迟获取）
        self._database_service = None

        logger.info("PredictionTrackingService initialized")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing PredictionTrackingService...")

            # 获取数据库服务（可选）
            try:
                from .database_service import DatabaseService
                if self._service_container.is_registered(DatabaseService):
                    self._database_service = self._service_container.resolve(DatabaseService)
                    logger.info("DatabaseService已注册并已获取")
                else:
                    logger.warning("DatabaseService未在容器中注册，将使用直接数据库连接")
            except Exception as e:
                logger.warning(f"无法获取DatabaseService: {e}，将使用直接数据库连接")

            # 初始化数据库表
            self._initialize_database_tables()

            # 加载现有记录和统计，保证重启后状态一致
            self._load_existing_records()
            self._load_existing_statistics()

            logger.info("PredictionTrackingService initialized successfully")

        except Exception as e:
            logger.error(f"PredictionTrackingService初始化失败: {e}")
            raise

    def _initialize_database_tables(self) -> None:
        """初始化数据库表结构"""
        try:
            if self._database_service:
                # 使用DatabaseService创建表（使用strategy_sqlite数据库）
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    self._create_prediction_records_table(conn)
                    self._create_accuracy_statistics_table(conn)
            else:
                logger.error("DatabaseService不可用，无法初始化预测跟踪表")
                raise RuntimeError("DatabaseService不可用，无法初始化预测跟踪表")

            logger.info("数据库表初始化完成")
        except Exception as e:
            logger.error(f"数据库表初始化失败: {e}")
            raise

    def _create_prediction_records_table(self, conn) -> None:
        """创建预测记录表"""
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prediction_records (
                    record_id TEXT PRIMARY KEY,
                    model_version_id TEXT NOT NULL,
                    prediction_type TEXT NOT NULL,
                    prediction_time TIMESTAMP NOT NULL,
                    prediction_result_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    actual_result_json TEXT,
                    accuracy REAL,
                    calculated_at TIMESTAMP,
                    FOREIGN KEY (model_version_id) REFERENCES model_versions(version_id)
                )
            """)
            
            # 创建索引以提高查询性能
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prediction_records_model_version 
                ON prediction_records(model_version_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prediction_records_type_time 
                ON prediction_records(prediction_type, prediction_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prediction_records_time 
                ON prediction_records(prediction_time)
            """)
            
            conn.commit()
            logger.debug("prediction_records表创建成功")
        except Exception as e:
            logger.error(f"创建prediction_records表失败: {e}")
            raise

    def _create_accuracy_statistics_table(self, conn) -> None:
        """创建准确性统计表"""
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accuracy_statistics (
                    stat_id TEXT PRIMARY KEY,
                    model_version_id TEXT NOT NULL,
                    prediction_type TEXT NOT NULL,
                    time_period TEXT NOT NULL,
                    total_predictions INTEGER DEFAULT 0,
                    correct_predictions INTEGER DEFAULT 0,
                    accuracy_rate REAL DEFAULT 0.0,
                    avg_confidence REAL DEFAULT 0.0,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (model_version_id) REFERENCES model_versions(version_id),
                    UNIQUE(model_version_id, prediction_type, time_period)
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_accuracy_statistics_model_version 
                ON accuracy_statistics(model_version_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_accuracy_statistics_type_period 
                ON accuracy_statistics(prediction_type, time_period)
            """)
            
            conn.commit()
            logger.debug("accuracy_statistics表创建成功")
        except Exception as e:
            logger.error(f"创建accuracy_statistics表失败: {e}")
            raise

    def _make_stat_key(self, model_version_id: str, prediction_type: str, time_period: str) -> str:
        """生成统计缓存的唯一键"""
        return f"{model_version_id or ''}_{prediction_type or ''}_{time_period or ''}"

    def _load_existing_statistics(self) -> None:
        """加载现有的准确性统计"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM accuracy_statistics")
                    rows = cursor.fetchall()

                    for row in rows:
                        stat_id = row[0]
                        model_version_id = row[1]
                        prediction_type = row[2]
                        time_period = row[3]
                        stat_key = self._make_stat_key(model_version_id, prediction_type, time_period)
                        self._accuracy_statistics[stat_key] = {
                            'stat_id': stat_id,
                            'model_version_id': model_version_id,
                            'prediction_type': prediction_type,
                            'time_period': time_period,
                            'total_predictions': row[4] or 0,
                            'correct_predictions': row[5] or 0,
                            'accuracy_rate': row[6] or 0.0,
                            'avg_confidence': row[7] or 0.0,
                            'calculated_at': row[8]
                        }
            else:
                logger.error("DatabaseService不可用，无法加载准确性统计")
                raise RuntimeError("DatabaseService不可用，无法加载准确性统计")

            logger.info(f"加载了 {len(self._accuracy_statistics)} 个现有准确性统计")
        except Exception as e:
            logger.warning(f"加载现有准确性统计失败: {e}")

    def _load_existing_records(self, limit: int = 500) -> None:
        """加载近期的预测记录以便UI可以立即显示历史数据"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT record_id, model_version_id, prediction_type, prediction_time,
                               prediction_result_json, confidence, actual_result_json, accuracy, calculated_at
                        FROM prediction_records
                        ORDER BY prediction_time DESC
                        LIMIT ?
                    """, (limit,))
                    rows = cursor.fetchall()
            else:
                logger.error("DatabaseService不可用，无法加载历史预测记录")
                raise RuntimeError("DatabaseService不可用，无法加载历史预测记录")

            with self._record_lock:
                for row in rows:
                    record_id = row[0]
                    self._prediction_records[record_id] = {
                        'record_id': record_id,
                        'model_version_id': row[1],
                        'prediction_type': row[2],
                        'prediction_time': row[3],
                        'prediction_result': json.loads(row[4]) if row[4] else {},
                        'confidence': row[5] or 0.0,
                        'actual_result': json.loads(row[6]) if row[6] else None,
                        'accuracy': row[7],
                        'calculated_at': row[8]
                    }

            logger.info(f"加载了 {len(self._prediction_records)} 条历史预测记录")
        except Exception as e:
            logger.warning(f"加载历史预测记录失败: {e}")

    def record_prediction(self, model_version_id: str, prediction_type: str,
                         prediction_result: Dict[str, Any],
                         confidence: float) -> str:
        """
        记录预测结果

        Args:
            model_version_id: 模型版本ID
            prediction_type: 预测类型
            prediction_result: 预测结果字典
            confidence: 置信度

        Returns:
            记录ID
        """
        try:
            import uuid
            record_id = str(uuid.uuid4())

            record_data = {
                'record_id': record_id,
                'model_version_id': model_version_id,
                'prediction_type': prediction_type,
                'prediction_time': datetime.now().isoformat(),
                'prediction_result': prediction_result,
                'confidence': confidence,
                'actual_result': None,
                'accuracy': None,
                'calculated_at': None
            }

            with self._record_lock:
                self._prediction_records[record_id] = record_data

            # 保存到数据库
            self._save_prediction_to_database(record_data)

            # 发布事件
            self._event_bus.publish("prediction.recorded",
                                    record_id=record_id,
                                    model_version_id=model_version_id,
                                    prediction_type=prediction_type)

            logger.debug(f"记录预测结果: {record_id}")
            return record_id

        except Exception as e:
            logger.error(f"记录预测结果失败: {e}")
            raise

    def _save_prediction_to_database(self, record_data: Dict[str, Any]) -> None:
        """保存预测记录到数据库"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO prediction_records 
                        (record_id, model_version_id, prediction_type, prediction_time,
                         prediction_result_json, confidence, actual_result_json, accuracy, calculated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record_data['record_id'],
                        record_data['model_version_id'],
                        record_data['prediction_type'],
                        record_data['prediction_time'],
                        json.dumps(record_data['prediction_result']),
                        record_data['confidence'],
                        json.dumps(record_data['actual_result']) if record_data['actual_result'] else None,
                        record_data['accuracy'],
                        record_data['calculated_at']
                    ))
                    conn.commit()
            else:
                logger.error("DatabaseService不可用，无法保存预测记录")
                raise RuntimeError("DatabaseService不可用，无法保存预测记录")
        except Exception as e:
            logger.error(f"保存预测记录到数据库失败: {e}")
            raise

    def update_accuracy(self, record_id: str, actual_result: Dict[str, Any]) -> float:
        """
        更新预测准确性

        Args:
            record_id: 记录ID
            actual_result: 实际结果

        Returns:
            计算出的准确性
        """
        try:
            with self._record_lock:
                if record_id not in self._prediction_records:
                    raise ValueError(f"预测记录不存在: {record_id}")

                record = self._prediction_records[record_id]
                record['actual_result'] = actual_result

                # 计算准确性
                accuracy = self._calculate_accuracy(
                    record['prediction_result'],
                    actual_result,
                    record['prediction_type']
                )
                record['accuracy'] = accuracy
                record['calculated_at'] = datetime.now().isoformat()

            # 更新数据库
            self._update_prediction_accuracy_in_database(record_id, actual_result, accuracy)

            # 更新统计
            self._update_statistics(record)

            # 发布事件
            self._event_bus.publish("prediction.accuracy_updated",
                                    record_id=record_id,
                                    accuracy=accuracy)

            logger.debug(f"更新预测准确性: {record_id} -> {accuracy:.2f}")
            return accuracy

        except Exception as e:
            logger.error(f"更新预测准确性失败: {e}")
            raise

    def _calculate_accuracy(self, prediction_result: Dict[str, Any],
                            actual_result: Dict[str, Any],
                            prediction_type: str) -> float:
        """
        计算预测准确性

        Args:
            prediction_result: 预测结果
            actual_result: 实际结果
            prediction_type: 预测类型

        Returns:
            准确性（0-1之间）
        """
        try:
            if prediction_type == PredictionType.PATTERN.value:
                # 形态预测：比较方向
                pred_direction = prediction_result.get('direction', '')
                actual_direction = actual_result.get('direction', '')
                return 1.0 if pred_direction == actual_direction else 0.0

            elif prediction_type == PredictionType.TREND.value:
                # 趋势预测：比较趋势方向
                pred_trend = prediction_result.get('trend', '')
                actual_trend = actual_result.get('trend', '')
                return 1.0 if pred_trend == actual_trend else 0.0

            elif prediction_type == PredictionType.PRICE.value:
                # 价格预测：计算价格误差
                pred_price = prediction_result.get('price', 0)
                actual_price = actual_result.get('price', 0)
                if actual_price == 0:
                    return 0.0
                error = abs(pred_price - actual_price) / actual_price
                # 误差越小，准确性越高（误差5%以内算准确）
                return max(0.0, 1.0 - error * 2) if error <= 0.05 else 0.0

            else:
                # 默认：比较主要字段
                return 1.0 if prediction_result == actual_result else 0.0

        except Exception as e:
            logger.warning(f"计算准确性失败: {e}")
            return 0.0

    def _update_prediction_accuracy_in_database(self, record_id: str,
                                               actual_result: Dict[str, Any],
                                               accuracy: float) -> None:
        """更新数据库中的预测准确性"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE prediction_records 
                        SET actual_result_json = ?, accuracy = ?, calculated_at = ?
                        WHERE record_id = ?
                    """, (
                        json.dumps(actual_result),
                        accuracy,
                        datetime.now().isoformat(),
                        record_id
                    ))
                    conn.commit()
            else:
                logger.error("DatabaseService不可用，无法更新预测准确性")
                raise RuntimeError("DatabaseService不可用，无法更新预测准确性")
        except Exception as e:
            logger.error(f"更新数据库中的预测准确性失败: {e}")
            raise

    def _update_statistics(self, record: Dict[str, Any]) -> None:
        """更新准确性统计"""
        try:
            model_version_id = record['model_version_id']
            prediction_type = record['prediction_type']
            
            # 确定时间周期（日/周/月）
            prediction_time = datetime.fromisoformat(record['prediction_time'])
            time_period = prediction_time.strftime('%Y-%m-%d')  # 按日统计
            
            stat_key = self._make_stat_key(model_version_id, prediction_type, time_period)
            
            with self._statistics_lock:
                if stat_key not in self._accuracy_statistics:
                    import uuid
                    stat_id = str(uuid.uuid4())
                    self._accuracy_statistics[stat_key] = {
                        'stat_id': stat_id,
                        'model_version_id': model_version_id,
                        'prediction_type': prediction_type,
                        'time_period': time_period,
                        'total_predictions': 0,
                        'correct_predictions': 0,
                        'accuracy_rate': 0.0,
                        'avg_confidence': 0.0,
                        'calculated_at': datetime.now().isoformat()
                    }
                
                stat = self._accuracy_statistics[stat_key]
                stat['total_predictions'] += 1
                
                if record['accuracy'] and record['accuracy'] > 0.5:  # 准确性大于50%算正确
                    stat['correct_predictions'] += 1
                
                # 重新计算准确率
                stat['accuracy_rate'] = stat['correct_predictions'] / stat['total_predictions'] if stat['total_predictions'] > 0 else 0.0
                
                # 更新平均置信度（简化计算）
                stat['avg_confidence'] = (stat['avg_confidence'] * (stat['total_predictions'] - 1) + record['confidence']) / stat['total_predictions']
                stat['calculated_at'] = datetime.now().isoformat()
            
            # 保存到数据库
            self._save_statistics_to_database(self._accuracy_statistics[stat_key])

        except Exception as e:
            logger.error(f"更新统计失败: {e}")

    def _save_statistics_to_database(self, stat_data: Dict[str, Any]) -> None:
        """保存统计到数据库"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO accuracy_statistics 
                        (stat_id, model_version_id, prediction_type, time_period,
                         total_predictions, correct_predictions, accuracy_rate, avg_confidence, calculated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        stat_data['stat_id'],
                        stat_data['model_version_id'],
                        stat_data['prediction_type'],
                        stat_data['time_period'],
                        stat_data['total_predictions'],
                        stat_data['correct_predictions'],
                        stat_data['accuracy_rate'],
                        stat_data['avg_confidence'],
                        stat_data['calculated_at']
                    ))
                    conn.commit()
            else:
                logger.error("DatabaseService不可用，无法保存统计")
                raise RuntimeError("DatabaseService不可用，无法保存统计")
        except Exception as e:
            logger.error(f"保存统计到数据库失败: {e}")
            raise

    def get_accuracy_statistics(self, model_version_id: Optional[str] = None,
                               prediction_type: Optional[str] = None,
                               time_period: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取准确性统计

        Args:
            model_version_id: 可选的模型版本ID筛选
            prediction_type: 可选的预测类型筛选
            time_period: 可选的时间周期筛选

        Returns:
            统计列表
        """
        with self._statistics_lock:
            stats = list(self._accuracy_statistics.values())
            
            if model_version_id:
                stats = [s for s in stats if s['model_version_id'] == model_version_id]
            
            if prediction_type:
                stats = [s for s in stats if s['prediction_type'] == prediction_type]
            
            if time_period:
                stats = [s for s in stats if s['time_period'] == time_period]
            
            return stats

    def get_accuracy_trend(self, model_version_id: str, prediction_type: str,
                          days: int = 30) -> List[Dict[str, Any]]:
        """
        获取准确性趋势

        Args:
            model_version_id: 模型版本ID
            prediction_type: 预测类型
            days: 天数

        Returns:
            趋势数据列表
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            stats = self.get_accuracy_statistics(
                model_version_id=model_version_id,
                prediction_type=prediction_type
            )
            
            # 按时间排序
            trend_data = []
            for stat in stats:
                try:
                    stat_date = datetime.fromisoformat(stat['time_period'])
                    if start_date <= stat_date <= end_date:
                        trend_data.append({
                            'date': stat['time_period'],
                            'accuracy_rate': stat['accuracy_rate'],
                            'total_predictions': stat['total_predictions'],
                            'correct_predictions': stat['correct_predictions'],
                            'avg_confidence': stat['avg_confidence']
                        })
                except:
                    continue
            
            # 按日期排序
            trend_data.sort(key=lambda x: x['date'])
            
            return trend_data

        except Exception as e:
            logger.error(f"获取准确性趋势失败: {e}")
            return []

    def get_prediction_records(self, model_version_id: Optional[str] = None,
                              prediction_type: Optional[str] = None,
                              limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取预测记录

        Args:
            model_version_id: 可选的模型版本ID筛选
            prediction_type: 可选的预测类型筛选
            limit: 返回记录数限制

        Returns:
            预测记录列表
        """
        with self._record_lock:
            records = list(self._prediction_records.values())
            
            if model_version_id:
                records = [r for r in records if r['model_version_id'] == model_version_id]
            
            if prediction_type:
                records = [r for r in records if r['prediction_type'] == prediction_type]
            
            # 按时间倒序排序
            records.sort(key=lambda x: x['prediction_time'], reverse=True)
            
            return records[:limit]

