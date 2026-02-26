from loguru import logger
"""
统一图表服务

基于ChartWidget的高性能图表渲染服务，为所有组件提供统一的图表API。
替换系统中分散的matplotlib实现，提供更好的性能和一致的用户体验。
"""

from typing import Dict, Any, Optional, List, Callable
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from gui.widgets.chart_widget import ChartWidget
from utils.config_manager import ConfigManager
from utils.theme import get_theme_manager
from core.metrics.app_metrics_service import measure
# Cache将在需要时动态导入
from core.containers import get_service_container

class ChartDataLoader(QThread):
    """异步图表数据加载器"""

    data_loaded = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int, str)

    def __init__(self, data_source, stock_code, period, indicators=None):
        super().__init__()
        self.data_source = data_source
        self.stock_code = stock_code
        self.period = period
        self.indicators = indicators or []
        self._should_stop = False

    def run(self):
        """加载图表数据"""
        try:
            # 验证data_source是否有get_kdata方法
            if not self.data_source:
                error_msg = "Data source is None"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return

            if not hasattr(self.data_source, 'get_kdata'):
                error_msg = f"Data source {type(self.data_source)} has no get_kdata method"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return

            self.progress_updated.emit(10, "正在获取K线数据...")

            # 获取K线数据
            try:
                kline_data = self.data_source.get_kdata(
                    self.stock_code, self.period)
            except AttributeError as e:
                error_msg = f"AttributeError calling get_kdata: {e}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return
            except Exception as e:
                error_msg = f"Error calling get_kdata: {e}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return

            if self._should_stop:
                return

            self.progress_updated.emit(50, "正在计算技术指标...")

            # 计算技术指标
            indicators_data = {}
            for indicator in self.indicators:
                if self._should_stop:
                    return
                try:
                    indicator_data = self._calculate_indicator(
                        kline_data, indicator)
                    indicators_data[indicator] = indicator_data
                except Exception as e:
                    logger.warning(f"计算指标 {indicator} 失败: {e}")

            self.progress_updated.emit(90, "正在准备图表数据...")

            # 准备图表数据
            chart_data = {
                'stock_code': self.stock_code,
                'period': self.period,
                'kline_data': kline_data,
                'indicators_data': indicators_data
            }

            self.progress_updated.emit(100, "数据加载完成")
            self.data_loaded.emit(chart_data)

        except Exception as e:
            logger.error(f"加载图表数据失败: {e}")
            self.error_occurred.emit(str(e))

    def stop(self):
        """停止加载"""
        self._should_stop = True
        self.quit()
        self.wait(3000)  # 等待3秒
        if self.isRunning():
            self.terminate()

    def _calculate_indicator(self, kline_data, indicator_name):
        """计算技术指标"""
        try:
            if kline_data is None or len(kline_data) == 0:
                return []

            # 尝试导入分析服务
            try:
                from core.services.analysis_service import AnalysisService
                service_container = get_service_container()
                analysis_service = service_container.resolve(AnalysisService)

                logger.debug(f"开始计算指标: {indicator_name}")

                # 根据指标名称计算不同指标
                if indicator_name.upper() == 'MA':
                    # 计算多种周期的移动平均线
                    result = {}
                    for period in [5, 10, 20, 60]:
                        try:
                            logger.debug(f"计算 MA{period}")
                            ma_data = analysis_service.calculate_ma(
                                kline_data, period)
                            if ma_data is not None and len(ma_data) > 0:
                                result[str(period)] = ma_data.tolist() if hasattr(
                                    ma_data, 'tolist') else ma_data
                                logger.debug(
                                    f"MA{period} 计算完成，数据长度: {len(ma_data) if ma_data is not None else 0}")
                            else:
                                logger.warning(f"MA{period} 计算结果为空")
                        except Exception as e:
                            logger.error(f"计算MA{period}失败: {e}")
                    return result

                elif indicator_name.upper() == 'MACD':
                    # 计算MACD指标
                    try:
                        logger.debug(f"计算 MACD")
                        macd_data = analysis_service.calculate_macd(kline_data)
                        if macd_data is not None:
                            # 确保键名与返回值匹配
                            result = {
                                'DIF': macd_data.get('MACD', []).tolist() if hasattr(macd_data.get('MACD', []), 'tolist') else macd_data.get('MACD', []),
                                'DEA': macd_data.get('Signal', []).tolist() if hasattr(macd_data.get('Signal', []), 'tolist') else macd_data.get('Signal', []),
                                'MACD': macd_data.get('Histogram', []).tolist() if hasattr(macd_data.get('Histogram', []), 'tolist') else macd_data.get('Histogram', [])
                            }
                            logger.debug(
                                f"MACD 计算完成，数据长度: {len(result['DIF']) if 'DIF' in result and result['DIF'] is not None else 0}")
                            return result
                        else:
                            logger.warning("MACD 计算结果为空")
                    except Exception as e:
                        logger.error(f"计算MACD失败: {e}")
                    return {}

                elif indicator_name.upper() == 'BOLL':
                    # 计算布林带
                    try:
                        logger.debug(f"计算 BOLL")
                        boll_data = analysis_service.calculate_bollinger_bands(
                            kline_data)
                        if boll_data is not None:
                            result = {
                                'UPPER': boll_data.get('Upper', []).tolist() if hasattr(boll_data.get('Upper', []), 'tolist') else boll_data.get('Upper', []),
                                'MID': boll_data.get('Middle', []).tolist() if hasattr(boll_data.get('Middle', []), 'tolist') else boll_data.get('Middle', []),
                                'LOWER': boll_data.get('Lower', []).tolist() if hasattr(boll_data.get('Lower', []), 'tolist') else boll_data.get('Lower', [])
                            }
                            logger.debug(
                                f"BOLL 计算完成，数据长度: {len(result['MID']) if 'MID' in result and result['MID'] is not None else 0}")
                            return result
                        else:
                            logger.warning("BOLL 计算结果为空")
                    except Exception as e:
                        logger.error(f"计算BOLL失败: {e}")
                    return {}

                elif indicator_name.upper() == 'RSI':
                    # 计算RSI
                    try:
                        logger.debug(f"计算 RSI")
                        rsi_data = analysis_service.calculate_rsi(kline_data)
                        result = rsi_data.tolist() if hasattr(rsi_data, 'tolist') else rsi_data
                        logger.debug(
                            f"RSI 计算完成，数据长度: {len(result) if result is not None else 0}")
                        return result
                    except Exception as e:
                        logger.error(f"计算RSI失败: {e}")
                    return []

                elif indicator_name.upper() == 'KDJ':
                    # 计算KDJ，使用公共接口
                    try:
                        logger.debug(f"计算 KDJ")
                        # 检查是否有公共接口
                        if hasattr(analysis_service, 'calculate_kdj'):
                            kdj_data = analysis_service.calculate_kdj(
                                kline_data)
                        else:
                            # 如果没有公共接口，使用私有方法
                            logger.warning("使用私有方法计算KDJ，建议添加公共接口")
                            kdj_data = analysis_service._calculate_kdj(
                                kline_data)

                        if kdj_data is not None:
                            result = {
                                'K': kdj_data.get('K', []).tolist() if hasattr(kdj_data.get('K', []), 'tolist') else kdj_data.get('K', []),
                                'D': kdj_data.get('D', []).tolist() if hasattr(kdj_data.get('D', []), 'tolist') else kdj_data.get('D', []),
                                'J': kdj_data.get('J', []).tolist() if hasattr(kdj_data.get('J', []), 'tolist') else kdj_data.get('J', [])
                            }
                            logger.debug(
                                f"KDJ 计算完成，数据长度: {len(result['K']) if 'K' in result and result['K'] is not None else 0}")
                            return result
                        else:
                            logger.warning("KDJ 计算结果为空")
                    except Exception as e:
                        logger.error(f"计算KDJ失败: {e}")
                    return {}

                elif indicator_name.upper() == 'ACOS':
                    # 尝试计算ACOS指标，若不存在则返回空字典
                    try:
                        logger.debug(f"尝试计算 ACOS")
                        # 检查是否存在calculate_acos方法
                        if hasattr(analysis_service, 'calculate_acos'):
                            acos_data = analysis_service.calculate_acos(
                                kline_data)
                            if acos_data is not None:
                                if isinstance(acos_data, dict):
                                    result = {}
                                    for key, value in acos_data.items():
                                        result[key] = value.tolist() if hasattr(
                                            value, 'tolist') else value
                                else:
                                    result = acos_data.tolist() if hasattr(acos_data, 'tolist') else acos_data
                                logger.debug(f"ACOS 计算完成")
                                return result
                            else:
                                logger.warning("ACOS 计算结果为空")
                        else:
                            logger.warning(
                                f"分析服务中不存在calculate_acos方法，无法计算ACOS指标")
                            # 添加系统内置指标支持信息
                            logger.info(
                                "系统目前支持的内置指标: MA, MACD, BOLL, RSI, KDJ")
                    except Exception as e:
                        logger.error(f"计算ACOS失败: {e}")
                    return {}

                # 如果没有匹配的指标，尝试通用计算方法
                try:
                    # 检查是否有通用指标计算方法
                    if hasattr(analysis_service, 'calculate_indicator'):
                        logger.info(f"尝试使用通用方法计算指标: {indicator_name}")
                        indicator_data = analysis_service.calculate_indicator(
                            kline_data, indicator_name)
                        if indicator_data is not None:
                            if isinstance(indicator_data, dict):
                                result = {}
                                for key, value in indicator_data.items():
                                    result[key] = value.tolist() if hasattr(
                                        value, 'tolist') else value
                                return result
                            else:
                                return indicator_data.tolist() if hasattr(indicator_data, 'tolist') else indicator_data
                except Exception as e:
                    logger.error(f"通用计算指标 {indicator_name} 失败: {e}")

                # 如果所有方法都失败，返回空字典并记录警告
                logger.warning(f"未知指标: {indicator_name}")
                # 返回空字典而不是空列表，以保持返回类型一致性
                return {}

            except ImportError as e:
                logger.error(f"导入分析服务失败: {e}")
                return {}

        except Exception as e:
            logger.error(f"计算指标 {indicator_name} 失败: {e}")
            return {}

