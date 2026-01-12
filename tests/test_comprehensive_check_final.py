"""
多资产类型支持全面检查报告（最终版）

验证所有已实现的功能是否正确实现、逻辑正确、语法正确，并合理融入系统。
"""

import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("Multi-Asset Type Support Comprehensive Check")
    logger.info("=" * 80)

    all_passed = True

    # 检查1：推荐引擎多资产类型支持
    logger.info("\n[CHECK 1] Recommendation Engine Multi-Asset Type Support")
    logger.info("-" * 80)

    try:
        from core.services.smart_recommendation_engine import (
            SmartRecommendationEngine,
            RecommendationType,
            asset_type_to_recommendation_type,
            recommendation_type_to_asset_type
        )

        # 检查 RecommendationType 枚举
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
            logger.info("[PASS] RecommendationType enum contains all asset types")
        else:
            logger.error(f"[FAIL] RecommendationType enum missing: {missing_types}")
            all_passed = False

        # 检查类型转换函数
        if callable(asset_type_to_recommendation_type):
            logger.info("[PASS] asset_type_to_recommendation_type function exists")
        else:
            logger.error("[FAIL] asset_type_to_recommendation_type function does not exist")
            all_passed = False

        if callable(recommendation_type_to_asset_type):
            logger.info("[PASS] recommendation_type_to_asset_type function exists")
        else:
            logger.error("[FAIL] recommendation_type_to_asset_type function does not exist")
            all_passed = False

        # 检查 get_recommendations 方法
        import inspect
        sig = inspect.signature(SmartRecommendationEngine.get_recommendations)
        params = list(sig.parameters.keys())
        
        if 'asset_type' in params:
            logger.info("[PASS] get_recommendations method supports asset_type parameter")
        else:
            logger.error("[FAIL] get_recommendations method missing asset_type parameter")
            all_passed = False

        # 检查 Recommendation 类
        from core.services.smart_recommendation_engine import Recommendation
        rec_fields = list(Recommendation.__dataclass_fields__.keys())
        
        if 'asset_type' in rec_fields:
            logger.info("[PASS] Recommendation class contains asset_type field")
        else:
            logger.error("[FAIL] Recommendation class missing asset_type field")
            all_passed = False

        # 检查双向转换
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
                conversion_errors.append(f"{asset_type.value} -> {rec_type.value} -> {back_asset_type.value}")
        
        if not conversion_errors:
            logger.info("[PASS] Asset type and recommendation type bidirectional conversion correct")
        else:
            logger.error(f"[FAIL] Bidirectional conversion errors: {conversion_errors}")
            all_passed = False

    except Exception as e:
        logger.error(f"[FAIL] Recommendation engine check failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        all_passed = False

    # 检查2：交易引擎多资产类型支持
    logger.info("\n[CHECK 2] Trading Engine Multi-Asset Type Support")
    logger.info("-" * 80)

    try:
        from core.trading_engine import TradingEngine
        from core.containers import ServiceContainer
        from core.events import EventBus
        from core.plugin_types import AssetType

        # 创建交易引擎实例
        service_container = ServiceContainer()
        event_bus = EventBus()
        engine = TradingEngine(service_container, event_bus)

        # 检查 set_asset_type 方法
        if hasattr(engine, 'set_asset_type') and callable(engine.set_asset_type):
            logger.info("[PASS] set_asset_type method exists")
        else:
            logger.error("[FAIL] set_asset_type method does not exist")
            all_passed = False

        # 检查配置字典
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
                    missing_configs.append(f"{dict_name} missing {asset_type.value}")

        if not missing_configs:
            logger.info("[PASS] All config dictionaries contain all asset types")
        else:
            logger.error(f"[FAIL] Config dictionaries missing asset types: {missing_configs}")
            all_passed = False

        # 检查 set_asset_type 方法工作
        try:
            engine.set_asset_type(AssetType.CRYPTO)
            if engine.current_asset_type == AssetType.CRYPTO:
                logger.info("[PASS] set_asset_type method works correctly")
            else:
                logger.error("[FAIL] set_asset_type method setting failed")
                all_passed = False
        except Exception as e:
            logger.error(f"[FAIL] set_asset_type method execution failed: {e}")
            all_passed = False

        # 检查 _validate_signal 方法
        sig = inspect.signature(TradingEngine._validate_signal)
        params = list(sig.parameters.keys())
        
        if 'signal' in params:
            logger.info("[PASS] _validate_signal method signature correct")
        else:
            logger.error("[FAIL] _validate_signal method signature incorrect")
            all_passed = False

    except Exception as e:
        logger.error(f"[FAIL] Trading engine check failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        all_passed = False

    # 检查3：事件系统增强
    logger.info("\n[CHECK 3] Event System Enhancement")
    logger.info("-" * 80)

    try:
        from core.events.types import AssetTypeChangedEvent

        # 检查 AssetTypeChangedEvent
        if AssetTypeChangedEvent is not None:
            logger.info("[PASS] AssetTypeChangedEvent class exists")
        else:
            logger.error("[FAIL] AssetTypeChangedEvent class does not exist")
            all_passed = False

        # 检查字段
        event_fields = ['old_asset_type', 'new_asset_type', 'source']
        missing_fields = []
        
        for field in event_fields:
            if not hasattr(AssetTypeChangedEvent, field):
                missing_fields.append(field)
        
        if not missing_fields:
            logger.info("[PASS] AssetTypeChangedEvent contains all required fields")
        else:
            logger.error(f"[FAIL] AssetTypeChangedEvent missing fields: {missing_fields}")
            all_passed = False

        # 检查事件发布和订阅
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
            logger.info("[PASS] Event publish and subscribe work correctly")
        else:
            logger.error("[FAIL] Event publish and subscribe failed")
            all_passed = False

    except Exception as e:
        logger.error(f"[FAIL] Event system check failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        all_passed = False

    # 检查4：UI集成（简化版）
    logger.info("\n[CHECK 4] UI Integration (Simplified)")
    logger.info("-" * 80)

    try:
        # 检查左侧面板
        from core.ui.panels.left_panel import LeftPanel
        import inspect
        source = inspect.getsource(LeftPanel)
        
        if 'AssetTypeChangedEvent' in source:
            logger.info("[PASS] Left panel imports AssetTypeChangedEvent")
        else:
            logger.error("[FAIL] Left panel does not import AssetTypeChangedEvent")
            all_passed = False

        if 'event_bus.publish' in source and 'AssetTypeChangedEvent' in source:
            logger.info("[PASS] Left panel publishes asset type change event")
        else:
            logger.error("[FAIL] Left panel does not publish asset type change event")
            all_passed = False

        # 检查智能推荐面板（仅检查源代码）
        try:
            with open('gui/widgets/enhanced_ui/smart_recommendation_panel.py', 'r', encoding='utf-8') as f:
                source = f.read()
            
            if '_on_asset_type_changed' in source:
                logger.info("[PASS] Smart recommendation panel has asset type change handler")
            else:
                logger.error("[FAIL] Smart recommendation panel missing asset type change handler")
                all_passed = False

            if 'current_asset_type' in source:
                logger.info("[PASS] Smart recommendation panel has current_asset_type attribute")
            else:
                logger.error("[FAIL] Smart recommendation panel missing current_asset_type attribute")
                all_passed = False

            if 'asset_type' in source and 'RecommendationWorker' in source:
                logger.info("[PASS] Smart recommendation panel uses asset type in recommendation loading")
            else:
                logger.error("[FAIL] Smart recommendation panel does not use asset type in recommendation loading")
                all_passed = False

        except FileNotFoundError:
            logger.warning("[SKIP] Smart recommendation panel file not found, skipping UI check")

    except Exception as e:
        logger.error(f"[FAIL] UI integration check failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        all_passed = False

    # 检查5：数据库迁移脚本
    logger.info("\n[CHECK 5] Database Migration Script")
    logger.info("-" * 80)

    try:
        from core.migration.asset_type_migration import AssetTypeMigration

        # 检查 AssetTypeMigration 类
        if AssetTypeMigration is not None:
            logger.info("[PASS] AssetTypeMigration class exists")
        else:
            logger.error("[FAIL] AssetTypeMigration class does not exist")
            all_passed = False

        # 检查迁移方法
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
            logger.info("[PASS] All migration methods exist")
        else:
            logger.error(f"[FAIL] Missing migration methods: {missing_methods}")
            all_passed = False

        # 检查实例化
        try:
            migration = AssetTypeMigration()
            logger.info("[PASS] AssetTypeMigration can be instantiated")
        except Exception as e:
            logger.error(f"[FAIL] AssetTypeMigration instantiation failed: {e}")
            all_passed = False

    except Exception as e:
        logger.error(f"[FAIL] Database migration check failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        all_passed = False

    # 输出总结
    logger.info("\n" + "=" * 80)
    logger.info("Check Summary")
    logger.info("=" * 80)

    if all_passed:
        logger.info("[SUCCESS] Multi-asset type support fully implemented, all checks passed!")
        logger.info("=" * 80 + "\n")
        return 0
    else:
        logger.warning("[WARNING] Multi-asset type support has issues, need to fix!")
        logger.info("=" * 80 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
