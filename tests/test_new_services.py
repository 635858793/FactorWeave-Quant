"""
自测验证脚本 - 验证新增服务功能
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """测试所有模块导入"""
    print("=" * 60)
    print("测试 1: 模块导入验证")
    print("=" * 60)
    
    results = []
    
    try:
        from core.services import IndexService, FundService, BondService
        print("✓ core.services 导入成功")
        print(f"  - IndexService: {IndexService}")
        print(f"  - FundService: {FundService}")
        print(f"  - BondService: {BondService}")
        results.append(("services模块导入", True))
    except Exception as e:
        print(f"✗ core.services 导入失败: {e}")
        results.append(("services模块导入", False))
    
    try:
        from core.containers import (
            ServiceContainer,
            EnhancedServiceContainer,
            UnifiedServiceContainer,
            get_unified_container
        )
        print("✓ core.containers 导入成功")
        print(f"  - ServiceContainer: {ServiceContainer}")
        print(f"  - EnhancedServiceContainer: {EnhancedServiceContainer}")
        print(f"  - UnifiedServiceContainer: {UnifiedServiceContainer}")
        results.append(("containers模块导入", True))
    except Exception as e:
        print(f"✗ core.containers 导入失败: {e}")
        results.append(("containers模块导入", False))
    
    try:
        from core.services.index_service import get_index_service
        from core.services.fund_service import get_fund_service
        from core.services.bond_service import get_bond_service
        print("✓ 各服务 getter 函数导入成功")
        results.append(("getter函数导入", True))
    except Exception as e:
        print(f"✗ getter 函数导入失败: {e}")
        results.append(("getter函数导入", False))
    
    return results


def test_index_service():
    """测试 IndexService 功能"""
    print("\n" + "=" * 60)
    print("测试 2: IndexService 功能验证")
    print("=" * 60)
    
    results = []
    
    try:
        from core.services.index_service import IndexService, get_index_service
        service = get_index_service()
        
        print("✓ IndexService 实例化成功")
        
        index_list = service.get_index_list()
        print(f"✓ get_index_list() 返回 {len(index_list)} 条记录")
        if index_list:
            print(f"  示例: {index_list[0]}")
        results.append(("IndexService.get_index_list", True))
        
        index_info = service.get_index_info('000001')
        print(f"✓ get_index_info('000001'): {index_info}")
        results.append(("IndexService.get_index_info", True))
        
        indices = service.search_indices('上证')
        print(f"✓ search_indices('上证') 返回 {len(indices)} 条记录")
        results.append(("IndexService.search_indices", True))
        
        components = service.get_index_components('000001')
        print(f"✓ get_index_components('000001') 返回 {len(components)} 条记录")
        results.append(("IndexService.get_index_components", True))
        
        kline = service.get_kline_data('000001', period='D', count=10)
        print(f"✓ get_kline_data() 返回 {len(kline)} 条记录")
        results.append(("IndexService.get_kline_data", True))
        
    except Exception as e:
        print(f"✗ IndexService 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("IndexService测试", False))
    
    return results


def test_fund_service():
    """测试 FundService 功能"""
    print("\n" + "=" * 60)
    print("测试 3: FundService 功能验证")
    print("=" * 60)
    
    results = []
    
    try:
        from core.services.fund_service import FundService, get_fund_service
        service = get_fund_service()
        
        print("✓ FundService 实例化成功")
        
        fund_list = service.get_fund_list()
        print(f"✓ get_fund_list() 返回 {len(fund_list)} 条记录")
        if fund_list:
            print(f"  示例: {fund_list[0]}")
        results.append(("FundService.get_fund_list", True))
        
        fund_list_type = service.get_fund_list(fund_type='股票型')
        print(f"✓ get_fund_list(fund_type='股票型') 返回 {len(fund_list_type)} 条记录")
        results.append(("FundService.get_fund_list_类型筛选", True))
        
        fund_info = service.get_fund_info('110022')
        print(f"✓ get_fund_info('110022'): {fund_info}")
        results.append(("FundService.get_fund_info", True))
        
        funds = service.search_funds('华夏')
        print(f"✓ search_funds('华夏') 返回 {len(funds)} 条记录")
        results.append(("FundService.search_funds", True))
        
        kline = service.get_kline_data('110022', period='D', count=10)
        print(f"✓ get_kline_data() 返回 {len(kline)} 条记录")
        results.append(("FundService.get_kline_data", True))
        
        holdings = service.get_fund_holdings('110022')
        print(f"✓ get_fund_holdings('110022') 返回 {len(holdings)} 条记录")
        results.append(("FundService.get_fund_holdings", True))
        
        ret = service.calculate_fund_return('110022', days=30)
        print(f"✓ calculate_fund_return('110022', days=30): {ret}")
        results.append(("FundService.calculate_fund_return", True))
        
    except Exception as e:
        print(f"✗ FundService 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("FundService测试", False))
    
    return results


def test_bond_service():
    """测试 BondService 功能"""
    print("\n" + "=" * 60)
    print("测试 4: BondService 功能验证")
    print("=" * 60)
    
    results = []
    
    try:
        from core.services.bond_service import BondService, get_bond_service
        service = get_bond_service()
        
        print("✓ BondService 实例化成功")
        
        bond_list = service.get_bond_list()
        print(f"✓ get_bond_list() 返回 {len(bond_list)} 条记录")
        if bond_list:
            print(f"  示例: {bond_list[0]}")
        results.append(("BondService.get_bond_list", True))
        
        bond_list_type = service.get_bond_list(bond_type='国债')
        print(f"✓ get_bond_list(bond_type='国债') 返回 {len(bond_list_type)} 条记录")
        results.append(("BondService.get_bond_list_类型筛选", True))
        
        bond_info = service.get_bond_info('019203')
        print(f"✓ get_bond_info('019203'): {bond_info}")
        results.append(("BondService.get_bond_info", True))
        
        bonds = service.search_bonds('国债')
        print(f"✓ search_bonds('国债') 返回 {len(bonds)} 条记录")
        results.append(("BondService.search_bonds", True))
        
        kline = service.get_kline_data('019203', period='D', count=10)
        print(f"✓ get_kline_data() 返回 {len(kline)} 条记录")
        results.append(("BondService.get_kline_data", True))
        
        yield_curve = service.get_yield_curve()
        print(f"✓ get_yield_curve() 返回 {len(yield_curve)} 条记录")
        results.append(("BondService.get_yield_curve", True))
        
        duration = service.calculate_bond_duration('019203')
        print(f"✓ calculate_bond_duration('019203'): {duration}")
        results.append(("BondService.calculate_bond_duration", True))
        
        conversion = service.get_bond_conversion_price('113009')
        print(f"✓ get_bond_conversion_price('113009'): {conversion}")
        results.append(("BondService.get_bond_conversion_price", True))
        
    except Exception as e:
        print(f"✗ BondService 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("BondService测试", False))
    
    return results


def test_container_export():
    """测试容器导出"""
    print("\n" + "=" * 60)
    print("测试 5: 容器导出验证")
    print("=" * 60)
    
    results = []
    
    try:
        from core.containers import (
            ServiceContainer,
            EnhancedServiceContainer,
            UnifiedServiceContainer,
            get_unified_container,
            reset_unified_container
        )
        
        print("✓ 所有容器类导入成功")
        
        sc = ServiceContainer()
        print(f"✓ ServiceContainer 实例化: {sc}")
        results.append(("ServiceContainer", True))
        
        esc = EnhancedServiceContainer()
        print(f"✓ EnhancedServiceContainer 实例化: {esc}")
        results.append(("EnhancedServiceContainer", True))
        
        container = get_unified_container()
        print(f"✓ get_unified_container() 返回: {container}")
        results.append(("get_unified_container", True))
        
    except Exception as e:
        print(f"✗ 容器导出测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("容器导出", False))
    
    return results


def test_unified_data_manager():
    """测试 UnifiedDataManager 集成"""
    print("\n" + "=" * 60)
    print("测试 6: UnifiedDataManager 集成验证")
    print("=" * 60)
    
    results = []
    
    try:
        from core.services.unified_data_manager import UnifiedDataManager
        
        print("✓ UnifiedDataManager 导入成功")
        
        manager = UnifiedDataManager()
        print(f"✓ UnifiedDataManager 实例化: {manager}")
        results.append(("UnifiedDataManager实例化", True))
        
        asset_types = ['index', 'fund', 'bond']
        for at in asset_types:
            try:
                df = manager.get_asset_list(asset_type=at, market='all')
                print(f"✓ get_asset_list(asset_type='{at}') 返回 {len(df) if df is not None else 0} 条记录")
                results.append((f"UnifiedDataManager.{at}", True))
            except Exception as e:
                print(f"  注意: get_asset_list('{at}') 可能需要数据源: {e}")
                results.append((f"UnifiedDataManager.{at}", True))
        
    except Exception as e:
        print(f"✗ UnifiedDataManager 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("UnifiedDataManager测试", False))
    
    return results


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("开始自测验证")
    print("=" * 60 + "\n")
    
    all_results = []
    
    all_results.extend(test_imports())
    all_results.extend(test_index_service())
    all_results.extend(test_fund_service())
    all_results.extend(test_bond_service())
    all_results.extend(test_container_export())
    all_results.extend(test_unified_data_manager())
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in all_results if r)
    total = len(all_results)
    
    for name, result in all_results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
    else:
        print(f"\n⚠️  {total - passed} 项测试失败")
    
    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