class UnifiedChartService(QObject):
    """统一图表服务

    提供统一的图表API，基于ChartWidget的高性能实现。
    支持：
    - 高性能K线图渲染
    - 技术指标计算和显示
    - 异步数据加载
    - 缓存机制
    - 主题支持
    - 交互功能
    """

    # 信号定义
    chart_updated = pyqtSignal(str, dict)  # 股票代码, 图表数据
    error_occurred = pyqtSignal(str)  # 错误信息
    loading_progress = pyqtSignal(int, str)  # 进度, 消息

    def __init__(self, service_container: 'ServiceContainer', config_manager=None, theme_manager=None, data_source=None):
        """
        初始化统一图表服务

        Args:
            service_container: 服务容器
            config_manager: 配置管理器
            theme_manager: 主题管理器
            data_source: 数据源
        """
        super().__init__()
        self.service_container = service_container
        self.config_manager = config_manager or ConfigManager()
        self.theme_manager = theme_manager or get_theme_manager()
        self.data_source = data_source

        try:
            from core.services.unified_cache_provider import get_unified_cache_provider
            self.cache = get_unified_cache_provider().get_cache_service()
        except ImportError:
            self.cache = None

        self.data_loader = None

        self._charts = {}

        logger.info("统一图表服务初始化完成")

    def create_chart_widget(self, parent=None, chart_id=None) -> ChartWidget:
        """
        创建并返回一个新的ChartWidget实例。
        如果提供了chart_id且已存在，则会替换掉旧的实例，确保总是返回一个新的、功能完好的控件。
        """
        if chart_id is None:
            chart_id = f"chart_{int(time.time() * 1000)}"  # 使用时间戳确保唯一性

        # 如果ID已存在，先从字典中移除并妥善处理旧实例
        if chart_id in self._charts:
            old_widget = self._charts.pop(chart_id, None)
            if old_widget:
                # 将控件的删除推迟到事件循环空闲时执行，是更安全的做法
                old_widget.deleteLater()
                logger.info(f"已移除并计划删除旧的ChartWidget实例: {chart_id}")

        # 始终创建并返回一个全新的实例
        logger.info(f"创建新的ChartWidget实例: {chart_id}")
        widget = ChartWidget(
            parent=parent,
            config_manager=self.config_manager,
            theme_manager=self.theme_manager,
            data_manager=self.data_source,
            chart_id=chart_id
        )

        self._charts[chart_id] = widget
        return widget

    def create_simple_chart_container(self, parent=None, chart_id=None) -> QWidget:
        """创建一个包含图表和基本控件的容器"""
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建图表控件
        chart_widget = self.create_chart_widget(container, chart_id)
        if chart_widget:
            layout.addWidget(chart_widget)

        return container

    def load_chart_data(self, stock_code: str, period: str = 'D',
                        indicators: List[str] = None, chart_id: str = None) -> None:
        """异步加载图表数据

        Args:
            stock_code: 股票代码
            period: 周期
            indicators: 技术指标列表
            chart_id: 图表ID
        """
        try:
            # 记录详细日志
            logger.info(
                f"开始加载图表数据: 股票={stock_code}, 周期={period}, 图表ID={chart_id}")
            logger.info(f"请求的指标列表: {indicators}")

            if not indicators:
                logger.warning(f"指标列表为空，将使用默认指标 ['MA']")
                # indicators = ['MA']

            cache_key = f"{stock_code}_{period}_{'-'.join(indicators or [])}"
            if self.cache:
                cached_data = self.cache.get(cache_key, namespace="chart_service")
                if cached_data:
                    logger.debug(f"从缓存获取图表数据: {stock_code}")
                    self.chart_updated.emit(stock_code, cached_data)
                    return

            # 停止之前的加载
            if self.data_loader and self.data_loader.isRunning():
                logger.debug("停止之前的数据加载线程")
                self.data_loader.stop()

            # 创建新的数据加载器
            self.data_loader = ChartDataLoader(
                self.data_source, stock_code, period, indicators
            )

            # 连接信号
            self.data_loader.data_loaded.connect(
                lambda data: self._on_data_loaded(data, cache_key, chart_id)
            )
            self.data_loader.error_occurred.connect(self.error_occurred.emit)
            self.data_loader.progress_updated.connect(
                self.loading_progress.emit)

            # 开始加载
            logger.debug(f"启动数据加载线程: 股票={stock_code}, 指标={indicators}")
            self.data_loader.start()

        except Exception as e:
            logger.error(f"加载图表数据失败: {e}", exc_info=True)
            self.error_occurred.emit(f"加载图表数据失败: {e}")

    def update_chart(self, chart_id: str, data: Dict[str, Any]) -> None:
        """更新指定图表的数据

        Args:
            chart_id: 图表ID
            data: 图表数据
        """
        try:
            if chart_id in self._charts:
                chart_widget = self._charts[chart_id]
                chart_widget.update_chart(data)
            else:
                logger.warning(f"图表 {chart_id} 不存在")

        except Exception as e:
            logger.error(f"更新图表失败: {e}")
            self.error_occurred.emit(f"更新图表失败: {e}")

    def set_chart_theme(self, theme_name: str) -> None:
        """设置图表主题

        Args:
            theme_name: 主题名称
        """
        try:
            # 更新主题管理器
            self.theme_manager.set_theme(theme_name)

            # 更新所有活跃图表
            for chart_widget in self._charts.values():
                chart_widget.apply_theme()

        except Exception as e:
            logger.error(f"设置图表主题失败: {e}")
            self.error_occurred.emit(f"设置图表主题失败: {e}")

    def get_chart_widget(self, chart_id: str) -> Optional[ChartWidget]:
        """获取图表控件

        Args:
            chart_id: 图表ID

        Returns:
            ChartWidget实例或None
        """
        return self._charts.get(chart_id)

    def remove_chart(self, chart_id: str) -> None:
        """移除图表

        Args:
            chart_id: 图表ID
        """
        try:
            if chart_id in self._charts:
                chart_widget = self._charts[chart_id]
                chart_widget.deleteLater()
                del self._charts[chart_id]
                logger.debug(f"移除图表: {chart_id}")

        except Exception as e:
            logger.error(f"移除图表失败: {e}")

    def clear_cache(self) -> None:
        """清空缓存"""
        if self.cache:
            self.cache.clear_namespace("chart_service")
        logger.info("图表缓存已清空")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            if self.cache:
                ns_stats = self.cache.get_namespace_stats("chart_service")
                return {
                    'size': ns_stats.get('key_count', 0),
                    'max_size': 'unlimited',
                    'hits': ns_stats.get('hits', 0),
                    'misses': ns_stats.get('misses', 0),
                    'type': 'CacheService'
                }
            return {
                'size': 0,
                'max_size': 0,
                'hits': 0,
                'misses': 0,
                'type': 'none'
            }
        except Exception as e:
            return {
                'error': str(e),
                'type': 'error'
            }

    @pyqtSlot(dict)
    def _on_data_loaded(self, data: Dict[str, Any], cache_key: str = None, chart_id: str = None) -> None:
        """处理数据加载完成"""
        try:
            stock_code = data.get('stock_code', '')
            logger.info(
                f"图表数据加载完成: {stock_code}, 指标数量: {len(data.get('indicators_data', {}))}")

            # 记录指标数据详情
            indicators_data = data.get('indicators_data', {})
            if not indicators_data:
                logger.warning(f"指标数据为空! 请检查指标计算过程。股票代码: {stock_code}")

            for indicator_name, indicator_data in indicators_data.items():
                if isinstance(indicator_data, dict):
                    logger.debug(
                        f"指标 {indicator_name} 包含子项: {list(indicator_data.keys())}")
                    for sub_name, sub_data in indicator_data.items():
                        data_len = len(sub_data) if hasattr(
                            sub_data, '__len__') else 0
                        logger.debug(
                            f"指标 {indicator_name}.{sub_name} 数据长度: {data_len}")
                else:
                    data_len = len(indicator_data) if hasattr(
                        indicator_data, '__len__') else 0
                    logger.debug(f"指标 {indicator_name} 数据长度: {data_len}")

            if cache_key and self.cache:
                from datetime import timedelta
                self.cache.set(cache_key, data, namespace="chart_service", ttl=timedelta(minutes=30))

            # 更新图表
            self.chart_updated.emit(stock_code, data)

            # 如果指定了图表ID，更新特定图表
            if chart_id and hasattr(self, '_charts'):
                if chart_id in self._charts:
                    chart_widget = self._charts[chart_id]
                    if chart_widget:
                        # 确保图表数据包含必要的字段
                        if 'kline_data' not in data or data['kline_data'] is None:
                            logger.warning(f"图表数据缺少K线数据，无法更新图表 {chart_id}")
                            return

                        # 为图表组件准备格式化的数据
                        chart_data = {
                            'kdata': data.get('kline_data'),
                            'stock_code': stock_code,
                            'indicators_data': indicators_data,  # 确保指标数据被传递
                            'title': data.get('stock_name', stock_code)
                        }

                        logger.debug(
                            f"更新图表 {chart_id}，数据包含指标: {list(indicators_data.keys())}")
                        chart_widget.update_chart(chart_data)
                        logger.debug(f"已更新图表 {chart_id}")
                    else:
                        logger.warning(f"图表 {chart_id} 不存在")
                else:
                    logger.warning(
                        f"找不到指定的图表ID: {chart_id}，可用图表: {list(self._charts.keys()) if hasattr(self, '_charts') else []}")

        except Exception as e:
            logger.error(f"处理图表数据失败: {e}", exc_info=True)
            self.error_occurred.emit(f"处理图表数据失败: {e}")

    @pyqtSlot(dict)
    def _on_chart_updated(self, data: Dict[str, Any]):
        """图表更新处理"""
        try:
            stock_code = data.get('stock_code', '')
            self.chart_updated.emit(stock_code, data)

        except Exception as e:
            logger.error(f"处理图表更新失败: {e}")

    def dispose(self) -> None:
        """释放资源"""
        try:
            # 停止数据加载器
            if self.data_loader and self.data_loader.isRunning():
                self.data_loader.stop()

            # 清理所有图表
            for chart_id in list(self._charts.keys()):
                self.remove_chart(chart_id)

            # 清空缓存
            self.clear_cache()

            logger.info("统一图表服务资源已释放")

        except Exception as e:
            logger.error(f"释放图表服务资源失败: {e}")

