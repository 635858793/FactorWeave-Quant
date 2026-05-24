"""
订单服务

负责订单生命周期管理
"""

from loguru import logger
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4
import threading

from core.trading.order_models import (
    Order, OrderRequest, OrderQuery, OrderType, OrderStatus, OrderCategory
)
from core.trading.order_validator import OrderValidator, ValidationResult
from core.trading.order_repository import OrderRepository
from core.trading.order_executor import OrderExecutor, ExecutionResult
from core.trading.trading_types import ExecutionStatus
from core.trading.order_monitor import OrderMonitor
from core.trading.order_analyzer import OrderAnalyzer
from core.containers import ServiceContainer
from core.events import EventBus


class OrderService:
    """订单服务"""

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        self.service_container = service_container
        self.event_bus = event_bus

        self.validator: OrderValidator = None
        self.repository: OrderRepository = None
        self.executor: OrderExecutor = None
        self.monitor: OrderMonitor = None
        self.analyzer: OrderAnalyzer = None

        # 并发控制：订单级别锁
        self._order_locks: Dict[str, threading.Lock] = {}
        self._lock_manager_lock = threading.Lock()

        self._initialize()

        # 订阅订单终态事件，用于清理资源
        self.event_bus.subscribe('order_terminal_state', self._on_order_terminal_state)

        logger.info("订单服务初始化完成")

    def _initialize(self):
        """初始化"""
        self.validator = OrderValidator(self.service_container, self.event_bus)
        self.repository = OrderRepository(self.service_container, self.event_bus)
        self.executor = OrderExecutor(self.service_container, self.event_bus)
        self.monitor = OrderMonitor(self.service_container, self.event_bus)
        self.analyzer = OrderAnalyzer(self.service_container, self.event_bus)

    def _get_order_lock(self, order_id: str) -> threading.Lock:
        """获取订单级别的锁"""
        with self._lock_manager_lock:
            if order_id not in self._order_locks:
                self._order_locks[order_id] = threading.Lock()
            return self._order_locks[order_id]

    def _cleanup_order_lock(self, order_id: str):
        """清理订单锁"""
        with self._lock_manager_lock:
            if order_id in self._order_locks:
                del self._order_locks[order_id]

    def create_order(self, request: OrderRequest) -> Optional[Order]:
        """创建订单"""
        try:
            logger.info(f"开始创建订单: {request.stock_code} {request.order_type.value} {request.order_quantity}")

            # 1. 验证订单请求
            if not request.validate():
                logger.error(f"订单请求参数无效")
                return None

            # 2. 执行订单验证
            validation_result = self.validator.validate_order_request(request)
            if not validation_result.passed:
                logger.error(f"订单验证失败: {validation_result.message}")
                self.event_bus.publish('order_validation_failed',
                    strategy_id=request.strategy_id,
                    stock_code=request.stock_code,
                    error=validation_result.message,
                    error_code=validation_result.error_code
                )
                return None

            # 3. 验证并获取有效的账号信息
            from core.trading.account_manager import AccountManager
            from core.trading.strategy_manager import StrategyManager
            
            try:
                account_manager = self.service_container.resolve(AccountManager)
            except ValueError as e:
                logger.error(f"AccountManager 未注册到服务容器: {e}")
                logger.error("将跳过账号验证，使用请求中的账号信息")
                account_manager = None
            
            try:
                strategy_manager = self.service_container.resolve(StrategyManager)
            except ValueError as e:
                logger.error(f"StrategyManager 未注册到服务容器: {e}")
                logger.error("将跳过策略验证，使用请求中的策略信息")
                strategy_manager = None
            
            # 验证 account_id
            account_id = request.account_id
            if account_manager and (account_id == "default" or not account_manager.get_account(account_id)):
                # 尝试从策略获取默认账号
                if request.strategy_id and request.strategy_id != "default":
                    strategy = strategy_manager.get_strategy(request.strategy_id) if strategy_manager else None
                    if strategy and strategy.default_account_id:
                        account = account_manager.get_account(strategy.default_account_id)
                        if account:
                            account_id = account.account_id
                            logger.info(f"使用策略的默认账号: {account_id}")
                
                # 如果还是没有有效账号，根据资产类型选择匹配的账号
                if account_id == "default":
                    accounts = account_manager.get_all_accounts()
                    if accounts:
                        # 优先选择与请求资产类型匹配的账号
                        matched_accounts = [
                            acc for acc in accounts 
                            if acc.account_id != "default"
                        ]
                        if matched_accounts:
                            account_id = matched_accounts[0].account_id
                            logger.info(f"使用系统第一个非默认账号: {account_id}")
                        else:
                            account_id = accounts[0].account_id
                            logger.warning(f"系统中只有默认账号，使用: {account_id}")
                    else:
                        logger.error("系统中没有可用的账号")
                        return None
            
            # 验证 strategy_id
            strategy_id = request.strategy_id
            if strategy_manager and (strategy_id == "default" or not strategy_manager.get_strategy(strategy_id)):
                strategies = strategy_manager.get_all_strategies()
                if strategies:
                    strategy_id = strategies[0].strategy_id
                    logger.info(f"使用系统默认策略: {strategy_id}")
                else:
                    logger.warning("系统中没有可用的策略，使用默认值")
                    strategy_id = "default"

            # 4. 创建订单对象
            order = Order(
                order_id=self.repository.generate_order_id(),
                strategy_id=strategy_id,
                asset_type=request.asset_type,
                stock_code=request.stock_code,
                order_type=request.order_type,
                order_category=request.order_category,
                order_price=request.order_price,
                order_quantity=request.order_quantity,
                order_status=OrderStatus.PENDING,
                create_time=datetime.now(),
                update_time=datetime.now(),
                stop_price=request.stop_price,
                user_id=request.user_id,
                account_id=account_id,
                tags=request.tags,
                metadata=request.metadata
            )

            # 4. 保存订单
            if not self.repository.save_order(order):
                logger.error(f"订单保存失败: {order.order_id}")
                return None

            # 5. 验证订单是否已保存到数据库
            saved_order = self.repository.get_order(order.order_id, asset_type=order.asset_type, use_cache=False)
            if not saved_order:
                logger.error(f"订单保存验证失败: {order.order_id} - 数据库中未找到订单")
                return None

            logger.info(f"订单创建成功: {order.order_id}")

            # 6. 发布事件（确认保存成功后）
            self.event_bus.publish('order_created',
                order_id=order.order_id,
                strategy_id=request.strategy_id,
                stock_code=request.stock_code,
                order_type=request.order_type.value,
                order_quantity=request.order_quantity
            )

            return order

        except Exception as e:
            logger.error(f"创建订单异常: {e}")
            return None

    def create_orders_batch(self, requests: List[OrderRequest]) -> List[Order]:
        """
        批量创建订单（性能优化）

        Args:
            requests: 订单请求列表

        Returns:
            List[Order]: 创建的订单列表
        """
        try:
            logger.info(f"开始批量创建订单: {len(requests)} 个订单")

            if not requests:
                return []

            orders = []
            failed_count = 0

            # 1. 验证所有订单请求
            for request in requests:
                if not request.validate():
                    logger.error(f"订单请求参数无效: {request.stock_code}")
                    failed_count += 1
                    continue

                validation_result = self.validator.validate_order_request(request)
                if not validation_result.passed:
                    logger.error(f"订单验证失败: {request.stock_code} - {validation_result.message}")
                    failed_count += 1
                    continue

                # 2. 创建订单对象
                order = Order(
                    order_id=self.repository.generate_order_id(),
                    strategy_id=request.strategy_id,
                    asset_type=request.asset_type,
                    stock_code=request.stock_code,
                    order_type=request.order_type,
                    order_category=request.order_category,
                    order_price=request.order_price,
                    order_quantity=request.order_quantity,
                    order_status=OrderStatus.PENDING,
                    create_time=datetime.now(),
                    update_time=datetime.now(),
                    stop_price=request.stop_price,
                    user_id=request.user_id,
                    account_id=request.account_id,
                    tags=request.tags,
                    metadata=request.metadata
                )

                orders.append(order)

            # 3. 批量保存订单（性能优化）
            save_results = self.repository.save_orders_batch(orders)

            # 4. 验证所有订单是否已保存到数据库
            verified_orders = []
            for order in orders:
                if save_results.get(order.order_id, False):
                    verified_order = self.repository.get_order(order.order_id, asset_type=order.asset_type, use_cache=False)
                    if verified_order:
                        verified_orders.append(verified_order)
                    else:
                        logger.error(f"订单保存验证失败: {order.order_id} - 数据库中未找到订单")
                        failed_count += 1
                else:
                    logger.error(f"订单保存失败: {order.order_id}")
                    failed_count += 1

            logger.info(f"批量创建订单完成: 成功 {len(verified_orders)}, 失败 {failed_count}")

            # 5. 发布批量事件（确认所有订单保存成功后）
            if verified_orders:
                self.event_bus.publish('batch_orders_created',
                    count=len(verified_orders),
                    order_ids=[order.order_id for order in verified_orders]
                )

            return verified_orders

        except Exception as e:
            logger.error(f"批量创建订单异常: {e}")
            return []

    def submit_order(self, order_id: str) -> ExecutionResult:
        """提交订单（带并发控制）"""
        lock = self._get_order_lock(order_id)
        try:
            with lock:
                logger.info(f"开始提交订单: {order_id}")

                # 1. 获取订单
                order = self.repository.get_order(order_id)
                if not order:
                    logger.error(f"订单不存在: {order_id}")
                    return ExecutionResult(
                        order_id=order_id,
                        status=ExecutionStatus.FAILED,
                        message="订单不存在",
                        error_code="ORDER_NOT_FOUND"
                    )

                # 2. 验证订单
                validation_result = self.validator.validate_order(order)
                if not validation_result.passed:
                    logger.error(f"订单验证失败: {validation_result.message}")

                    order.order_status = OrderStatus.REJECTED
                    order.error_message = validation_result.message
                    order.update_time = datetime.now()
                    self.repository.update_order(order)

                    # 订单达到终态（REJECTED），清理锁防止内存泄漏
                    self._cleanup_order_lock(order_id)

                    # 发布订单被拒绝事件
                    self.event_bus.publish('order_rejected',
                        order_id=order_id,
                        error=validation_result.message
                    )

                    return ExecutionResult(
                        order_id=order_id,
                        status=ExecutionStatus.FAILED,
                        message=validation_result.message,
                        error_code=validation_result.error_code
                    )

                # 3. 执行订单
                result = self.executor.submit_order(order)

                # 4. 发布事件
                if result.status == ExecutionStatus.SUCCESS:
                    self.event_bus.publish('order_submitted',
                        order_id=order_id,
                        exchange_order_id=result.exchange_order_id
                    )
                else:
                    # 执行失败时更新订单状态
                    if result.status == ExecutionStatus.FAILED:
                        order.order_status = OrderStatus.FAILED
                        order.error_message = result.message
                        order.update_time = datetime.now()
                        self.repository.update_order(order)
                        
                        # 订单状态变为终态，清理锁防止内存泄漏
                        self._cleanup_order_lock(order_id)

                    self.event_bus.publish('order_submit_failed',
                        order_id=order_id,
                        error=result.message
                    )

                return result

        except Exception as e:
            logger.error(f"提交订单异常: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"提交订单异常: {str(e)}",
                error_code="SUBMIT_ERROR"
            )

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """取消订单（带并发控制）"""
        lock = self._get_order_lock(order_id)
        try:
            with lock:
                logger.info(f"开始取消订单: {order_id}")

                # 发布取消请求事件
                self.event_bus.publish('order_cancel_requested', order_id=order_id)

                result = self.executor.cancel_order(order_id)

                return result

        except Exception as e:
            logger.error(f"取消订单异常: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"取消订单异常: {str(e)}",
                error_code="CANCEL_ERROR"
            )

    def cancel_orders_batch(self, order_ids: List[str]) -> Dict[str, bool]:
        """
        批量取消订单

        Args:
            order_ids: 订单ID列表

        Returns:
            Dict[str, bool]: 取消结果字典，key为order_id，value为是否成功
        """
        try:
            logger.info(f"开始批量取消订单: {len(order_ids)} 个订单")

            if not order_ids:
                return {}

            results = {}
            success_count = 0
            failed_count = 0

            # 批量发布取消请求事件
            for order_id in order_ids:
                try:
                    result = self.executor.cancel_order(order_id)
                    results[order_id] = (result.status == ExecutionStatus.SUCCESS)

                    if result.status == ExecutionStatus.SUCCESS:
                        success_count += 1
                    else:
                        failed_count += 1

                except Exception as e:
                    logger.error(f"批量取消订单异常: {order_id} - {e}")
                    results[order_id] = False
                    failed_count += 1

            logger.info(f"批量取消订单完成: 成功 {success_count}, 失败 {failed_count}")

            # 发布批量取消事件
            if success_count > 0:
                self.event_bus.publish('batch_orders_cancelled',
                    count=success_count,
                    order_ids=[order_id for order_id, success in results.items() if success]
                )

            return results

        except Exception as e:
            logger.error(f"批量取消订单异常: {e}")
            return {order_id: False for order_id in order_ids}

    def modify_order(self, order_id: str, new_price: Optional[float] = None,
                   new_quantity: Optional[int] = None) -> bool:
        """修改订单（带并发控制，原子操作）"""
        lock = self._get_order_lock(order_id)
        try:
            with lock:
                logger.info(f"开始修改订单: {order_id}")

                # 1. 获取订单
                order = self.repository.get_order(order_id)
                if not order:
                    logger.error(f"订单不存在: {order_id}")
                    return False

                # 2. 验证订单状态
                if order.is_completed:
                    logger.error(f"订单已完成，不能修改: {order_id}")
                    return False

                # 3. 检查部分成交状态
                if order.order_status == OrderStatus.PARTIALLY_FILLED:
                    logger.error(f"订单部分成交，不能修改: {order_id}")
                    return False

                # 4. 取消原订单（先取消，再创建新订单，避免竞态）
                cancel_result = self.cancel_order(order_id)
                if cancel_result.status != ExecutionStatus.SUCCESS:
                    logger.error(f"取消原订单失败: {order_id}")
                    return False

                # 5. 创建新订单
                final_price = new_price if new_price is not None else order.order_price
                final_quantity = new_quantity if new_quantity is not None else order.order_quantity

                new_request = OrderRequest(
                    strategy_id=order.strategy_id,
                    stock_code=order.stock_code,
                    order_type=order.order_type,
                    order_category=order.order_category,
                    order_price=final_price,
                    order_quantity=final_quantity,
                    stop_price=order.stop_price,
                    user_id=order.user_id,
                    account_id=order.account_id,
                    tags=order.tags,
                    metadata={**order.metadata, 'modified_from_order_id': order.order_id}
                )

                new_order = self.create_order(new_request)
                if not new_order:
                    logger.error(f"创建新订单失败")
                    return False

                # 6. 提交新订单
                result = self.submit_order(new_order.order_id)
                if result.status != ExecutionStatus.SUCCESS:
                    logger.error(f"提交新订单失败: {new_order.order_id}")
                    return False

                logger.info(f"订单修改成功: {order_id} -> {new_order.order_id}")

                # 7. 发布事件
                self.event_bus.publish('order_modified',
                    old_order_id=order_id,
                    new_order_id=new_order.order_id
                )

                return True

        except Exception as e:
            logger.error(f"修改订单异常: {e}")
            return False

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        try:
            return self.repository.get_order(order_id)
        except Exception as e:
            logger.error(f"获取订单异常: {e}")
            return None

    def query_orders(self, query: OrderQuery) -> List[Order]:
        """查询订单"""
        try:
            return self.repository.query_orders(query)
        except Exception as e:
            logger.error(f"查询订单异常: {e}")
            return []

    def get_active_orders(self, account_id: Optional[str] = None) -> List[Order]:
        """获取活跃订单"""
        try:
            return self.repository.get_active_orders(account_id)
        except Exception as e:
            logger.error(f"获取活跃订单异常: {e}")
            return []

    def get_orders_by_strategy(self, strategy_id: str, limit: int = 100) -> List[Order]:
        """获取策略订单"""
        try:
            return self.repository.get_orders_by_strategy(strategy_id, limit)
        except Exception as e:
            logger.error(f"获取策略订单异常: {e}")
            return []

    def get_orders_by_stock(self, stock_code: str, limit: int = 100) -> List[Order]:
        """获取股票订单"""
        try:
            return self.repository.get_orders_by_stock(stock_code, limit)
        except Exception as e:
            logger.error(f"获取股票订单异常: {e}")
            return []

    def get_order_fills(self, order_id: str) -> List:
        """获取订单成交记录"""
        try:
            order = self.repository.get_order(order_id)
            if not order:
                logger.warning(f"订单不存在: {order_id}")
                return []
            
            return self.repository.get_order_fills(order_id, order.asset_type)
        except Exception as e:
            logger.error(f"获取订单成交记录异常: {e}")
            return []

    def get_order_statistics(self, query: OrderQuery) -> Dict[str, Any]:
        """获取订单统计"""
        try:
            return self.repository.get_order_statistics(query)
        except Exception as e:
            logger.error(f"获取订单统计异常: {e}")
            return {}

    def delete_order(self, order_id: str) -> bool:
        """删除订单"""
        try:
            logger.info(f"开始删除订单: {order_id}")

            # 1. 获取订单
            order = self.repository.get_order(order_id)
            if not order:
                logger.error(f"订单不存在: {order_id}")
                return False

            # 2. 检查订单状态
            if order.is_active:
                logger.error(f"订单活跃中，不能删除: {order_id}")
                return False

            # 3. 删除订单
            success = self.repository.delete_order(order_id, order.asset_type)

            if success:
                logger.info(f"订单删除成功: {order_id}")

                # 4. 发布事件
                self.event_bus.publish('order_deleted', order_id=order_id)

            return success

        except Exception as e:
            logger.error(f"删除订单异常: {e}")
            return False

    def batch_create_orders(self, requests: List[OrderRequest]) -> List[Order]:
        """批量创建订单"""
        try:
            logger.info(f"开始批量创建订单: {len(requests)} 个")

            orders = []
            failed_requests = []

            for request in requests:
                order = self.create_order(request)
                if order:
                    orders.append(order)
                else:
                    failed_requests.append(request)

            logger.info(f"批量创建订单完成: 成功 {len(orders)}, 失败 {len(failed_requests)}")

            # 发布事件
            self.event_bus.publish('batch_orders_created',
                total=len(requests),
                success=len(orders),
                failed=len(failed_requests)
            )

            return orders

        except Exception as e:
            logger.error(f"批量创建订单异常: {e}")
            return []

    def cancel_all_active_orders(self, account_id: Optional[str] = None) -> int:
        """取消所有活跃订单"""
        try:
            logger.info(f"开始取消所有活跃订单")

            active_orders = self.get_active_orders(account_id)
            cancelled_count = 0

            for order in active_orders:
                result = self.cancel_order(order.order_id)
                if result.status == ExecutionStatus.SUCCESS:
                    cancelled_count += 1

            logger.info(f"取消活跃订单完成: {cancelled_count}/{len(active_orders)}")

            # 发布事件
            self.event_bus.publish('all_active_orders_cancelled',
                total=len(active_orders),
                cancelled=cancelled_count
            )

            return cancelled_count

        except Exception as e:
            logger.error(f"取消所有活跃订单异常: {e}")
            return 0

    def start_monitoring(self):
        """启动订单监控"""
        try:
            if self.monitor:
                self.monitor.start_monitoring()
                logger.info("订单监控已启动")
            else:
                logger.warning("订单监控器未初始化")
        except Exception as e:
            logger.error(f"启动订单监控失败: {e}")

    def stop_monitoring(self):
        """停止订单监控"""
        try:
            if self.monitor:
                self.monitor.stop_monitoring()
                logger.info("订单监控已停止")
            else:
                logger.warning("订单监控器未初始化")
        except Exception as e:
            logger.error(f"停止订单监控失败: {e}")

    def check_orders(self):
        """检查订单状态"""
        try:
            if self.monitor:
                alerts = self.monitor.check_orders()
                logger.info(f"订单检查完成: 发现 {len(alerts)} 个告警")
                return alerts
            else:
                logger.warning("订单监控器未初始化")
                return []
        except Exception as e:
            logger.error(f"检查订单失败: {e}")
            return []

    def get_order_alerts(self, limit: int = 100) -> List:
        """获取订单告警"""
        try:
            if self.monitor:
                return self.monitor.get_alerts(limit=limit)
            else:
                logger.warning("订单监控器未初始化")
                return []
        except Exception as e:
            logger.error(f"获取订单告警失败: {e}")
            return []

    def analyze_orders(self, period: str = "day") -> Dict[str, Any]:
        """分析订单"""
        try:
            if self.analyzer:
                analysis = self.analyzer.analyze_order_execution(period)
                logger.info(f"订单分析完成: {period}")
                return analysis.to_dict() if hasattr(analysis, 'to_dict') else analysis
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"分析订单失败: {e}")
            return {}

    def analyze_slippage(self, period: str = "day") -> Dict[str, Any]:
        """分析滑点"""
        try:
            if self.analyzer:
                analysis = self.analyzer.analyze_slippage(period)
                logger.info(f"滑点分析完成: {period}")
                return analysis.to_dict() if hasattr(analysis, 'to_dict') else analysis
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"分析滑点失败: {e}")
            return {}

    def analyze_volume(self, period: str = "day") -> Dict[str, Any]:
        """分析成交量"""
        try:
            if self.analyzer:
                analysis = self.analyzer.analyze_volume(period)
                logger.info(f"成交量分析完成: {period}")
                return analysis.to_dict() if hasattr(analysis, 'to_dict') else analysis
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"分析成交量失败: {e}")
            return {}

    def analyze_efficiency(self, period: str = "day") -> Dict[str, Any]:
        """分析效率"""
        try:
            if self.analyzer:
                analysis = self.analyzer.analyze_order_efficiency(period)
                logger.info(f"效率分析完成: {period}")
                return analysis.to_dict() if hasattr(analysis, 'to_dict') else analysis
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"分析效率失败: {e}")
            return {}

    def analyze_order_path(self, order_id: str) -> Dict[str, Any]:
        """分析订单执行路径"""
        try:
            if self.analyzer:
                analysis = self.analyzer.analyze_order_path(order_id)
                logger.info(f"订单执行路径分析完成: {order_id}")
                return analysis
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"分析订单执行路径失败: {e}")
            return {}

    def analyze_order_cost(self, order_id: str) -> Dict[str, Any]:
        """分析订单成本"""
        try:
            if self.analyzer:
                analysis = self.analyzer.analyze_order_cost(order_id)
                logger.info(f"订单成本分析完成: {order_id}")
                return analysis
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"分析订单成本失败: {e}")
            return {}

    def analyze_order_timing(self, period: str = "day") -> Dict[str, Any]:
        """分析订单时间特征"""
        try:
            if self.analyzer:
                from core.trading.order_analyzer import AnalysisPeriod
                
                # 将字符串转换为AnalysisPeriod枚举
                period_map = {
                    "hour": AnalysisPeriod.HOUR,
                    "day": AnalysisPeriod.DAY,
                    "week": AnalysisPeriod.WEEK,
                    "month": AnalysisPeriod.MONTH,
                    "custom": AnalysisPeriod.CUSTOM
                }
                
                analysis_period = period_map.get(period.lower(), AnalysisPeriod.DAY)
                analysis = self.analyzer.analyze_order_timing(analysis_period)
                logger.info(f"订单时间特征分析完成: {period}")
                return analysis
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"分析订单时间特征失败: {e}")
            return {}

    def analyze_order_risk(self, order_id: str) -> Dict[str, Any]:
        """分析订单风险"""
        try:
            if self.analyzer:
                analysis = self.analyzer.analyze_order_risk(order_id)
                logger.info(f"订单风险分析完成: {order_id}")
                return analysis
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"分析订单风险失败: {e}")
            return {}

    def predict_order_fill_probability(self, order_request: Dict[str, Any]) -> Dict[str, Any]:
        """预测订单成交概率"""
        try:
            if self.analyzer:
                prediction = self.analyzer.predict_order_fill_probability(order_request)
                logger.info(f"订单成交概率预测完成")
                return prediction
            else:
                logger.warning("订单分析器未初始化")
                return {}
        except Exception as e:
            logger.error(f"预测订单成交概率失败: {e}")
            return {}

    def _on_order_terminal_state(self, order_id: str, status: str):
        """处理订单终态事件，清理相关资源"""
        try:
            # 订单达到终态（FILLED/CANCELLED/REJECTED/EXPIRED），清理锁
            self._cleanup_order_lock(order_id)
            logger.debug(f"订单达到终态，已清理锁: {order_id} ({status})")
        except Exception as e:
            logger.error(f"清理订单终态资源失败: {order_id} - {e}")
