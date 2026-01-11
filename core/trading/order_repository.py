"""
订单仓储

负责订单数据的持久化
"""

from loguru import logger
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from core.trading.order_models import Order, OrderFill, OrderQuery, OrderType, OrderStatus
from core.containers import ServiceContainer
from core.events import EventBus
from core.plugin_types import AssetType
from core.asset_database_manager import AssetSeparatedDatabaseManager
from core.trading.order_cache import OrderCache


class OrderRepository:
    """订单仓储"""

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        self.service_container = service_container
        self.event_bus = event_bus
        
        self.asset_db_manager = AssetSeparatedDatabaseManager.get_instance()

        # 初始化订单缓存
        self.cache = OrderCache(ttl_seconds=300)

        logger.info("订单仓储初始化完成")

    def _get_database_pool_name(self, asset_type: AssetType) -> str:
        """根据资产类型获取数据库名称"""
        return f"{asset_type.value.lower()}_orders"

    def save_order(self, order: Order) -> bool:
        """保存订单"""
        try:
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            order_data = order.to_dict()

            sql = """
            INSERT INTO orders (
                order_id, strategy_id, asset_type, stock_code, order_type, order_category,
                order_price, order_quantity, order_status, create_time, update_time,
                execute_time, filled_quantity, filled_price, commission, error_message,
                stop_price, user_id, account_id, tags, metadata,
                contract_multiplier, margin_ratio, strike_price, expiry_date, option_type
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """

            params = [
                order_data['order_id'],
                order_data['strategy_id'],
                order_data['asset_type'],
                order_data['stock_code'],
                order_data['order_type'],
                order_data['order_category'],
                order_data['order_price'],
                order_data['order_quantity'],
                order_data['order_status'],
                order_data['create_time'],
                order_data['update_time'],
                order_data['execute_time'],
                order_data['filled_quantity'],
                order_data['filled_price'],
                order_data['commission'],
                order_data['error_message'],
                order_data['stop_price'],
                order_data['user_id'],
                order_data['account_id'],
                order_data['tags'],
                order_data['metadata'],
                order_data['contract_multiplier'],
                order_data['margin_ratio'],
                order_data['strike_price'],
                order_data['expiry_date'],
                order_data['option_type']
            ]

            pool_name = self._get_database_pool_name(order.asset_type)
            logger.debug(f"准备保存订单到数据池: {pool_name}")
            
            db_service.execute_query(sql, params, pool_name=pool_name)

            logger.info(f"订单保存成功: {order.order_id} → {pool_name}")
            self.event_bus.publish('order_saved', order_id=order.order_id)
            return True

        except Exception as e:
            pool_name = self._get_database_pool_name(order.asset_type) if hasattr(order, 'asset_type') else 'unknown'
            logger.error(f"保存订单失败: {order.order_id} ({order.asset_type.value if hasattr(order, 'asset_type') else 'unknown'}) - {e}")
            logger.error(f"订单详细信息: stock_code={order.stock_code if hasattr(order, 'stock_code') else 'unknown'}, order_type={order.order_type.value if hasattr(order, 'order_type') else 'unknown'}, order_quantity={order.order_quantity if hasattr(order, 'order_quantity') else 'unknown'}")
            logger.error(f"数据池: {pool_name}")
            logger.error(f"可能原因：")
            logger.error(f"  1. 数据库连接失败")
            logger.error(f"  2. 数据表不存在")
            logger.error(f"  3. 数据库事务失败")
            logger.error(f"  4. 数据类型不匹配")
            logger.error(f"  5. 约束冲突（如订单ID重复）")
            return False

    def update_order(self, order: Order) -> bool:
        """更新订单"""
        try:
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            order_data = order.to_dict()

            sql = """
            UPDATE orders SET
                strategy_id = ?,
                asset_type = ?,
                stock_code = ?,
                order_type = ?,
                order_category = ?,
                order_price = ?,
                order_quantity = ?,
                order_status = ?,
                update_time = ?,
                execute_time = ?,
                filled_quantity = ?,
                filled_price = ?,
                commission = ?,
                error_message = ?,
                stop_price = ?,
                user_id = ?,
                account_id = ?,
                tags = ?,
                metadata = ?,
                contract_multiplier = ?,
                margin_ratio = ?,
                strike_price = ?,
                expiry_date = ?,
                option_type = ?
            WHERE order_id = ?
            """

            params = [
                order_data['strategy_id'],
                order_data['asset_type'],
                order_data['stock_code'],
                order_data['order_type'],
                order_data['order_category'],
                order_data['order_price'],
                order_data['order_quantity'],
                order_data['order_status'],
                order_data['update_time'],
                order_data['execute_time'],
                order_data['filled_quantity'],
                order_data['filled_price'],
                order_data['commission'],
                order_data['error_message'],
                order_data['stop_price'],
                order_data['user_id'],
                order_data['account_id'],
                order_data['tags'],
                order_data['metadata'],
                order_data['contract_multiplier'],
                order_data['margin_ratio'],
                order_data['strike_price'],
                order_data['expiry_date'],
                order_data['option_type'],
                order_data['order_id']
            ]

            pool_name = self._get_database_pool_name(order.asset_type)
            db_service.execute_query(sql, params, pool_name=pool_name)

            # 更新缓存
            self.cache.update(order)

            logger.info(f"订单更新成功: {order.order_id} → {pool_name}")
            self.event_bus.publish('order_updated', order_id=order.order_id)
            return True

        except Exception as e:
            logger.error(f"更新订单失败: {e}")
            return False

    def update_orders_batch(self, orders: List[Order]) -> Dict[str, bool]:
        """
        批量更新订单

        Args:
            orders: 订单列表

        Returns:
            Dict[str, bool]: 更新结果字典，key为order_id，value为是否成功
        """
        try:
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            results = {}
            success_count = 0
            failed_count = 0

            # 按资产类型分组
            orders_by_asset_type: Dict[AssetType, List[Order]] = {}
            for order in orders:
                if order.asset_type not in orders_by_asset_type:
                    orders_by_asset_type[order.asset_type] = []
                orders_by_asset_type[order.asset_type].append(order)

            # 按资产类型批量更新
            for asset_type, asset_orders in orders_by_asset_type.items():
                pool_name = self._get_database_pool_name(asset_type)

                for order in asset_orders:
                    try:
                        order_data = order.to_dict()

                        sql = """
                        UPDATE orders SET
                            strategy_id = ?,
                            asset_type = ?,
                            stock_code = ?,
                            order_type = ?,
                            order_category = ?,
                            order_price = ?,
                            order_quantity = ?,
                            order_status = ?,
                            update_time = ?,
                            execute_time = ?,
                            filled_quantity = ?,
                            filled_price = ?,
                            commission = ?,
                            error_message = ?,
                            stop_price = ?,
                            user_id = ?,
                            account_id = ?,
                            tags = ?,
                            metadata = ?,
                            contract_multiplier = ?,
                            margin_ratio = ?,
                            strike_price = ?,
                            expiry_date = ?,
                            option_type = ?
                        WHERE order_id = ?
                        """

                        params = [
                            order_data['strategy_id'],
                            order_data['asset_type'],
                            order_data['stock_code'],
                            order_data['order_type'],
                            order_data['order_category'],
                            order_data['order_price'],
                            order_data['order_quantity'],
                            order_data['order_status'],
                            order_data['update_time'],
                            order_data['execute_time'],
                            order_data['filled_quantity'],
                            order_data['filled_price'],
                            order_data['commission'],
                            order_data['error_message'],
                            order_data['stop_price'],
                            order_data['user_id'],
                            order_data['account_id'],
                            order_data['tags'],
                            order_data['metadata'],
                            order_data['contract_multiplier'],
                            order_data['margin_ratio'],
                            order_data['strike_price'],
                            order_data['expiry_date'],
                            order_data['option_type'],
                            order_data['order_id']
                        ]

                        db_service.execute_query(sql, params, pool_name=pool_name)

                        # 更新缓存
                        self.cache.update(order)

                        results[order.order_id] = True
                        success_count += 1

                    except Exception as e:
                        logger.error(f"批量更新订单失败: {order.order_id} - {e}")
                        results[order.order_id] = False
                        failed_count += 1

            logger.info(f"批量更新订单完成: 成功 {success_count}, 失败 {failed_count}")
            return results

        except Exception as e:
            logger.error(f"批量更新订单异常: {e}")
            return {order.order_id: False for order in orders}

    def get_order(self, order_id: str, asset_type: Optional[AssetType] = None, use_cache: bool = True) -> Optional[Order]:
        """
        获取订单

        Args:
            order_id: 订单ID
            asset_type: 资产类型（可选）
            use_cache: 是否使用缓存，默认True

        Returns:
            Optional[Order]: 订单对象
        """
        try:
            # 先从缓存获取
            if use_cache:
                cached_order = self.cache.get(order_id)
                if cached_order:
                    logger.debug(f"从缓存获取订单: {order_id}")
                    return cached_order

            # 从数据库获取
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            sql = "SELECT * FROM orders WHERE order_id = ?"
            parameters = [order_id]

            if asset_type:
                pool_name = self._get_database_pool_name(asset_type)
                logger.debug(f"从指定数据池查询订单: {order_id} -> {pool_name}")
                result = db_service.fetch_all(sql, parameters, pool_name=pool_name)
            else:
                logger.debug(f"从所有数据池查询订单: {order_id}")
                for asset_type_enum in AssetType:
                    pool_name = self._get_database_pool_name(asset_type_enum)
                    result = db_service.fetch_all(sql, parameters, pool_name=pool_name)
                    if result and len(result) > 0:
                        logger.debug(f"在数据池 {pool_name} 中找到订单: {order_id}")
                        break
                else:
                    result = []

            if result and len(result) > 0:
                order_data = result[0]
                order = Order.from_dict(order_data)

                # 存入缓存
                if use_cache:
                    self.cache.set(order)

                logger.debug(f"获取订单成功: {order_id}")
                return order
            else:
                logger.warning(f"订单不存在: {order_id}")
                if not asset_type:
                    logger.warning(f"已查询所有资产类型的数据池，未找到订单")
                return None

        except Exception as e:
            logger.error(f"获取订单失败: {order_id} - {e}")
            return None

    def query_orders(self, query: OrderQuery) -> List[Order]:
        """查询订单（支持跨资产类型）"""
        try:
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            conditions = []
            parameters = []

            if query.strategy_id:
                conditions.append("strategy_id = ?")
                parameters.append(query.strategy_id)

            if query.asset_type:
                conditions.append("asset_type = ?")
                parameters.append(query.asset_type.value)

            if query.stock_code:
                conditions.append("stock_code = ?")
                parameters.append(query.stock_code)

            if query.order_type:
                conditions.append("order_type = ?")
                parameters.append(query.order_type.value)

            if query.order_status:
                conditions.append("order_status = ?")
                parameters.append(query.order_status.value)

            if query.user_id:
                conditions.append("user_id = ?")
                parameters.append(query.user_id)

            if query.account_id:
                conditions.append("account_id = ?")
                parameters.append(query.account_id)

            if query.start_time:
                conditions.append("create_time >= ?")
                parameters.append(query.start_time.isoformat())

            if query.end_time:
                conditions.append("create_time <= ?")
                parameters.append(query.end_time.isoformat())

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            sql = f"""
            SELECT * FROM orders
            WHERE {where_clause}
            ORDER BY {query.sort_by} {query.sort_order.upper()}
            """

            if query.asset_type:
                pool_name = self._get_database_pool_name(query.asset_type)
                sql_with_limit = f"{sql} LIMIT ? OFFSET ?"
                all_params = parameters + [query.limit, query.offset]
                results = db_service.fetch_all(sql_with_limit, all_params, pool_name=pool_name)
                orders = [Order.from_dict(order_data) for order_data in results]
            else:
                all_orders = []
                for asset_type_enum in AssetType:
                    pool_name = self._get_database_pool_name(asset_type_enum)
                    sql_with_limit = f"{sql} LIMIT ? OFFSET ?"
                    all_params = parameters + [query.limit, query.offset]
                    results = db_service.fetch_all(sql_with_limit, all_params, pool_name=pool_name)
                    orders = [Order.from_dict(order_data) for order_data in results]
                    all_orders.extend(orders)

                orders = all_orders
                orders.sort(key=lambda o: getattr(o, query.sort_by), 
                          reverse=(query.sort_order.upper() == 'DESC'))
                orders = orders[query.offset:query.offset + query.limit]

            logger.debug(f"查询订单成功: 返回 {len(orders)} 条记录")
            return orders

        except Exception as e:
            logger.error(f"查询订单失败: {e}")
            return []

    def get_active_orders(self, account_id: Optional[str] = None) -> List[Order]:
        """获取活跃订单"""
        query = OrderQuery(
            order_status=OrderStatus.PENDING,
            account_id=account_id,
            limit=1000
        )
        return self.query_orders(query)

    def get_orders_by_strategy(self, strategy_id: str, limit: int = 100) -> List[Order]:
        """获取策略订单"""
        query = OrderQuery(
            strategy_id=strategy_id,
            limit=limit
        )
        return self.query_orders(query)

    def get_orders_by_stock(self, stock_code: str, limit: int = 100) -> List[Order]:
        """获取股票订单"""
        query = OrderQuery(
            stock_code=stock_code,
            limit=limit
        )
        return self.query_orders(query)

    def save_order_fill(self, fill: OrderFill, asset_type: AssetType) -> bool:
        """保存订单成交记录"""
        try:
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            fill_data = fill.to_dict()

            sql = """
            INSERT INTO order_fills (
                fill_id, order_id, stock_code, fill_price, fill_quantity,
                fill_time, commission
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?
            )
            """

            params = [
                fill_data['fill_id'],
                fill_data['order_id'],
                fill_data['stock_code'],
                fill_data['fill_price'],
                fill_data['fill_quantity'],
                fill_data['fill_time'],
                fill_data['commission']
            ]

            pool_name = self._get_database_pool_name(asset_type)
            db_service.execute_query(sql, params, pool_name=pool_name)

            logger.info(f"订单成交记录保存成功: {fill.fill_id} → {pool_name}")
            self.event_bus.publish('order_fill_saved', fill_id=fill.fill_id)
            return True

        except Exception as e:
            logger.error(f"保存订单成交记录失败: {e}")
            return False

    def get_order_fills(self, order_id: str, asset_type: AssetType) -> List[OrderFill]:
        """获取订单成交记录"""
        try:
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            sql = """
            SELECT * FROM order_fills
            WHERE order_id = ?
            ORDER BY fill_time ASC
            """

            parameters = [order_id]
            pool_name = self._get_database_pool_name(asset_type)

            results = db_service.fetch_all(sql, parameters, pool_name=pool_name)

            fills = [OrderFill.from_dict(fill_data) for fill_data in results]

            logger.debug(f"获取订单成交记录成功: {order_id}, 返回 {len(fills)} 条记录")
            return fills

        except Exception as e:
            logger.error(f"获取订单成交记录失败: {e}")
            return []

    def delete_order(self, order_id: str, asset_type: AssetType = None) -> bool:
        """删除订单"""
        try:
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            sql = "DELETE FROM orders WHERE order_id = ?"
            parameters = [order_id]

            pools_to_try = []
            if asset_type:
                pools_to_try.append(self._get_database_pool_name(asset_type))
            else:
                for asset_type_enum in AssetType:
                    pools_to_try.append(self._get_database_pool_name(asset_type_enum))

            deleted = False
            for pool_name in pools_to_try:
                try:
                    db_service.execute_query(sql, parameters, pool_name=pool_name)
                    deleted = True
                    logger.info(f"订单删除成功: {order_id} → {pool_name}")
                    break
                except Exception:
                    continue

            if deleted:
                self.cache.delete(order_id)
                self.event_bus.publish('order_deleted', order_id=order_id)
                return True
            else:
                logger.warning(f"订单未找到: {order_id}")
                return False

        except Exception as e:
            logger.error(f"删除订单失败: {e}")
            return False

    def get_order_statistics(self, query: OrderQuery) -> Dict[str, Any]:
        """获取订单统计"""
        try:
            from core.services.database_service import DatabaseService
            db_service = self.service_container.resolve(DatabaseService)

            conditions = []
            parameters = []

            if query.strategy_id:
                conditions.append("strategy_id = ?")
                parameters.append(query.strategy_id)

            if query.stock_code:
                conditions.append("stock_code = ?")
                parameters.append(query.stock_code)

            if query.order_type:
                conditions.append("order_type = ?")
                parameters.append(query.order_type.value)

            if query.order_status:
                conditions.append("order_status = ?")
                parameters.append(query.order_status.value)

            if query.user_id:
                conditions.append("user_id = ?")
                parameters.append(query.user_id)

            if query.account_id:
                conditions.append("account_id = ?")
                parameters.append(query.account_id)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            sql = f"""
            SELECT
                COUNT(*) as total_orders,
                SUM(CASE WHEN order_status = 'filled' THEN 1 ELSE 0 END) as filled_orders,
                SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders,
                SUM(CASE WHEN order_status = 'rejected' THEN 1 ELSE 0 END) as rejected_orders,
                SUM(order_price * order_quantity) as total_value,
                SUM(filled_price * filled_quantity) as filled_value,
                SUM(commission) as total_commission
            FROM orders
            WHERE {where_clause}
            """

            result = db_service.fetch_all(sql, parameters, pool_name="strategy_sqlite")

            if result and len(result) > 0:
                row = result[0]
                total_orders = row['total_orders'] or 0
                filled_orders = row['filled_orders'] or 0
                cancelled_orders = row['cancelled_orders'] or 0
                rejected_orders = row['rejected_orders'] or 0

                statistics = {
                    'total_orders': total_orders,
                    'filled_orders': filled_orders,
                    'cancelled_orders': cancelled_orders,
                    'rejected_orders': rejected_orders,
                    'fill_rate': filled_orders / total_orders if total_orders > 0 else 0,
                    'total_value': row['total_value'] or 0,
                    'filled_value': row['filled_value'] or 0,
                    'total_commission': row['total_commission'] or 0
                }

                logger.debug(f"获取订单统计成功: {statistics}")
                return statistics
            else:
                return {
                    'total_orders': 0,
                    'filled_orders': 0,
                    'cancelled_orders': 0,
                    'rejected_orders': 0,
                    'fill_rate': 0,
                    'total_value': 0,
                    'filled_value': 0,
                    'total_commission': 0
                }

        except Exception as e:
            logger.error(f"获取订单统计失败: {e}")
            return {}

    def generate_order_id(self) -> str:
        """生成订单ID"""
        return f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:8].upper()}"

    def generate_fill_id(self) -> str:
        """生成成交ID"""
        return f"FIL{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:8].upper()}"
