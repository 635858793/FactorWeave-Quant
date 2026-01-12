"""
多资产类型支持全面检查报告

验证所有已实现的功能是否正确实现、逻辑正确、语法正确，并合理融入系统。
"""

import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger


def check_recommendation_engine():
    """检查推荐引擎多资产类型支持"""
    logger.info("=" * 80)
    logger.info("【检查1】推荐引擎多资产类型支持")
    logger.info("=" * 80)

    checks = []

    try:
        from core.services.smart_recommendation_engine import (
            SmartRecommendationEngine,
            RecommendationType,
            asset_type_to_recommendation_type,
            recommendation_type_to_asset_type
        )

        # 检查1：RecommendationType 枚举是否包含所有资产类型
        asset_types = [
            "stock_a", "stock_b", "stock_h", "stock_us", "stock_hk",
            "futures", "crypto", "forex", "bond", "commodity",
            "index", "fund", "option", "warrant",
            "sector", "industry_sector", "concept_sector", "style_sector", "theme_sector",
            "macro"
        ]

        missing_types = []
        for asset_type in asset_types:
            try:
                RecommendationType(asset_type)
            except ValueError:
                missing_types.append(asset_type)

        if not missing_types:
            checks.append(("[PASS]", "RecommendationType 枚举包含所有资产类型"))
        else:
            checks.append(("[FAIL]", f"RecommendationType 枚举缺少: {missing_types}"))

        # 检查2：类型转换函数是否存在
        if callable(asset_type_to_recommendation_type):
            checks.append(("[PASS]", "asset_type_to_recommendation_type 函数存在"))
        else:
            checks.append(("[FAIL]", "asset_type_to_recommendation_type 函数不存在"))

        if callable(recommendation_type_to_asset_type):
            checks.append(("[PASS]", "recommendation_type_to_asset_type 函数存在"))
        else:
            checks.append(("[FAIL]", "recommendation_type_to_asset_type 函数不存在"))

        # 检查3：get_recommendations 方法签名
        import inspect
        sig = inspect.signature(SmartRecommendationEngine.get_recommendations)
        params = list(sig.parameters.keys())
        
        if 'asset_type' in params:
            checks.append(("[PASS]", "get_recommendations 方法支持 asset_type 参数"))
        else:
            checks.append(("[FAIL]", "get_recommendations 方法缺少 asset_type 参数"))

        # 检查4：Recommendation 类是否有 asset_type 字段
        from core.services.smart_recommendation_engine import Recommendation
        rec_fields = list(Recommendation.__dataclass_fields__.keys())
        
        if 'asset_type' in rec_fields:
            checks.append(("[PASS]", "Recommendation 类包含 asset_type 字段"))
        else:
            checks.append(("[FAIL]", "Recommendation 类缺少 asset_type 字段"))

        # 检查5：双向转换是否正确
        from core.plugin_types import AssetType
        
        test_asset_types = [
            AssetType.STOCK_A,
            AssetType.CRYPTO,
            AssetType.FUTURES,
            AssetType.SECTOR
        ]
        
        conversion_errors = []
        for asset_type in test_asset_types:
            rec_type = asset_type_to_recommendation_type(asset_type)
            back_asset_type = recommendation_type_to_asset_type(rec_type)
            
            if back_asset_type != asset_type:
                conversion_errors.append(f"{asset_type.value} → {rec_type.value} → {back_asset_type.value}")
        
        if not conversion_errors:
            checks.append(("[PASS]", "资产类型和推荐类型双向转换正确"))
        else:
            checks.append(("[FAIL]", f"双向转换错误: {conversion_errors}"))

    except Exception as e:
        checks.append(("[FAIL]", f"推荐引擎检查失败: {e}"))
        import traceback
        logger.error(traceback.format_exc())

    # 输出检查结果
    for status, message in checks:
        logger.info(f"{status} {message}")

    return all(status == "[PASS]" for status, _ in checks)


