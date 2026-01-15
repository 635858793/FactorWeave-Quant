#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应连接池系统初始化器

在系统启动时自动初始化并启动自适应连接池管理。

作者: AI Assistant
日期: 2025-10-13
"""

from loguru import logger
from typing import Optional

from .database.factorweave_analytics_db import get_analytics_db
from .database.adaptive_connection_pool import (
    AdaptiveConnectionPoolManager,
    AdaptivePoolConfig,
    start_adaptive_management
)
from .database.connection_pool_config import ConnectionPoolConfigManager
from .containers import get_service_container
from .services.config_service import ConfigService


# 全局管理器引用
_adaptive_manager: Optional[AdaptiveConnectionPoolManager] = None


def initialize_adaptive_pool() -> Optional[AdaptiveConnectionPoolManager]:
    """
    初始化自适应连接池管理（旧版本，仅支持 analytics_duckdb）

    此函数应在系统启动时调用，会：
    1. 从ConfigService加载配置
    2. 创建AdaptiveConnectionPoolManager
    3. 启动自适应管理

    Returns:
        AdaptiveConnectionPoolManager实例或None（如果禁用或失败）

    注意：此函数已被 initialize_adaptive_pools_by_config() 替代
    建议使用新的初始化函数以支持多连接池管理
    """
    global _adaptive_manager

    try:
        logger.info("🔄 初始化自适应连接池管理（旧版本）...")

        # 获取ConfigService
        try:
            container = get_service_container()
            config_service = container.resolve(ConfigService)
            config_manager = ConnectionPoolConfigManager(config_service)
        except Exception as e:
            logger.warning(f"无法获取ConfigService，使用默认配置: {e}")
            config_manager = None

        # 检查是否启用
        if config_manager and not config_manager.is_adaptive_enabled():
            logger.info("⏸️ 自适应连接池已禁用")
            return None

        # 加载配置
        if config_manager:
            adaptive_config_dict = config_manager.load_adaptive_config()
            adaptive_config = AdaptivePoolConfig(**adaptive_config_dict)
            logger.info(f"📋 已加载自适应配置: min={adaptive_config.min_pool_size}, max={adaptive_config.max_pool_size}")
        else:
            adaptive_config = AdaptivePoolConfig()  # 使用默认配置
            logger.info("📋 使用默认自适应配置")

        # 获取数据库实例
        db = get_analytics_db()

        # 创建并启动自适应管理器
        _adaptive_manager = AdaptiveConnectionPoolManager(db, adaptive_config)
        _adaptive_manager.start()

        logger.info("✅ 自适应连接池管理已成功初始化并启动")
        return _adaptive_manager

    except Exception as e:
        logger.error(f"❌ 初始化自适应连接池失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def initialize_adaptive_pools_by_config() -> Optional[AdaptiveConnectionPoolManager]:
    """
    初始化所有连接池的自适应管理（新版本，支持多连接池）

    此函数应在系统启动时调用，会：
    1. 从ConfigService加载连接池级别的自适应配置
    2. 遍历所有连接池，根据配置决定是否创建管理器
    3. 对于启用的连接池，创建AdaptiveConnectionPoolManager并启动
    4. 对于禁用的连接池，使用DatabaseService的固定配置

    Returns:
        第一个成功创建的AdaptiveConnectionPoolManager实例（如果有）

    默认配置策略：
    - analytics_duckdb: enabled=true（高频并发，必须启用）
    - strategy_sqlite: enabled=false（中频，默认禁用但可选启用）
    - factorweave_system_sqlite: enabled=false（低频，默认禁用）
    - tradeaccount_sqlite: enabled=false（低频，默认禁用）
    """
    global _adaptive_manager

    try:
        logger.info("🔄 初始化所有连接池的自适应管理...")

        # 获取ConfigService
        try:
            container = get_service_container()
            config_service = container.resolve(ConfigService)
            config_manager = ConnectionPoolConfigManager(config_service)
        except Exception as e:
            logger.warning(f"无法获取ConfigService，使用默认配置: {e}")
            config_manager = None

        # 加载连接池级别的自适应配置
        per_pool_config = config_manager.get('adaptive_pool_per_pool', {})

        # 定义所有连接池及其默认配置
        all_pools = {
            "analytics_duckdb": {
                "enabled": True,
                "min_pool_size": 3,
                "max_pool_size": 50,
                "scale_up_usage_threshold": 0.8,
                "scale_down_usage_threshold": 0.3,
                "scale_up_overflow_threshold": 0.5,
                "metrics_window_seconds": 60,
                "cooldown_seconds": 60,
                "collection_interval": 10,
                "scale_up_factor": 1.5,
                "scale_down_factor": 0.8
            },
            "strategy_sqlite": {
                "enabled": False,
                "pool_size": 10,
                "max_pool_size": 30
            },
            "factorweave_system_sqlite": {
                "enabled": False,
                "pool_size": 10,
                "max_pool_size": 30
            },
            "tradeaccount_sqlite": {
                "enabled": False,
                "pool_size": 10,
                "max_pool_size": 30
            }
        }

        # 确保默认配置存在
        if not per_pool_config:
            config_manager.set('adaptive_pool_per_pool', all_pools)
            logger.info("✅ 已初始化连接池级别的自适应默认配置")

        # 遍历所有连接池，创建自适应管理器
        created_manager = None

        for pool_name, default_config in all_pools.items():
            try:
                # 加载该连接池的自适应配置
                pool_config = config_manager.load_adaptive_pool_config(pool_name)

                # 检查是否启用自适应
                if not pool_config.get('enabled', False):
                    logger.info(f"连接池 {pool_name} 未启用自适应管理，使用固定配置")
                    continue

                # 获取数据库实例
                if pool_name == "analytics_duckdb":
                    db = get_analytics_db()
                else:
                    logger.warning(f"连接池 {pool_name} 不支持自适应管理（仅 analytics_duckdb 支持）")
                    continue

                # 创建自适应配置
                from .database.adaptive_connection_pool import AdaptivePoolConfig
                adaptive_config = AdaptivePoolConfig(**pool_config)

                # 创建并启动自适应管理器
                manager = AdaptiveConnectionPoolManager(db, adaptive_config)
                manager.start()

                # 保存第一个成功创建的管理器
                if created_manager is None:
                    created_manager = manager
                    logger.info(f"✅ 连接池 {pool_name} 的自适应管理器已创建并启动")

            except Exception as e:
                logger.error(f"创建连接池 {pool_name} 的自适应管理器失败: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # 返回第一个成功创建的管理器
        _adaptive_manager = created_manager
        return _adaptive_manager

    except Exception as e:
        logger.error(f"❌ 初始化所有连接池的自适应管理失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def get_adaptive_manager() -> Optional[AdaptiveConnectionPoolManager]:
    """获取全局自适应管理器实例"""
    return _adaptive_manager


def stop_adaptive_pool():
    """停止自适应连接池管理"""
    global _adaptive_manager

    if _adaptive_manager:
        try:
            _adaptive_manager.stop()
            logger.info("⏸️ 自适应连接池管理已停止")
        except Exception as e:
            logger.error(f"停止自适应管理失败: {e}")
        finally:
            _adaptive_manager = None
