from loguru import logger
"""
服务引导模块

负责在应用程序启动时按正确的顺序注册和初始化所有服务。
"""

import time
from typing import Optional, Set, Type
import traceback
import pandas as pd
from threading import Lock

# 先导入容器和事件总线
from core.containers import ServiceContainer, get_service_container
from core.containers.service_registry import ServiceScope
from core.events import EventBus, get_event_bus

# 然后导入服务类型
from core.services.config_service import ConfigService
from core.services.extension_service import ExtensionService
from core.services.cache_service import CacheService
from core.services.database_service import DatabaseService
from core.services.stock_service import StockService
from core.services.chart_service import ChartService
from core.services.analysis_service import AnalysisService
from core.services.industry_service import IndustryService
from core.services.ai_prediction_service import AIPredictionService
from core.services.unified_data_manager import UnifiedDataManager
from core.plugin_manager import PluginManager
from core.services.uni_plugin_data_manager import UniPluginDataManager

# 增量下载相关服务
from core.services.data_completeness_checker import DataCompletenessChecker
from core.services.incremental_data_analyzer import IncrementalDataAnalyzer
from core.services.incremental_update_recorder import IncrementalUpdateRecorder
from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
# # from core.services.error_service import LoguruErrorService  # 暂时注释，让系统先启动

# 最后导入监控服务
from core.metrics.repository import MetricsRepository
from core.metrics.resource_service import SystemResourceService
from core.metrics.app_metrics_service import ApplicationMetricsService, initialize_app_metrics_service
from core.metrics.aggregation_service import MetricsAggregationService

# 策略相关服务
from core.strategy.strategy_dependency_manager import StrategyDependencyManager
from core.strategy.strategy_hot_reloader import StrategyHotReloader
from core.strategy.strategy_registry import StrategyRegistry
from core.strategy.strategy_factory import StrategyFactory
from core.strategy.strategy_engine import StrategyEngine

# 插件相关服务
from core.plugin_hot_reloader import PluginHotReloader
from core.plugin_version_manager import PluginVersionManager

# 交易相关服务
from core.trading.order_service import OrderService
from core.trading.order_validator import OrderValidator
from core.trading.order_executor import OrderExecutor
from core.trading.order_repository import OrderRepository
from core.trading.order_monitor import OrderMonitor
from core.trading.order_analyzer import OrderAnalyzer
from core.trading.account_manager import AccountManager
from core.trading.account_repository import AccountRepository

from core.services.task_scheduler import TaskScheduler

# 通知服务
from core.services.notification_service import NotificationService, init_notification_service


