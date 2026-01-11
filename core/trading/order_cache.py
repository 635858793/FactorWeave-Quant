#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单缓存管理器

提供订单缓存功能，减少数据库查询次数，提高性能
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from loguru import logger
from threading import Lock

from core.trading.order_models import Order


class OrderCache:
    """订单缓存"""

    def __init__(self, ttl_seconds: int = 300):
        """
        初始化订单缓存

        Args:
            ttl_seconds: 缓存过期时间（秒），默认5分钟
        """
        self._cache: Dict[str, Order] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = Lock()

        logger.info(f"订单缓存初始化完成 (TTL: {ttl_seconds}秒)")

    def get(self, order_id: str) -> Optional[Order]:
        """
        从缓存获取订单

        Args:
            order_id: 订单ID

        Returns:
            Optional[Order]: 订单对象，如果不存在或已过期则返回None
        """
        with self._lock:
            if order_id not in self._cache:
                return None

            # 检查是否过期
            if datetime.now() - self._timestamps[order_id] > self._ttl:
                logger.debug(f"订单缓存已过期: {order_id}")
                del self._cache[order_id]
                del self._timestamps[order_id]
                return None

            logger.debug(f"从缓存获取订单: {order_id}")
            return self._cache[order_id]

    def set(self, order: Order):
        """
        将订单存入缓存

        Args:
            order: 订单对象
        """
        with self._lock:
            self._cache[order.order_id] = order
            self._timestamps[order.order_id] = datetime.now()
            logger.debug(f"订单已缓存: {order.order_id}")

    def delete(self, order_id: str):
        """
        从缓存删除订单

        Args:
            order_id: 订单ID
        """
        with self._lock:
            if order_id in self._cache:
                del self._cache[order_id]
                del self._timestamps[order_id]
                logger.debug(f"订单已从缓存删除: {order_id}")

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            logger.info("订单缓存已清空")

    def size(self) -> int:
        """
        获取缓存大小

        Returns:
            int: 缓存中的订单数量
        """
        with self._lock:
            return len(self._cache)

    def cleanup_expired(self):
        """清理过期的缓存"""
        with self._lock:
            now = datetime.now()
            expired_ids = [
                order_id for order_id, timestamp in self._timestamps.items()
                if now - timestamp > self._ttl
            ]

            for order_id in expired_ids:
                del self._cache[order_id]
                del self._timestamps[order_id]

            if expired_ids:
                logger.info(f"清理过期缓存: {len(expired_ids)} 个订单")

    def get_all(self) -> List[Order]:
        """
        获取所有缓存的订单

        Returns:
            List[Order]: 订单列表
        """
        with self._lock:
            # 清理过期缓存
            self.cleanup_expired()
            return list(self._cache.values())

    def get_by_status(self, status) -> List[Order]:
        """
        根据状态获取订单

        Args:
            status: 订单状态

        Returns:
            List[Order]: 订单列表
        """
        with self._lock:
            self.cleanup_expired()
            return [order for order in self._cache.values() if order.order_status == status]

    def get_by_asset_type(self, asset_type) -> List[Order]:
        """
        根据资产类型获取订单

        Args:
            asset_type: 资产类型

        Returns:
            List[Order]: 订单列表
        """
        with self._lock:
            self.cleanup_expired()
            return [order for order in self._cache.values() if order.asset_type == asset_type]

    def get_by_strategy(self, strategy_id: str) -> List[Order]:
        """
        根据策略ID获取订单

        Args:
            strategy_id: 策略ID

        Returns:
            List[Order]: 订单列表
        """
        with self._lock:
            self.cleanup_expired()
            return [order for order in self._cache.values() if order.strategy_id == strategy_id]

    def get_by_stock_code(self, stock_code: str) -> List[Order]:
        """
        根据股票代码获取订单

        Args:
            stock_code: 股票代码

        Returns:
            List[Order]: 订单列表
        """
        with self._lock:
            self.cleanup_expired()
            return [order for order in self._cache.values() if order.stock_code == stock_code]

    def update(self, order: Order):
        """
        更新缓存中的订单

        Args:
            order: 订单对象
        """
        with self._lock:
            if order.order_id in self._cache:
                self._cache[order.order_id] = order
                self._timestamps[order.order_id] = datetime.now()
                logger.debug(f"订单缓存已更新: {order.order_id}")

    def exists(self, order_id: str) -> bool:
        """
        检查订单是否在缓存中

        Args:
            order_id: 订单ID

        Returns:
            bool: 是否存在
        """
        with self._lock:
            if order_id not in self._cache:
                return False

            # 检查是否过期
            if datetime.now() - self._timestamps[order_id] > self._ttl:
                del self._cache[order_id]
                del self._timestamps[order_id]
                return False

            return True

    def get_stats(self) -> Dict[str, any]:
        """
        获取缓存统计信息

        Returns:
            Dict[str, any]: 统计信息
        """
        with self._lock:
            self.cleanup_expired()
            return {
                'size': len(self._cache),
                'ttl_seconds': self._ttl.total_seconds(),
                'by_status': {
                    status.value: len([o for o in self._cache.values() if o.order_status == status])
                    for status in set(order.order_status for order in self._cache.values())
                },
                'by_asset_type': {
                    asset_type.value: len([o for o in self._cache.values() if o.asset_type == asset_type])
                    for asset_type in set(order.asset_type for order in self._cache.values())
                }
            }
