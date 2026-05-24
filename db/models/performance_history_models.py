#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能历史数据模型
用于存储风险监控和执行监控的历史数据
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from loguru import logger
from core.database.unified_sqlite_access import UnifiedSQLiteAccess

@dataclass
class RiskHistoryRecord:
    """风险历史记录"""
    timestamp: datetime
    symbol: str
    var_95: float
    max_drawdown: float
    volatility: float
    beta: float
    sharpe_ratio: float
    position_risk: float
    market_risk: float
    sector_risk: float
    liquidity_risk: float
    credit_risk: float
    operational_risk: float
    concentration_risk: float
    overall_risk_score: float
    risk_level: str
    portfolio_value: float = 0.0
    notes: str = ""

@dataclass
class ExecutionHistoryRecord:
    """执行历史记录"""
    timestamp: datetime
    order_id: str
    symbol: str
    direction: str  # 'buy' or 'sell'
    quantity: int
    order_price: float
    execution_price: float
    execution_time: datetime
    latency_ms: float
    slippage_pct: float
    trading_cost_pct: float
    market_impact_pct: float
    twap_deviation_pct: float
    vwap_deviation_pct: float
    implementation_shortfall_pct: float
    execution_quality_score: float
    order_status: str  # 'filled', 'partial', 'cancelled'
    venue: str = ""
    notes: str = ""