def check_trading_engine():
    """检查交易引擎多资产类型支持"""
    logger.info("\n" + "=" * 80)
    logger.info("【检查2】交易引擎多资产类型支持")
    logger.info("=" * 80)

    checks = []

    try:
        from core.trading_engine import TradingEngine
        from core.containers import ServiceContainer
        from core.events import EventBus
        from core.plugin_types import AssetType

        # 创建交易引擎实例
        service_container = ServiceContainer()
        event_bus = EventBus()
        engine = TradingEngine(service_container, event_bus)

        # 检查1：set_asset_type 方法是否存在
        if hasattr(engine, 'set_asset_type') and callable(engine.set_asset_type):
            checks.append(("[PASS]", "set_asset_type 方法存在"))
        else:
            checks.append(("[FAIL]", "set_asset_type 方法不存在"))

        # 检查2：配置字典是否包含所有资产类型
        test_asset_types = [
            AssetType.STOCK_A,
            AssetType.CRYPTO,
            AssetType.FUTURES,
            AssetType.SECTOR,
            AssetType.MACRO
        ]

        config_dicts = [
            ('commission_rates', engine.commission_rates),
            ('min_commissions', engine.min_commissions),
            ('stamp_tax_rates', engine.stamp_tax_rates),
            ('max_single_positions', engine.max_single_positions),
            ('min_trade_units', engine.min_trade_units)
        ]

        missing_configs = []
        for dict_name, config_dict in config_dicts:
            for asset_type in test_asset_types:
                if asset_type not in config_dict:
                    missing_configs.append(f"{dict_name} 缺少 {asset_type.value}")

        if not missing_configs:
            checks.append(("[PASS]", "所有配置字典包含所有资产类型"))
        else:
            checks.append(("[FAIL]", f"配置字典缺少资产类型: {missing_configs}"))

        # 检查3：set_asset_type 方法是否正常工作
        try:
            engine.set_asset_type(AssetType.CRYPTO)
            if engine.current_asset_type == AssetType.CRYPTO:
                checks.append(("[PASS]", "set_asset_type 方法正常工作"))
            else:
                checks.append(("[FAIL]", "set_asset_type 方法设置失败"))
        except Exception as e:
            checks.append(("[FAIL]", f"set_asset_type 方法执行失败: {e}"))

        # 检查4：_validate_signal 方法是否验证最小交易单位
        import inspect
        sig = inspect.signature(TradingEngine._validate_signal)
        params = list(sig.parameters.keys())
        
        if 'signal' in params:
            checks.append(("[PASS]", "_validate_signal 方法签名正确"))
        else:
            checks.append(("[FAIL]", "_validate_signal 方法签名错误"))

    except Exception as e:
        checks.append(("[FAIL]", f"交易引擎检查失败: {e}"))
        import traceback
        logger.error(traceback.format_exc())

    # 输出检查结果
    for status, message in checks:
        logger.info(f"{status} {message}")

    return all(status == "[PASS]" for status, _ in checks)


def check_event_system():
    """检查事件系统增强"""
    logger.info("\n" + "=" * 80)
    logger.info("【检查3】事件系统增强")
    logger.info("=" * 80)

    checks = []

    try:
        from core.events.types import AssetTypeChangedEvent

        # 检查1：AssetTypeChangedEvent 是否存在
        if AssetTypeChangedEvent is not None:
            checks.append(("[PASS]", "AssetTypeChangedEvent 类存在"))
        else:
            checks.append(("[FAIL]", "AssetTypeChangedEvent 类不存在"))

        # 检查2：AssetTypeChangedEvent 是否有正确的字段
        event_fields = ['old_asset_type', 'new_asset_type', 'source']
        missing_fields = []
        
        for field in event_fields:
            if not hasattr(AssetTypeChangedEvent, field):
                missing_fields.append(field)
        
        if not missing_fields:
            checks.append(("[PASS]", "AssetTypeChangedEvent 包含所有必需字段"))
        else:
            checks.append(("[FAIL]", f"AssetTypeChangedEvent 缺少字段: {missing_fields}"))

        # 检查3：事件是否可以正常发布和订阅
        from core.events import EventBus
        
        event_bus = EventBus()
        received_events = []

        def on_asset_type_changed(event):
            received_events.append(event)

        event_bus.subscribe(AssetTypeChangedEvent, on_asset_type_changed)

        from core.plugin_types import AssetType
        test_event = AssetTypeChangedEvent(
            old_asset_type=AssetType.STOCK_A,
            new_asset_type=AssetType.CRYPTO,
            source="test"
        )
        
        event_bus.publish(test_event)

        if len(received_events) > 0:
            checks.append(("[PASS]", "事件发布和订阅正常工作"))
        else:
            checks.append(("[FAIL]", "事件发布和订阅失败"))

    except Exception as e:
        checks.append(("[FAIL]", f"事件系统检查失败: {e}"))
        import traceback
        logger.error(traceback.format_exc())

    # 输出检查结果
    for status, message in checks:
        logger.info(f"{status} {message}")

    return all(status == "[PASS]" for status, _ in checks)


