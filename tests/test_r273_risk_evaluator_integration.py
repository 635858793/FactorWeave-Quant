# -*- coding: utf-8 -*-
"""R273-C 集成测试: RiskEvaluator 接入回测后处理 (2026-08-09)

背景:
- R273 死代码价值评估确认 RiskEvaluator + generate_comprehensive_risk_report
  为高价值死代码 (价值 7/10, 四维风险评估: VaR/CVaR/波动率/回撤/Beta + 集中度
  HHI + 流动性 + 操作/模型风险), 此前全仓库 0 消费, 用户已授权融入系统。
- 接入点: api_server.py 回测结果后处理 —— _generate_backtest_risk_report 在
  run_backtest (单股) 与 _run_portfolio_backtest (组合) 中附加 risk_report。

本文件验证 (真实实例化 + 真实方法调用, 不 mock 核心逻辑):
- A: RiskEvaluator 真实实例化 (临时 db_path, 避免依赖生产 data/factorweave_system.sqlite)。
- B: generate_comprehensive_risk_report 四维评估真实输出 (market/concentration/
  liquidity/operational + risk_summary/recommendations/overall_risk_level)。
- C: api_server._generate_backtest_risk_report 调用链端到端 (含集中度 HHI + 流动性)。
- D: api_server.run_backtest 单股回测 → 结果附加 risk_report (真实回测 + 真实后处理)。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.risk, pytest.mark.r273]


def make_returns(n_periods: int = 252, seed: int = 42) -> pd.Series:
    """构造策略收益率序列 (合成, 无需 DB)。"""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range('2024-01-01', periods=n_periods)
    returns = pd.Series(rng.normal(0.001, 0.02, n_periods), index=dates)
    return returns


def make_volumes(n_periods: int = 252, seed: int = 1) -> pd.Series:
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range('2024-01-01', periods=n_periods)
    return pd.Series(rng.lognormal(10, 1, n_periods), index=dates)


def test_risk_evaluator_instantiation_and_report():
    """A+B: RiskEvaluator 真实实例化 + 四维综合风险报告真实输出。

    db_path 用固定缓存路径 (Windows 下 SQLite 文件锁会导致临时目录清理
    PermissionError, 故不用 TemporaryDirectory; 测试结束显式删除)。
    """
    from evaluation.risk_evaluation import RiskEvaluator, create_risk_evaluator

    cache_dir = PROJECT_ROOT / 'cache'
    cache_dir.mkdir(exist_ok=True)
    db_path = str(cache_dir / 'test_r273_eval.sqlite')
    try:
        evaluator = create_risk_evaluator(db_path=db_path)
        assert isinstance(evaluator, RiskEvaluator)

        returns = make_returns()
        weights = {'AAPL': 0.3, 'GOOGL': 0.25, 'MSFT': 0.2, 'TSLA': 0.15, 'AMZN': 0.1}

        report = evaluator.generate_comprehensive_risk_report(
            returns=returns,
            portfolio_weights=weights,
            trading_volumes=make_volumes(),
            system_metrics={'uptime': 0.995, 'data_quality': 0.98},
        )

        # 顶层结构
        for key in ('timestamp', 'risk_metrics', 'risk_summary',
                    'recommendations', 'overall_risk_level'):
            assert key in report

        # 四维评估全部触发
        assert 'market' in report['risk_metrics']
        for mkey in ('var_95', 'var_99', 'cvar_95', 'volatility', 'max_drawdown'):
            assert mkey in report['risk_metrics']['market'], f"市场风险缺 {mkey}"
        assert 'concentration' in report['risk_metrics']
        assert 'hhi' in report['risk_metrics']['concentration']
        assert 'liquidity' in report['risk_metrics']
        assert 'liquidity_ratio' in report['risk_metrics']['liquidity']
        assert 'operational' in report['risk_metrics']

        # 风险等级合法
        assert report['overall_risk_level'] in ('low', 'medium', 'high', 'extreme')
    finally:
        try:
            Path(db_path).unlink(missing_ok=True)
        except OSError:
            pass


def test_generate_risk_report_helper():
    """C: api_server._generate_backtest_risk_report 调用链端到端 (四维 + 集中度 + 流动性)。"""
    from api_server import _generate_backtest_risk_report

    returns = make_returns(n_periods=120)
    weights = {'A': 0.5, 'B': 0.3, 'C': 0.2}

    report = _generate_backtest_risk_report(
        returns,
        portfolio_weights=weights,
        trading_volumes=make_volumes(n_periods=120),
    )

    assert report is not None
    assert 'risk_metrics' in report
    assert 'concentration' in report['risk_metrics']
    assert 'hhi' in report['risk_metrics']['concentration']
    assert 'liquidity' in report['risk_metrics']
    assert 'overall_risk_level' in report


def test_run_backtest_appends_risk_report():
    """D: api_server.run_backtest 单股回测 → 结果附加 risk_report (真实调用链)。"""
    from api_server import run_backtest

    n = 100
    rng = np.random.RandomState(3)
    prices = 100.0 * np.cumprod(1 + rng.normal(0.001, 0.02, n))
    signals = rng.choice([-1, 0, 1], size=n, p=[0.15, 0.7, 0.15])
    df = pd.DataFrame({
        'date': pd.bdate_range('2024-01-01', periods=n),
        'close': prices,
        'signal': signals,
    })

    response = run_backtest({'data': df.to_dict(orient='records')})

    assert response['result'] == 'success', response.get('error')
    metrics = response.get('metrics', {})
    # R273-C: risk_report 已附加到回测结果
    assert 'risk_report' in metrics, "单股回测结果应附加 risk_report"
    assert 'risk_metrics' in metrics['risk_report']
    assert 'overall_risk_level' in metrics['risk_report']
