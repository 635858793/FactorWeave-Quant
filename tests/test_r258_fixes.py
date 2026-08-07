#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R258 修复验证测试（TDD RED→GREEN 基线）

覆盖 3 个 100% 确认项（主智能体源码行号交叉验证实证，缺失引用标记"待验证"）：

1. 财务列名断裂 P0 —— total_revenue 数据 0 行落库链
   - core/tet_data_pipeline.py:187 FINANCIAL_STATEMENT 利润表映射缺 'total_revenue' 键
     （插件产出 eastmoney_unified_plugin.py:440）
   - core/database/duckdb_operations.py:382-407 _upsert_batch 无表结构列过滤
     → DuckDB Binder Error → 全事务 ROLLBACK (:176-177) → 财务数据 0 行落库
   - core/services/unified_data_manager.py:3106-3111 _store_financial_to_duckdb
     未传 conflict_columns → 走普通 INSERT (duckdb_operations.py:163 条件
     `upsert and conflict_columns`) → 主键重复即 ROLLBACK
2. conftest mock 污染治理 —— tests/conftest.py:18-41 注入 22 个 GUI 模块 MagicMock
   - 其中 'gui'(:19) / 'gui.utils'(:30) / 'gui.utils.responsive_helper'(:31) 阻断真实模块
   - 实证: responsive_helper.py:27-31 无 QApplication 时安全返回 1.0 → 应放开真实导入
3. enable_risk_control 死代码 —— 写 4 读 0
   - core/services/trading_service.py:283/:343/:348/:353 写入, 全库 0 读取
   - 真实风控链: core/trading/order_executor.py:756-859 _pre_trade_risk_check 无条件执行
   - 修复: OrderExecutor._risk_control_enabled 开关 + set_trading_mode 联动下发

测试策略 (同 R252-R255 模式):
- 隔离重型 DB 依赖: order_repository / account_repository 以 MagicMock 承担
  (MagicMock 自动属性特性使 `from ... import OrderRepository` 不失败)
- TestConftestMockGovernance 故意不弹出 gui mock —— RED 阶段实证 conftest 污染,
  修复 conftest.py 后自动转 GREEN
