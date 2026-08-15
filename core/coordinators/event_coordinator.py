"""
事件协调器模块

负责处理所有事件订阅、取消订阅和事件回调方法。
从MainWindowCoordinator中提取的事件处理职责。
"""

from loguru import logger
from typing import Dict, Any, Optional, Union
import asyncio
import traceback
import pandas as pd
from datetime import datetime
from PyQt5.QtCore import QTimer

from core.coordinators.base_coordinator import BaseCoordinator
from core.events import (
    EventBus, StockSelectedEvent, AssetSelectedEvent, ChartUpdateEvent, AnalysisCompleteEvent,
    DataUpdateEvent, ErrorEvent, ThemeChangedEvent, UIDataReadyEvent, AssetDataReadyEvent,
    ComputedIndicatorEvent
)
from core.plugin_types import AssetType
from core.containers import ServiceContainer
from core.services import ChartService, AnalysisService, UnifiedDataManager
from core.performance import measure_performance


class EventCoordinator(BaseCoordinator):
    """
    事件协调器
    
    负责：
    1. 订阅和取消订阅所有事件
    2. 处理事件回调方法
    3. 协调事件与UI和服务的交互
    
    从MainWindowCoordinator中提取的事件处理职责。
    """

    def __init__(self, 
                 main_window_coordinator: Any,
                 service_container: ServiceContainer,
                 event_bus: EventBus):
        """
        初始化事件协调器
        
        Args:
            main_window_coordinator: 主窗口协调器引用
            service_container: 服务容器
            event_bus: 事件总线
        """
        super().__init__(service_container, event_bus)
        self._main_window_coordinator = main_window_coordinator
        self._event_subscriptions = []
        
    def subscribe_all_events(self) -> None:
        """
        统一订阅所有事件
        
        此方法应在主窗口协调器初始化时调用，
        注册所有需要监听的事件及其处理器。
        """
        try:
            # 注册股票选择事件处理器
            self._subscribe_event(StockSelectedEvent, self._handle_stock_selected_sync)
            
            # 注册通用资产选择事件处理器
            self._subscribe_event(AssetSelectedEvent, self._on_asset_selected)
            
            # 注册图表更新事件处理器
            self._subscribe_event(ChartUpdateEvent, self._on_chart_updated)
            
            # 注册分析完成事件处理器
            self._subscribe_event(AnalysisCompleteEvent, self._on_analysis_completed)
            
            # 注册数据更新事件处理器
            self._subscribe_event(DataUpdateEvent, self._on_data_update)
            
            # 注册错误事件处理器
            self._subscribe_event(ErrorEvent, self._on_error)
            
            # 注册UI数据就绪事件处理器（向后兼容）
            self._subscribe_event(UIDataReadyEvent, self._on_ui_data_ready)
            
            # 注册通用资产数据就绪事件处理器
            self._subscribe_event(AssetDataReadyEvent, self._on_asset_data_ready)
            
            # 注册主题变化事件处理器
            self._subscribe_event(ThemeChangedEvent, self._on_theme_changed)

            # 注册计算指标事件处理器（监控实时计算引擎的指标输出）
            self._subscribe_event(ComputedIndicatorEvent, self._on_computed_indicator)

            # R237-D HVD-237-P2-ORPHAN-GOVERNANCE 治理 (2026-07-30, 子智能体 D 实施)
            # Why: R235-A 扫描器确认 14 个 P2 业务监控 ORPHAN_PUB 事件 100% 缺失订阅方
            # Fix: 沿用 R236-D 模板, 实施 R237P2EventHandlers 集中订阅块
            try:
                from core.trading.r237_p2_event_handlers import (
                    R237P2EventHandlers, register_r237_p2_handlers,
                )
                self._r237_p2_event_handlers = register_r237_p2_handlers(
                    self._event_bus,
                    self._main_window_coordinator,
                )
            except ImportError as _r237_import_exc:
                logger.warning(f"EventCoordinator: R237P2EventHandlers 模块导入失败 (非致命): {_r237_import_exc}")
                self._r237_p2_event_handlers = None

            # R240-B HVD-240-P0-006: account_load_failed 孤儿事件治理 (账户加载失败链路)
            # Why: 启动期 bootstrap (main.py:229) 早于本订阅 (main_window_coordinator.py:232),
            #      EventBus 无历史回放 (event_bus.py:501-502 无 handler 仅 debug) → 启动期事件必丢
            # Fix: 订阅 (覆盖运行期 publish) + 启动补查 (覆盖启动期时序缺口), 双保险
            self._subscribe_event("account_load_failed", self._on_account_load_failed)

            # HVD-240-P0-006 启动补查: bootstrap 阶段事件已丢失, 主动检查账户初始化状态
            try:
                from core.trading.account_manager import AccountManager
                _account_manager = self._service_container.resolve(AccountManager)
                if _account_manager is not None and not _account_manager.is_initialized():
                    logger.error(
                        "[R240-B] 启动补查: 账户加载失败 (AccountManager.is_initialized()=False), "
                        "bootstrap 阶段 account_load_failed 事件已丢失 (EventBus 无历史回放时序缺口)")
                    _alert_event = type('Event', (), {})()
                    _alert_event.error = "启动补查: 账户数据未加载 (数据库连接可能故障)"
                    self._on_account_load_failed(_alert_event)
            except Exception as _check_exc:
                logger.warning(f"[R240-B] 账户初始化状态补查失败 (非致命): {_check_exc}")

            logger.info("EventCoordinator: 所有事件订阅完成")

        except Exception as e:
            logger.error(f"EventCoordinator: 事件订阅失败: {e}")
            raise

    def _on_account_load_failed(self, event) -> None:
        """
        账户加载失败事件处理器 (R240-B HVD-240-P0-006)

        业务链: account_manager.py:88 publish 'account_load_failed' → 空账户状态
        (is_initialized()=False, account_manager.py:91-97) → GUI 账户表格空
        (account_management_dialog.py:289) → 下单账户下拉空 (order_management_dialog.py:1766)
        → order_service.py 下单静默失败

        Why: EventBus 无历史回放 (event_bus.py:501-502), 无订阅方时事件静默丢弃;
             失败不静默 (R51 §7.1 #5) → 显式告警 + UI 状态栏推送
        """
        try:
            error_detail = getattr(event, 'error', '未知错误') if event is not None else '未知错误'
            logger.error(
                f"✗ 账户加载失败 (HVD-240-P0-006): {error_detail} — "
                f"将使用空账户状态启动, 下单/持仓功能可能不可用")
            if hasattr(self._main_window_coordinator, 'show_message'):
                self._main_window_coordinator.show_message(
                    f"账户加载失败: {error_detail}", level='error')
        except Exception as e:
            logger.error(f"[R240-B] _on_account_load_failed 处理失败: {e}", exc_info=True)
            
    def unsubscribe_all_events(self) -> None:
        """
        取消所有事件订阅
        
        此方法应在主窗口协调器释放时调用，
        取消所有已注册的事件监听器。
        """
        try:
            # 使用BaseCoordinator的_unregister_event_handlers方法
            self._unregister_event_handlers()
            logger.info("EventCoordinator: 所有事件订阅已取消")
        except Exception as e:
            logger.error(f"EventCoordinator: 取消事件订阅失败: {e}")

    def _do_dispose(self) -> None:
        """清理EventCoordinator内部资源"""
        try:
            self.unsubscribe_all_events()
            self._event_subscriptions.clear()
            self._main_window_coordinator = None
            logger.info("EventCoordinator: 内部资源已清理")
        except Exception as e:
            logger.error(f"EventCoordinator: 清理内部资源失败: {e}")
            
    def _handle_stock_selected_sync(self, event: StockSelectedEvent) -> None:
        """同步包装器：处理股票选择事件"""
        try:
            def schedule_handler():
                coro = self._on_stock_selected(event)
                self._run_async_handler(coro)
            
            # 使用QTimer.singleShot在主线程中异步执行
            QTimer.singleShot(0, schedule_handler)
        except Exception as e:
            logger.error(f"EventCoordinator: 调度股票选择事件处理失败: {e}")
            logger.error(traceback.format_exc())

    def _run_async_handler(self, coro):
        """运行异步处理器"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(coro)
            else:
                loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"EventCoordinator: 运行异步处理器失败: {e}")

    @measure_performance("EventCoordinator._on_stock_selected")
    async def _on_stock_selected(self, event: StockSelectedEvent) -> None:
        """处理股票选择事件 - 新的统一数据加载流程"""
        if not event or not event.stock_code or self._is_loading:
            return

        # 在开始新任务前，取消之前所有相关的请求
        previous_stock_code = getattr(self._main_window_coordinator, '_current_stock_code', '未知')
        try:
            await self._chart_service.cancel_previous_requests()
            await self._analysis_service.cancel_previous_requests()
            logger.info(f"已取消先前为 {previous_stock_code} 发出的请求。")
        except Exception as e:
            logger.error(f"取消先前请求时出错: {e}", exc_info=True)

        self._is_loading = True
        self._main_window_coordinator._current_stock_code = event.stock_code
        self._main_window_coordinator.show_message(
            f"正在加载 {event.stock_name} ({event.stock_code}) 的数据...", level='info')

        try:
            # 从事件中提取参数
            period = event.period if event.period else 'D'  # 默认日线
            time_range = event.time_range if event.time_range else "最近1年"  # 默认最近1年
            chart_type = event.chart_type if event.chart_type else "K线图"  # 默认K线图

            logger.info(f"加载数据，股票：{event.stock_code}，周期：{period}，时间范围：{time_range}，图表类型：{chart_type}")

            # 1. 优化：优先使用事件中的K线数据，避免重复查询
            kline_data = None
            asset_type = getattr(event, 'asset_type', AssetType.STOCK_A)
            if hasattr(event, 'kline_data') and event.kline_data is not None:
                logger.info(f"使用LeftPanel预加载的K线数据: {event.stock_code}")
                kline_data = event.kline_data
                logger.debug(f"预加载数据行数: {len(kline_data) if hasattr(kline_data, '__len__') else 'N/A'}")
                # R274: 校验预加载数据质量 - 少于2行视为退化数据（如仅1条实时收盘价/网络失败产物），
                # 直接使用会导致图表只显示一天数据；降级走 request_data 重新请求完整K线
                if hasattr(kline_data, '__len__') and len(kline_data) < 2:
                    logger.warning(
                        f"预加载K线数据过少({len(kline_data)}行)，疑似退化数据，降级重新请求: {event.stock_code}")
                    kline_data = None
            if kline_data is None:
                # 降级：重新查询K线数据
                logger.info(f"事件中无可用K线数据，开始请求K线数据: {event.stock_code} ({asset_type.value})")
                kline_data_response = await self._data_manager.request_data(
                    stock_code=event.stock_code,
                    data_type='kdata',
                    period=period,          # 传递周期
                    time_range=time_range,  # 传递时间范围
                    asset_type=asset_type   # 传递资产类型
                )

                if isinstance(kline_data_response, dict):
                    kline_data = kline_data_response.get('kline_data')
                else:
                    kline_data = kline_data_response

            # 关键检查点：确认核心数据是否存在
            if kline_data is None or kline_data.empty:
                logger.warning(f"无法获取 {event.stock_name} 的K线数据。")
                self._main_window_coordinator.show_message(
                    f"无法获取 {event.stock_name} ({event.stock_code}) 的K线数据，请尝试其他股票。", level='warning')
                return

            logger.info(f"K线数据加载完成: {event.stock_code}, 开始请求分析数据...")

            # 2. 再获取分析数据，传入已获取的K线数据（可选，失败不影响K线显示）
            analysis_data = None
            try:
                analysis_data = await self._analysis_service.analyze_stock(
                    stock_code=event.stock_code,
                    analysis_type='comprehensive',
                    kline_data=kline_data
                )
                logger.info(f"分析数据加载完成: {event.stock_code}")
            except Exception as analysis_error:
                logger.warning(f"分析数据加载失败（继续显示K线）: {analysis_error}")
                analysis_data = {'data_available': False, 'error': str(analysis_error)}

            # 3. 存储到中央数据状态 - 增强数据验证和日志
            logger.info(f"=== 准备中央数据状态 ===")
            logger.info(f"K线数据类型: {type(kline_data).__name__}")
            if hasattr(kline_data, 'shape'):
                logger.info(f"K线数据形状: {kline_data.shape}")
            elif hasattr(kline_data, '__len__'):
                logger.info(f"K线数据长度: {len(kline_data)}")

            self._main_window_coordinator._current_stock_data = {
                'stock_code': event.stock_code,
                'stock_name': event.stock_name,
                'market': event.market,
                'kline_data': kline_data,  # 确保使用正确的键名
                'kdata': kline_data,       # 向后兼容
                'analysis': analysis_data,
                'period': period,
                'time_range': time_range,
                'chart_type': chart_type
            }

            # 验证数据完整性
            if analysis_data:
                logger.info(f"分析数据包含键: {list(analysis_data.keys()) if isinstance(analysis_data, dict) else 'Not a dict'}")
                # 如果分析数据中包含指标数据，添加到主数据中
                if isinstance(analysis_data, dict):
                    if 'indicators' in analysis_data:
                        self._main_window_coordinator._current_stock_data['indicators'] = analysis_data['indicators']
                        self._main_window_coordinator._current_stock_data['indicators_data'] = analysis_data['indicators']
                    if 'technical_analysis' in analysis_data:
                        self._main_window_coordinator._current_stock_data['technical_analysis'] = analysis_data['technical_analysis']

            logger.info(f"中央数据状态键: {list(self._main_window_coordinator._current_stock_data.keys())}")
            logger.info(f"数据已存储到中央状态，准备发布UIDataReadyEvent事件: {event.stock_code}")

            # 4. 发布数据准备就绪事件 - 增强事件数据
            logger.info(f"=== 创建UIDataReadyEvent ===")
            data_ready_event = UIDataReadyEvent(
                source="EventCoordinator",
                stock_code=event.stock_code,
                stock_name=event.stock_name,
                ui_data=self._main_window_coordinator._current_stock_data
            )

            self.event_bus.publish(data_ready_event)
            logger.info(f"已发布UIDataReadyEvent事件: {event.stock_code}")

            self._main_window_coordinator.show_message(f"{event.stock_name} 数据加载完成", level='success')

        except Exception as e:
            logger.error(f"EventCoordinator: 加载股票 {event.stock_code} 数据时出错: {e}", exc_info=True)
            self._main_window_coordinator.show_message(
                f"加载 {event.stock_name} 数据失败", level='error')

            error_event = ErrorEvent(
                source='EventCoordinator',
                error_type=type(e).__name__,
                error_message=str(e),
                error_traceback=traceback.format_exc(),
                severity='high'
            )
            self.event_bus.publish(error_event)

        finally:
            self._is_loading = False

    @measure_performance("EventCoordinator._on_asset_selected")
    async def _on_asset_selected(self, event: AssetSelectedEvent) -> None:
        """处理通用资产选择事件（支持多资产类型）"""
        if not event or not event.symbol or self._is_loading:
            return

        # 在开始新任务前，取消之前所有相关的请求
        try:
            await self._chart_service.cancel_previous_requests()
            await self._analysis_service.cancel_previous_requests()
            logger.info(f"已取消先前为 {self._current_symbol} 发出的请求。")
        except Exception as e:
            logger.error(f"取消先前请求时出错: {e}", exc_info=True)

        self._is_loading = True

        # 更新当前资产状态
        self._main_window_coordinator._current_symbol = event.symbol
        self._main_window_coordinator._current_asset_name = event.name
        self._main_window_coordinator._current_asset_type = event.asset_type
        self._main_window_coordinator._current_market = event.market

        # 更新窗口标题
        asset_type_name = self._get_asset_type_display_name(event.asset_type)
        main_window = self._main_window_coordinator._main_window
        main_window.setWindowTitle(f"FactorWeave-Quant  2.0 - {event.name} ({event.symbol}) - {asset_type_name}")

        self._main_window_coordinator.show_message(
            f"正在加载 {event.name} ({event.symbol}) 的{asset_type_name}数据...", level='info')

        try:
            # 从事件中提取参数
            period = event.period if event.period else 'D'  # 默认日线
            time_range = event.time_range if event.time_range else "最近1年"  # 默认最近1年
            chart_type = event.chart_type if event.chart_type else "K线图"  # 默认K线图

            logger.info(f"加载数据，资产：{event.symbol}，类型：{event.asset_type.value}，周期：{period}，时间范围：{time_range}")

            # 尝试使用资产服务获取数据
            asset_data = None
            try:
                if hasattr(self, '_asset_service') and self._asset_service:
                    asset_data = self._asset_service.get_historical_data(
                        symbol=event.symbol,
                        asset_type=event.asset_type,
                        period=period
                    )
                else:
                    # 降级到统一数据管理器
                    asset_data = self._data_manager.get_asset_data(
                        symbol=event.symbol,
                        asset_type=event.asset_type,
                        period=period
                    )
            except Exception as e:
                logger.warning(f"使用TET模式获取数据失败，尝试传统方式: {e}")

                # 降级到传统request_data方式（支持所有资产类型）
                kline_data_response = await self._data_manager.request_data(
                    stock_code=event.symbol,
                    data_type='kdata',
                    period=period,
                    time_range=time_range,
                    asset_type=event.asset_type  # 传递资产类型
                )

                if isinstance(kline_data_response, dict):
                    asset_data = kline_data_response.get('kline_data')
                else:
                    asset_data = kline_data_response

            # 关键检查点：确认核心数据是否存在
            if asset_data is None or asset_data.empty:
                logger.warning(f"无法获取 {event.name} 的数据。")
                self._main_window_coordinator.show_message(
                    f"无法获取 {event.name} ({event.symbol}) 的数据，请尝试其他{asset_type_name}。", level='warning')
                return

            logger.info(f"资产数据加载完成: {event.symbol}, 开始分析...")

            # 如果是股票类型，进行传统分析
            analysis_data = None
            if event.asset_type == AssetType.STOCK_A:
                try:
                    analysis_data = await self._analysis_service.analyze_stock(
                        stock_code=event.symbol,
                        analysis_type='comprehensive',
                        kline_data=asset_data
                    )
                    logger.info(f"股票分析数据加载完成: {event.symbol}")
                except Exception as e:
                    logger.warning(f"股票分析失败: {e}")

            # 存储到中央数据状态
            self._main_window_coordinator._current_asset_data = {
                'symbol': event.symbol,
                'name': event.name,
                'asset_type': event.asset_type.value,
                'market': event.market,
                'period': period,
                'time_range': time_range,
                'chart_type': chart_type,
                'kline_data': asset_data,
                'analysis_data': analysis_data or {}
            }

            # 发送资产数据就绪事件
            asset_data_ready_event = AssetDataReadyEvent(
                symbol=event.symbol,
                name=event.name,
                asset_type=event.asset_type,
                market=event.market,
                data_type="kline",
                data=asset_data
            )

            # 同时发送向后兼容的UIDataReadyEvent（如果是股票）
            if event.asset_type == AssetType.STOCK_A:
                # R251-R4 修复: 补 ui_data 字段, 与 _on_stock_selected 路径(:316-321)保持事件契约一致
                # Why: 之前仅传 kline_data/market, right_panel._on_ui_data_ready 读
                #      event.ui_data.get('analysis') 抛 AttributeError (被 try/except 吞掉后右侧面板不更新)
                ui_data_ready_event = UIDataReadyEvent(
                    stock_code=event.symbol,
                    stock_name=event.name,
                    kline_data=asset_data,
                    market=event.market,
                    ui_data={
                        'kline_data': asset_data,
                        'kdata': asset_data,  # 向后兼容
                        'analysis': analysis_data or {}
                    }
                )
                self.event_bus.publish(ui_data_ready_event)

            self.event_bus.publish(asset_data_ready_event)

            # 更新状态栏
            self._main_window_coordinator.show_message(
                f"{event.name} ({event.symbol}) 数据加载完成", level='success')

            logger.info(f"资产数据流程完成: {event.symbol}")

        except Exception as e:
            logger.error(f"EventCoordinator: 加载资产 {event.symbol} 数据时出错: {e}", exc_info=True)
            self._main_window_coordinator.show_message(
                f"加载 {event.name} 数据失败", level='error')

            error_event = ErrorEvent(
                source='EventCoordinator',
                error_type=type(e).__name__,
                error_message=str(e),
                error_traceback=traceback.format_exc(),
                severity='high'
            )
            self.event_bus.publish(error_event)

        finally:
            self._is_loading = False

    def _get_asset_type_display_name(self, asset_type: AssetType) -> str:
        """获取资产类型的显示名称"""
        display_names = {
            AssetType.STOCK_A: "股票",
            AssetType.CRYPTO: "加密货币",
            AssetType.FUTURES: "期货",
            AssetType.FOREX: "外汇",
            AssetType.INDEX: "指数",
            AssetType.FUND: "基金",
            AssetType.BOND: "债券",
            AssetType.COMMODITY: "商品"
        }
        return display_names.get(asset_type, "未知资产")

    def _on_asset_data_ready(self, event: AssetDataReadyEvent) -> None:
        """处理通用资产数据就绪事件"""
        try:
            if not event or not event.symbol:
                return

            # 更新窗口标题
            asset_type_name = self._get_asset_type_display_name(event.asset_type)
            title = f"FactorWeave-Quant  2.0 - {event.name} ({event.symbol}) - {asset_type_name}"
            if event.market:
                title += f" [{event.market}]"

            main_window = self._main_window_coordinator._main_window
            main_window.setWindowTitle(title)

            # 更新状态栏
            status_text = f"当前资产: {event.name} ({event.symbol}) | 类型: {asset_type_name}"
            if event.market:
                status_text += f" | 市场: {event.market}"

            self._main_window_coordinator.show_message(status_text, level='info')

            logger.info(f"EventCoordinator: 资产数据就绪事件处理完成: {event.symbol}")

        except Exception as e:
            logger.error(f"EventCoordinator: 处理资产数据就绪事件失败: {e}")

    def _on_ui_data_ready(self, event: UIDataReadyEvent) -> None:
        """处理UI数据就绪事件，更新主窗口状态栏并重新渲染图表"""
        try:
            # 兼容两种事件格式：ui_data.kline_data 和 直接的 kline_data
            kdata = None
            ui_data = {}
            
            # 尝试从 event.ui_data 获取数据（新型事件格式）
            if hasattr(event, 'ui_data') and event.ui_data:
                kdata = event.ui_data.get('kline_data')
                ui_data = event.ui_data
                logger.debug(f"从event.ui_data获取K线数据: {type(kdata)}")
            
            # 如果没有从 ui_data 获取到，尝试从 event.kline_data 获取（传统事件格式）
            if kdata is None and hasattr(event, 'kline_data') and event.kline_data is not None:
                kdata = event.kline_data
                ui_data = {'kline_data': kdata}
                logger.debug(f"从event.kline_data获取K线数据: {type(kdata)}")
            
            if kdata is not None and not kdata.empty:
                # 更新状态标签显示加载数量
                self._main_window_coordinator._status_label.setText(f"已加载 ({len(kdata)})")

                # 更新数据时间标签
                latest_date = kdata.index[-1]
                if isinstance(latest_date, (datetime, pd.Timestamp)):
                    time_str = latest_date.strftime('%Y-%m-%d')
                else:
                    time_str = str(latest_date)
                self._main_window_coordinator._data_time_label.setText(f"数据时间: {time_str}")
                
                # 🔧 修复技术指标刷新问题：触发图表更新以重新渲染指标
                self._trigger_chart_update_with_indicators(ui_data, event.stock_code)
            else:
                self._main_window_coordinator._status_label.setText("已加载 (0)")
                self._main_window_coordinator._data_time_label.setText("数据时间: -")
                logger.warning("未获取到有效的K线数据，无法更新图表")
        except Exception as e:
            logger.error(f"EventCoordinator: 更新主窗口状态栏失败: {e}", exc_info=True)
            self._main_window_coordinator._status_label.setText("状态更新失败")
            self._main_window_coordinator._data_time_label.setText("数据时间: -")
            
    def _trigger_chart_update_with_indicators(self, ui_data: dict, stock_code: str) -> None:
        """触发图表更新并重新渲染指标"""
        try:
            # 获取中间面板的图表控件
            middle_panel = self._main_window_coordinator._panels.get('middle')
            if not middle_panel or not hasattr(middle_panel, 'chart_widget'):
                return
                
            chart_widget = middle_panel.chart_widget
            if not chart_widget:
                logger.warning("图表控件不存在，跳过指标刷新")
                return
            
            # 🔧 确保在数据更新前保留当前指标状态
            current_indicators = getattr(chart_widget, 'active_indicators', None)
            if current_indicators:
                logger.info(f"保留当前指标状态: {[ind.get('name', 'unknown') for ind in current_indicators]}")
                
            # 构建更新数据，确保包含指标数据
            update_data = {
                'kline_data': ui_data.get('kline_data'),
                'stock_code': stock_code,
                'title': getattr(chart_widget, 'current_stock', stock_code)
            }
            
            # 如果有指标数据，也传递过去
            indicators_data = ui_data.get('indicators_data', {})
            if indicators_data:
                update_data['indicators_data'] = indicators_data
                logger.info(f"传递指标数据到图表: {list(indicators_data.keys())}")
            
            # 🔧 如果没有通过indicators_data传递指标，则通过active_indicators字段传递
            if not indicators_data and current_indicators:
                update_data['active_indicators'] = current_indicators
                logger.info(f"通过active_indicators字段传递指标: {[ind.get('name', 'unknown') for ind in current_indicators]}")
            
            # 触发图表更新，这将重新渲染所有指标
            logger.info(f"触发图表更新，股票代码: {stock_code}")
            chart_widget.update_chart(update_data)
            logger.info("图表更新完成，指标将重新渲染")
            
        except Exception as e:
            logger.error(f"EventCoordinator: 触发图表更新失败: {e}", exc_info=True)

    def _on_chart_updated(self, event: ChartUpdateEvent) -> None:
        """处理图表更新事件"""
        try:
            stock_code = getattr(event, 'stock_code', '')
            period = getattr(event, 'period', '')

            logger.info(f"EventCoordinator: Chart updated: {stock_code} - {period}")

        except Exception as e:
            logger.error(f"EventCoordinator: Failed to handle chart update: {e}")

    def _on_analysis_completed(self, event) -> None:
        """处理分析完成事件"""
        try:
            stock_code = getattr(event, 'stock_code', '')
            analysis_type = getattr(event, 'analysis_type', '')

            logger.info(f"EventCoordinator: Analysis completed: {stock_code} - {analysis_type}")

        except Exception as e:
            logger.error(f"EventCoordinator: Failed to handle analysis completion: {e}")

    def _on_computed_indicator(self, event) -> None:
        """处理计算指标事件"""
        try:
            symbol = getattr(event, 'symbol', '')
            computed_indicators = getattr(event, 'computed_indicators', {})

            indicator_names = list(computed_indicators.keys()) if computed_indicators else []
            logger.info(f"EventCoordinator: Computed indicators for {symbol}: {indicator_names}")

        except Exception as e:
            logger.error(f"EventCoordinator: Failed to handle computed indicator: {e}")

    def _on_error(self, event: Union[ErrorEvent, dict]):
        """
        健壮的错误事件处理器，能同时处理事件对象和字典。
        """
        try:
            error_type = "UnknownError"
            error_message = "An unknown error occurred."
            event_id = "N/A"

            if isinstance(event, ErrorEvent):
                # 标准事件对象
                error_type = event.data.get('error_type', 'UnknownError')
                error_message = event.data.get('error_message', 'An unknown error occurred.')
                event_id = event.event_id
            elif isinstance(event, dict):
                # 兼容字典形式的事件
                error_type = event.get('error_type', 'UnknownError')
                error_message = event.get('error_message', 'An unknown error occurred.')
                event_id = event.get('event_id', 'N/A')

            logger.error(f"[ERROR] {error_type}: {error_message}",
                         extra={'trace_id': event_id})

            self._main_window_coordinator.show_message(f"发生错误: {error_message}", level='error')

        except Exception as e:
            logger.critical(f"EventCoordinator: 在处理错误事件时发生严重错误: {e}", exc_info=True)
            self._main_window_coordinator.show_message("发生严重错误，请检查日志", level='critical')

    def _on_data_update(self, event: DataUpdateEvent):
        """处理数据更新事件"""
        try:
            data_type = event.data.get('data_type', 'N/A')
            logger.info(f"EventCoordinator: Data update: {data_type}")
            self._main_window_coordinator.show_message(f"数据已更新: {data_type}", level='info')
        except Exception as e:
            logger.error(f"EventCoordinator: Failed to handle data update event: {e}", exc_info=True)

    def _on_theme_changed(self, theme_data) -> None:
        """智能主题变更处理 - 支持事件对象和字符串参数"""
        try:
            # 智能参数识别
            if hasattr(theme_data, 'theme_name'):
                # 事件对象
                theme_name = theme_data.theme_name
                logger.info(f"EventCoordinator: Theme changed via event: {theme_name}")

                # 重新应用主题
                self._main_window_coordinator._apply_theme()

                # 更新状态栏
                if hasattr(self._main_window_coordinator, '_status_label') and self._main_window_coordinator._status_label:
                    self._main_window_coordinator._status_label.setText(f"主题已更改: {theme_name}")

            elif isinstance(theme_data, str):
                # 字符串参数
                theme_name = theme_data
                logger.info(f"EventCoordinator: Theme changed via menu: {theme_name}")

                # 使用ThemeManager
                if hasattr(self._main_window_coordinator, '_theme_manager') and self._main_window_coordinator._theme_manager:
                    self._main_window_coordinator._theme_manager.set_theme(theme_name)
                    self._main_window_coordinator.show_message(f"主题已切换为: {theme_name}")
                else:
                    # 降级到应用主题
                    self._main_window_coordinator._apply_theme()
                    self._main_window_coordinator.show_message(f"主题已切换为: {theme_name}")
            else:
                logger.warning(f"EventCoordinator: 未知的主题数据类型: {type(theme_data)}")

        except Exception as e:
            logger.error(f"EventCoordinator: Failed to handle theme change: {e}")
            if hasattr(self._main_window_coordinator, 'show_message'):
                self._main_window_coordinator.show_message(f"主题切换失败: {e}")

    @property
    def _chart_service(self) -> ChartService:
        """获取图表服务"""
        return self._main_window_coordinator._chart_service

    @property
    def _analysis_service(self) -> AnalysisService:
        """获取分析服务"""
        return self._main_window_coordinator._analysis_service

    @property
    def _data_manager(self) -> UnifiedDataManager:
        """获取统一数据管理器"""
        return self._main_window_coordinator._data_manager

    @property
    def _is_loading(self) -> bool:
        """获取加载状态"""
        return self._main_window_coordinator._is_loading

    @_is_loading.setter
    def _is_loading(self, value: bool) -> None:
        """设置加载状态"""
        self._main_window_coordinator._is_loading = value

    @property
    def _current_symbol(self) -> Optional[str]:
        """获取当前资产符号"""
        return self._main_window_coordinator._current_symbol
