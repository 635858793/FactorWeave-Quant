#!/usr/bin/env python3
"""
数据访问最佳实践示例

演示如何正确使用系统框架获取数据，而不是直接实例化DataAccess类。
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

# 系统框架导入
from core.containers import get_service_container
from core.services.unified_data_manager import get_unified_data_manager
from core.services.stock_service import StockService


class DataAccessExamples:
    """数据访问最佳实践示例类"""

    def __init__(self):
        self.service_container = None
        self.data_manager = None
        self.stock_service = None
        self._initialize_services()

    def _initialize_services(self):
        """初始化服务"""
        try:
            #  获取服务容器
            self.service_container = get_service_container()
            logger.info("获取服务容器成功")

            #  获取统一数据管理器
            self.data_manager = get_unified_data_manager()
            if self.data_manager:
                logger.info("获取统一数据管理器成功")

            #  从服务容器获取股票服务
            if self.service_container and self.service_container.is_registered(StockService):
                self.stock_service = self.service_container.resolve(StockService)
                logger.info("获取股票服务成功")

        except Exception as e:
            logger.error(f"服务初始化失败: {e}")

    def example_1_get_stock_list_via_unified_manager(self) -> List[Dict[str, Any]]:
        """
        示例1：通过统一数据管理器获取股票列表
         推荐方式
        """
        logger.info("=== 示例1：使用统一数据管理器获取股票列表 ===")

        try:
            if not self.data_manager:
                logger.warning("统一数据管理器不可用")
                return []

            # 使用统一数据管理器获取股票列表
            stock_list = self.data_manager.get_stock_list()

            if stock_list:
                logger.info(f" 通过统一数据管理器获取到 {len(stock_list)} 只股票")
                return stock_list[:10]  # 返回前10只股票作为示例
            else:
                logger.warning("未获取到股票数据")
                return []

        except Exception as e:
            logger.error(f"通过统一数据管理器获取股票列表失败: {e}")
            return []

    def example_2_get_stock_list_via_stock_service(self) -> List[Dict[str, Any]]:
        """
        示例2：通过股票服务获取股票列表
         推荐方式
        """
        logger.info("=== 示例2：使用股票服务获取股票列表 ===")

        try:
            if not self.stock_service:
                logger.warning("股票服务不可用")
                return []

            # 使用股票服务获取股票列表
            stock_list = self.stock_service.get_stock_list()

            if stock_list:
                logger.info(f" 通过股票服务获取到 {len(stock_list)} 只股票")
                return stock_list[:10]  # 返回前10只股票作为示例
            else:
                logger.warning("未获取到股票数据")
                return []

        except Exception as e:
            logger.error(f"通过股票服务获取股票列表失败: {e}")
            return []

    def example_3_get_stock_data_with_fallback(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        示例3：获取单只股票数据（带回退机制）
         推荐方式 - 多重回退保证可用性
        """
        logger.info(f"=== 示例3：获取股票 {symbol} 的数据（带回退机制） ===")

        # 方法1：尝试使用统一数据管理器
        try:
            if self.data_manager:
                stock_data = self.data_manager.get_stock_data(symbol, period='D', count=30)
                if stock_data is not None and not stock_data.empty:
                    logger.info(f" 通过统一数据管理器获取到 {symbol} 的数据")
                    return {
                        'symbol': symbol,
                        'data': stock_data,
                        'source': 'UnifiedDataManager',
                        'timestamp': datetime.now()
                    }
        except Exception as e:
            logger.warning(f"统一数据管理器获取 {symbol} 失败: {e}")

        # 方法2：尝试使用股票服务
        try:
            if self.stock_service:
                stock_data = self.stock_service.get_stock_data(symbol, period='D', count=30)
                if stock_data is not None and not stock_data.empty:
                    logger.info(f" 通过股票服务获取到 {symbol} 的数据")
                    return {
                        'symbol': symbol,
                        'data': stock_data,
                        'source': 'StockService',
                        'timestamp': datetime.now()
                    }
        except Exception as e:
            logger.warning(f"股票服务获取 {symbol} 失败: {e}")

        # 方法3：最后的备用方案 - 直接使用DataAccess（不推荐，仅作备用）
        try:
            logger.warning(f"使用备用方案获取 {symbol} 数据")
            from core.data.data_access import DataAccess

            data_access = DataAccess()
            data_access.connect()

            kline_data_obj = data_access.get_kline_data(symbol, period='D', count=30)
            if kline_data_obj and kline_data_obj.data is not None and not kline_data_obj.data.empty:
                logger.info(f" 通过备用方案获取到 {symbol} 的数据")
                return {
                    'symbol': symbol,
                    'data': kline_data_obj.data,
                    'source': 'DataAccess (fallback)',
                    'timestamp': datetime.now()
                }
        except Exception as e:
            logger.error(f"备用方案获取 {symbol} 失败: {e}")

        logger.error(f" 所有方法都无法获取 {symbol} 的数据")
        return None

    def example_4_wrong_way_direct_instantiation(self):
        """
        示例4：错误的方式 - 直接实例化DataAccess
         不推荐，仅用于说明
        """
        logger.info("=== 示例4：错误的方式 - 直接实例化DataAccess ===")
        logger.warning("以下代码展示了不推荐的做法：")

        #  错误的做法
        # from core.data.data_access import DataAccess
        # data_access = DataAccess()  # 直接实例化

        logger.warning("问题：")
        logger.warning("1. 违反了依赖注入原则")
        logger.warning("2. 无法利用系统的缓存和优化")
        logger.warning("3. 难以进行单元测试")
        logger.warning("4. 可能造成资源浪费")

        logger.info("应该使用前面示例中的方法")


