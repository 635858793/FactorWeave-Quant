import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from sklearn.metrics import confusion_matrix
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from loguru import logger

logger = logger

class CommonVisualization:
    """通用可视化工具类"""

    def __init__(self, style=None):
        """
        初始化可视化工具

        参数:
            style: dict, 自定义样式配置
        """
        self.style = style or {
            'price_color': 'blue',
            'buy_color': '#FF0000',
            'sell_color': '#00FF00',
            'grid_alpha': 0.3,
            'buy_marker': '^',
            'sell_marker': 'v',
            'marker_size': 100,
            'font_size': 12
        }

        # 设置默认样式
        plt.style.use('seaborn-v0_8-whitegrid')

    def _validate_dataframe(self, df, required_columns):
        """验证DataFrame的有效性

        参数:
            df: pandas DataFrame
            required_columns: list, 必需的列名列表
        """
        if df is None or df.empty:
            raise ValueError("输入的DataFrame为空")

        missing_cols = [
            col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"DataFrame中缺少必需的列: {', '.join(missing_cols)}")

        return True

    def plot_signals_on_price(self, df, price_col='close', signal_col='signal',
                              figsize=(15, 8), style=None):
        """
        在价格图上绘制交易信号

        参数:
            df: DataFrame，包含价格和信号数据
            price_col: str，价格列名
            signal_col: str，信号列名
            figsize: tuple，图形大小
            style: dict，自定义样式
        """
        try:
            # 验证数据
            self._validate_dataframe(df, [price_col, signal_col])

            # 合并自定义样式
            current_style = self.style.copy()
            if style:
                current_style.update(style)

            # 创建图形
            fig = plt.figure(figsize=figsize)
            ax = fig.add_subplot(111)

            # 绘制价格
            ax.plot(df.index, df[price_col], label='Price',
                    color=current_style['price_color'])

            # 使用布尔索引提高性能
            buy_mask = df[signal_col] == 1
            sell_mask = df[signal_col] == -1

            if buy_mask.any():
                ax.scatter(df.index[buy_mask], df[price_col][buy_mask],
                           color=current_style['buy_color'],
                           marker=current_style['buy_marker'],
                           s=current_style['marker_size'],
                           label='Buy Signal')

            if sell_mask.any():
                ax.scatter(df.index[sell_mask], df[price_col][sell_mask],
                           color=current_style['sell_color'],
                           marker=current_style['sell_marker'],
                           s=current_style['marker_size'],
                           label='Sell Signal')

            # 设置标题和标签
            ax.set_title('Price Chart with Trading Signals',
                         fontsize=current_style['font_size'] * 1.2)
            ax.set_xlabel('Date', fontsize=current_style['font_size'])
            ax.set_ylabel('Price', fontsize=current_style['font_size'])

            # 设置图例
            ax.legend(fontsize=current_style['font_size'])

            # 添加网格
            ax.grid(True, alpha=current_style['grid_alpha'])

            # 格式化日期轴
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            fig.autofmt_xdate()

            # 优化显示
            plt.tight_layout()

            return fig

        except Exception as e:
            logger.error(f"绘制信号图表失败: {str(e)}")
            raise

    def plot_signal_performance(self, df, price_col='close', signal_col='signal',
                                position_col='position', trade_profit_col='trade_profit',
                                figsize=(15, 10), style=None, chunk_size=1000):
        """
        绘制信号表现分析图

        参数:
            df: DataFrame，包含交易数据
            price_col: str，价格列名
            signal_col: str，信号列名
            position_col: str，持仓列名
            trade_profit_col: str，交易收益列名
            figsize: tuple，图形大小
            style: dict，自定义样式
            chunk_size: int，数据分块大小，用于优化大数据集的处理
        """
        try:
            # 验证数据
            required_cols = [price_col, signal_col, position_col]
            if trade_profit_col:
                required_cols.append(trade_profit_col)
            self._validate_dataframe(df, required_cols)

            # 合并自定义样式
            current_style = self.style.copy()
            if style:
                current_style.update(style)

            # 创建子图
            fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True,
                                     gridspec_kw={'height_ratios': [2, 1, 1]})

            # 分块处理数据以优化性能
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i+chunk_size]

                # 绘制价格
                if i == 0:  # 只在第一次迭代时添加标签
                    axes[0].plot(chunk.index, chunk[price_col],
                                 color=current_style['price_color'],
                                 label='Price')
                else:
                    axes[0].plot(chunk.index, chunk[price_col],
                                 color=current_style['price_color'])

                # 处理信号
                buy_mask = chunk[signal_col] == 1
                sell_mask = chunk[signal_col] == -1

                if buy_mask.any():
                    axes[0].scatter(chunk.index[buy_mask],
                                    chunk[price_col][buy_mask],
                                    color=current_style['buy_color'],
                                    marker=current_style['buy_marker'],
                                    s=current_style['marker_size'],
                                    label='Buy Signal' if i == 0 else None)

                if sell_mask.any():
                    axes[0].scatter(chunk.index[sell_mask],
                                    chunk[price_col][sell_mask],
                                    color=current_style['sell_color'],
                                    marker=current_style['sell_marker'],
                                    s=current_style['marker_size'],
                                    label='Sell Signal' if i == 0 else None)

            # 设置第一个子图的属性
            axes[0].set_title('Signal Performance Analysis',
                              fontsize=current_style['font_size'] * 1.2)
            axes[0].set_ylabel('Price', fontsize=current_style['font_size'])
            axes[0].legend(fontsize=current_style['font_size'])
            axes[0].grid(True, alpha=current_style['grid_alpha'])

            # 绘制持仓状态
            axes[1].plot(df.index, df[position_col],
                         label='Position', color='purple')
            axes[1].set_ylabel('Position\n(1=Long, -1=Short, 0=Flat)',
                               fontsize=current_style['font_size'])
            axes[1].axhline(y=0, color='black', linestyle='-',
                            alpha=current_style['grid_alpha'])
            axes[1].grid(True, alpha=current_style['grid_alpha'])

            # 绘制交易收益
            if trade_profit_col in df.columns:
                trade_profits = df[df[trade_profit_col] != 0]

                if not trade_profits.empty:
                    colors = np.where(trade_profits[trade_profit_col] > 0,
                                      current_style['buy_color'],
                                      current_style['sell_color'])

                    axes[2].bar(trade_profits.index,
                                trade_profits[trade_profit_col],
                                color=colors, label='Trade Profit')

                    axes[2].set_ylabel('Trade Profit',
                                       fontsize=current_style['font_size'])
                    axes[2].axhline(y=0, color='black', linestyle='-',
                                    alpha=current_style['grid_alpha'])
                    axes[2].grid(True, alpha=current_style['grid_alpha'])
            else:
                axes[2].set_visible(False)

            # 设置x轴标签
            plt.xlabel('Date', fontsize=current_style['font_size'])

            # 格式化日期轴
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.gcf().autofmt_xdate()

            # 优化显示
            plt.tight_layout()

            return fig

        except Exception as e:
            logger.error(f"绘制信号性能分析图表失败: {str(e)}")
            raise

    def plot_signal_distribution(self, df, signal_col='signal', figsize=(15, 8)):
        """
        分析信号分布

        参数:
            df: DataFrame，包含信号数据
            signal_col: str，信号列名
            figsize: tuple，图形大小
        """
        if signal_col not in df.columns:
            raise ValueError(f"DataFrame中缺少信号列: {signal_col}")

        # 计算信号分布
        signal_counts = df[signal_col].value_counts()

        # 创建图形
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # 柱状图显示信号计数
        ax1.bar(signal_counts.index.map({1: 'Buy', -1: 'Sell', 0: 'Hold'}),
                signal_counts.values, color=['green', 'grey', 'red'])
        ax1.set_title('Signal Distribution', fontsize=15)
        ax1.set_ylabel('Count')
        ax1.grid(True, alpha=0.3)

        # 计算信号在时间上的分布
        signal_over_time = pd.DataFrame(index=df.index)
        signal_over_time['month'] = df.index.month
        signal_over_time['year'] = df.index.year
        signal_over_time['signal'] = df[signal_col]

        # 按月份统计信号
        monthly_signals = signal_over_time.groupby(['year', 'month'])['signal'].apply(
            lambda x: pd.Series({
                'buy': (x == 1).sum(),
                'sell': (x == -1).sum(),
                'hold': (x == 0).sum()
            })
        ).unstack()

        # 热力图显示月度信号分布
        if hasattr(monthly_signals.index, 'levels'):  # MultiIndex
            month_labels = monthly_signals.index.get_level_values(1)
            year_labels = monthly_signals.index.get_level_values(0)

            # 创建热力图
            sns.heatmap(monthly_signals, ax=ax2, cmap='YlOrRd',
                        annot=True, fmt='.0f', cbar=True)

            ax2.set_title('Monthly Signal Distribution', fontsize=15)
            ax2.set_xlabel('Signal Type')
            ax2.set_ylabel('Year-Month')

        plt.tight_layout()

        return fig

    def plot_confusion_matrix_custom(self, y_true, y_pred, figsize=(10, 8), normalize=True):
        """
        绘制自定义混淆矩阵

        参数:
            y_true: array-like，真实标签
            y_pred: array-like，预测标签
            figsize: tuple，图形大小
            normalize: bool，是否归一化
        """
        # 计算混淆矩阵
        cm = confusion_matrix(y_true, y_pred)

        if normalize:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

        # 创建图形
        plt.figure(figsize=figsize)

        # 绘制热力图
        sns.heatmap(cm, annot=True, fmt='.2f' if normalize else 'd',
                    cmap='Blues', square=True)

        plt.title('Confusion Matrix', fontsize=15)
        plt.xlabel('Predicted Label')
        plt.ylabel('True Label')

        plt.tight_layout()

        return plt.gcf()

    def create_interactive_chart(self, df, price_col='close', signal_col='signal',
                                 position_col='position', return_col='cumulative_return'):
        """
        创建交互式图表

        参数:
            df: DataFrame，包含交易数据
            price_col: str，价格列名
            signal_col: str，信号列名
            position_col: str，持仓列名
            return_col: str，收益率列名
        """
        # 创建子图
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                            vertical_spacing=0.05,
                            subplot_titles=('Price and Signals', 'Position', 'Returns'))

        # 添加价格线
        fig.add_trace(
            go.Scatter(x=df.index, y=df[price_col],
                       name='Price', line=dict(color='blue')),
            row=1, col=1
        )

        # 添加信号点
        buy_signals = df[df[signal_col] == 1]
        sell_signals = df[df[signal_col] == -1]

        fig.add_trace(
            go.Scatter(x=buy_signals.index, y=buy_signals[price_col],
                       name='Buy Signal', mode='markers',
                       marker=dict(color='green', symbol='triangle-up', size=10)),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(x=sell_signals.index, y=sell_signals[price_col],
                       name='Sell Signal', mode='markers',
                       marker=dict(color='red', symbol='triangle-down', size=10)),
            row=1, col=1
        )

        # 添加持仓线
        fig.add_trace(
            go.Scatter(x=df.index, y=df[position_col],
                       name='Position', line=dict(color='purple')),
            row=2, col=1
        )

        # 添加收益率线
        if return_col in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df[return_col],
                           name='Returns', line=dict(color='orange')),
                row=3, col=1
            )

        # 更新布局
        fig.update_layout(height=900, title_text="Interactive Trading Analysis",
                          showlegend=True)

        return fig
