"""
订单服务
"""

from sqlalchemy.orm import Session
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.schemas.order import OrderCreate, OrderUpdate, OrderFilter
from web.backend.models.order import OrderTemplate, OrderGroup, Fill
from core.trading.order_service import OrderService as CoreOrderService
from core.trading.order_analyzer import OrderAnalyzer
from core.containers.service_container import ServiceContainer
from core.events.event_bus import EventBus


class OrderService:
    """
    订单服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.service_container = ServiceContainer()
        self.event_bus = EventBus()
        self.core_order_service = CoreOrderService(self.service_container, self.event_bus)
        self.order_analyzer = OrderAnalyzer(self.service_container, self.event_bus)
    
    def get_orders(
        self,
        page: int = 1,
        page_size: int = 20,
        filter_params: OrderFilter = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取订单列表
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM orders WHERE 1=1"
        params = {}
        
        if filter_params:
            if filter_params.asset_type:
                query += " AND asset_type = :asset_type"
                params["asset_type"] = filter_params.asset_type
            
            if filter_params.account_id:
                query += " AND account_id = :account_id"
                params["account_id"] = filter_params.account_id
            
            if filter_params.status:
                query += " AND status = :status"
                params["status"] = filter_params.status
            
            if filter_params.start_time:
                query += " AND created_at >= :start_time"
                params["start_time"] = filter_params.start_time
            
            if filter_params.end_time:
                query += " AND created_at <= :end_time"
                params["end_time"] = filter_params.end_time
        
        query += " ORDER BY created_at DESC"
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        orders = duckdb_manager.execute_query(query, params)
        
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        count_query = count_query.split("ORDER BY")[0]
        total = duckdb_manager.execute_query(count_query, params)[0]["count"]
        
        return orders, total
    
    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取订单
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM orders WHERE order_id = :order_id"
        params = {"order_id": order_id}
        
        orders = duckdb_manager.execute_query(query, params)
        
        if orders:
            return orders[0]
        
        return None
    
    def create_order(self, order_data: OrderCreate) -> Dict[str, Any]:
        """
        创建订单
        """
        from core.trading.order import Order, OrderSide, OrderType
        
        order = Order(
            account_id=order_data.account_id,
            asset_type=order_data.asset_type,
            symbol=order_data.symbol,
            side=OrderSide(order_data.side.value),
            order_type=OrderType(order_data.order_type.value),
            quantity=order_data.quantity,
            price=order_data.price,
            stop_price=order_data.stop_price,
            time_in_force=order_data.time_in_force,
            remark=order_data.remark
        )
        
        self.core_order_service.create_order(order)
        
        return self.get_order_by_id(order.order_id)
    
    def update_order(self, order_id: str, order_data: OrderUpdate) -> Optional[Dict[str, Any]]:
        """
        修改订单
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        updates = {}
        if order_data.quantity is not None:
            updates["quantity"] = order_data.quantity
        if order_data.price is not None:
            updates["price"] = order_data.price
        if order_data.stop_price is not None:
            updates["stop_price"] = order_data.stop_price
        if order_data.remark is not None:
            updates["remark"] = order_data.remark
        
        if updates:
            updates["updated_at"] = datetime.now()
            
            set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
            query = f"UPDATE orders SET {set_clause} WHERE order_id = :order_id"
            params = {**updates, "order_id": order_id}
            
            duckdb_manager.execute_query(query, params)
        
        return self.get_order_by_id(order_id)
    
    def cancel_order(self, order_id: str) -> bool:
        """
        取消订单
        """
        from core.trading.order import Order
        
        order = self.core_order_service.get_order(order_id)
        if order:
            self.core_order_service.cancel_order(order_id)
            return True
        
        return False
    
    def batch_cancel_orders(self, order_ids: List[str]) -> Tuple[int, int]:
        """
        批量取消订单
        """
        success_count = 0
        failed_count = 0
        
        for order_id in order_ids:
            if self.cancel_order(order_id):
                success_count += 1
            else:
                failed_count += 1
        
        return success_count, failed_count
    
    def get_order_fills(self, order_id: str) -> List[Dict[str, Any]]:
        """
        获取订单成交记录
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM fills WHERE order_id = :order_id ORDER BY fill_time DESC"
        params = {"order_id": order_id}
        
        fills = duckdb_manager.execute_query(query, params)
        
        return fills
    
    def get_order_analysis(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        获取订单分析报告
        """
        order = self.get_order_by_id(order_id)
        if not order:
            return None
        
        start_time = order.get("created_at")
        end_time = datetime.now()
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        return report
    
    def create_order_template(self, user_id: int, template_data: Dict[str, Any]) -> OrderTemplate:
        """
        创建订单模板
        """
        template = OrderTemplate(
            user_id=user_id,
            name=template_data.get("name"),
            asset_type=template_data.get("asset_type"),
            symbol=template_data.get("symbol"),
            side=template_data.get("side"),
            order_type=template_data.get("order_type"),
            quantity=template_data.get("quantity"),
            price=template_data.get("price"),
            stop_price=template_data.get("stop_price"),
            time_in_force=template_data.get("time_in_force"),
            description=template_data.get("description")
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    def get_order_templates(self, user_id: int) -> List[OrderTemplate]:
        """
        获取订单模板
        """
        return self.db.query(OrderTemplate).filter(
            OrderTemplate.user_id == user_id
        ).all()
    
    def get_order_template_by_id(self, template_id: int) -> Optional[OrderTemplate]:
        """
        根据ID获取订单模板
        """
        return self.db.query(OrderTemplate).filter(
            OrderTemplate.id == template_id
        ).first()
    
    def update_order_template(self, template_id: int, template_data: Dict[str, Any]) -> Optional[OrderTemplate]:
        """
        更新订单模板
        """
        template = self.get_order_template_by_id(template_id)
        if template:
            for key, value in template_data.items():
                if hasattr(template, key) and value is not None:
                    setattr(template, key, value)
            
            self.db.commit()
            self.db.refresh(template)
        
        return template
    
    def delete_order_template(self, template_id: int) -> bool:
        """
        删除订单模板
        """
        template = self.get_order_template_by_id(template_id)
        if template:
            self.db.delete(template)
            self.db.commit()
            return True
        
        return False
    
    def create_order_from_template(self, template_id: int, account_id: int, overrides: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        从模板创建订单
        """
        template = self.get_order_template_by_id(template_id)
        if not template:
            return None
        
        order_data = {
            "account_id": account_id,
            "asset_type": template.asset_type,
            "symbol": template.symbol,
            "side": template.side,
            "order_type": template.order_type,
            "quantity": template.quantity,
            "price": template.price,
            "stop_price": template.stop_price,
            "time_in_force": template.time_in_force
        }
        
        if overrides:
            order_data.update(overrides)
        
        return self.create_order(order_data)
    
    def create_order_group(self, user_id: int, group_data: Dict[str, Any]) -> OrderGroup:
        """
        创建订单分组
        """
        group = OrderGroup(
            user_id=user_id,
            name=group_data.get("name"),
            description=group_data.get("description")
        )
        
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        
        return group
    
    def get_order_groups(self, user_id: int) -> List[OrderGroup]:
        """
        获取订单分组
        """
        return self.db.query(OrderGroup).filter(
            OrderGroup.user_id == user_id
        ).all()
    
    def add_orders_to_group(self, group_id: int, order_ids: List[str]) -> bool:
        """
        将订单添加到分组
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        for order_id in order_ids:
            query = "UPDATE orders SET group_id = :group_id WHERE order_id = :order_id"
            params = {"group_id": group_id, "order_id": order_id}
            duckdb_manager.execute_query(query, params)
        
        return True
    
    def remove_orders_from_group(self, group_id: int, order_ids: List[str]) -> bool:
        """
        将订单从分组中移除
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        for order_id in order_ids:
            query = "UPDATE orders SET group_id = NULL WHERE order_id = :order_id"
            params = {"order_id": order_id}
            duckdb_manager.execute_query(query, params)
        
        return True
    
    def get_orders_by_group(self, group_id: int, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取分组中的订单
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM orders WHERE group_id = :group_id ORDER BY created_at DESC"
        params = {"group_id": group_id}
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        orders = duckdb_manager.execute_query(query, params)
        
        count_query = "SELECT COUNT(*) as count FROM orders WHERE group_id = :group_id"
        total = duckdb_manager.execute_query(count_query, params)[0]["count"]
        
        return orders, total
    
    def batch_create_orders(self, orders_data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        批量创建订单
        """
        success_orders = []
        failed_order_ids = []
        
        for order_data in orders_data:
            try:
                order = self.create_order(order_data)
                success_orders.append(order)
            except Exception as e:
                failed_order_ids.append(order_data.get("order_id", "unknown"))
        
        return success_orders, failed_order_ids
    
    def get_order_statistics(self, start_time: datetime = None, end_time: datetime = None) -> Dict[str, Any]:
        """
        获取订单统计
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        if not start_time:
            start_time = datetime.now() - timedelta(days=30)
        
        if not end_time:
            end_time = datetime.now()
        
        query = """
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) as filled_orders,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_orders,
                SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buy_orders,
                SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sell_orders
            FROM orders 
            WHERE created_at >= :start_time AND created_at <= :end_time
        """
        
        params = {"start_time": start_time, "end_time": end_time}
        stats = duckdb_manager.execute_query(query, params)[0]
        
        return stats
    
    def get_active_orders(self, account_id: str = None) -> List[Dict[str, Any]]:
        """
        获取活跃订单
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM orders WHERE status IN ('pending', 'partial_filled')"
        params = {}
        
        if account_id:
            query += " AND account_id = :account_id"
            params["account_id"] = account_id
        
        query += " ORDER BY created_at DESC"
        
        orders = duckdb_manager.execute_query(query, params)
        
        return orders
    
    def get_order_history(
        self,
        account_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取订单历史
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM orders WHERE 1=1"
        params = {}
        
        if account_id:
            query += " AND account_id = :account_id"
            params["account_id"] = account_id
        
        if start_time:
            query += " AND created_at >= :start_time"
            params["start_time"] = start_time
        
        if end_time:
            query += " AND created_at <= :end_time"
            params["end_time"] = end_time
        
        query += " ORDER BY created_at DESC"
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        orders = duckdb_manager.execute_query(query, params)
        
        count_query = query.split("ORDER BY")[0].replace("SELECT *", "SELECT COUNT(*)")
        total = duckdb_manager.execute_query(count_query, params)[0]["count"]
        
        return orders, total
