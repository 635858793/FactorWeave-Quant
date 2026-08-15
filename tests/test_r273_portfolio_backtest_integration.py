# -*- coding: utf-8 -*-
"""R273-B 集成测试: PortfolioBacktestEngine 接入 (2026-08-09)

背景:
- R273 死代码价值评估确认 PortfolioBacktestEngine + create_portfolio_backtest_engine
  为高价值死代码 (价值 8/10, 多股票组合权重 + D/M/Q/BH 再平衡, 无同等功能等价物),
  此前全仓库 0 消费, 用户已授权融入系统。
- 接入点: api_server.py /api/backtest 组合回测分支 (portfolio_mode) ——
  _run_portfolio_backtest: create_portfolio_backtest_engine → run_portfolio_backtest
  → 风险报告后处理 (R273-C 共用)。

本文件验证 (真实实例化 + 真实方法调用, 不 mock 核心逻辑):
- A: create_portfolio_backtest_engine 可实例化 (basic/professional 级别)。
- B: run_portfolio_backtest 真实运行 (3 只股票合成 K 线, D/M/Q/BH 四种再平衡频率),
  返回结构完整 (portfolio_result/portfolio_metrics/individual_data/weights)。
- C: 接入点端到端 —— api_server._run_portfolio_backtest 组合请求 → success,
  portfolio_metrics 完整 + risk_report 附加 (RiskEvaluator 四维报告)。
- D: run_backtest 组合分支路由 (portfolio_mode=True 走组合引擎)。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.backtest, pytest.mark.r273]

STOCK_CODES = ['A', 'B', 'C']
WEIGHTS = {'A': 0.4, 'B': 0.3, 'C': 0.3}


def make_portfolio_data(n_periods: int = 80, seed: int = 42):
    """构造 3 只股票合成 K 线 (工作日序列, 含 close/volume)。"""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range('2024-01-01', periods=n_periods)
    portfolio_data = {}
    for i, code in enumerate(STOCK_CODES):
        drift = 0.001 + 0.0005 * i
        prices = 100.0 * np.cumprod(1 + rng.normal(drift, 0.015, n_periods))
        df = pd.DataFrame({
            'close': prices,
            'volume': rng.randint(1000, 10000, n_periods),
        }, index=dates)
        portfolio_data[code] = df
    return portfolio_data


def make_api_payload(n_periods: int = 80, seed: int = 42):
    """构造 api_server 组合回测请求体 (JSON 兼容形式)。"""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range('2024-01-01', periods=n_periods)
    portfolio_data = {}
    for i, code in enumerate(STOCK_CODES):
        drift = 0.001 + 0.0005 * i
        prices = 100.0 * np.cumprod(1 + rng.normal(drift, 0.015, n_periods))
        portfolio_data[code] = {
            'data': [
                {'date': d.isoformat(), 'close': float(p), 'volume': int(v)}
                for d, p, v in zip(
                    dates, prices, rng.randint(1000, 10000, n_periods))
            ]
        }
    return portfolio_data


def test_create_portfolio_backtest_engine_instances():
    """A: create_portfolio_backtest_engine 真实实例化 (多级别)。"""
    from backtest.unified_backtest_engine import (
        BacktestLevel,
        PortfolioBacktestEngine,
        create_portfolio_backtest_engine,
    )
    for level in ['basic', 'professional', 'institutional', 'investment_bank']:
        engine = create_portfolio_backtest_engine(level=level)
        assert isinstance(engine, PortfolioBacktestEngine)
        assert engine.backtest_level in BacktestLevel

    # 非法级别降级为 PROFESSIONAL
    engine = create_portfolio_backtest_engine(level='unknown')
    assert engine.backtest_level == BacktestLevel.PROFESSIONAL


@pytest.mark.parametrize('rebalance', ['D', 'M', 'Q', 'BH'])
def test_run_portfolio_backtest_all_rebalance_frequencies(rebalance):
    """B: run_portfolio_backtest 真实运行, 四种再平衡频率结果结构完整。"""
    from backtest.unified_backtest_engine import create_portfolio_backtest_engine

    engine = create_portfolio_backtest_engine(level='professional')
    result = engine.run_portfolio_backtest(
        portfolio_data=make_portfolio_data(),
        weights=WEIGHTS,
        rebalance_frequency=rebalance,
        initial_capital=1_000_000,
    )

    assert set(result.keys()) == {
        'portfolio_result', 'portfolio_metrics', 'individual_data', 'weights'}

    portfolio_result = result['portfolio_result']
    assert isinstance(portfolio_result, pd.DataFrame)
    assert {'portfolio_returns', 'cumulative_returns', 'portfolio_value'} <= set(portfolio_result.columns)
    assert len(portfolio_result) > 0
    assert portfolio_result['portfolio_value'].iloc[-1] > 0

    metrics = result['portfolio_metrics']
    for key in ('total_return', 'annualized_return', 'volatility',
                'sharpe_ratio', 'max_drawdown', 'calmar_ratio'):
        assert key in metrics, f"缺少组合指标: {key}"

    assert result['weights'] == WEIGHTS
    assert set(result['individual_data'].keys()) == set(STOCK_CODES)


def test_api_portfolio_backtest_endpoint():
    """C: 接入点端到端 —— api_server._run_portfolio_backtest 组合请求。"""
    from api_server import _run_portfolio_backtest

    params = {
        'portfolio_mode': True,
        'portfolio_data': make_api_payload(),
        'portfolio_weights': WEIGHTS,
        'rebalance_frequency': 'M',
        'initial_capital': 1_000_000,
        'backtest_level': 'professional',
    }
    response = _run_portfolio_backtest(params)

    assert response['result'] == 'success', response.get('error')
    metrics = response['metrics']
    assert metrics['portfolio_mode'] is True
    assert metrics['stocks'] == STOCK_CODES
    assert metrics['weights'] == WEIGHTS
    assert metrics['rebalance_frequency'] == 'M'

    # 组合指标完整 (JSON 安全返回)
    pm = metrics['portfolio_metrics']
    for key in ('total_return', 'annualized_return', 'volatility',
                'sharpe_ratio', 'max_drawdown', 'calmar_ratio'):
        assert key in pm

    # 净值曲线 (列表形式, JSON 安全)
    assert isinstance(metrics['equity_curve'], list) and len(metrics['equity_curve']) > 0
    assert isinstance(metrics['final_equity'], float)

    # R273-C: 风险报告附加 (四维 + 集中度 HHI, 因传入 portfolio_weights)
    risk_report = metrics.get('risk_report')
    assert risk_report is not None
    assert 'risk_metrics' in risk_report
    assert 'concentration' in risk_report['risk_metrics'], "组合回测应含集中度 HHI 评估"
    assert 'hhi' in risk_report['risk_metrics']['concentration']
    assert 'overall_risk_level' in risk_report


def test_api_run_backtest_portfolio_route():
    """D: run_backtest 组合分支路由 (portfolio_mode=True → 组合引擎, 不落单股路径)。"""
    from api_server import run_backtest

    params = {
        'data': [{'date': '2024-01-02', 'close': 100.0, 'signal': 1}],  # 单股数据 (不应被使用)
        'portfolio_mode': True,
        'portfolio_data': make_api_payload(n_periods=60, seed=7),
        'portfolio_weights': WEIGHTS,
        'rebalance_frequency': 'Q',
    }
    response = run_backtest(params)
    assert response['result'] == 'success', response.get('error')
    assert response['metrics']['portfolio_mode'] is True
    assert 'portfolio_metrics' in response['metrics']


def test_api_portfolio_backtest_error_paths():
    """组合回测错误路径: 空数据/缺权重/缺列 返回 error 而非抛异常。"""
    from api_server import _run_portfolio_backtest

    # 空组合数据
    r = _run_portfolio_backtest({'portfolio_data': {}, 'portfolio_weights': WEIGHTS})
    assert r['result'] == 'error'

    # 缺权重
    r = _run_portfolio_backtest({'portfolio_data': make_api_payload()})
    assert r['result'] == 'error'

    # 缺 close/returns 列
    r = _run_portfolio_backtest({
        'portfolio_data': {'X': {'data': [{'date': '2024-01-02', 'foo': 1}]}},
        'portfolio_weights': {'X': 1.0},
    })
    assert r['result'] == 'error'
