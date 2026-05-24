#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
板块资金流功能使用示例

本示例展示如何使用FactorWeave-Quant系统的板块资金流功能，包括：
1. 获取板块资金流排行榜
2. 查看板块历史趋势
3. 获取板块分时资金流数据
4. 导入板块历史数据
5. 使用API接口访问数据

运行前提：
- 确保已正确安装系统依赖
- 数据库已初始化
- 数据源服务可用
"""

import sys
import os
import asyncio
import requests
import json
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.services.unified_data_manager import get_unified_data_manager

class SectorFundFlowExample:
    """板块资金流功能使用示例类"""

    def __init__(self):
        """初始化示例"""
        self.data_manager = None
        self.sector_service = None
        self.api_base_url = "http://localhost:8000"

    def initialize(self):
        """初始化数据管理器和服务"""
        try:
            logger.info("正在直接创建服务...")

            # 直接创建SectorDataService，避免依赖服务容器
            from core.services.sector_data_service import SectorDataService
            from core.tet_data_pipeline import TETDataPipeline

            # 创建必要的组件（这里可以使用None，SectorDataService会处理）
            cache_manager = None  # SectorDataService会处理None情况
            tet_pipeline = None   # SectorDataService会处理None情况

            self.sector_service = SectorDataService(cache_manager, tet_pipeline)

            if self.sector_service is None:
                raise ValueError("板块资金流服务创建失败")

            logger.info("直接创建SectorDataService成功")
            return True

        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            return False

    def example_get_ranking(self):
        """示例：获取板块资金流排行榜"""
        logger.info("\n=== 示例1: 获取板块资金流排行榜 ===")

        try:
            # 获取今日排行榜
            logger.info("获取今日板块资金流排行榜...")
            ranking_data = self.sector_service.get_sector_fund_flow_ranking(
                date_range="today",
                sort_by="main_net_inflow"
            )

            if not ranking_data.empty:
                logger.info(f"成功获取 {len(ranking_data)} 条排行榜数据")
                logger.info("前5名板块:")
                for i, row in ranking_data.head(5).iterrows():
                    logger.info(f"  {i+1}. {row['sector_name']} - 主力净流入: {row['main_net_inflow']:,.0f}")
            else:
                logger.warning("⚠️ 未获取到排行榜数据")

        except Exception as e:
            logger.error(f"❌ 获取排行榜失败: {e}")

    def example_get_historical_trend(self):
        """示例：获取板块历史趋势"""
        logger.info("\n=== 示例2: 获取板块历史趋势 ===")

        try:
            # 获取BK0001板块近30天历史趋势
            sector_id = "BK0001"
            period = 30

            logger.info(f"获取板块 {sector_id} 近 {period} 天历史趋势...")
            trend_data = self.sector_service.get_sector_historical_trend(
                sector_id=sector_id,
                period=period
            )

            if not trend_data.empty:
                logger.info(f"成功获取 {len(trend_data)} 条历史趋势数据")
                logger.info("近5天数据:")
                for i, row in trend_data.tail(5).iterrows():
                    logger.info(f"  {row['trade_date']} - 主力净流入: {row['main_net_inflow']:,.0f}")
            else:
                logger.warning(f"⚠️ 未获取到板块 {sector_id} 的历史趋势数据")

        except Exception as e:
            logger.error(f"❌ 获取历史趋势失败: {e}")

    def example_get_intraday_flow(self):
        """示例：获取板块分时资金流"""
        logger.info("\n=== 示例3: 获取板块分时资金流 ===")

        try:
            # 获取BK0001板块今日分时数据
            sector_id = "BK0001"
            date = datetime.now().strftime("%Y-%m-%d")

            logger.info(f"获取板块 {sector_id} 在 {date} 的分时资金流...")
            intraday_data = self.sector_service.get_sector_intraday_flow(
                sector_id=sector_id,
                date=date
            )

            if not intraday_data.empty:
                logger.info(f"成功获取 {len(intraday_data)} 条分时数据")
                logger.info("近5个时间点数据:")
                for i, row in intraday_data.tail(5).iterrows():
                    logger.info(f"  {row['trade_time']} - 净流入: {row['net_inflow']:,.0f}")
            else:
                logger.warning(f"⚠️ 未获取到板块 {sector_id} 在 {date} 的分时数据")

        except Exception as e:
            logger.error(f"❌ 获取分时资金流失败: {e}")

    def example_import_historical_data(self):
        """示例：导入板块历史数据"""
        logger.info("\n=== 示例4: 导入板块历史数据 ===")

        try:
            # 导入近7天的数据
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            source = "akshare"

            logger.info(f"从 {source} 导入 {start_date} 到 {end_date} 的板块历史数据...")
            import_result = self.sector_service.import_sector_historical_data(
                source=source,
                start_date=start_date,
                end_date=end_date
            )

            if import_result.get('success', False):
                processed_count = import_result.get('processed_count', 0)
                logger.info(f"成功导入 {processed_count} 条历史数据")
            else:
                error_msg = import_result.get('error', '未知错误')
                logger.warning(f"⚠️ 导入失败: {error_msg}")

        except Exception as e:
            logger.error(f"❌ 导入历史数据失败: {e}")

    def example_api_calls(self):
        """示例：使用API接口访问数据"""
        logger.info("\n=== 示例5: API接口调用 ===")

        try:
            # 1. 检查服务状态
            logger.info("检查板块资金流服务状态...")
            status_response = requests.get(f"{self.api_base_url}/api/sector/fund-flow/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                logger.info(f"服务状态: {status_data['status']}")
            else:
                logger.warning(f"⚠️ 服务状态检查失败: {status_response.status_code}")
                return

            # 2. 获取排行榜
            logger.info("通过API获取板块资金流排行榜...")
            ranking_response = requests.get(
                f"{self.api_base_url}/api/sector/fund-flow/ranking",
                params={"date_range": "today", "sort_by": "main_net_inflow"}
            )
            if ranking_response.status_code == 200:
                ranking_data = ranking_response.json()
                count = ranking_data.get('count', 0)
                logger.info(f"API获取 {count} 条排行榜数据")
            else:
                logger.warning(f"⚠️ API获取排行榜失败: {ranking_response.status_code}")

            # 3. 获取历史趋势
            logger.info("通过API获取板块历史趋势...")
            trend_response = requests.get(
                f"{self.api_base_url}/api/sector/fund-flow/trend/BK0001",
                params={"period": 30}
            )
            if trend_response.status_code == 200:
                trend_data = trend_response.json()
                count = trend_data.get('count', 0)
                logger.info(f"API获取 {count} 条历史趋势数据")
            else:
                logger.warning(f"⚠️ API获取历史趋势失败: {trend_response.status_code}")

            # 4. 导入数据
            logger.info("通过API导入板块历史数据...")
            import_payload = {
                "source": "akshare",
                "start_date": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
                "end_date": datetime.now().strftime("%Y-%m-%d")
            }
            import_response = requests.post(
                f"{self.api_base_url}/api/sector/fund-flow/import",
                json=import_payload
            )
            if import_response.status_code == 200:
                import_data = import_response.json()
                processed_count = import_data.get('processed_count', 0)
                logger.info(f"API导入 {processed_count} 条数据")
            else:
                logger.warning(f"⚠️ API导入数据失败: {import_response.status_code}")

        except requests.exceptions.ConnectionError:
            logger.error("❌ 无法连接到API服务器，请确保API服务已启动 (python api_server.py)")
        except Exception as e:
            logger.error(f"❌ API调用失败: {e}")

    def run_all_examples(self):
        """运行所有示例"""
        logger.info("开始运行板块资金流功能示例")
        logger.info("=" * 50)

        # 初始化
        if not self.initialize():
            logger.error("❌ 初始化失败，退出示例")
            return

        # 运行各个示例
        self.example_get_ranking()
        self.example_get_historical_trend()
        self.example_get_intraday_flow()
        self.example_import_historical_data()
        self.example_api_calls()

        logger.info("\n" + "=" * 50)
        logger.info("🎉 所有示例运行完成！")
        logger.info("\n提示:")
        logger.info("- 如果某些示例没有返回数据，可能是因为数据源暂时不可用或需要先导入历史数据")
        logger.info("- 要使用API功能，请先启动API服务: python api_server.py")
        logger.info("- 更多功能请参考README.md中的详细文档")

def main():
    """主函数"""
    example = SectorFundFlowExample()
    example.run_all_examples()

if __name__ == "__main__":
    # 配置日志格式
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )

    main()
