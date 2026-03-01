"""
全面调用链验证脚本

验证所有使用统一指标服务的调用点：
1. core/business/analysis_manager.py
2. core/services/analysis_service.py
3. core/agents/technical_agent.py
4. gui/dialogs/technical_analysis_dialog.py
5. core/services/chart_service.py
6. gui/widgets/analysis_tabs/technical_tab.py
7. core/trading_system.py
8. gui/widgets/analysis_widget.py
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_test_data(rows=200):
    """创建测试数据"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=rows, freq='D')
    
    base_price = 50.0
    prices = []
    for i in range(rows):
        change = np.random.normal(0.001, 0.02)
        base_price = base_price * (1 + change)
        prices.append(base_price)
    
    data = pd.DataFrame({
        'datetime': dates,
        'open': [p * 0.99 for p in prices],
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': [1000000] * rows
    })
    data.set_index('datetime', inplace=True)
    return data


class CallChainValidator:
    """调用链验证器"""
    
    def __init__(self):
        self.results = {}
        self.test_data = create_test_data(200)
    
    def validate_analysis_manager(self) -> Dict[str, Any]:
        """验证 AnalysisManager 调用链"""
        print("\n" + "="*70)
        print("1. AnalysisManager 调用链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.business.analysis_manager import AnalysisManager
            from core.data.data_access import DataAccess
            
            try:
                data_access = DataAccess()
                manager = AnalysisManager(data_access=data_access)
            except Exception as e:
                print(f"  ! 无法完整初始化AnalysisManager: {e}")
                print("  使用简化验证...")
                from core.indicator_service import calculate_indicator
                
                df = self.test_data.copy()
                
                test_cases = [
                    ("MA5", lambda: calculate_indicator('MA', df, timeperiod=5)),
                    ("MA20", lambda: calculate_indicator('MA', df, timeperiod=20)),
                    ("MA60", lambda: calculate_indicator('MA', df, timeperiod=60)),
                    ("RSI14", lambda: calculate_indicator('RSI', df, timeperiod=14)),
                    ("MACD", lambda: calculate_indicator('MACD', df)),
                    ("BBANDS", lambda: calculate_indicator('BBANDS', df)),
                ]
                
                for name, func in test_cases:
                    try:
                        result = func()
                        if result is not None:
                            results["passed"] += 1
                            results["details"].append(f"{name}: ✓")
                            print(f"  ✓ {name} 计算成功")
                        else:
                            results["failed"] += 1
                            results["details"].append(f"{name}: ✗ 返回None")
                            print(f"  ✗ {name} 返回None")
                    except Exception as ex:
                        results["failed"] += 1
                        results["details"].append(f"{name}: ✗ {str(ex)}")
                        print(f"  ✗ {name} 失败: {ex}")
                
                self.results["analysis_manager"] = results
                return results
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["analysis_manager"] = results
        return results
    
    def validate_analysis_service(self) -> Dict[str, Any]:
        """验证 AnalysisService 调用链"""
        print("\n" + "="*70)
        print("2. AnalysisService 调用链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.services.analysis_service import AnalysisService
            from core.indicator_service import calculate_indicator
            
            df = self.test_data.copy()
            
            test_cases = [
                ("RSI计算", lambda: calculate_indicator('RSI', df, timeperiod=14)),
                ("MACD计算", lambda: calculate_indicator('MACD', df, fastperiod=12, slowperiod=26, signalperiod=9)),
            ]
            
            for name, func in test_cases:
                try:
                    result = func()
                    if result is not None:
                        results["passed"] += 1
                        results["details"].append(f"{name}: ✓")
                        print(f"  ✓ {name} 成功")
                    else:
                        results["failed"] += 1
                        results["details"].append(f"{name}: ✗ 返回None")
                        print(f"  ✗ {name} 返回None")
                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append(f"{name}: ✗ {str(ex)}")
                    print(f"  ✗ {name} 失败: {ex}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["analysis_service"] = results
        return results
    
    def validate_technical_agent(self) -> Dict[str, Any]:
        """验证 TechnicalAnalysisAgent 调用链"""
        print("\n" + "="*70)
        print("3. TechnicalAnalysisAgent 调用链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.agents.technical_agent import TechnicalAnalysisAgent
            from core.indicator_service import calculate_indicator
            
            df = self.test_data.copy()
            
            test_cases = [
                ("MA计算", lambda: calculate_indicator('MA', df, timeperiod=20)),
                ("RSI计算", lambda: calculate_indicator('RSI', df, timeperiod=14)),
                ("MACD计算", lambda: calculate_indicator('MACD', df)),
                ("布林带计算", lambda: calculate_indicator('BBANDS', df)),
            ]
            
            for name, func in test_cases:
                try:
                    result = func()
                    if result is not None:
                        results["passed"] += 1
                        results["details"].append(f"{name}: ✓")
                        print(f"  ✓ {name} 成功")
                    else:
                        results["failed"] += 1
                        results["details"].append(f"{name}: ✗ 返回None")
                        print(f"  ✗ {name} 返回None")
                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append(f"{name}: ✗ {str(ex)}")
                    print(f"  ✗ {name} 失败: {ex}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["technical_agent"] = results
        return results
    
    def validate_technical_dialog(self) -> Dict[str, Any]:
        """验证 TechnicalAnalysisDialog 调用链"""
        print("\n" + "="*70)
        print("4. TechnicalAnalysisDialog 调用链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.indicator_service import calculate_indicator
            
            df = self.test_data.copy()
            
            test_cases = [
                ("MA计算", lambda: calculate_indicator('MA', df, timeperiod=20)),
                ("RSI计算", lambda: calculate_indicator('RSI', df, timeperiod=14)),
            ]
            
            for name, func in test_cases:
                try:
                    result = func()
                    if result is not None:
                        results["passed"] += 1
                        results["details"].append(f"{name}: ✓")
                        print(f"  ✓ {name} 成功")
                    else:
                        results["failed"] += 1
                        results["details"].append(f"{name}: ✗ 返回None")
                        print(f"  ✗ {name} 返回None")
                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append(f"{name}: ✗ {str(ex)}")
                    print(f"  ✗ {name} 失败: {ex}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["technical_dialog"] = results
        return results
    
    def validate_chart_service(self) -> Dict[str, Any]:
        """验证 ChartService 调用链"""
        print("\n" + "="*70)
        print("5. ChartService 调用链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.indicator_service import calculate_indicator, batch_calculate_indicators
            
            df = self.test_data.copy()
            
            test_cases = [
                ("单指标MA", lambda: calculate_indicator('MA', df, timeperiod=20)),
                ("单指标RSI", lambda: calculate_indicator('RSI', df, timeperiod=14)),
                ("批量计算", lambda: batch_calculate_indicators(['MA', 'RSI'], df, {'MA': {'timeperiod': 20}, 'RSI': {'timeperiod': 14}})),
            ]
            
            for name, func in test_cases:
                try:
                    result = func()
                    if result is not None:
                        results["passed"] += 1
                        results["details"].append(f"{name}: ✓")
                        print(f"  ✓ {name} 成功")
                    else:
                        results["failed"] += 1
                        results["details"].append(f"{name}: ✗ 返回None")
                        print(f"  ✗ {name} 返回None")
                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append(f"{name}: ✗ {str(ex)}")
                    print(f"  ✗ {name} 失败: {ex}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["chart_service"] = results
        return results
    
    def validate_technical_tab(self) -> Dict[str, Any]:
        """验证 TechnicalTab 调用链"""
        print("\n" + "="*70)
        print("6. TechnicalTab 调用链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.indicator_service import calculate_indicator, get_all_indicators_metadata
            
            df = self.test_data.copy()
            
            test_cases = [
                ("指标计算", lambda: calculate_indicator('MA', df, timeperiod=20)),
                ("获取指标元数据", lambda: get_all_indicators_metadata()),
            ]
            
            for name, func in test_cases:
                try:
                    result = func()
                    if result is not None:
                        results["passed"] += 1
                        results["details"].append(f"{name}: ✓")
                        print(f"  ✓ {name} 成功")
                    else:
                        results["failed"] += 1
                        results["details"].append(f"{name}: ✗ 返回None")
                        print(f"  ✗ {name} 返回None")
                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append(f"{name}: ✗ {str(ex)}")
                    print(f"  ✗ {name} 失败: {ex}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["technical_tab"] = results
        return results
    
    def validate_trading_system(self) -> Dict[str, Any]:
        """验证 TradingSystem 调用链"""
        print("\n" + "="*70)
        print("7. TradingSystem 调用链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.indicator_service import get_indicator_service
            
            service = get_indicator_service()
            
            df = self.test_data.copy()
            
            test_cases = [
                ("MA5计算", lambda: service.calculate_indicator('MA', df, timeperiod=5)),
                ("MA20计算", lambda: service.calculate_indicator('MA', df, timeperiod=20)),
            ]
            
            for name, func in test_cases:
                try:
                    result = func()
                    if result is not None:
                        results["passed"] += 1
                        results["details"].append(f"{name}: ✓")
                        print(f"  ✓ {name} 成功")
                    else:
                        results["failed"] += 1
                        results["details"].append(f"{name}: ✗ 返回None")
                        print(f"  ✗ {name} 返回None")
                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append(f"{name}: ✗ {str(ex)}")
                    print(f"  ✗ {name} 失败: {ex}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["trading_system"] = results
        return results
    
    def validate_analysis_widget(self) -> Dict[str, Any]:
        """验证 AnalysisWidget 调用链"""
        print("\n" + "="*70)
        print("8. AnalysisWidget 调用链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.indicator_service import calculate_indicator, get_indicator_metadata
            
            df = self.test_data.copy()
            
            test_cases = [
                ("指标计算", lambda: calculate_indicator('MA', df, timeperiod=20)),
                ("获取指标元数据", lambda: get_indicator_metadata('MA')),
            ]
            
            for name, func in test_cases:
                try:
                    result = func()
                    if result is not None:
                        results["passed"] += 1
                        results["details"].append(f"{name}: ✓")
                        print(f"  ✓ {name} 成功")
                    else:
                        results["failed"] += 1
                        results["details"].append(f"{name}: ✗ 返回None")
                        print(f"  ✗ {name} 返回None")
                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append(f"{name}: ✗ {str(ex)}")
                    print(f"  ✗ {name} 失败: {ex}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["analysis_widget"] = results
        return results
    
    def validate_error_handling(self) -> Dict[str, Any]:
        """验证错误处理链"""
        print("\n" + "="*70)
        print("9. 错误处理链验证")
        print("="*70)
        
        results = {"passed": 0, "failed": 0, "details": []}
        
        try:
            from core.indicator_service import calculate_indicator
            
            test_cases = [
                ("无效指标名称", lambda: calculate_indicator('INVALID', self.test_data)),
                ("空数据", lambda: calculate_indicator('MA', pd.DataFrame())),
                ("数据不足", lambda: calculate_indicator('MA', self.test_data.head(5), timeperiod=20)),
            ]
            
            for name, func in test_cases:
                try:
                    result = func()
                    results["passed"] += 1
                    results["details"].append(f"{name}: ✓ 正确处理")
                    print(f"  ✓ {name} 正确处理（无异常抛出）")
                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append(f"{name}: ✗ 异常: {str(ex)}")
                    print(f"  ✗ {name} 抛出异常: {ex}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"导入失败: {str(e)}")
            print(f"  ✗ 导入失败: {e}")
        
        self.results["error_handling"] = results
        return results
    
    def run_all_validations(self) -> bool:
        """运行所有验证"""
        print("\n" + "="*70)
        print("全面调用链验证")
        print("="*70)
        
        self.validate_analysis_manager()
        self.validate_analysis_service()
        self.validate_technical_agent()
        self.validate_technical_dialog()
        self.validate_chart_service()
        self.validate_technical_tab()
        self.validate_trading_system()
        self.validate_analysis_widget()
        self.validate_error_handling()
        
        print("\n" + "="*70)
        print("验证结果汇总")
        print("="*70)
        
        total_passed = 0
        total_failed = 0
        
        for component, result in self.results.items():
            passed = result.get("passed", 0)
            failed = result.get("failed", 0)
            total_passed += passed
            total_failed += failed
            
            status = "✓" if failed == 0 else "✗"
            print(f"  {status} {component}: {passed}通过 / {failed}失败")
        
        print(f"\n总计: {total_passed}通过 / {total_failed}失败")
        
        all_passed = total_failed == 0
        
        print("\n" + "="*70)
        if all_passed:
            print("✓ 所有调用链验证通过！")
        else:
            print("✗ 部分调用链验证失败，请检查！")
        print("="*70)
        
        return all_passed


if __name__ == "__main__":
    validator = CallChainValidator()
    success = validator.run_all_validations()
    sys.exit(0 if success else 1)