class PerformanceHistoryManager:
    """性能历史数据管理器"""

    def __init__(self, db_path: str = 'data/factorweave_system.sqlite'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self._init_tables()

    def _init_tables(self):
        """初始化数据库表"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # 创建风险历史表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS risk_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        var_95 REAL DEFAULT 0.0,
                        max_drawdown REAL DEFAULT 0.0,
                        volatility REAL DEFAULT 0.0,
                        beta REAL DEFAULT 1.0,
                        sharpe_ratio REAL DEFAULT 0.0,
                        position_risk REAL DEFAULT 0.0,
                        market_risk REAL DEFAULT 0.0,
                        sector_risk REAL DEFAULT 0.0,
                        liquidity_risk REAL DEFAULT 0.0,
                        credit_risk REAL DEFAULT 0.0,
                        operational_risk REAL DEFAULT 0.0,
                        concentration_risk REAL DEFAULT 0.0,
                        overall_risk_score REAL DEFAULT 0.0,
                        risk_level TEXT DEFAULT 'unknown',
                        portfolio_value REAL DEFAULT 0.0,
                        notes TEXT DEFAULT '',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 创建执行历史表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS execution_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        order_id TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        quantity INTEGER NOT NULL,
                        order_price REAL NOT NULL,
                        execution_price REAL NOT NULL,
                        execution_time TEXT NOT NULL,
                        latency_ms REAL DEFAULT 0.0,
                        slippage_pct REAL DEFAULT 0.0,
                        trading_cost_pct REAL DEFAULT 0.0,
                        market_impact_pct REAL DEFAULT 0.0,
                        twap_deviation_pct REAL DEFAULT 0.0,
                        vwap_deviation_pct REAL DEFAULT 0.0,
                        implementation_shortfall_pct REAL DEFAULT 0.0,
                        execution_quality_score REAL DEFAULT 0.0,
                        order_status TEXT DEFAULT 'unknown',
                        venue TEXT DEFAULT '',
                        notes TEXT DEFAULT '',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 创建索引以提高查询性能
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_history(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_risk_symbol ON risk_history(symbol)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_execution_timestamp ON execution_history(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_execution_symbol ON execution_history(symbol)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_execution_order_id ON execution_history(order_id)')
                self.logger.info("性能历史数据表初始化完成")

        except Exception as e:
            self.logger.error(f"初始化性能历史数据表失败: {e}")

    def save_risk_record(self, record: RiskHistoryRecord) -> bool:
        """保存风险历史记录"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO risk_history (
                        timestamp, symbol, var_95, max_drawdown, volatility, beta,
                        sharpe_ratio, position_risk, market_risk, sector_risk,
                        liquidity_risk, credit_risk, operational_risk, concentration_risk,
                        overall_risk_score, risk_level, portfolio_value, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.timestamp.isoformat(),
                    record.symbol,
                    record.var_95,
                    record.max_drawdown,
                    record.volatility,
                    record.beta,
                    record.sharpe_ratio,
                    record.position_risk,
                    record.market_risk,
                    record.sector_risk,
                    record.liquidity_risk,
                    record.credit_risk,
                    record.operational_risk,
                    record.concentration_risk,
                    record.overall_risk_score,
                    record.risk_level,
                    record.portfolio_value,
                    record.notes
                ))
                self.logger.debug(f"风险历史记录已保存: {record.symbol} at {record.timestamp}")
                return True

        except Exception as e:
            self.logger.error(f"保存风险历史记录失败: {e}")
            return False

    def save_execution_record(self, record: ExecutionHistoryRecord) -> bool:
        """保存执行历史记录"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO execution_history (
                        timestamp, order_id, symbol, direction, quantity, order_price,
                        execution_price, execution_time, latency_ms, slippage_pct,
                        trading_cost_pct, market_impact_pct, twap_deviation_pct,
                        vwap_deviation_pct, implementation_shortfall_pct,
                        execution_quality_score, order_status, venue, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.timestamp.isoformat(),
                    record.order_id,
                    record.symbol,
                    record.direction,
                    record.quantity,
                    record.order_price,
                    record.execution_price,
                    record.execution_time.isoformat(),
                    record.latency_ms,
                    record.slippage_pct,
                    record.trading_cost_pct,
                    record.market_impact_pct,
                    record.twap_deviation_pct,
                    record.vwap_deviation_pct,
                    record.implementation_shortfall_pct,
                    record.execution_quality_score,
                    record.order_status,
                    record.venue,
                    record.notes
                ))
                self.logger.debug(f"执行历史记录已保存: {record.order_id}")
                return True

        except Exception as e:
            self.logger.error(f"保存执行历史记录失败: {e}")
            return False

    def get_risk_history(self, symbol: str = None, start_time: datetime = None,
                         end_time: datetime = None, limit: int = 1000) -> List[RiskHistoryRecord]:
        """获取风险历史记录"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # 构建查询条件
                conditions = []
                params = []

                if symbol:
                    conditions.append("symbol = ?")
                    params.append(symbol)

                if start_time:
                    conditions.append("timestamp >= ?")
                    params.append(start_time.isoformat())

                if end_time:
                    conditions.append("timestamp <= ?")
                    params.append(end_time.isoformat())

                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

                query = f'''
                    SELECT timestamp, symbol, var_95, max_drawdown, volatility, beta,
                           sharpe_ratio, position_risk, market_risk, sector_risk,
                           liquidity_risk, credit_risk, operational_risk, concentration_risk,
                           overall_risk_score, risk_level, portfolio_value, notes
                    FROM risk_history
                    {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ?
                '''

                params.append(limit)
                cursor.execute(query, params)

                records = []
                for row in cursor.fetchall():
                    record = RiskHistoryRecord(
                        timestamp=datetime.fromisoformat(row[0]),
                        symbol=row[1],
                        var_95=row[2],
                        max_drawdown=row[3],
                        volatility=row[4],
                        beta=row[5],
                        sharpe_ratio=row[6],
                        position_risk=row[7],
                        market_risk=row[8],
                        sector_risk=row[9],
                        liquidity_risk=row[10],
                        credit_risk=row[11],
                        operational_risk=row[12],
                        concentration_risk=row[13],
                        overall_risk_score=row[14],
                        risk_level=row[15],
                        portfolio_value=row[16],
                        notes=row[17]
                    )
                    records.append(record)

                return records

        except Exception as e:
            self.logger.error(f"获取风险历史记录失败: {e}")
            return []

    def get_execution_history(self, symbol: str = None, start_time: datetime = None,
                              end_time: datetime = None, limit: int = 1000) -> List[ExecutionHistoryRecord]:
        """获取执行历史记录"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # 构建查询条件
                conditions = []
                params = []

                if symbol:
                    conditions.append("symbol = ?")
                    params.append(symbol)

                if start_time:
                    conditions.append("timestamp >= ?")
                    params.append(start_time.isoformat())

                if end_time:
                    conditions.append("timestamp <= ?")
                    params.append(end_time.isoformat())

                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

                query = f'''
                    SELECT timestamp, order_id, symbol, direction, quantity, order_price,
                           execution_price, execution_time, latency_ms, slippage_pct,
                           trading_cost_pct, market_impact_pct, twap_deviation_pct,
                           vwap_deviation_pct, implementation_shortfall_pct,
                           execution_quality_score, order_status, venue, notes
                    FROM execution_history
                    {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ?
                '''

                params.append(limit)
                cursor.execute(query, params)

                records = []
                for row in cursor.fetchall():
                    record = ExecutionHistoryRecord(
                        timestamp=datetime.fromisoformat(row[0]),
                        order_id=row[1],
                        symbol=row[2],
                        direction=row[3],
                        quantity=row[4],
                        order_price=row[5],
                        execution_price=row[6],
                        execution_time=datetime.fromisoformat(row[7]),
                        latency_ms=row[8],
                        slippage_pct=row[9],
                        trading_cost_pct=row[10],
                        market_impact_pct=row[11],
                        twap_deviation_pct=row[12],
                        vwap_deviation_pct=row[13],
                        implementation_shortfall_pct=row[14],
                        execution_quality_score=row[15],
                        order_status=row[16],
                        venue=row[17],
                        notes=row[18]
                    )
                    records.append(record)

                return records

        except Exception as e:
            self.logger.error(f"获取执行历史记录失败: {e}")
            return []

    def get_risk_statistics(self, symbol: str = None, days: int = 30) -> Dict[str, Any]:
        """获取风险统计信息"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            records = self.get_risk_history(symbol, start_time, end_time)

            if not records:
                return {}

            # 计算统计信息
            var_values = [r.var_95 for r in records if r.var_95 > 0]
            drawdown_values = [r.max_drawdown for r in records if r.max_drawdown > 0]
            volatility_values = [r.volatility for r in records if r.volatility > 0]
            risk_scores = [r.overall_risk_score for r in records if r.overall_risk_score > 0]

            stats = {
                'total_records': len(records),
                'avg_var': sum(var_values) / len(var_values) if var_values else 0,
                'max_var': max(var_values) if var_values else 0,
                'avg_drawdown': sum(drawdown_values) / len(drawdown_values) if drawdown_values else 0,
                'max_drawdown': max(drawdown_values) if drawdown_values else 0,
                'avg_volatility': sum(volatility_values) / len(volatility_values) if volatility_values else 0,
                'avg_risk_score': sum(risk_scores) / len(risk_scores) if risk_scores else 0,
                'max_risk_score': max(risk_scores) if risk_scores else 0,
                'period_days': days
            }

            return stats

        except Exception as e:
            self.logger.error(f"获取风险统计信息失败: {e}")
            return {}

    def get_execution_statistics(self, symbol: str = None, days: int = 30) -> Dict[str, Any]:
        """获取执行统计信息"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            records = self.get_execution_history(symbol, start_time, end_time)

            if not records:
                return {}

            # 计算统计信息
            latencies = [r.latency_ms for r in records if r.latency_ms > 0]
            slippages = [abs(r.slippage_pct) for r in records if r.slippage_pct != 0]
            costs = [r.trading_cost_pct for r in records if r.trading_cost_pct > 0]
            quality_scores = [r.execution_quality_score for r in records if r.execution_quality_score > 0]

            filled_orders = len([r for r in records if r.order_status == 'filled'])
            partial_orders = len([r for r in records if r.order_status == 'partial'])
            cancelled_orders = len([r for r in records if r.order_status == 'cancelled'])

            stats = {
                'total_orders': len(records),
                'filled_orders': filled_orders,
                'partial_orders': partial_orders,
                'cancelled_orders': cancelled_orders,
                'fill_rate': (filled_orders / len(records)) * 100 if records else 0,
                'avg_latency': sum(latencies) / len(latencies) if latencies else 0,
                'max_latency': max(latencies) if latencies else 0,
                'avg_slippage': sum(slippages) / len(slippages) if slippages else 0,
                'max_slippage': max(slippages) if slippages else 0,
                'avg_cost': sum(costs) / len(costs) if costs else 0,
                'avg_quality_score': sum(quality_scores) / len(quality_scores) if quality_scores else 0,
                'period_days': days
            }

            return stats

        except Exception as e:
            self.logger.error(f"获取执行统计信息失败: {e}")
            return {}

    def cleanup_old_records(self, days_to_keep: int = 90):
        """清理旧记录"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)

            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # 删除旧的风险记录
                cursor.execute(
                    "DELETE FROM risk_history WHERE timestamp < ?",
                    (cutoff_time.isoformat(),)
                )
                risk_deleted = cursor.rowcount

                # 删除旧的执行记录
                cursor.execute(
                    "DELETE FROM execution_history WHERE timestamp < ?",
                    (cutoff_time.isoformat(),)
                )
                execution_deleted = cursor.rowcount
                self.logger.info(f"清理完成: 删除{risk_deleted}条风险记录, {execution_deleted}条执行记录")
                return True

        except Exception as e:
            self.logger.error(f"清理旧记录失败: {e}")
            return False

# 全局实例
_performance_history_manager = None

def get_performance_history_manager() -> PerformanceHistoryManager:
    """获取性能历史数据管理器实例"""
    global _performance_history_manager
    if _performance_history_manager is None:
        _performance_history_manager = PerformanceHistoryManager()
    return _performance_history_manager