class ServiceBootstrap:
    """
    服务引导类

    负责在应用程序启动时按正确的顺序注册和初始化所有服务。
    包含初始化防护机制，防止重复服务创建。
    """

    # 类级别的初始化跟踪
    _initialized_services: Set[Type] = set()
    _registration_attempts: dict = {}
    _initialization_lock = Lock()

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """
        初始化服务引导器

        Args:
            service_container: 服务容器，如果为None则使用全局容器
        """
        self.service_container = service_container or get_service_container()
        self.event_bus = get_event_bus()

        # 实例级别的跟踪
        self._instance_registered_services: Set[Type] = set()
        self._duplicate_attempts = 0

    def _is_service_registered(self, service_type: Type) -> bool:
        """检查服务是否已注册"""
        return service_type in self._instance_registered_services or self.service_container.is_registered(service_type)

    def _mark_service_registered(self, service_type: Type):
        """标记服务已注册"""
        self._instance_registered_services.add(service_type)
        logger.debug(f"服务已标记为已注册: {service_type.__name__}")

    def _safe_register_service(self, service_type: Type, implementation=None, scope=ServiceScope.SINGLETON, name="") -> bool:
        """
        安全注册服务，包含重复检测和防护

        Args:
            service_type: 服务类型
            implementation: 服务实现
            scope: 服务作用域
            name: 服务名称

        Returns:
            是否成功注册（False表示已存在或注册失败）
        """
        with self._initialization_lock:
            service_name = name or service_type.__name__

            # 检查是否已在容器中注册
            if self.service_container.is_registered(service_type):
                self._duplicate_attempts += 1

                # 记录重复注册尝试
                if service_type not in self._registration_attempts:
                    self._registration_attempts[service_type] = 0
                self._registration_attempts[service_type] += 1

                logger.warning(
                    f"Service {service_name} already registered in container. "
                    f"Duplicate attempt #{self._registration_attempts[service_type]}. "
                    f"Stack trace: {traceback.format_stack()[-3:-1]}"
                )
                return False

            # 检查是否已在类级别跟踪中
            if service_type in self._initialized_services:
                self._duplicate_attempts += 1
                logger.warning(
                    f"Service {service_name} already in initialized services list. "
                    f"Skipping registration."
                )
                return False

            # 检查是否已在实例级别跟踪中
            if service_type in self._instance_registered_services:
                self._duplicate_attempts += 1
                logger.warning(
                    f"Service {service_name} already registered in this bootstrap instance. "
                    f"Skipping registration."
                )
                return False

            try:
                # 执行实际注册
                if implementation:
                    self.service_container.register(service_type, implementation, scope, name)
                else:
                    self.service_container.register(service_type, scope=scope, name=name)

                # 记录成功注册
                self._initialized_services.add(service_type)
                self._instance_registered_services.add(service_type)

                logger.info(f"Service {service_name} registered successfully")
                return True

            except Exception as e:
                logger.error(
                    f"[ERROR] Failed to register service {service_name}: {e}\n"
                    f"Stack trace: {traceback.format_exc()}"
                )
                return False

    def bootstrap(self) -> bool:
        """
        引导所有服务

        Returns:
            引导是否成功
        """
        try:
            logger.info("[BOOTSTRAP] Starting service bootstrap with duplicate detection...")

            # 1. 注册核心服务
            self._register_core_services()

            # 2. 注册业务服务（包含UnifiedDataManager）
            self._register_business_services()

            # 2.5. 注册增量下载服务（在业务服务之后，插件服务之前）
            self._register_incremental_services()

            # 3. 注册插件服务（在UnifiedDataManager之后）
            self._register_plugin_services()

            # 4. 注册交易服务
            self._register_trading_services()

            # 5. 注册监控服务
            self._register_monitoring_services()

            # 6. 注册高级服务（GPU加速等）
            self._register_advanced_services()

            # 7. 执行插件发现和注册（在所有服务注册完成后）
            self._post_initialization_plugin_discovery()

            # 8. 输出重复检测报告
            self._report_duplicate_attempts()

            logger.info("Service bootstrap completed successfully")
            return True
        except Exception as e:
            logger.error(f"[ERROR] 服务引导失败: {e}")
            logger.error(traceback.format_exc())
            raise  # 重新抛出异常，让调用方知道服务引导失败

    def _report_duplicate_attempts(self) -> None:
        """报告重复初始化尝试统计"""
        if self._duplicate_attempts > 0 or self._registration_attempts:
            logger.warning(f"Duplicate Registration Detection Report:")
            logger.warning(f"   Total duplicate attempts prevented: {self._duplicate_attempts}")

            if self._registration_attempts:
                logger.warning(f"   Services with multiple registration attempts:")
                for service_type, count in self._registration_attempts.items():
                    logger.warning(f"     - {service_type.__name__}: {count} attempts")

            logger.warning(f"   Successfully registered services: {len(self._instance_registered_services)}")
        else:
            logger.info("[INFO] No duplicate service registration attempts detected")

    def _register_core_services(self) -> None:
        """注册核心服务"""
        logger.info("注册核心服务...")

        # 注册事件总线 (EventBus)
        self.service_container.register_instance(EventBus, self.event_bus)
        # 确保也注册具体类型，以便能够通过类型注入
        self.service_container.register_instance(
            type(self.event_bus), self.event_bus)
        logger.info("事件总线注册完成")

        # 注册统一配置服务
        config_service = ConfigService(config_file='config/config.json', use_sqlite=True)
        config_service.initialize()
        self.service_container.register_instance(ConfigService, config_service)
        # 也按名称注册，方便通过名称访问
        self.service_container.register_instance(ConfigService, config_service, name='config_service')

        # 为了兼容性，也注册为ConfigManager类型
        from utils.config_manager import ConfigManager
        self.service_container.register_instance(ConfigManager, config_service)
        logger.info("统一配置服务注册完成（类型 + 名称 'config_service'）")

        # 注册扩展服务 (ExtensionService)
        extension_service = ExtensionService()
        extension_service.initialize()
        self.service_container.register_instance(ExtensionService, extension_service)
        logger.info("扩展服务注册完成")

        # 注册缓存服务 (CacheService)
        if not self._is_service_registered(CacheService):
            self.service_container.register(
                CacheService,
                scope=ServiceScope.SINGLETON,
                factory=lambda: CacheService(service_container=self.service_container)
            )
            cache_service = self.service_container.resolve(CacheService)
            cache_service.initialize()
            logger.info("缓存服务注册完成")

        # 日志服务现在由纯Loguru系统全局管理，无需注册到容器
        # log_manager = LogManager()
        # self.service_container.register_instance(LogManager, log_manager)
        logger.info("纯Loguru日志系统已全局可用")

        # 注册基于Loguru的错误处理服务 (暂时注释)
        # error_service = LoguruErrorService()
        # self.service_container.register_instance(LoguruErrorService, error_service)
        logger.info("Loguru日志系统运行正常，错误处理集成待完善")

    def _register_business_services(self) -> None:
        """注册业务服务"""
        logger.info("注册业务服务...")

        # 添加依赖检查
        self._check_dependencies()

        # 先注册DataSourceRouter（TET模式依赖）
        logger.info("注册数据源路由器...")
        try:
            from ..data_source_router import DataSourceRouter
            self.service_container.register_factory(
                DataSourceRouter,
                lambda: DataSourceRouter(),
                scope=ServiceScope.SINGLETON
            )
            router = self.service_container.resolve(DataSourceRouter)
            logger.info("数据源路由器注册完成")
        except Exception as e:
            logger.warning(f" 数据源路由器注册失败: {e}")

        # 注册数据库服务（在其他业务服务之前）
        logger.info("注册数据库服务...")
        try:
            if not self._is_service_registered(DatabaseService):
                self.service_container.register(
                    DatabaseService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: DatabaseService(
                        service_container=self.service_container
                    )
                )
            database_service = self.service_container.resolve(DatabaseService)
            database_service.initialize()
            logger.info("数据库服务注册完成")
        except Exception as e:
            logger.error(f"❌ 数据库服务注册失败: {e}")
            logger.error(traceback.format_exc())
            raise  # 数据库服务是核心服务，必须成功注册

        # 然后注册UnifiedDataManager（使用安全注册）
        if not self._safe_register_service(
            UnifiedDataManager,
            lambda: UnifiedDataManager(self.service_container, self.event_bus),
            ServiceScope.SINGLETON
        ):
            logger.warning("UnifiedDataManager already registered, skipping...")

        # 延迟初始化模式 - 不要立即解析以避免触发构造函数初始化

        # 安全注册完成，进行备份检查
        try:
            # 验证注册是否成功
            if self.service_container.is_registered(UnifiedDataManager):
                logger.info("UnifiedDataManager registration verified")

            logger.info("统一数据管理器注册完成（延迟初始化模式）")

        except Exception as e:

            logger.error(f"Failed to initialize UnifiedDataManager: {e}")

            # 提供回退机制

            self._initialize_fallback_data_manager()

        #  股票服务 - 使用工厂方法传递服务容器（延迟初始化）
        self.service_container.register_factory(
            StockService,
            lambda: StockService(service_container=self.service_container),
            scope=ServiceScope.SINGLETON
        )
        # 注意：StockService的初始化将在分阶段初始化中进行，以确保UnifiedDataManager已经初始化
        logger.info("股票服务注册完成（延迟初始化）")

        # 图表服务

        if not self._is_service_registered(ChartService):
            self.service_container.register(
                ChartService, scope=ServiceScope.SINGLETON)
        chart_service = self.service_container.resolve(ChartService)
        chart_service.initialize()
        logger.info("图表服务注册完成")

        # WebGPU图表渲染器
        try:
            from optimization.webgpu_chart_renderer import get_webgpu_chart_renderer, WebGPUChartRenderer
            webgpu_renderer = get_webgpu_chart_renderer()
            self.service_container.register_instance(
                WebGPUChartRenderer, webgpu_renderer)
            logger.info("WebGPU图表渲染器注册完成")
        except ImportError as e:
            logger.warning(f"WebGPU图表渲染器不可用: {e}")
        except Exception as e:
            logger.error(f"WebGPU图表渲染器注册失败: {e}")

        # 分析服务

        if not self._is_service_registered(AnalysisService):
            self.service_container.register(
                AnalysisService, scope=ServiceScope.SINGLETON)
        analysis_service = self.service_container.resolve(AnalysisService)
        analysis_service.initialize()
        logger.info("分析服务注册完成")

        # 行业服务
        try:

            if not self._is_service_registered(IndustryService):
                self.service_container.register(
                    IndustryService, scope=ServiceScope.SINGLETON)
            industry_service = self.service_container.resolve(IndustryService)
            industry_service.initialize()
            logger.info("行业服务注册完成")
        except Exception as e:
            logger.error(f" 行业服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # AI预测服务
        try:

            if not self._is_service_registered(AIPredictionService):
                self.service_container.register(
                    AIPredictionService, scope=ServiceScope.SINGLETON)
            ai_prediction_service = self.service_container.resolve(AIPredictionService)
            logger.info("AI预测服务注册完成")
        except Exception as e:
            logger.error(f" AI预测服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 增强指标服务
        try:
            from .enhanced_indicator_service import EnhancedIndicatorService
            if not self._is_service_registered(EnhancedIndicatorService):
                self.service_container.register(
                    EnhancedIndicatorService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: EnhancedIndicatorService()
                )
            enhanced_indicator_service = self.service_container.resolve(EnhancedIndicatorService)
            if hasattr(enhanced_indicator_service, 'initialize'):
                enhanced_indicator_service.initialize()
            logger.info("增强指标服务注册完成")
        except Exception as e:
            logger.error(f"❌ 增强指标服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 注册智能推荐引擎
        try:
            from .smart_recommendation_engine import SmartRecommendationEngine
            if not self._is_service_registered(SmartRecommendationEngine):
                self.service_container.register(
                    SmartRecommendationEngine,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: SmartRecommendationEngine(database_service=self.service_container.resolve(DatabaseService))
                )
            smart_recommendation_engine = self.service_container.resolve(SmartRecommendationEngine)
            logger.info("智能推荐引擎注册完成")
        except Exception as e:
            logger.error(f"❌ 智能推荐引擎注册失败: {e}")
            logger.error(traceback.format_exc())

        # AI可解释性服务（必须在RecommendationExplanationGenerator之前注册）
        try:
            from .ai_explainability_service import AIExplainabilityService
            if not self._is_service_registered(AIExplainabilityService):
                self.service_container.register(
                    AIExplainabilityService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: AIExplainabilityService(
                        service_container=self.service_container
                    )
                )
            ai_explainability_service = self.service_container.resolve(AIExplainabilityService)
            if hasattr(ai_explainability_service, 'initialize'):
                ai_explainability_service.initialize()
            logger.info("AI可解释性服务注册完成")
        except Exception as e:
            logger.error(f"❌ AI可解释性服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 注册推荐理由生成器
        try:
            from .recommendation_explanation_generator import RecommendationExplanationGenerator
            if not self._is_service_registered(RecommendationExplanationGenerator):
                self.service_container.register(
                    RecommendationExplanationGenerator,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: RecommendationExplanationGenerator()
                )
            logger.info("推荐理由生成器注册完成")
        except Exception as e:
            logger.error(f"❌ 推荐理由生成器注册失败: {e}")
            logger.error(traceback.format_exc())

        # 注册持续学习管理器
        try:
            from core.ai.continuous_learning_manager import ContinuousLearningManager
            if not self._is_service_registered(ContinuousLearningManager):
                self.service_container.register(
                    ContinuousLearningManager,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: ContinuousLearningManager()
                )
            logger.info("持续学习管理器注册完成")
        except Exception as e:
            logger.error(f"❌ 持续学习管理器注册失败: {e}")
            logger.error(traceback.format_exc())

        # 注册推荐模型训练器
        try:
            from .recommendation_model_trainer import RecommendationModelTrainer
            if not self._is_service_registered(RecommendationModelTrainer):
                self.service_container.register(
                    RecommendationModelTrainer,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: RecommendationModelTrainer(
                        recommendation_engine=self.service_container.resolve(SmartRecommendationEngine),
                        continuous_learning_manager=self.service_container.resolve(ContinuousLearningManager),
                        database_service=self.service_container.resolve(DatabaseService)
                    )
                )
            logger.info("推荐模型训练器注册完成")
        except Exception as e:
            logger.error(f"❌ 推荐模型训练器注册失败: {e}")
            logger.error(traceback.format_exc())

        # 在所有推荐相关服务注册完成后，设置推荐理由生成器到推荐引擎
        try:
            if self.service_container.is_registered(SmartRecommendationEngine) and self.service_container.is_registered(RecommendationExplanationGenerator):
                smart_recommendation_engine = self.service_container.resolve(SmartRecommendationEngine)
                explanation_generator = self.service_container.resolve(RecommendationExplanationGenerator)
                smart_recommendation_engine.set_explanation_generator(explanation_generator)
                logger.info("推荐理由生成器已设置到推荐引擎")
        except Exception as e:
            logger.error(f"❌ 设置推荐理由生成器到推荐引擎失败: {e}")
            logger.error(traceback.format_exc())

        # LLM配置服务（必须在AISelectionIntegrationService之前注册）
        try:
            from .llm_config_service import LLMConfigService
            if not self._is_service_registered(LLMConfigService):
                self.service_container.register(
                    LLMConfigService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: LLMConfigService(
                        config={},
                        event_bus=self.event_bus
                    )
                )
            llm_config_service = self.service_container.resolve(LLMConfigService)
            if hasattr(llm_config_service, 'initialize'):
                llm_config_service.initialize()
            logger.info("LLM配置服务注册完成")
        except Exception as e:
            logger.error(f"❌ LLM配置服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # AI选股集成服务
        try:
            from .ai_selection_integration_service import AISelectionIntegrationService
            if not self._is_service_registered(AISelectionIntegrationService):
                self.service_container.register(
                    AISelectionIntegrationService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: AISelectionIntegrationService(
                        service_container=self.service_container
                    )
                )
            ai_selection_service = self.service_container.resolve(AISelectionIntegrationService)
            if hasattr(ai_selection_service, 'initialize'):
                ai_selection_service.initialize()
            logger.info("AI选股集成服务注册完成")
        except Exception as e:
            logger.error(f"❌ AI选股集成服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # AI选股回测服务
        try:
            from .ai_selection_backtest_service import AISelectionBacktestService
            if not self._is_service_registered(AISelectionBacktestService):
                self.service_container.register(
                    AISelectionBacktestService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: AISelectionBacktestService(
                        database_service=self.service_container.resolve(DatabaseService),
                        ai_selection_service=self.service_container.resolve(AISelectionIntegrationService),
                        personalization_engine=None  # 将通过后续步骤注入
                    )
                )
            ai_backtest_service = self.service_container.resolve(AISelectionBacktestService)
            if hasattr(ai_backtest_service, 'initialize'):
                ai_backtest_service.initialize()
            logger.info("AI选股回测服务注册完成")
        except Exception as e:
            logger.error(f"❌ AI选股回测服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 回测结果管理器
        try:
            from ..services.backtest_result_manager import BacktestResultManager
            if not self._is_service_registered(BacktestResultManager):
                self.service_container.register(
                    BacktestResultManager,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: BacktestResultManager()
                )
            backtest_result_manager = self.service_container.resolve(BacktestResultManager)
            logger.info("回测结果管理器注册完成")
        except Exception as e:
            logger.error(f"❌ 回测结果管理器注册失败: {e}")
            logger.error(traceback.format_exc())

        # AI选股风险控制服务
        try:
            from .ai_selection_risk_control_service import AISelectionRiskControlService
            if not self._is_service_registered(AISelectionRiskControlService):
                self.service_container.register(
                    AISelectionRiskControlService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: AISelectionRiskControlService(
                        database_service=self.service_container.resolve(DatabaseService),
                        ai_selection_service=self.service_container.resolve(AISelectionIntegrationService),
                        ai_backtest_service=self.service_container.resolve(AISelectionBacktestService),
                        personalization_engine=None,  # 将通过后续步骤注入
                        indicator_service=self.service_container.resolve(EnhancedIndicatorService),
                        risk_control_level='standard'  # 默认风险控制级别
                    )
                )
            ai_risk_control_service = self.service_container.resolve(AISelectionRiskControlService)
            if hasattr(ai_risk_control_service, 'initialize'):
                ai_risk_control_service.initialize()
            logger.info("AI选股风险控制服务注册完成")
        except Exception as e:
            logger.error(f"❌ AI选股风险控制服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 注册混合推荐引擎
        try:
            from .hybrid_recommendation_engine import HybridRecommendationEngine
            if not self._is_service_registered(HybridRecommendationEngine):
                self.service_container.register(
                    HybridRecommendationEngine,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: HybridRecommendationEngine(event_bus=self.event_bus)
                )
            hybrid_recommendation_engine = self.service_container.resolve(HybridRecommendationEngine)
            # 初始化混合推荐引擎
            if hasattr(hybrid_recommendation_engine, 'initialize'):
                hybrid_recommendation_engine.initialize()
            logger.info("混合推荐引擎注册完成")
        except Exception as e:
            logger.error(f"❌ 混合推荐引擎注册失败: {e}")
            logger.error(traceback.format_exc())

        # 模型训练服务
        try:
            from .model_training_service import ModelTrainingService
            if not self._is_service_registered(ModelTrainingService):
                self.service_container.register(
                    ModelTrainingService, scope=ServiceScope.SINGLETON)
            model_training_service = self.service_container.resolve(ModelTrainingService)
            model_training_service.initialize()
            logger.info("模型训练服务注册完成")
        except Exception as e:
            logger.error(f" 模型训练服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 预测跟踪服务
        try:
            from .prediction_tracking_service import PredictionTrackingService
            if not self._is_service_registered(PredictionTrackingService):
                self.service_container.register(
                    PredictionTrackingService, scope=ServiceScope.SINGLETON)
            prediction_tracking_service = self.service_container.resolve(PredictionTrackingService)
            prediction_tracking_service.initialize()
            logger.info("预测跟踪服务注册完成")
        except Exception as e:
            logger.error(f" 预测跟踪服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 资产服务（多资产类型支持）
        try:
            from .asset_service import AssetService
            self.service_container.register_factory(
                AssetService,
                lambda: AssetService(
                    unified_data_manager=self.service_container.resolve(UnifiedDataManager),
                    stock_service=self.service_container.resolve(StockService),
                    service_container=self.service_container
                ),
                scope=ServiceScope.SINGLETON
            )
            asset_service = self.service_container.resolve(AssetService)
            logger.info("资产服务注册完成")
        except Exception as e:
            logger.error(f" 资产服务注册失败: {e}")
            logger.error(traceback.format_exc())

            # 情绪数据服务和K线情绪分析服务已删除（被热点分析功能取代）
            # 相关文件已清理：sentiment_data_service.py、kline_sentiment_analyzer.py
            # 相关UI组件已删除：enhanced_kline_sentiment_tab.py、sentiment_overview_widget.py
            logger.debug("情绪数据服务和K线情绪分析服务已移除（功能已整合到热点分析）")

            # 板块资金流服务
        try:
            logger.info("开始注册板块资金流服务...")
            from .sector_fund_flow_service import SectorFundFlowService, SectorFlowConfig
            logger.info("板块资金流服务模块导入成功")

            # 创建配置
            logger.info("创建板块资金流服务配置...")
            sector_config = SectorFlowConfig(
                cache_duration_minutes=5,
                auto_refresh_interval_minutes=10,
                enable_auto_refresh=True
            )
            logger.info("板块资金流服务配置创建完成")

            def create_sector_flow_service():
                logger.info("开始创建板块资金流服务实例...")
                start_time = time.time()

                # 获取数据管理器
                logger.info("尝试获取统一数据管理器...")
                data_manager = None
                try:
                    if self.service_container.is_registered(UnifiedDataManager):
                        data_manager = self.service_container.resolve(UnifiedDataManager)
                        logger.info("统一数据管理器获取成功")
                    else:
                        logger.warning("统一数据管理器未注册")
                except Exception as e:
                    logger.warning(f" 统一数据管理器获取失败: {e}")

                # 创建服务
                logger.info("创建板块资金流服务实例...")
                service = SectorFundFlowService(
                    data_manager=data_manager,
                    config=sector_config
                )

                end_time = time.time()
                logger.info(f" 板块资金流服务实例创建完成，耗时: {(end_time - start_time):.2f}秒")
                return service

            # 注册服务工厂
            self.service_container.register_factory(
                SectorFundFlowService,
                create_sector_flow_service,
                scope=ServiceScope.SINGLETON
            )

            logger.info("板块资金流服务注册完成")
        except Exception as e:
            logger.error(f" 板块资金流服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 外部告警渠道服务
        try:
            from .external_alert_channels_service import ExternalAlertManager, get_alert_manager
            if not self._is_service_registered(ExternalAlertManager):
                self.service_container.register(
                    ExternalAlertManager,
                    scope=ServiceScope.SINGLETON,
                    factory=get_alert_manager
                )
            logger.info("外部告警渠道服务注册完成")
        except Exception as e:
            logger.error(f"❌ 外部告警渠道服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 在分阶段初始化之前，先注册PluginManager和UniPluginDataManager
        self._register_plugin_manager_early()
        self._register_uni_plugin_data_manager()

        # 分阶段初始化服务
        self._initialize_services_in_order()

    def _initialize_services_in_order(self):
        """按正确顺序初始化服务，避免循环依赖"""
        logger.info("开始分阶段初始化服务...")

        try:
            # 阶段1: 初始化插件管理器
            if self.service_container.is_registered(PluginManager):
                plugin_manager = self.service_container.resolve(PluginManager)
                if hasattr(plugin_manager, 'initialize'):
                    plugin_manager.initialize()
                logger.info("插件管理器初始化完成")

            # 阶段2: 初始化UniPluginDataManager
            if self.service_container.is_registered(UniPluginDataManager):
                uni_plugin_manager = self.service_container.resolve(UniPluginDataManager)
                if hasattr(uni_plugin_manager, 'initialize'):
                    uni_plugin_manager.initialize()
                logger.info("UniPluginDataManager初始化完成")

            # 阶段3: 初始化UnifiedDataManager
            if self.service_container.is_registered(UnifiedDataManager):
                unified_manager = self.service_container.resolve(UnifiedDataManager)
                if hasattr(unified_manager, 'initialize'):
                    unified_manager.initialize()
                logger.info("UnifiedDataManager初始化完成")

            # 阶段4: 初始化依赖UnifiedDataManager的服务
            from core.services.stock_service import StockService
            if self.service_container.is_registered(StockService):
                stock_service = self.service_container.resolve(StockService)
                if hasattr(stock_service, 'initialize'):
                    stock_service.initialize()
                logger.info("StockService初始化完成")

            # 阶段5: 初始化AI选股相关服务
            try:
                from core.services.ai_selection_integration_service import AISelectionIntegrationService
                if self.service_container.is_registered(AISelectionIntegrationService):
                    ai_selection_service = self.service_container.resolve(AISelectionIntegrationService)
                    if hasattr(ai_selection_service, 'initialize'):
                        ai_selection_service.initialize()
                    logger.info("AISelectionIntegrationService初始化完成")
            except ImportError as e:
                logger.warning(f"AISelectionIntegrationService未找到: {e}")
            except Exception as e:
                logger.error(f"AISelectionIntegrationService初始化失败: {e}")

            try:
                from core.services.ai_explainability_service import AIExplainabilityService
                if self.service_container.is_registered(AIExplainabilityService):
                    ai_explain_service = self.service_container.resolve(AIExplainabilityService)
                    if hasattr(ai_explain_service, 'initialize') and not ai_explain_service.initialized:
                        ai_explain_service.initialize()
                    logger.info("AIExplainabilityService初始化完成")
            except ImportError as e:
                logger.warning(f"AIExplainabilityService未找到: {e}")
            except Exception as e:
                logger.error(f"AIExplainabilityService初始化失败: {e}")

            try:
                from core.services.ai_selection_backtest_service import AISelectionBacktestService
                if self.service_container.is_registered(AISelectionBacktestService):
                    ai_backtest_service = self.service_container.resolve(AISelectionBacktestService)
                    if hasattr(ai_backtest_service, 'initialize'):
                        ai_backtest_service.initialize()
                    logger.info("AISelectionBacktestService初始化完成")
            except ImportError as e:
                logger.warning(f"AISelectionBacktestService未找到: {e}")
            except Exception as e:
                logger.error(f"AISelectionBacktestService初始化失败: {e}")

            logger.info("分阶段初始化完成")

        except Exception as e:
            logger.error(f"[ERROR] 分阶段初始化失败: {e}")
            raise

    def _check_dependencies(self):
        """检查UnifiedDataManager的依赖项"""
        from .config_service import ConfigService

        dependencies = {
            'config_service': ConfigService
        }

        for dep_name, dep_class in dependencies.items():
            try:
                # 尝试解析依赖服务
                self.service_container.resolve(dep_class)
                logger.debug(f"Dependency {dep_name} is available")
            except Exception as e:
                logger.warning(
                    f"Dependency {dep_name} not available for UnifiedDataManager: {e}")

    def _initialize_fallback_data_manager(self):
        """初始化失败时的回退策略"""
        logger.info("Initializing fallback data manager")
        try:
            # 尝试使用UnifiedDataManager作为回退
            fallback_manager = UnifiedDataManager()
            self.service_container.register_instance(
                type(fallback_manager), fallback_manager, name='unified_data_manager')
            logger.info("回退数据管理器注册完成")
        except Exception as e:
            logger.error(f"Failed to initialize fallback data manager: {e}")
            # 创建最小可用的数据管理器

            # 使用UnifiedDataManager作为最终回退
            minimal_manager = UnifiedDataManager()
            self.service_container.register_instance(
                type(minimal_manager), minimal_manager, name='unified_data_manager')
            logger.warning("最小数据管理器注册完成 - 功能受限")

    def _register_monitoring_services(self) -> None:
        """注册监控服务"""
        logger.info("注册监控服务...")

        try:
            # 1. 注册数据库仓储
            self.service_container.register(
                MetricsRepository, scope=ServiceScope.SINGLETON)
            logger.info("指标数据库仓储(MetricsRepository)注册完成")

            # 2. 初始化并注册应用性能度量服务
            app_metrics_service = initialize_app_metrics_service(
                self.event_bus)
            self.service_container.register_instance(
                ApplicationMetricsService, app_metrics_service)
            logger.info("应用性能度量服务(ApplicationMetricsService)初始化完成")

            # 3. 注册系统资源服务
            # 确保直接传递事件总线实例，而不是通过容器解析
            self.service_container.register_factory(
                SystemResourceService,
                lambda: SystemResourceService(self.event_bus)
            )
            resource_service = self.service_container.resolve(
                SystemResourceService)
            resource_service.start()
            logger.info("系统资源服务(SystemResourceService)启动完成")

            # 4. 注册指标聚合服务
            # 同样使用工厂函数直接传递事件总线
            self.service_container.register_factory(
                MetricsAggregationService,
                lambda: MetricsAggregationService(
                    self.event_bus, self.service_container.resolve(MetricsRepository))
            )
            aggregation_service = self.service_container.resolve(
                MetricsAggregationService)
            aggregation_service.start()
            logger.info("指标聚合服务(MetricsAggregationService)启动完成")

            # 5. 新增：注册性能数据桥接器
            try:
                from core.services.performance_data_bridge import initialize_performance_bridge, PerformanceDataBridge
                performance_bridge = initialize_performance_bridge(auto_start=True)
                self.service_container.register_instance(
                    PerformanceDataBridge, performance_bridge)
                logger.info("性能数据桥接器(PerformanceDataBridge)初始化完成")
            except Exception as e:
                logger.error(f"性能数据桥接器初始化失败: {e}")

            #  新增：注册告警事件处理器
            try:
                from core.services.alert_event_handler import register_alert_handlers
                register_alert_handlers(self.event_bus)
                logger.info("告警事件处理器注册完成")
            except Exception as e:
                logger.error(f" 告警事件处理器注册失败: {e}")
                logger.error(traceback.format_exc())

            #  新增：确保告警数据库已初始化
            try:
                from db.models.alert_config_models import get_alert_config_database
                alert_db = get_alert_config_database()
                logger.info("告警数据库初始化完成")
            except Exception as e:
                logger.error(f" 告警数据库初始化失败: {e}")
                logger.error(traceback.format_exc())

            #  新增：注册告警去重服务
            try:
                from .alert_deduplication_service import AlertDeduplicationService, initialize_alert_deduplication_service
                self.service_container.register(
                    AlertDeduplicationService,
                    scope=ServiceScope.SINGLETON
                )

                # 自动初始化告警去重服务
                dedup_service = initialize_alert_deduplication_service()
                logger.info("告警去重服务注册并初始化完成")
            except Exception as e:
                logger.error(f" 告警去重服务注册失败: {e}")
                logger.error(traceback.format_exc())

            #  新增：注册并启动告警规则引擎服务
            try:
                from .alert_rule_engine import AlertRuleEngine, initialize_alert_rule_engine

                # 使用工厂函数注册 AlertRuleEngine，确保依赖注入正确
                if not self._is_service_registered(AlertRuleEngine):
                    self.service_container.register(
                        AlertRuleEngine,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: initialize_alert_rule_engine(
                            self.event_bus,
                            self.service_container.try_resolve(AlertDeduplicationService)
                        )
                    )

                # 自动启动告警引擎
                alert_engine = self.service_container.resolve(AlertRuleEngine)
                alert_engine.start()
                logger.info("告警规则引擎服务注册并启动完成")
            except Exception as e:
                logger.error(f" 告警规则引擎服务注册失败: {e}")

            #  新增：注册并启动告警规则热加载服务
            try:
                from .alert_rule_hot_loader import AlertRuleHotLoader, initialize_alert_rule_hot_loader
                self.service_container.register(
                    AlertRuleHotLoader,
                    scope=ServiceScope.SINGLETON
                )

                # 自动初始化并启动热加载服务
                hot_loader = initialize_alert_rule_hot_loader(check_interval=5)
                hot_loader.start()

                # 将引擎作为热加载回调
                try:
                    dedup_service = self.service_container.try_resolve(AlertDeduplicationService)
                    alert_engine = initialize_alert_rule_engine(self.event_bus, dedup_service)
                    hot_loader.add_update_callback(alert_engine.reload_rules_sync)
                    logger.info("告警引擎与热加载服务关联完成")
                except:
                    pass

                logger.info("告警规则热加载服务注册并启动完成")
            except Exception as e:
                logger.error(f" 告警规则热加载服务注册失败: {e}")

        except Exception as e:
            logger.error(f" 监控服务注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_incremental_services(self) -> None:
        """注册增量下载相关服务"""
        logger.info("注册增量下载服务...")

        try:
            # 获取必要的依赖服务
            uni_plugin_manager = self.service_container.resolve(UniPluginDataManager)
            unified_data_manager = self.service_container.resolve(UnifiedDataManager)
            event_bus = self.event_bus

            # 1. 注册数据完整性检查器
            logger.info("注册数据完整性检查器...")
            from ..services.data_completeness_checker import DataCompletenessChecker
            completeness_checker = DataCompletenessChecker(
                db_manager=unified_data_manager.duckdb_manager,
                event_bus=event_bus,
                db_path="data/factorweave_system.sqlite"
            )
            self.service_container.register_instance(
                DataCompletenessChecker,
                completeness_checker
            )
            logger.info("数据完整性检查器注册完成")

            # 2. 注册增量数据分析仪
            logger.info("注册增量数据分析仪...")
            from ..services.incremental_data_analyzer import IncrementalDataAnalyzer
            incremental_analyzer = IncrementalDataAnalyzer(
                db_manager=unified_data_manager.duckdb_manager,
                event_bus=event_bus,
                completeness_checker=completeness_checker
            )
            self.service_container.register_instance(
                IncrementalDataAnalyzer,
                incremental_analyzer
            )
            logger.info("增量数据分析仪注册完成")

            # 3. 注册增量更新记录器
            logger.info("注册增量更新记录器...")
            from ..services.incremental_update_recorder import IncrementalUpdateRecorder
            update_recorder = IncrementalUpdateRecorder(
                db_manager=unified_data_manager.duckdb_manager,
                event_bus=event_bus,
                db_path="data/factorweave_system.sqlite"
            )
            self.service_container.register_instance(
                IncrementalUpdateRecorder,
                update_recorder
            )
            logger.info("增量更新记录器注册完成")

            # 4. 注册增强的DuckDB数据下载器
            logger.info("注册增强的DuckDB数据下载器...")
            from ..services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
            enhanced_downloader = EnhancedDuckDBDataDownloader(
                uni_plugin_manager=uni_plugin_manager,
                tet_pipeline=unified_data_manager.tet_pipeline,
                data_source_router=unified_data_manager.data_source_router,
                incremental_analyzer=incremental_analyzer,
                completeness_checker=completeness_checker,
                update_recorder=update_recorder
            )
            self.service_container.register_instance(
                EnhancedDuckDBDataDownloader,
                enhanced_downloader
            )
            logger.info("增强的DuckDB数据下载器注册完成")

            logger.info("所有增量下载服务注册完成")

            # 5. 注册增量更新调度器
            logger.info("注册增量更新调度器...")
            from ..services.incremental_update_scheduler import IncrementalUpdateScheduler
            scheduler = IncrementalUpdateScheduler(
                analyzer=incremental_analyzer,
                downloader=enhanced_downloader,
                recorder=update_recorder,
                event_bus=event_bus
            )
            self.service_container.register_instance(
                IncrementalUpdateScheduler,
                scheduler
            )
            logger.info("增量更新调度器注册完成")
            
            # 自动启动增量更新调度器
            try:
                scheduler.start_scheduler()
                logger.info("增量更新调度器已自动启动")
            except Exception as start_e:
                logger.warning(f"增量更新调度器自动启动失败: {start_e}")

            # 6. 注册断点续传管理器
            logger.info("注册断点续传管理器...")
            from ..services.breakpoint_resume_manager import BreakpointResumeManager
            resume_manager = BreakpointResumeManager()
            self.service_container.register_instance(
                BreakpointResumeManager,
                resume_manager
            )
            logger.info("断点续传管理器注册完成")

        except Exception as e:
            logger.error(f" 增量下载服务注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_plugin_services(self) -> None:
        """注册插件服务"""
        logger.info("注册插件服务...")

        try:
            # PluginManager和UniPluginDataManager已经在业务服务阶段注册，这里只需要初始化
            if self.service_container.is_registered(PluginManager):
                plugin_manager = self.service_container.resolve(PluginManager)
                plugin_manager.initialize()
                logger.info("插件管理器初始化完成")
            else:
                logger.warning("PluginManager未注册，跳过初始化")

            # 注册策略依赖管理器
            if not self._is_service_registered(StrategyDependencyManager):
                self.service_container.register(
                    StrategyDependencyManager,
                    scope=ServiceScope.SINGLETON
                )
                strategy_dependency_manager = self.service_container.resolve(StrategyDependencyManager)
                logger.info("策略依赖管理器注册完成")
            else:
                logger.warning("StrategyDependencyManager已注册，跳过")

            # 注册策略热重载器
            if not self._is_service_registered(StrategyHotReloader):
                self.service_container.register(
                    StrategyHotReloader,
                    scope=ServiceScope.SINGLETON
                )
                strategy_hot_reloader = self.service_container.resolve(StrategyHotReloader)
                logger.info("策略热重载器注册完成")
            else:
                logger.warning("StrategyHotReloader已注册，跳过")

            # 注册策略核心组件（确保DatabaseService已注册）
            if not self._is_service_registered(StrategyRegistry):
                self.service_container.register(
                    StrategyRegistry,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: StrategyRegistry()
                )
                strategy_registry = self.service_container.resolve(StrategyRegistry)
                logger.info("策略注册器注册完成")
            else:
                strategy_registry = self.service_container.resolve(StrategyRegistry)
                logger.warning("StrategyRegistry已注册，跳过")

            # 处理待注册的策略（在模块导入时使用装饰器注册的策略）
            try:
                from core.strategy.strategy_registry import process_pending_registrations
                process_pending_registrations()
            except Exception as e:
                logger.warning(f"处理待注册策略失败: {e}")

            if not self._is_service_registered(StrategyFactory):
                self.service_container.register(
                    StrategyFactory,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: StrategyFactory(registry=strategy_registry)
                )
                strategy_factory = self.service_container.resolve(StrategyFactory)
                logger.info("策略工厂注册完成")
            else:
                logger.warning("StrategyFactory已注册，跳过")

            if not self._is_service_registered(StrategyEngine):
                self.service_container.register(
                    StrategyEngine,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: StrategyEngine(registry=strategy_registry)
                )
                strategy_engine = self.service_container.resolve(StrategyEngine)
                logger.info("策略执行引擎注册完成")
            else:
                logger.warning("StrategyEngine已注册，跳过")

            # 注册插件热重载器
            if not self._is_service_registered(PluginHotReloader):
                self.service_container.register(
                    PluginHotReloader,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: PluginHotReloader()
                )
                plugin_hot_reloader = self.service_container.resolve(PluginHotReloader)
                logger.info("插件热重载器注册完成")
            else:
                logger.warning("PluginHotReloader已注册，跳过")

            # 注册插件版本管理器
            if not self._is_service_registered(PluginVersionManager):
                self.service_container.register(
                    PluginVersionManager,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: PluginVersionManager(
                        storage_dir=None
                    )
                )
                plugin_version_manager = self.service_container.resolve(PluginVersionManager)
                logger.info("插件版本管理器注册完成")
            else:
                logger.warning("PluginVersionManager已注册，跳过")

            # 情绪数据服务已删除（功能已整合到热点分析）
            logger.debug("情绪数据服务初始化已跳过（服务已移除）")

        except Exception as e:
            logger.error(f" 插件管理器服务注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_trading_services(self) -> None:
        """注册交易服务"""
        logger.info("注册交易服务...")

        try:
            # 注册账户仓储（必须在OrderService之前）
            if not self._is_service_registered(AccountRepository):
                self.service_container.register(
                    AccountRepository,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: AccountRepository(
                        service_container=self.service_container,
                        event_bus=self.event_bus
                    )
                )
                logger.info("账户仓储注册完成")
            else:
                logger.warning("AccountRepository已注册，跳过")

            # 注册账户管理器（必须在OrderService之前）
            if not self._is_service_registered(AccountManager):
                self.service_container.register(
                    AccountManager,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: AccountManager(
                        service_container=self.service_container,
                        event_bus=self.event_bus
                    )
                )
                account_manager = self.service_container.resolve(AccountManager)
                logger.info("账户管理器注册完成")
            else:
                logger.warning("AccountManager已注册，跳过")

            # 注册订单服务
            if not self._is_service_registered(OrderService):
                self.service_container.register(
                    OrderService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: OrderService(
                        service_container=self.service_container,
                        event_bus=self.event_bus
                    )
                )
                order_service = self.service_container.resolve(OrderService)
                logger.info("订单服务注册完成")
            else:
                logger.warning("OrderService已注册，跳过")

            # 注册任务调度器
            if not self._is_service_registered(TaskScheduler):
                self.service_container.register(
                    TaskScheduler,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: TaskScheduler(
                        storage_path="cache/scheduled_tasks.json"
                    )
                )
                task_scheduler = self.service_container.resolve(TaskScheduler)
                logger.info("任务调度器注册完成")
            else:
                logger.warning("TaskScheduler已注册，跳过")

            # 注册订单监控器
            if not self._is_service_registered(OrderMonitor):
                self.service_container.register(
                    OrderMonitor,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: OrderMonitor(
                        service_container=self.service_container,
                        event_bus=self.event_bus
                    )
                )
                order_monitor = self.service_container.resolve(OrderMonitor)
                logger.info("订单监控器注册完成")
            else:
                logger.warning("OrderMonitor已注册，跳过")

            # 注册订单分析器
            if not self._is_service_registered(OrderAnalyzer):
                self.service_container.register(
                    OrderAnalyzer,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: OrderAnalyzer(
                        service_container=self.service_container,
                        event_bus=self.event_bus
                    )
                )
                order_analyzer = self.service_container.resolve(OrderAnalyzer)
                logger.info("订单分析器注册完成")
            else:
                logger.warning("OrderAnalyzer已注册，跳过")

            # 注册TradingService（兼容性）
            try:
                from .trading_service import TradingService

                if not self._is_service_registered(TradingService):
                    self.service_container.register(
                        TradingService,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: TradingService(
                            service_container=self.service_container
                        )
                    )
                    logger.info("TradingService 已注册")

                # 初始化交易服务
                trading_service = self.service_container.resolve(TradingService)
                if trading_service and hasattr(trading_service, 'initialize'):
                    try:
                        trading_service.initialize()
                        logger.info("TradingService 初始化成功")
                    except Exception as init_error:
                        logger.warning(f"TradingService 初始化失败: {init_error}, 使用未初始化状态")
                logger.info("交易服务（TradingService）注册完成")

            except ImportError as e:
                logger.error(f"❌ TradingService 导入失败: {e}")
                logger.error(traceback.format_exc())
                raise  # 重新抛出异常，阻止服务启动
            except Exception as e:
                logger.error(f"❌ 交易服务（TradingService）注册失败: {e}")
                logger.error(traceback.format_exc())
                raise  # 重新抛出异常，阻止服务启动

            # 注册StrategyService
            try:
                from .strategy_service import StrategyService

                if not self._is_service_registered(StrategyService):
                    self.service_container.register(
                        StrategyService,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: StrategyService(
                            event_bus=self.event_bus,
                            config={}
                        )
                    )

                # 初始化策略服务
                strategy_service = self.service_container.resolve(StrategyService)
                if hasattr(strategy_service, 'initialize'):
                    strategy_service.initialize()
                logger.info("策略服务注册完成")

                # 注册策略管理器（作为 StrategyService 的适配器）
                from ..trading.strategy_manager import StrategyManager
                if not self._is_service_registered(StrategyManager):
                    self.service_container.register(
                        StrategyManager,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: StrategyManager(
                            service_container=self.service_container
                        )
                    )
                logger.info("策略管理器注册完成")

            except Exception as e:
                logger.warning(f" 策略服务注册失败: {e}")
                logger.warning(traceback.format_exc())

            # 注册TradingEngine
            try:
                from ..trading_engine import TradingEngine

                if not self._is_service_registered(TradingEngine):
                    self.service_container.register(
                        TradingEngine,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: TradingEngine(
                            service_container=self.service_container,
                            event_bus=self.event_bus
                        )
                    )
                logger.info("交易引擎注册完成")

            except Exception as e:
                logger.warning(f" 交易引擎注册失败: {e}")
                logger.warning(traceback.format_exc())

            # 注册TradingController
            try:
                from ..trading_controller import TradingController

                if not self._is_service_registered(TradingController):
                    self.service_container.register(
                        TradingController,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: TradingController(
                            service_container=self.service_container
                        )
                    )
                logger.info("交易控制器注册完成")

            except Exception as e:
                logger.warning(f" 交易控制器注册失败: {e}")
                logger.warning(traceback.format_exc())

            # 启动订单监控并创建定时任务
            self._setup_order_monitoring()

            # 注册数据脱敏服务
            try:
                from .data_masking_service import DataMaskingService

                if not self._is_service_registered(DataMaskingService):
                    self.service_container.register(
                        DataMaskingService,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: DataMaskingService(
                            config={},
                            event_bus=self.event_bus
                        )
                    )
                    data_masking_service = self.service_container.resolve(DataMaskingService)
                    data_masking_service.initialize()
                    logger.info("数据脱敏服务注册完成")
            except Exception as e:
                logger.warning(f"数据脱敏服务注册失败: {e}")
                logger.warning(traceback.format_exc())

            # 注册资金费率分析服务
            try:
                from .funding_rate_analysis_service import FundingRateAnalysisService

                if not self._is_service_registered(FundingRateAnalysisService):
                    self.service_container.register(
                        FundingRateAnalysisService,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: FundingRateAnalysisService(
                            service_container=self.service_container,
                            event_bus=self.event_bus
                        )
                    )
                    funding_rate_service = self.service_container.resolve(FundingRateAnalysisService)
                    funding_rate_service.initialize()
                    logger.info("资金费率分析服务注册完成")
            except Exception as e:
                logger.warning(f"资金费率分析服务注册失败: {e}")
                logger.warning(traceback.format_exc())

            # 注册交易确认与风控服务
            try:
                from .trading_confirmation_service import TradingConfirmationService

                if not self._is_service_registered(TradingConfirmationService):
                    self.service_container.register(
                        TradingConfirmationService,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: TradingConfirmationService(
                            service_container=self.service_container,
                            event_bus=self.event_bus
                        )
                    )
                    trading_confirmation_service = self.service_container.resolve(TradingConfirmationService)
                    trading_confirmation_service.initialize()
                    logger.info("交易确认与风控服务注册完成")
            except Exception as e:
                logger.warning(f"交易确认与风控服务注册失败: {e}")
                logger.warning(traceback.format_exc())

            logger.info("交易服务注册完成")

        except Exception as e:
            logger.error(f" 交易服务注册失败: {e}")
            logger.error(traceback.format_exc())
            raise  # 重新抛出异常，让调用方知道服务注册失败

    def _setup_order_monitoring(self) -> None:
        """设置订单监控定时任务"""
        try:
            # 获取订单服务
            order_service = self.service_container.resolve(OrderService)

            # 启动订单监控
            order_service.start_monitoring()

            # 检查是否有 TaskScheduler
            if not self.service_container.is_registered(TaskScheduler):
                logger.warning("TaskScheduler 未注册，跳过订单监控定时任务")
                return

            # 获取 TaskScheduler
            task_scheduler = self.service_container.resolve(TaskScheduler)

            # 注册订单检查任务执行器
            task_scheduler.register_task_executor(
                'check_orders',
                lambda task_data: order_service.check_orders()
            )

            # 调度重复任务（每5分钟检查一次，用于超时检测）
            task_scheduler.schedule_recurring_task(
                task_id='order_monitor_check',
                name='订单监控检查',
                function_name='check_orders',
                task_data={},
                interval_seconds=300  # 300秒 = 5分钟
            )

            logger.info("订单监控定时任务已设置（每5分钟检查超时）")

        except Exception as e:
            logger.error(f"设置订单监控失败: {e}")
            logger.error(traceback.format_exc())

    def _post_initialization_plugin_discovery(self) -> None:
        """
        在所有服务注册完成后执行异步插件发现和注册
        """
        logger.info("启动异步插件发现和注册...")
        try:
            # 导入异步插件发现服务
            from .async_plugin_discovery import get_async_plugin_discovery_service

            # 获取插件管理器和数据管理器
            plugin_manager = self.service_container.resolve(PluginManager)
            data_manager = None
            if self.service_container.is_registered(UnifiedDataManager):
                data_manager = self.service_container.resolve(UnifiedDataManager)

            # 获取异步插件发现服务
            async_discovery = get_async_plugin_discovery_service()

            # 连接信号处理进度更新
            async_discovery.progress_updated.connect(self._on_plugin_discovery_progress)
            async_discovery.discovery_completed.connect(self._on_plugin_discovery_completed)
            async_discovery.discovery_failed.connect(self._on_plugin_discovery_failed)

            # 启动异步插件发现
            async_discovery.start_discovery(plugin_manager, data_manager)
            logger.info("异步插件发现服务已启动")

        except Exception as e:
            logger.error(f" 启动异步插件发现失败: {e}")
            logger.error(traceback.format_exc())

            # 降级到同步模式
            logger.info("降级到同步插件发现模式...")
            self._fallback_sync_plugin_discovery()

    def _on_plugin_discovery_progress(self, progress: int, message: str):
        """插件发现进度更新"""
        logger.info(f"插件发现进度: {progress}% - {message}")

    def _on_plugin_discovery_completed(self, result: dict):
        """插件发现完成"""
        logger.info("异步插件发现和注册完成")
        logger.info(f"发现结果: {result}")

    def _on_plugin_discovery_failed(self, error_msg: str):
        """插件发现失败"""
        logger.error(f" 异步插件发现失败: {error_msg}")
        # 可以选择降级到同步模式
        logger.info("尝试降级到同步插件发现模式...")
        self._fallback_sync_plugin_discovery()

    def _fallback_sync_plugin_discovery(self):
        """降级到同步插件发现模式"""
        try:
            logger.info("执行同步插件发现...")

            # 1. 插件管理器插件发现
            plugin_manager = self.service_container.resolve(PluginManager)
            plugin_manager.discover_and_register_plugins()
            logger.info("插件管理器插件发现完成")

            # 2. 统一数据管理器数据源插件发现
            if self.service_container.is_registered(UnifiedDataManager):
                data_manager = self.service_container.resolve(UnifiedDataManager)
                if hasattr(data_manager, 'discover_and_register_data_source_plugins'):
                    data_manager.discover_and_register_data_source_plugins()
                    logger.info("数据源插件发现和注册完成")
                else:
                    logger.warning("UnifiedDataManager不支持插件发现")
            else:
                logger.warning("UnifiedDataManager未注册")

        except Exception as e:
            logger.error(f" 同步插件发现失败: {e}")
            logger.error(traceback.format_exc())

    def _register_advanced_services(self) -> None:
        """注册高级服务（GPU加速、分布式、深度优化功能等）"""
        logger.info("注册高级服务...")

        # GPU加速服务
        try:
            from .gpu_acceleration_manager import GPUAccelerationManager

            def create_gpu_service():
                """创建GPU加速服务实例"""
                return GPUAccelerationManager()

            self.service_container.register_factory(
                GPUAccelerationManager,
                create_gpu_service,
                scope=ServiceScope.SINGLETON
            )

            # 立即解析以触发初始化
            gpu_service = self.service_container.resolve(GPUAccelerationManager)
            logger.info("GPU加速服务注册完成")

        except ImportError:
            logger.warning("GPU加速模块不可用，跳过注册")
        except Exception as e:
            logger.error(f" GPU加速服务注册失败: {e}")
            logger.error(traceback.format_exc())
        
        # 分布式服务
        try:
            from .distributed_service import DistributedService
            
            def create_distributed_service():
                """创建分布式服务实例"""
                service = DistributedService()
                # 自动启动服务
                service.start_service()
                logger.info("分布式服务已启动")
                return service
            
            # 按类型注册（主注册）
            self.service_container.register_factory(
                DistributedService,
                create_distributed_service,
                scope=ServiceScope.SINGLETON
            )
            
            # 添加名称注册，方便UI按名称访问
            self.service_container.register_factory(
                DistributedService,
                create_distributed_service,
                scope=ServiceScope.SINGLETON,
                name='distributed_service'
            )
            
            logger.info("分布式服务注册完成（类型 + 名称 'distributed_service'）")
            
        except ImportError as e:
            logger.warning(f"分布式服务模块不可用，跳过注册: {e}")
        except Exception as e:
            logger.error(f"❌ 分布式服务注册失败: {e}")
            logger.error(traceback.format_exc())

        # 深度分析框架服务
        try:
            from core.services.deep_analysis_framework import (
                DeepAnalysisFramework,
                get_deep_analysis_framework,
                get_performance_coordinator,
                get_advanced_analytics
            )
            
            def create_deep_analysis_framework():
                """创建深度分析框架实例"""
                return get_deep_analysis_framework()
            
            self.service_container.register_factory(
                DeepAnalysisFramework,
                create_deep_analysis_framework,
                scope=ServiceScope.SINGLETON
            )
            
            self.service_container.register_factory(
                DeepAnalysisFramework,
                create_deep_analysis_framework,
                scope=ServiceScope.SINGLETON,
                name='deep_analysis_framework'
            )
            
            logger.info("深度分析框架注册完成（类型 + 名称 'deep_analysis_framework'）")
            
        except ImportError as e:
            logger.warning(f"深度分析框架模块不可用，跳过注册: {e}")
        except Exception as e:
            logger.error(f"❌ 深度分析框架注册失败: {e}")
            logger.error(traceback.format_exc())

        # 注册5个深度优化功能模块
        self._register_optimization_modules()

        # 注册通知服务
        self._register_notification_service()

        # 注册数据质量服务
        self._register_data_quality_services()

    def _register_data_quality_services(self) -> None:
        """注册数据质量相关服务"""
        logger.info("注册数据质量服务...")

        try:
            # 1. 注册数据质量风险管理器
            try:
                from core.data_quality_risk_manager import DataQualityRiskManager

                if not self._is_service_registered(DataQualityRiskManager):
                    self.service_container.register(
                        DataQualityRiskManager,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: DataQualityRiskManager()
                    )
                data_quality_risk_manager = self.service_container.resolve(DataQualityRiskManager)
                logger.info("数据质量风险管理器注册完成")
            except Exception as e:
                logger.error(f"❌ 数据质量风险管理器注册失败: {e}")
                logger.error(traceback.format_exc())

            # 2. 注册增强数据质量监控器（依赖 DataQualityRiskManager 和 AlertRuleEngine）
            try:
                from core.services.enhanced_data_quality_monitor import EnhancedDataQualityMonitor
                from .alert_rule_engine import AlertRuleEngine

                # 确保依赖服务已注册
                if not self.service_container.is_registered(AlertRuleEngine):
                    logger.warning("AlertRuleEngine 未注册，跳过 EnhancedDataQualityMonitor 注册")
                    return

                if not self._is_service_registered(EnhancedDataQualityMonitor):
                    self.service_container.register(
                        EnhancedDataQualityMonitor,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: EnhancedDataQualityMonitor(
                            risk_manager=self.service_container.resolve(DataQualityRiskManager),
                            alert_engine=self.service_container.resolve(AlertRuleEngine)
                        )
                    )
                enhanced_data_quality_monitor = self.service_container.resolve(EnhancedDataQualityMonitor)
                logger.info("增强数据质量监控器注册完成")
            except Exception as e:
                logger.error(f"❌ 增强数据质量监控器注册失败: {e}")
                logger.error(traceback.format_exc())

            # 3. 注册质量报告生成器（依赖 EnhancedDataQualityMonitor）
            try:
                from core.services.quality_report_generator import QualityReportGenerator

                if not self._is_service_registered(QualityReportGenerator):
                    self.service_container.register(
                        QualityReportGenerator,
                        scope=ServiceScope.SINGLETON,
                        factory=lambda: QualityReportGenerator(
                            quality_monitor=self.service_container.resolve(EnhancedDataQualityMonitor)
                        )
                    )
                quality_report_generator = self.service_container.resolve(QualityReportGenerator)
                logger.info("质量报告生成器注册完成")
            except Exception as e:
                logger.error(f"❌ 质量报告生成器注册失败: {e}")
                logger.error(traceback.format_exc())

            logger.info("数据质量服务注册完成")

        except Exception as e:
            logger.error(f"❌ 数据质量服务注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_optimization_modules(self) -> None:
        """注册5个深度优化功能模块"""
        logger.info("开始注册5个深度优化功能模块...")
        
        try:
            # 1. 注册统一缓存管理器（使用 CacheService 替代 IntelligentCache）
            self._register_unified_cache()
            
            # 2. 注册组件虚拟化
            self._register_component_virtualization()
            
            # 3. 注册WebSocket客户端
            self._register_websocket_client()
            
            # 4. 注册智能图表推荐器
            self._register_smart_chart_recommender()
            
            # 5. 注册响应式界面适配器
            self._register_responsive_adapter()
            
            logger.info("5个深度优化功能模块注册完成")
            
        except Exception as e:
            logger.error(f"❌ 深度优化模块注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_unified_cache(self) -> None:
        """注册统一缓存管理器（CacheService）"""
        try:
            from core.services.cache_service import CacheService
            
            def create_cache_service():
                """创建统一缓存服务实例"""
                cache = CacheService()
                cache._do_initialize()
                cache.load_config_from_db('default')
                return cache
            
            self.service_container.register_factory(
                CacheService,
                create_cache_service,
                scope=ServiceScope.SINGLETON
            )
            
            self.service_container.register_factory(
                CacheService,
                create_cache_service,
                scope=ServiceScope.SINGLETON,
                name='unified_cache'
            )
            
            self.service_container.register_factory(
                CacheService,
                create_cache_service,
                scope=ServiceScope.SINGLETON,
                name='cache_service'
            )
            
            logger.info("统一缓存管理器注册完成（CacheService）")
            
        except ImportError as e:
            logger.warning(f"统一缓存模块不可用，跳过注册: {e}")
        except Exception as e:
            logger.error(f"❌ 统一缓存管理器注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_component_virtualization(self) -> None:
        """注册组件虚拟化"""
        try:
            from core.advanced_optimization.performance.virtualization import VirtualScrollRenderer
            
            def create_component_virtualization():
                """创建组件虚拟化服务实例"""
                virtualization = VirtualScrollRenderer()
                return virtualization
            
            # 按类型注册（主注册）
            self.service_container.register_factory(
                VirtualScrollRenderer,
                create_component_virtualization,
                scope=ServiceScope.SINGLETON
            )
            
            # 添加名称注册
            self.service_container.register_factory(
                VirtualScrollRenderer,
                create_component_virtualization,
                scope=ServiceScope.SINGLETON,
                name='component_virtualization'
            )
            
            logger.info("组件虚拟化注册完成（类型 + 名称 'component_virtualization'）")
            
        except ImportError as e:
            logger.warning(f"组件虚拟化模块不可用，跳过注册: {e}")
        except Exception as e:
            logger.error(f"❌ 组件虚拟化注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_websocket_client(self) -> None:
        """注册WebSocket客户端"""
        try:
            from core.advanced_optimization.timing.websocket_client import RealTimeDataProcessor
            
            def create_websocket_client():
                """创建WebSocket客户端服务实例"""
                client = RealTimeDataProcessor()
                return client
            
            # 按类型注册（主注册）
            self.service_container.register_factory(
                RealTimeDataProcessor,
                create_websocket_client,
                scope=ServiceScope.SINGLETON
            )
            
            # 添加名称注册
            self.service_container.register_factory(
                RealTimeDataProcessor,
                create_websocket_client,
                scope=ServiceScope.SINGLETON,
                name='websocket_client'
            )
            
            # 添加常用名称
            self.service_container.register_factory(
                RealTimeDataProcessor,
                create_websocket_client,
                scope=ServiceScope.SINGLETON,
                name='ws_client'
            )
            
            logger.info("WebSocket客户端注册完成（类型 + 名称 'websocket_client' + 'ws_client'）")
            
        except ImportError as e:
            logger.warning(f"WebSocket客户端模块不可用，跳过注册: {e}")
        except Exception as e:
            logger.error(f"❌ WebSocket客户端注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_smart_chart_recommender(self) -> None:
        """注册智能图表推荐器"""
        try:
            from core.advanced_optimization.ai.smart_chart_recommender import UserBehaviorAnalyzer
            
            def create_smart_chart_recommender():
                """创建智能图表推荐器服务实例"""
                recommender = UserBehaviorAnalyzer()
                return recommender
            
            # 按类型注册（主注册）
            self.service_container.register_factory(
                UserBehaviorAnalyzer,
                create_smart_chart_recommender,
                scope=ServiceScope.SINGLETON
            )
            
            # 添加名称注册
            self.service_container.register_factory(
                UserBehaviorAnalyzer,
                create_smart_chart_recommender,
                scope=ServiceScope.SINGLETON,
                name='smart_chart_recommender'
            )
            
            # 添加常用名称
            self.service_container.register_factory(
                UserBehaviorAnalyzer,
                create_smart_chart_recommender,
                scope=ServiceScope.SINGLETON,
                name='chart_recommender'
            )
            
            logger.info("智能图表推荐器注册完成（类型 + 名称 'smart_chart_recommender' + 'chart_recommender'）")
            
        except ImportError as e:
            logger.warning(f"智能图表推荐器模块不可用，跳过注册: {e}")
        except Exception as e:
            logger.error(f"❌ 智能图表推荐器注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_responsive_adapter(self) -> None:
        """注册响应式界面适配器"""
        try:
            from core.advanced_optimization.ui.responsive_adapter import ResponsiveLayoutManager
            
            def create_responsive_adapter():
                """创建响应式界面适配器服务实例"""
                adapter = ResponsiveLayoutManager()
                return adapter
            
            # 按类型注册（主注册）
            self.service_container.register_factory(
                ResponsiveLayoutManager,
                create_responsive_adapter,
                scope=ServiceScope.SINGLETON
            )
            
            # 添加名称注册
            self.service_container.register_factory(
                ResponsiveLayoutManager,
                create_responsive_adapter,
                scope=ServiceScope.SINGLETON,
                name='responsive_adapter'
            )
            
            # 添加常用名称
            self.service_container.register_factory(
                ResponsiveLayoutManager,
                create_responsive_adapter,
                scope=ServiceScope.SINGLETON,
                name='ui_adapter'
            )
            
            logger.info("响应式界面适配器注册完成（类型 + 名称 'responsive_adapter' + 'ui_adapter'）")
            
        except ImportError as e:
            logger.warning(f"响应式界面适配器模块不可用，跳过注册: {e}")
        except Exception as e:
            logger.error(f"❌ 响应式界面适配器注册失败: {e}")
            logger.error(traceback.format_exc())

        # 注册统一优化服务接口
        self._register_unified_optimization_service()

    def _register_unified_optimization_service(self) -> None:
        """注册统一优化服务接口"""
        try:
            from ..advanced_optimization.unified_optimization_service import UnifiedOptimizationService, OptimizationMode, OptimizationConfig
            
            def create_unified_optimization_service():
                """创建统一优化服务实例"""
                config = OptimizationConfig(
                    mode=OptimizationMode.BALANCED,
                    enable_cache=True,
                    enable_virtual_scroll=True,
                    enable_realtime_data=True,
                    enable_ai_recommendation=True,
                    enable_responsive_ui=True,
                    cache_size_mb=512,
                    cache_ttl_seconds=3600,
                    chunk_size=100,
                    preload_threshold=5,
                    max_connections=50,
                    buffer_size=1024,
                    recommendation_count=5,
                    learning_window_days=30,
                    screen_adaptation=True,
                    touch_optimization=True
                )
                
                service = UnifiedOptimizationService(config)
                return service
            
            # 按类型注册（主注册）
            self.service_container.register_factory(
                UnifiedOptimizationService,
                create_unified_optimization_service,
                scope=ServiceScope.SINGLETON
            )
            
            # 添加名称注册，方便UI按名称访问
            self.service_container.register_factory(
                UnifiedOptimizationService,
                create_unified_optimization_service,
                scope=ServiceScope.SINGLETON,
                name='unified_optimization_service'
            )
            
            # 添加常用名称
            self.service_container.register_factory(
                UnifiedOptimizationService,
                create_unified_optimization_service,
                scope=ServiceScope.SINGLETON,
                name='optimization_service'
            )
            
            logger.info("统一优化服务接口注册完成（类型 + 名称 'unified_optimization_service' + 'optimization_service'）")
            
        except ImportError as e:
            logger.warning(f"统一优化服务模块不可用，跳过注册: {e}")
        except Exception as e:
            logger.error(f"❌ 统一优化服务接口注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_plugin_manager_early(self) -> None:
        """提前注册插件管理器，以便在分阶段初始化时可用"""
        logger.info("提前注册插件管理器...")

        try:
            # 注册插件管理器，传递必要的依赖项
            from utils.config_manager import ConfigManager

            # 获取或创建ConfigManager
            config_manager = None
            if self.service_container.is_registered(ConfigManager):
                config_manager = self.service_container.resolve(ConfigManager)
            else:
                config_manager = ConfigManager()

            # 使用安全注册方法注册PluginManager
            if not self._safe_register_service(
                PluginManager,
                lambda: PluginManager(
                    plugin_dir="plugins",
                    main_window=None,  # 稍后在主窗口创建时设置
                    data_manager=None,  # 稍后设置
                    config_manager=config_manager
                ),
                ServiceScope.SINGLETON
            ):
                logger.warning("PluginManager already registered, using existing instance...")

            plugin_manager = self.service_container.resolve(PluginManager)

            # 将UnifiedDataManager连接到插件管理器
            if self.service_container.is_registered(UnifiedDataManager):
                data_manager = self.service_container.resolve(UnifiedDataManager)
                plugin_manager.data_manager = data_manager
                logger.info("插件管理器已连接到UnifiedDataManager")

            logger.info("插件管理器提前注册完成")

        except Exception as e:
            logger.error(f"插件管理器提前注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_uni_plugin_data_manager(self) -> None:
        """注册统一插件数据管理器"""
        logger.info("注册统一插件数据管理器...")

        try:
            # 获取必需的依赖服务
            plugin_manager = self.service_container.resolve(PluginManager)

            # 获取数据源路由器
            from core.data_source_router import DataSourceRouter
            data_source_router = None
            if self.service_container.is_registered(DataSourceRouter):
                data_source_router = self.service_container.resolve(DataSourceRouter)
            else:
                # 如果未注册，创建新实例
                data_source_router = DataSourceRouter()
                self.service_container.register_instance(
                    DataSourceRouter, data_source_router)

            # 获取TET数据管道
            from core.tet_data_pipeline import TETDataPipeline
            tet_pipeline = TETDataPipeline(data_source_router)

            # 注册统一插件数据管理器工厂
            def create_uni_plugin_data_manager():
                manager = UniPluginDataManager(
                    plugin_manager=plugin_manager,
                    data_source_router=data_source_router,
                    tet_pipeline=tet_pipeline
                )
                # 初始化管理器
                manager.initialize()
                return manager

            self.service_container.register_factory(
                UniPluginDataManager,
                create_uni_plugin_data_manager,
                scope=ServiceScope.SINGLETON
            )

            # 设置全局实例
            uni_manager = self.service_container.resolve(UniPluginDataManager)
            from core.services.uni_plugin_data_manager import set_uni_plugin_data_manager
            set_uni_plugin_data_manager(uni_manager)

            logger.info("统一插件数据管理器注册完成")

        except Exception as e:
            logger.error(f"统一插件数据管理器注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_notification_service(self) -> None:
        """注册通知服务"""
        logger.info("注册通知服务...")

        try:
            if not self._is_service_registered(NotificationService):
                self.service_container.register(
                    NotificationService,
                    scope=ServiceScope.SINGLETON,
                    factory=lambda: NotificationService(service_container=self.service_container)
                )
            notification_service = self.service_container.resolve(NotificationService)
            
            logger.info("通知服务注册完成")

            logger.info("初始化全局通知服务实例...")
            init_notification_service(self.service_container)
            logger.info("全局通知服务实例初始化完成")

        except Exception as e:
            logger.error(f"❌ 通知服务注册失败: {e}")
            logger.error(traceback.format_exc())


def bootstrap_services() -> bool:
    """
    引导所有服务的便捷函数

    Returns:
        引导是否成功
    """
    # 使用全局服务容器确保一致性
    from core.containers.service_container import get_service_container
    container = get_service_container()
    bootstrap = ServiceBootstrap(container)
    return bootstrap.bootstrap()
