#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SimNow集成测试

测试SimNow配置模块和CTP接口集成功能
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger


class SimNowIntegrationTest:
    """SimNow集成测试"""
    
    def __init__(self):
        self.test_results = []
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 80)
        logger.info("开始SimNow集成测试")
        logger.info("=" * 80)
        
        # 测试SimNow配置模块
        results = []
        results.append(("测试SimNow配置模块导入", self.test_simnow_config_import()))
        results.append(("测试SimNow环境枚举", self.test_simnow_environment()))
        results.append(("测试SimNow配置类", self.test_simnow_config_class()))
        results.append(("测试SimNow账户创建工具", self.test_simnow_account_creator()))
        results.append(("测试SimNow环境信息", self.test_simnow_environment_info()))
        
        # 测试CTP行情接口
        results.append(("测试CTP行情接口导入", self.test_ctp_market_interface_import()))
        results.append(("测试CTP行情接口初始化", self.test_ctp_market_interface_init()))
        
        # 测试TradingService CTP支持
        results.append(("测试TradingService CTP支持", self.test_trading_service_ctp_support()))
        
        # 输出测试结果
        logger.info("\n" + "=" * 80)
        logger.info("测试结果汇总")
        logger.info("=" * 80)
        
        passed = 0
        failed = 0
        
        for test_name, result in results:
            status = "✓ 通过" if result else "✗ 失败"
            logger.info(f"{test_name}: {status}")
            
            if result:
                passed += 1
            else:
                failed += 1
        
        logger.info("=" * 80)
        logger.info(f"总计: {passed} 个通过, {failed} 个失败")
        logger.info("=" * 80)
        
        return failed == 0
    
    def test_simnow_config_import(self):
        """测试SimNow配置模块导入"""
        try:
            from core.trading.simnow_config import (
                SimNowEnvironment,
                SimNowConfig,
                SimNowAccountCreator,
                SimNowEnvironmentInfo
            )
            logger.info("✓ SimNow配置模块导入成功")
            return True
        except Exception as e:
            logger.error(f"✗ SimNow配置模块导入失败: {e}")
            return False
    
    def test_simnow_environment(self):
        """测试SimNow环境枚举"""
        try:
            from core.trading.simnow_config import SimNowEnvironment
            
            # 检查所有环境类型
            assert SimNowEnvironment.GROUP_1.value == "group_1"
            assert SimNowEnvironment.GROUP_2.value == "group_2"
            assert SimNowEnvironment.GROUP_3.value == "group_3"
            assert SimNowEnvironment.ENV_7X24.value == "env_7x24"
            
            logger.info("✓ SimNow环境枚举测试通过")
            return True
        except Exception as e:
            logger.error(f"✗ SimNow环境枚举测试失败: {e}")
            return False
    
    def test_simnow_config_class(self):
        """测试SimNow配置类"""
        try:
            from core.trading.simnow_config import SimNowConfig, SimNowEnvironment
            
            # 测试默认配置
            config = SimNowConfig()
            assert config.broker_id == "9999"
            assert config.app_id == "simnow_client_test"
            assert config.auth_code == "0000000000000000"
            
            # 测试环境切换
            config.set_environment(SimNowEnvironment.GROUP_1)
            assert config.trade_front == "tcp://180.168.146.187:10130"
            assert config.quote_front == "tcp://180.168.146.187:10131"
            
            config.set_environment(SimNowEnvironment.ENV_7X24)
            assert config.trade_front == "tcp://180.168.146.187:10201"
            assert config.quote_front == "tcp://180.168.146.187:10211"
            
            # 测试to_dict方法
            config_dict = config.to_dict()
            assert 'broker_id' in config_dict
            assert 'investor_id' in config_dict
            
            logger.info("✓ SimNow配置类测试通过")
            return True
        except Exception as e:
            logger.error(f"✗ SimNow配置类测试失败: {e}")
            return False
    
    def test_simnow_account_creator(self):
        """测试SimNow账户创建工具"""
        try:
            from core.trading.simnow_config import SimNowAccountCreator, SimNowEnvironment
            
            # 创建SimNow账户
            account = SimNowAccountCreator.create_simnow_account(
                investor_id="test_user",
                password="test_password",
                environment=SimNowEnvironment.GROUP_1,
                account_name="测试账户"
            )
            
            # 验证账户信息
            assert account.account_id == "simnow_test_user"
            assert account.account_name == "测试账户"
            assert account.account_type == "futures"
            assert account.balance == 20000000.0
            assert account.ctp_broker_id == "9999"
            assert account.ctp_investor_id == "test_user"
            assert account.ctp_password == "test_password"
            assert account.ctp_trade_front == "tcp://180.168.146.187:10130"
            assert account.ctp_quote_front == "tcp://180.168.146.187:10131"
            
            logger.info("✓ SimNow账户创建工具测试通过")
            return True
        except Exception as e:
            logger.error(f"✗ SimNow账户创建工具测试失败: {e}")
            return False
    
    def test_simnow_environment_info(self):
        """测试SimNow环境信息"""
        try:
            from core.trading.simnow_config import SimNowEnvironmentInfo, SimNowEnvironment
            
            # 获取环境信息
            info = SimNowEnvironmentInfo.get_environment_info(SimNowEnvironment.GROUP_1)
            
            assert 'name' in info
            assert 'description' in info
            assert 'trade_front' in info
            assert 'quote_front' in info
            assert info['name'] == "第一组（推荐）"
            
            # 获取所有环境信息
            all_info = SimNowEnvironmentInfo.get_all_environments_info()
            assert len(all_info) == 4
            
            logger.info("✓ SimNow环境信息测试通过")
            return True
        except Exception as e:
            logger.error(f"✗ SimNow环境信息测试失败: {e}")
            return False
    
    def test_ctp_market_interface_import(self):
        """测试CTP行情接口导入"""
        try:
            from core.trading.interfaces.ctp_market_interface import (
                CTPMarketInterface,
                CTPMarketData
            )
            logger.info("✓ CTP行情接口导入成功")
            return True
        except Exception as e:
            logger.error(f"✗ CTP行情接口导入失败: {e}")
            return False
    
    def test_ctp_market_interface_init(self):
        """测试CTP行情接口初始化"""
        try:
            from core.trading.interfaces.ctp_market_interface import CTPMarketInterface, CTP_AVAILABLE
            from core.trading.interfaces.ctp_config import CTPConfig
            
            config = CTPConfig(
                broker_id="9999",
                investor_id="test_user",
                password="test_password",
                quote_front="tcp://180.168.146.187:10131",
                use_simulation=True
            )
            
            market_interface = CTPMarketInterface(config)
            
            if not CTP_AVAILABLE:
                assert market_interface.connect() == False
                assert market_interface.login() == False
                logger.info("✓ CTP行情接口初始化测试通过（无CTP SDK，正确返回失败）")
                return True
            
            assert market_interface.connect() == True
            assert market_interface.login() == True
            assert market_interface.subscribe_quote(["au2506"]) == True
            
            market_interface.disconnect()
            assert market_interface._connected == False
            
            logger.info("✓ CTP行情接口初始化测试通过")
            return True
        except Exception as e:
            logger.error(f"✗ CTP行情接口初始化测试失败: {e}")
            return False
    
    def test_trading_service_ctp_support(self):
        """测试TradingService CTP支持"""
        try:
            from core.services.trading_service import TradingService
            
            # 创建TradingService实例
            trading_service = TradingService()
            
            # 检查CTP相关属性
            assert hasattr(trading_service, '_ctp_interfaces')
            assert hasattr(trading_service, '_ctp_market_interfaces')
            assert hasattr(trading_service, '_ctp_lock')
            
            # 检查CTP相关方法
            assert hasattr(trading_service, 'connect_ctp_account')
            assert hasattr(trading_service, 'disconnect_ctp_account')
            assert hasattr(trading_service, 'get_ctp_connection_status')
            assert hasattr(trading_service, 'subscribe_ctp_quote')
            assert hasattr(trading_service, 'get_ctp_quote')
            
            logger.info("✓ TradingService CTP支持测试通过")
            return True
        except Exception as e:
            logger.error(f"✗ TradingService CTP支持测试失败: {e}")
            return False


def main():
    """主函数"""
    test = SimNowIntegrationTest()
    success = test.run_all_tests()
    
    if success:
        logger.info("\n🎉 所有测试通过！SimNow集成成功！")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
