#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略管理器

作为 StrategyService 的适配器，提供统一的策略管理接口。
主要用于订单执行器中的策略级别账号解析。
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger


@dataclass
class Strategy:
    """
    策略数据类

    用于订单执行器中获取策略的默认账号信息
    """
    strategy_id: str
    name: str
    plugin_type: str
    default_account_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class StrategyManager:
    """
    策略管理器

    作为 StrategyService 的适配器，提供统一的策略管理接口。
    主要用于订单执行器中的策略级别账号解析。
    """

    def __init__(self, service_container=None):
        """
        初始化策略管理器

        Args:
            service_container: 服务容器，用于获取 StrategyService
        """
        self.service_container = service_container
        self._strategy_service = None
        self._strategy_cache: Dict[str, Strategy] = {}

        logger.info("策略管理器初始化完成")

    def _get_strategy_service(self):
        """
        获取 StrategyService 实例（延迟加载）

        Returns:
            StrategyService: 策略服务实例，如果不可用则返回 None
        """
        if self._strategy_service is not None:
            return self._strategy_service

        try:
            from core.services.strategy_service import StrategyService

            if self.service_container:
                self._strategy_service = self.service_container.resolve(StrategyService)
                logger.debug("成功从服务容器获取 StrategyService")
            else:
                logger.warning("服务容器不可用，无法获取 StrategyService")

        except ImportError as e:
            logger.warning(f"StrategyService 模块导入失败: {e}")
        except Exception as e:
            logger.warning(f"获取 StrategyService 失败: {e}")

        return self._strategy_service

    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """
        获取策略信息

        Args:
            strategy_id: 策略ID

        Returns:
            Strategy: 策略对象，如果不存在则返回 None
        """
        # 检查缓存
        if strategy_id in self._strategy_cache:
            return self._strategy_cache[strategy_id]

        strategy_service = self._get_strategy_service()
        if not strategy_service:
            logger.debug(f"StrategyService 不可用，无法获取策略: {strategy_id}")
            return None

        try:
            # 从 StrategyService 获取策略配置
            strategy_config = strategy_service.get_strategy_config(strategy_id)

            if not strategy_config:
                logger.debug(f"策略配置不存在: {strategy_id}")
                return None

            # 创建 Strategy 对象
            strategy = Strategy(
                strategy_id=strategy_config.strategy_id,
                name=strategy_config.strategy_id,  # 使用 strategy_id 作为名称
                plugin_type=strategy_config.plugin_type,
                default_account_id=strategy_config.metadata.get('default_account_id'),
                metadata=strategy_config.metadata
            )

            # 缓存策略信息
            self._strategy_cache[strategy_id] = strategy

            logger.debug(f"成功获取策略: {strategy_id}, 默认账号: {strategy.default_account_id}")
            return strategy

        except Exception as e:
            logger.error(f"获取策略信息失败 {strategy_id}: {e}")
            return None

    def clear_cache(self):
        """清除策略缓存"""
        self._strategy_cache.clear()
        logger.debug("策略缓存已清除")

    def get_all_strategies(self) -> Dict[str, Strategy]:
        """
        获取所有策略

        Returns:
            Dict[str, Strategy]: 策略字典，key 为 strategy_id
        """
        strategy_service = self._get_strategy_service()
        if not strategy_service:
            logger.debug("StrategyService 不可用，无法获取策略列表")
            return {}

        try:
            strategy_configs = strategy_service.get_all_strategy_configs()
            strategies = {}

            for config in strategy_configs:
                strategy = Strategy(
                    strategy_id=config.strategy_id,
                    name=config.strategy_id,
                    plugin_type=config.plugin_type,
                    default_account_id=config.metadata.get('default_account_id'),
                    metadata=config.metadata
                )
                strategies[config.strategy_id] = strategy
                self._strategy_cache[config.strategy_id] = strategy

            logger.debug(f"成功获取 {len(strategies)} 个策略")
            return strategies

        except Exception as e:
            logger.error(f"获取策略列表失败: {e}")
            return {}