"""
import os
import sys
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# 隔离重型 DB 依赖 (同 R255 模式: tests/test_r255_trading_mode.py:59-60, 88-89)
sys.modules['core.trading.order_repository'] = MagicMock(name='order_repository_mock')
sys.modules['core.trading.account_repository'] = MagicMock(name='account_repository_mock')

import pandas as pd
import pytest

from core.trading.order_executor import OrderExecutor
from core.tet_data_pipeline import TETDataPipeline
from core.plugin_types import DataType
from core.database.duckdb_operations import DuckDBOperations
from core.services.unified_data_manager import UnifiedDataManager


# ===========================================================================
# 1. conftest mock 污染治理 (tests/conftest.py:18-41)
# ===========================================================================
class TestConftestMockGovernance:
    """conftest 不得 mock 无 Qt 依赖的真实模块 (responsive_helper 实证无 app 安全)"""

    def test_responsive_helper_is_real_module(self):
        """conftest.py:31 不应 mock 'gui.utils.responsive_helper'
        实证: responsive_helper.py:27-31 无 QApplication 时安全返回 1.0"""
        import gui.utils.responsive_helper as rh
        assert not isinstance(rh, MagicMock), \
            "conftest mock 污染: gui.utils.responsive_helper 仍被 MagicMock 替代"
        assert hasattr(rh, 'get_device_pixel_ratio')

    def test_get_device_pixel_ratio_offscreen_safe(self):
        """responsive_helper.py:27-31: 无 QApplication 时安全返回 1.0 (不崩溃)"""
        import gui.utils.responsive_helper as rh
        helper = rh.get_responsive_helper()
        helper.invalidate_cache()
        assert helper.get_device_pixel_ratio() == 1.0


# ===========================================================================
# 2. 财务列名断裂 P0 (total_revenue 数据 0 行落库链)
# ===========================================================================
class TestFinancialColumnBreak:
    """P0 数据丢失: 插件产出列名与统一表 schema 断裂 → 全事务 ROLLBACK"""

    def test_tet_mapping_has_total_revenue_key(self):
        """tet_data_pipeline.py:187 利润表映射须含 'total_revenue' → 'operating_revenue'
        否则插件产出 (eastmoney_unified_plugin.py:440) 无法标准化 → 落库 Binder Error"""
        pipe = TETDataPipeline(MagicMock())
        fs_map = pipe.field_mappings[DataType.FINANCIAL_STATEMENT]
        assert fs_map.get('total_revenue') == 'operating_revenue', \
            "映射缺 total_revenue 键 (tet_data_pipeline.py:187) — 待修复"

    def test_upsert_filters_unknown_columns(self):
        """duckdb_operations.py:382-407 _upsert_batch 须过滤表结构不存在列
        (参照 K线先例: duckdb_operations.py:355-357 keep_columns 白名单)"""
        import tempfile
        import shutil
        td = tempfile.mkdtemp()  # 手动目录, 清理忽略权限错误 (duckdb 句柄占用的已知平台行为)
        try:
            db_path = os.path.join(td, 't.duckdb')
            conn = __import__('duckdb').connect(db_path)
            conn.execute('''
                CREATE TABLE financial_statements (
                    symbol VARCHAR,
                    report_date DATE,
                    report_type VARCHAR,
                    operating_revenue DECIMAL(20,2),
                    net_profit DECIMAL(20,2),
                    PRIMARY KEY (symbol, report_date, report_type))
            ''')
            conn.close()
            ops = DuckDBOperations()
            df = pd.DataFrame([{
                'symbol': '600000',
                'report_date': pd.Timestamp('2024-01-01').date(),
                'report_type': 'annual',
                'total_revenue': 100.0,       # 表结构不存在列 → 修复前 Binder Error
                'operating_revenue': 100.0,
                'net_profit': 20.0,
            }])
            result = ops.insert_dataframe(
                database_path=db_path,
                table_name='financial_statements',
                data=df,
                upsert=True,
                conflict_columns=['symbol', 'report_date', 'report_type'],
            )
            assert result.success, \
                f"落库失败 (total_revenue 列未过滤 → Binder Error → ROLLBACK): {result.failed_batches}"
            # 验证 total_revenue 未落入表
            check = ops.execute_query(
                database_path=db_path,
                query='SELECT operating_revenue, net_profit FROM financial_statements',
            )
            assert check.success and len(check.data) > 0, "修复后应成功落库 1 行"
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_store_financial_passes_conflict_columns(self):
        """unified_data_manager.py:3116-3122 应传 conflict_columns=['symbol','report_date','report_type']
        (真实表主键 table_manager.py:287; 表无 update_time 列, 引用即 Binder Error)
        且兼容 TET 管道 DataFrame 输入 (unified_data_manager.py:2963-2967)"""
        mgr = UnifiedDataManager.__new__(UnifiedDataManager)
        mgr.duckdb_operations = MagicMock()
        mgr.asset_manager = MagicMock()
        mgr.asset_identifier = MagicMock()
        mgr.table_manager = MagicMock()
        mgr.asset_identifier.identify_asset_type.return_value = None
        mgr.asset_manager.get_database_path.return_value = '/tmp/r258_x.duckdb'
        mgr.table_manager.ensure_table_exists.return_value = 'financial_statements'
        mgr._migrate_legacy_financial_tables = MagicMock()
        mgr.duckdb_operations.insert_dataframe.return_value = MagicMock(success=True)

        # dict 输入 (旧路径)
        await mgr._store_financial_to_duckdb('600000', {'net_profit': 1.0})
        kwargs = mgr.duckdb_operations.insert_dataframe.call_args.kwargs
        assert kwargs.get('conflict_columns') == ['symbol', 'report_date', 'report_type'], \
            "unified_data_manager.py conflict_columns 未对齐真实表主键 — 待修复"

        # DataFrame 输入 (TET 管道真实路径) → 不抛 ValueError
        await mgr._store_financial_to_duckdb(
            '600000',
            pd.DataFrame([{'net_profit': 2.0, 'operating_revenue': 3.0}]),
        )
        assert mgr.duckdb_operations.insert_dataframe.call_count == 2, \
            "DataFrame 输入应正常走到 insert_dataframe (pd.DataFrame([DataFrame]) 会 ValueError)"


# ===========================================================================
# 3. enable_risk_control 死代码接入真实风控链
# ===========================================================================
class TestRiskControlEnableChain:
    """enable_risk_control (trading_service.py:283/343/348/353 写 4 读 0)
    接入真实风控链 OrderExecutor._pre_trade_risk_check (order_executor.py:756-859)"""

    def _make_executor(self):
        return OrderExecutor(MagicMock(), MagicMock())

    def test_executor_has_risk_control_flag(self):
        """order_executor.py:340 附近应初始化 _risk_control_enabled=True (默认开, 资金安全)"""
        ex = self._make_executor()
        assert getattr(ex, '_risk_control_enabled', None) is True, \
            "OrderExecutor 缺少 _risk_control_enabled 开关 — 待修复"

    def test_set_trading_mode_propagates_risk_control(self):
        """set_trading_mode 联动 _risk_control_enabled:
        backtest 可关 (enable_risk_control=False), live/paper 强制开 (资金安全)"""
        ex = self._make_executor()
        ex.set_trading_mode('backtest', enable_risk_control=False)
        assert ex._risk_control_enabled is False, "backtest 关闭风控未联动"
        ex.set_trading_mode('live')
        assert ex._risk_control_enabled is True, "live 必须强制开启风控"

    def test_pre_trade_risk_check_respects_switch(self):
        """禁用时 _pre_trade_risk_check 快速放行 (passed=True), 不阻断业务"""
        ex = self._make_executor()
        ex._risk_control_enabled = False
        order = MagicMock()
        result = ex._pre_trade_risk_check(order)
        assert result.get('passed') is True, "风控开关禁用后仍被阻断 — 待修复"