class ComponentWithProperDataAccess:
    """
    示例组件：展示如何在组件中正确使用数据访问
    """

    def __init__(self, service_container=None):
        """
         正确的构造函数 - 接收服务容器
        """
        self.service_container = service_container
        self.data_manager = None
        self.stock_service = None
        self._initialized = False

    def initialize(self):
        """初始化组件"""
        try:
            #  从服务容器获取依赖
            if self.service_container:
                try:
                    from core.services.unified_data_manager import UnifiedDataManager
                    self.data_manager = self.service_container.resolve(UnifiedDataManager)
                    logger.info("组件获取到统一数据管理器")
                except Exception as e:
                    logger.warning(f"无法获取统一数据管理器: {e}")

                try:
                    self.stock_service = self.service_container.resolve(StockService)
                    logger.info("组件获取到股票服务")
                except Exception as e:
                    logger.warning(f"无法获取股票服务: {e}")

            # 备用方案
            if not self.data_manager and not self.stock_service:
                self.data_manager = get_unified_data_manager()
                logger.info("组件通过全局函数获取到统一数据管理器")

            self._initialized = True

        except Exception as e:
            logger.error(f"组件初始化失败: {e}")

    def get_data(self, symbol: str):
        """获取数据的方法"""
        if not self._initialized:
            self.initialize()

        #  使用注入的依赖获取数据
        if self.data_manager:
            return self.data_manager.get_stock_data(symbol)
        elif self.stock_service:
            return self.stock_service.get_stock_data(symbol)
        else:
            logger.error("没有可用的数据服务")
            return None


def main():
    """主函数：运行所有示例"""
    logger.info("开始数据访问最佳实践示例")

    # 创建示例实例
    examples = DataAccessExamples()

    # 运行示例1
    stock_list_1 = examples.example_1_get_stock_list_via_unified_manager()
    if stock_list_1:
        logger.info(f"示例1成功：获取到 {len(stock_list_1)} 只股票")

    # 运行示例2
    stock_list_2 = examples.example_2_get_stock_list_via_stock_service()
    if stock_list_2:
        logger.info(f"示例2成功：获取到 {len(stock_list_2)} 只股票")

    # 运行示例3
    if stock_list_1 or stock_list_2:
        # 使用第一只股票作为示例
        test_symbols = ['000001', '000002', '600000']
        for symbol in test_symbols:
            stock_data = examples.example_3_get_stock_data_with_fallback(symbol)
            if stock_data:
                logger.info(f"示例3成功：获取到 {symbol} 的数据，来源：{stock_data['source']}")
                break

    # 运行示例4（错误方式说明）
    examples.example_4_wrong_way_direct_instantiation()

    # 组件示例
    logger.info("=== 组件使用示例 ===")
    service_container = get_service_container()
    component = ComponentWithProperDataAccess(service_container)
    component.initialize()

    logger.info("数据访问最佳实践示例完成")


if __name__ == "__main__":
    # Loguru配置在core.loguru_config中统一管理
    main()