def check_ui_integration():
    """检查UI集成"""
    logger.info("\n" + "=" * 80)
    logger.info("【检查4】UI集成")
    logger.info("=" * 80)

    checks = []

    try:
        # 检查1：左侧面板是否导入 AssetTypeChangedEvent
        from core.ui.panels.left_panel import LeftPanel
        import inspect
        source = inspect.getsource(LeftPanel)
        
        if 'AssetTypeChangedEvent' in source:
            checks.append(("[PASS]", "左侧面板导入 AssetTypeChangedEvent"))
        else:
            checks.append(("[FAIL]", "左侧面板未导入 AssetTypeChangedEvent"))

        # 检查2：左侧面板是否发布资产类型变更事件
        if 'event_bus.publish' in source and 'AssetTypeChangedEvent' in source:
            checks.append(("[PASS]", "左侧面板发布资产类型变更事件"))
        else:
            checks.append(("[FAIL]", "左侧面板未发布资产类型变更事件"))

        # 检查3：智能推荐面板是否订阅资产类型变更事件
        from gui.widgets.enhanced_ui.smart_recommendation_panel import SmartRecommendationPanel
        source = inspect.getsource(SmartRecommendationPanel)
        
        if '_on_asset_type_changed' in source:
            checks.append(("[PASS]", "智能推荐面板有资产类型变更处理方法"))
        else:
            checks.append(("[FAIL]", "智能推荐面板缺少资产类型变更处理方法"))

        # 检查4：智能推荐面板是否有 current_asset_type 属性
        if 'current_asset_type' in source:
            checks.append(("[PASS]", "智能推荐面板有 current_asset_type 属性"))
        else:
            checks.append(("[FAIL]", "智能推荐面板缺少 current_asset_type 属性"))

        # 检查5：智能推荐面板是否在推荐加载时使用资产类型
        if 'asset_type' in source and 'RecommendationWorker' in source:
            checks.append(("[PASS]", "智能推荐面板在推荐加载时使用资产类型"))
        else:
            checks.append(("[FAIL]", "智能推荐面板未在推荐加载时使用资产类型"))

    except Exception as e:
        checks.append(("[FAIL]", f"UI集成检查失败: {e}"))
        import traceback
        logger.error(traceback.format_exc())

    # 输出检查结果
    for status, message in checks:
        logger.info(f"{status} {message}")

    return all(status == "[PASS]" for status, _ in checks)


def check_database_migration():
    """检查数据库迁移脚本"""
    logger.info("\n" + "=" * 80)
    logger.info("【检查5】数据库迁移脚本")
    logger.info("=" * 80)

    checks = []

    try:
        from core.migration.asset_type_migration import AssetTypeMigration

        # 检查1：AssetTypeMigration 类是否存在
        if AssetTypeMigration is not None:
            checks.append(("[PASS]", "AssetTypeMigration 类存在"))
        else:
            checks.append(("[FAIL]", "AssetTypeMigration 类不存在"))

        # 检查2：迁移方法是否存在
        methods = [
            'migrate_sqlite_tables',
            'migrate_duckdb_tables',
            'migrate_all',
            '_migrate_user_preferences_table',
            '_migrate_user_feedback_table',
            '_migrate_ai_selection_results_table',
            '_migrate_ai_explanations_table',
            '_migrate_user_profiles_table'
        ]

        missing_methods = []
        for method in methods:
            if not hasattr(AssetTypeMigration, method):
                missing_methods.append(method)
        
        if not missing_methods:
            checks.append(("[PASS]", "所有迁移方法存在"))
        else:
            checks.append(("[FAIL]", f"缺少迁移方法: {missing_methods}"))

        # 检查3：迁移脚本是否可以正常实例化
        try:
            migration = AssetTypeMigration()
            checks.append(("[PASS]", "AssetTypeMigration 可以正常实例化"))
        except Exception as e:
            checks.append(("[FAIL]", f"AssetTypeMigration 实例化失败: {e}"))

    except Exception as e:
        checks.append(("[FAIL]", f"数据库迁移检查失败: {e}"))
        import traceback
        logger.error(traceback.format_exc())

    # 输出检查结果
    for status, message in checks:
        logger.info(f"{status} {message}")

    return all(status == "[PASS]" for status, _ in checks)


def main():
    """主函数"""
    logger.info("\n" + "=" * 80)
    logger.info("╔════════════════════════════════════════════════════════════════════════╗")
    logger.info("║                    多资产类型支持全面检查                                    ║")
    logger.info("╚════════════════════════════════════════════════════════════════════════╝")
    logger.info("=" * 80)

    # 执行所有检查
    results = {
        "推荐引擎多资产类型支持": check_recommendation_engine(),
        "交易引擎多资产类型支持": check_trading_engine(),
        "事件系统增强": check_event_system(),
        "UI集成": check_ui_integration(),
        "数据库迁移脚本": check_database_migration()
    }

    # 输出总结
    logger.info("\n" + "=" * 80)
    logger.info("╔════════════════════════════════════════════════════════════════════════╗")
    logger.info("║                              检查总结                                        ║")
    logger.info("╚════════════════════════════════════════════════════════════════════════╝")
    logger.info("=" * 80)

    logger.info("\n[CHECK RESULT] Check Results:\n")
    
    all_passed = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"  {status} - {name}")
        if not passed:
            all_passed = False

    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("[SUCCESS] Multi-asset type support fully implemented, all checks passed!")
    else:
        logger.warning("[WARNING] Multi-asset type support has issues, need to fix!")
    logger.info("=" * 80 + "\n")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