# 全局统一图表服务实例
_chart_service_instance = None

def get_unified_chart_service(config_manager=None, theme_manager=None, data_source=None) -> UnifiedChartService:
    """获取或创建统一图表服务的单例"""
    global _chart_service_instance
    if _chart_service_instance is None:
        service_container = get_service_container()
        _chart_service_instance = UnifiedChartService(
            service_container=service_container,
            config_manager=config_manager,
            theme_manager=theme_manager,
            data_source=data_source
        )
    return _chart_service_instance

def create_chart_widget(parent=None, chart_id=None, coordinator=None, **kwargs) -> ChartWidget:
    """
    创建一个新的ChartWidget实例。
    """
    try:
        from core.services import UnifiedDataManager
        from core.events import EventBus
        from utils.config_manager import ConfigManager  # 修复：从正确路径导入

        container = get_service_container()

        # 解析依赖
        config_manager = container.resolve(ConfigManager)
        theme_manager = get_theme_manager(config_manager)
        # LogManager已移除，使用Loguru
        event_bus = container.resolve(EventBus)
        data_manager = container.resolve(UnifiedDataManager)

        # 创建ChartWidget实例
        chart = ChartWidget(
            parent=parent,
            config_manager=config_manager,
            theme_manager=theme_manager,
            # log_manager已迁移到Loguru,
            data_manager=data_manager,
            chart_id=chart_id,
            coordinator=coordinator,  # 传递 coordinator
            **kwargs
        )
        return chart
    except Exception as e:
        logger.error(f"创建ChartWidget实例失败: {e}", exc_info=True)

        # 创建一个替代组件，确保它具有必要的接口
        from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
        from PyQt5.QtCore import pyqtSignal

        class FallbackChartWidget(QWidget):
            """当ChartWidget创建失败时使用的替代组件"""
            # 确保实现与ChartWidget相同的关键信号
            request_stat_dialog = pyqtSignal(str)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QVBoxLayout(self)
                self.error_label = QLabel(f"图表创建失败:\n{e}")
                self.error_label.setStyleSheet("color: red;")
                layout.addWidget(self.error_label)

            def update_chart(self, data=None):
                """模拟ChartWidget的update_chart方法"""
                pass

            def apply_theme(self):
                """模拟ChartWidget的apply_theme方法"""
                pass

        return FallbackChartWidget(parent)

def create_simple_chart(parent=None, chart_id=None, **kwargs) -> QWidget:
    """便捷函数：创建简单图表容器

    Args:
        parent: 父控件
        chart_id: 图表ID
        **kwargs: 其他参数

    Returns:
        包含ChartWidget的容器控件
    """
    service = get_unified_chart_service(**kwargs)
    return service.create_simple_chart_container(parent, chart_id)
