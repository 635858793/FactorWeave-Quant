from utils.imports import (
    plt, pd, np, go, px, sns,
    get_plotly
)
from loguru import logger
from typing import Dict, List, Optional
from datetime import datetime

# 获取plotly子模块
_plotly_modules = get_plotly()
make_subplots = getattr(_plotly_modules.get(
    'subplots'), 'make_subplots', None) if _plotly_modules.get('subplots') else None

# 检查seaborn可用性
HAS_SEABORN = sns is not None

class RiskVisualizer:
    """风险报告可视化器"""

    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}

        # 设置matplotlib样式
        try:
            # 尝试使用seaborn样式
            sns.set_style("whitegrid")
            plt.style.use('seaborn-v0_8')
        except ImportError:
            try:
                # 如果seaborn不可用，尝试使用ggplot样式
                plt.style.use('ggplot')
            except:
                # 如果ggplot也不可用，使用默认样式
                plt.style.use('default')
                logger.warning("无法设置seaborn或ggplot样式，使用默认样式")

    def visualize_risk_report(self, report: Dict, output_path: Optional[str] = None) -> None:
        """可视化风险报告"""
        try:
            # 创建子图布局
            fig = make_subplots(
                rows=3, cols=2,
                subplot_titles=(
                    '风险指标趋势', '市场风险分析',
                    '行业风险暴露', '流动性风险分析',
                    '组合风险分析', '预警分析'
                )
            )

            # 1. 风险指标趋势
            self._plot_risk_indicators(fig, report['summary'], row=1, col=1)

            # 2. 市场风险分析
            self._plot_market_risk(fig, report['market_risk'], row=1, col=2)

            # 3. 行业风险暴露
            self._plot_sector_risk(fig, report['sector_risk'], row=2, col=1)

            # 4. 流动性风险分析
            self._plot_liquidity_risk(
                fig, report['liquidity_risk'], row=2, col=2)

            # 5. 组合风险分析
            self._plot_portfolio_risk(
                fig, report['portfolio_risk'], row=3, col=1)

            # 6. 预警分析
            self._plot_alert_analysis(
                fig, report['alert_analysis'], row=3, col=2)

            # 更新布局
            fig.update_layout(
                height=1200,
                width=1600,
                title_text="风险分析报告",
                showlegend=True
            )

            # 保存图表
            if output_path:
                fig.write_html(f"{output_path}/risk_report.html")
                fig.write_image(f"{output_path}/risk_report.png")

            return fig

        except Exception as e:
            logger.error(f"可视化风险报告时出错: {str(e)}")
            return None

    def _plot_risk_indicators(self, fig: go.Figure, summary: Dict, row: int, col: int) -> None:
        """绘制风险指标趋势"""
        try:
            indicators = summary['key_risk_indicators']

            for indicator in indicators:
                fig.add_trace(
                    go.Scatter(
                        x=list(range(len(indicator.get('historical_values', [])))),
                        y=indicator.get('historical_values', []),
                        name=indicator['name'],
                        mode='lines+markers'
                    ),
                    row=row, col=col
                )

            fig.update_xaxes(title_text="时间", row=row, col=col)
            fig.update_yaxes(title_text="指标值", row=row, col=col)

        except Exception as e:
            logger.error(f"绘制风险指标趋势时出错: {str(e)}")

    def _plot_market_risk(self, fig: go.Figure, market_risk: Dict, row: int, col: int) -> None:
        """绘制市场风险分析"""
        try:
            # 波动率分析
            volatility = market_risk['volatility_analysis']
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(volatility.get('historical', [])))),
                    y=volatility.get('historical', []),
                    name='波动率',
                    mode='lines'
                ),
                row=row, col=col
            )

            # Beta分析
            beta = market_risk['beta_analysis']
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(beta.get('historical', [])))),
                    y=beta.get('historical', []),
                    name='Beta',
                    mode='lines'
                ),
                row=row, col=col
            )

            fig.update_xaxes(title_text="时间", row=row, col=col)
            fig.update_yaxes(title_text="指标值", row=row, col=col)

        except Exception as e:
            logger.error(f"绘制市场风险分析时出错: {str(e)}")

    def _plot_sector_risk(self, fig: go.Figure, sector_risk: Dict, row: int, col: int) -> None:
        """绘制行业风险暴露"""
        try:
            sector_exposure = sector_risk['sector_exposure']

            fig.add_trace(
                go.Bar(
                    x=list(sector_exposure.keys()),
                    y=list(sector_exposure.values()),
                    name='行业暴露'
                ),
                row=row, col=col
            )

            fig.update_xaxes(title_text="行业", row=row, col=col)
            fig.update_yaxes(title_text="暴露比例", row=row, col=col)

        except Exception as e:
            logger.error(f"绘制行业风险暴露时出错: {str(e)}")

    def _plot_liquidity_risk(self, fig: go.Figure, liquidity_risk: Dict, row: int, col: int) -> None:
        """绘制流动性风险分析"""
        try:
            liquidity_ratios = liquidity_risk['liquidity_ratios']

            fig.add_trace(
                go.Bar(
                    x=list(liquidity_ratios.keys()),
                    y=list(liquidity_ratios.values()),
                    name='流动性比率'
                ),
                row=row, col=col
            )

            fig.update_xaxes(title_text="资产", row=row, col=col)
            fig.update_yaxes(title_text="流动性比率", row=row, col=col)

        except Exception as e:
            logger.error(f"绘制流动性风险分析时出错: {str(e)}")

    def _plot_portfolio_risk(self, fig: go.Figure, portfolio_risk: Dict, row: int, col: int) -> None:
        """绘制组合风险分析"""
        try:
            # VaR分析
            var = portfolio_risk['var_analysis']
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(var.get('historical', [])))),
                    y=var.get('historical', []),
                    name='VaR',
                    mode='lines'
                ),
                row=row, col=col
            )

            # ES分析
            es = portfolio_risk['es_analysis']
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(es.get('historical', [])))),
                    y=es.get('historical', []),
                    name='ES',
                    mode='lines'
                ),
                row=row, col=col
            )

            fig.update_xaxes(title_text="时间", row=row, col=col)
            fig.update_yaxes(title_text="风险值", row=row, col=col)

        except Exception as e:
            logger.error(f"绘制组合风险分析时出错: {str(e)}")

    def _plot_alert_analysis(self, fig: go.Figure, alert_analysis: Dict, row: int, col: int) -> None:
        """绘制预警分析"""
        try:
            alert_summary = alert_analysis['alert_summary']

            # 按级别统计
            fig.add_trace(
                go.Bar(
                    x=list(alert_summary['alert_by_level'].keys()),
                    y=list(alert_summary['alert_by_level'].values()),
                    name='预警级别分布'
                ),
                row=row, col=col
            )

            fig.update_xaxes(title_text="预警级别", row=row, col=col)
            fig.update_yaxes(title_text="数量", row=row, col=col)

        except Exception as e:
            logger.error(f"绘制预警分析时出错: {str(e)}")

    def create_risk_dashboard(self, report: Dict, output_path: Optional[str] = None) -> None:
        """创建风险仪表盘"""
        try:
            # 创建仪表盘布局
            fig = make_subplots(
                rows=2, cols=2,
                specs=[[{"type": "indicator"}, {"type": "indicator"}],
                       [{"type": "indicator"}, {"type": "indicator"}]],
                subplot_titles=(
                    '总体风险分数', '市场风险分数',
                    '行业风险分数', '流动性风险分数'
                )
            )

            # 添加风险分数指示器
            summary = report['summary']
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=summary['total_risk_score'] * 100,
                    title={'text': "总体风险分数"},
                    gauge={'axis': {'range': [0, 100]}}
                ),
                row=1, col=1
            )

            # 添加市场风险分数
            market_risk = report['market_risk']
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=market_risk.get('risk_score', 0) * 100,
                    title={'text': "市场风险分数"},
                    gauge={'axis': {'range': [0, 100]}}
                ),
                row=1, col=2
            )

            # 添加行业风险分数
            sector_risk = report['sector_risk']
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=sector_risk.get('risk_score', 0) * 100,
                    title={'text': "行业风险分数"},
                    gauge={'axis': {'range': [0, 100]}}
                ),
                row=2, col=1
            )

            # 添加流动性风险分数
            liquidity_risk = report['liquidity_risk']
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=liquidity_risk.get('risk_score', 0) * 100,
                    title={'text': "流动性风险分数"},
                    gauge={'axis': {'range': [0, 100]}}
                ),
                row=2, col=2
            )

            # 更新布局
            fig.update_layout(
                height=800,
                width=1200,
                title_text="风险监控仪表盘",
                showlegend=False
            )

            # 保存仪表盘
            if output_path:
                fig.write_html(f"{output_path}/risk_dashboard.html")
                fig.write_image(f"{output_path}/risk_dashboard.png")

            return fig

        except Exception as e:
            logger.error(f"创建风险仪表盘时出错: {str(e)}")
            return None
