"""
AI选股集成服务

提供AI选股系统的完整功能，包括与核心服务的深度集成：
- 与UnifiedDataManager的集成，获取市场数据
- 与EnhancedIndicatorService的集成，计算技术指标
- 与DatabaseService的集成，存储策略和结果
- 提供可解释性和个性化功能
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import warnings

from loguru import logger
from ..containers import ServiceContainer, get_service_container
from ..events import EventBus, get_event_bus
from ..plugin_types import AssetType
from .unified_data_manager import UnifiedDataManager
from .enhanced_indicator_service import EnhancedIndicatorService
from .database_service import DatabaseService
from .cache_service import CacheService
from ..utils.error_collector import ErrorCollector, ErrorType, ErrorSeverity


class SelectionStrategy(Enum):
    """选股策略类型"""
    MOMENTUM_BASED = "momentum"      # 动量策略
    VALUE_BASED = "value"           # 价值策略  
    GROWTH_BASED = "growth"         # 成长策略
    QUALITY_BASED = "quality"       # 质量策略
    DIVIDEND_BASED = "dividend"     # 股息策略
    TECH_ANALYSIS = "technical"     # 技术分析策略
    QUANTITATIVE = "quantitative"   # 量化策略
    HYBRID = "hybrid"               # 混合策略


class RiskLevel(Enum):
    """风险等级"""
    CONSERVATIVE = "conservative"    # 保守型
    MODERATE = "moderate"           # 平衡型
    AGGRESSIVE = "aggressive"       # 激进型


class SelectionStatus(Enum):
    """选股结果状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class StockSelectionCriteria:
    """选股标准"""
    # 基础条件
    stock_codes: Optional[List[str]] = None           # 指定股票代码列表
    market_cap_min: Optional[float] = None            # 最小市值（亿元）
    market_cap_max: Optional[float] = None            # 最大市值（亿元）
    max_stocks: int = 50                              # 最大选股数量
    
    # 技术指标条件
    sma_period: int = 20                              # 移动平均周期
    rsi_min: Optional[float] = None                   # RSI最小值
    rsi_max: Optional[float] = None                   # RSI最大值
    macd_signal: Optional[str] = None                 # MACD信号
    volume_threshold: Optional[float] = None          # 成交量阈值
    
    # 财务指标条件
    pe_ratio_min: Optional[float] = None              # 最小市盈率
    pe_ratio_max: Optional[float] = None              # 最大市盈率
    pb_ratio_min: Optional[float] = None              # 最小市净率
    pb_ratio_max: Optional[float] = None              # 最大市净率
    roe_min: Optional[float] = None                   # 最小ROE
    debt_ratio_max: Optional[float] = None            # 最大负债率
    
    # 行业和主题条件
    industries: Optional[List[str]] = None            # 行业列表
    themes: Optional[List[str]] = None                # 主题列表
    
    # 时间和频率条件
    selection_date: datetime = field(default_factory=datetime.now)
    rebalance_frequency: str = "monthly"              # 调仓频率
    time_period: int = 90                             # 时间周期（天）
    
    # 风险和策略条件
    risk_level: RiskLevel = RiskLevel.MODERATE        # 风险等级
    risk_tolerance: str = "moderate"                  # 风险容忍度（用于UI）
    strategy_type: SelectionStrategy = SelectionStrategy.QUANTITATIVE  # 策略类型
    
    # 指标权重
    technical_indicators: Dict[str, float] = field(default_factory=dict)  # 技术指标权重
    fundamental_indicators: Dict[str, float] = field(default_factory=dict)  # 基本面指标权重


@dataclass
class SelectionPerformanceMetrics:
    """选股性能指标"""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_return: float = 0.0
    risk_adjusted_return: float = 0.0


@dataclass
class SelectionExplanation:
    """选股结果解释"""
    stock_code: str                                   # 股票代码
    selection_reason: str                            # 入选原因
    score: float                                     # 评分 (0-100)
    key_indicators: Dict[str, float]                 # 关键指标值
    technical_signals: Dict[str, Any]               # 技术信号
    fundamental_signals: Dict[str, Any]             # 基本面信号
    risk_assessment: Dict[str, Any]                 # 风险评估
    recommendation_strength: str                    # 推荐强度 (strong/moderate/weak)


@dataclass
class StockSelectionResult:
    """选股结果"""
    result_id: str                                    # 结果ID
    strategy_id: str                                  # 策略ID
    selection_date: datetime                         # 选股日期
    status: SelectionStatus                          # 状态
    criteria: StockSelectionCriteria                 # 选股标准
    
    # 选股结果
    selected_stocks: List[str]                       # 选中的股票代码
    stock_scores: Dict[str, float]                   # 股票评分
    weights: Dict[str, float]                        # 权重分配
    
    # 解释和说明
    explanations: List[SelectionExplanation]         # 选股解释
    overall_explanation: str                         # 整体说明
    
    # 性能指标
    portfolio_metrics: Dict[str, Any]               # 组合指标
    backtest_metrics: Optional[Dict[str, Any]] = None  # 回测指标
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    computation_time: float = 0.0                    # 计算时间
    data_freshness: Dict[str, datetime] = field(default_factory=dict)  # 数据时效性
    error_message: Optional[str] = None             # 错误信息


class AISelectionIntegrationService:
    """AI选股集成服务
    
    深度集成现有核心服务，提供完整的AI选股功能
    """
    
    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """初始化AI选股集成服务
        
        Args:
            service_container: 服务容器，用于解析依赖服务
        """
        self._container = service_container or get_service_container()
        if not self._container:
            raise ValueError("无法获取服务容器，请确保服务容器已初始化")
            
        # 解析核心依赖服务
        self._data_manager = self._container.resolve(UnifiedDataManager)
        self._indicator_service = self._container.resolve(EnhancedIndicatorService)
        self._database_service = self._container.resolve(DatabaseService)
        self._event_bus = get_event_bus()
        
        # 解析可解释性服务
        self._explainability_service = None
        try:
            from .ai_explainability_service import AIExplainabilityService
            self._explainability_service = self._container.resolve(AIExplainabilityService)
            logger.info("AI可解释性服务加载成功")
        except Exception as e:
            logger.warning(f"AI可解释性服务加载失败: {e}")
        
        # 线程池用于异步计算
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="AI_Selection")
        
        # 获取缓存服务
        self._cache_service = self._container.resolve(CacheService)
        
        # 策略注册
        self._strategies: Dict[str, Any] = {}
        self._register_default_strategies()
        
        # LLM 解析器（用于自然语言解析）
        self._llm_parser = None
        self._init_llm_parser()
        
        logger.info("AI选股集成服务初始化完成")
    
    def _init_llm_parser(self):
        """初始化 LLM 解析器"""
        try:
            # 尝试获取 LLM 配置服务
            try:
                from .llm_config_service import LLMConfigService, LLMProvider
                llm_config_service = self._container.resolve(LLMConfigService)
                
                # 获取当前配置
                current_config = llm_config_service.get_current_config()
                if current_config and current_config.api_key:
                    # 根据提供商初始化对应的客户端
                    if current_config.provider == LLMProvider.OPENAI:
                        from openai import OpenAI
                        self._llm_parser = OpenAI(
                            api_key=current_config.api_key,
                            base_url=current_config.base_url,
                            timeout=current_config.timeout
                        )
                        logger.info(f"LLM 解析器初始化成功 (OpenAI - {current_config.model})")
                    elif current_config.provider == LLMProvider.ANTHROPIC:
                        from anthropic import Anthropic
                        self._llm_parser = Anthropic(
                            api_key=current_config.api_key,
                            base_url=current_config.base_url,
                            timeout=current_config.timeout
                        )
                        logger.info(f"LLM 解析器初始化成功 (Anthropic - {current_config.model})")
                    elif current_config.provider == LLMProvider.GOOGLE:
                        import google.generativeai as genai
                        genai.configure(api_key=current_config.api_key)
                        self._llm_parser = genai.GenerativeModel(current_config.model)
                        logger.info(f"LLM 解析器初始化成功 (Google - {current_config.model})")
                    elif current_config.provider == LLMProvider.QIANWEN:
                        import dashscope
                        from dashscope import Generation
                        dashscope.api_key = current_config.api_key
                        self._llm_parser = Generation
                        logger.info(f"LLM 解析器初始化成功 (通义千问 - {current_config.model})")
                    else:
                        logger.warning(f"暂不支持 {current_config.provider.value} 提供商")
                        self._llm_parser = None
                else:
                    logger.warning("未配置 LLM API key，LLM 解析功能不可用")
                    self._llm_parser = None
                    
            except Exception as config_error:
                logger.warning(f"LLM 配置服务不可用，尝试传统方式: {config_error}")
                self._init_llm_parser_legacy()
                
        except ImportError:
            logger.warning("OpenAI 库未安装，LLM 解析功能不可用")
            self._llm_parser = None
        except Exception as e:
            logger.warning(f"LLM 解析器初始化失败: {e}")
            self._llm_parser = None
    
    def _init_llm_parser_legacy(self):
        """使用传统方式初始化 LLM 解析器（向后兼容）"""
        try:
            from openai import OpenAI
            
            api_key = self._get_llm_api_key_legacy()
            if api_key:
                self._llm_parser = OpenAI(api_key=api_key)
                logger.info("LLM 解析器初始化成功（传统方式）")
            else:
                logger.warning("未配置 OpenAI API key，LLM 解析功能不可用")
        except ImportError:
            logger.warning("OpenAI 库未安装，LLM 解析功能不可用")
        except Exception as e:
            logger.warning(f"LLM 解析器初始化失败: {e}")
    
    def _get_llm_api_key_legacy(self) -> Optional[str]:
        """获取 LLM API key（传统方式，向后兼容）
        
        Returns:
            API key 或 None
        """
        try:
            import os
            api_key = os.environ.get('OPENAI_API_KEY')
            if api_key:
                return api_key
            
            try:
                import configparser
                config = configparser.ConfigParser()
                config.read('config.ini', encoding='utf-8')
                if 'AI' in config and 'openai_api_key' in config['AI']:
                    return config['AI']['openai_api_key']
            except Exception:
                pass
            
            return None
        except Exception as e:
            logger.error(f"获取 LLM API key 失败: {e}")
            return None
    
    async def parse_natural_language(
        self,
        user_input: str
    ) -> Dict[str, Any]:
        """解析自然语言输入
        
        Args:
            user_input: 用户输入的自然语言选股需求
            
        Returns:
            解析后的选股条件字典
        """
        if not self._llm_parser:
            logger.warning("LLM 解析器不可用，返回空结果")
            return {}
        
        try:
            # 构建提示词
            prompt = self._build_llm_prompt(user_input)
            
            # 调用 LLM API
            response = self._llm_parser.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的股票选股助手，请将用户的自然语言需求转换为结构化的选股条件。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            # 解析响应
            content = response.choices[0].message.content
            parsed_result = json.loads(content)
            
            logger.info(f"LLM 解析成功: {parsed_result}")
            return parsed_result
            
        except Exception as e:
            logger.error(f"LLM 解析失败: {e}")
            return {}
    
    def _build_llm_prompt(self, user_input: str) -> str:
        """构建 LLM 提示词
        
        Args:
            user_input: 用户输入
            
        Returns:
            提示词字符串
        """
        prompt = f"""
请将以下选股需求转换为结构化的选股条件，输出 JSON 格式：

用户需求：{user_input}

请输出以下字段（如果用户没有提到某个条件，则不包含该字段）：
- market_cap_min: 最小市值（亿元）
- market_cap_max: 最大市值（亿元）
- pe_ratio_min: 最小市盈率
- pe_ratio_max: 最大市盈率
- pb_ratio_min: 最小市净率
- pb_ratio_max: 最大市净率
- roe_min: 最小ROE
- roe_max: 最大ROE
- industries: 行业列表（数组）
- themes: 主题列表（数组）
- risk_level: 风险等级（conservative/moderate/aggressive）
- strategy_type: 策略类型（momentum/value/growth/quality/technical/quantitative/hybrid）

示例输出：
{{
    "market_cap_min": 100,
    "pe_ratio_max": 20,
    "roe_min": 15,
    "industries": ["科技", "医药"],
    "risk_level": "moderate",
    "strategy_type": "growth"
}}
"""
        return prompt
    
    async def select_stocks_with_nlp(
        self,
        user_input: str,
        strategy_type: SelectionStrategy = SelectionStrategy.QUANTITATIVE
    ) -> StockSelectionResult:
        """使用自然语言输入进行选股
        
        Args:
            user_input: 用户输入的自然语言选股需求
            strategy_type: 默认策略类型
            
        Returns:
            选股结果
        """
        try:
            # 1. 使用 LLM 解析自然语言
            logger.info(f"开始解析自然语言: {user_input}")
            parsed_conditions = await self.parse_natural_language(user_input)
            
            if not parsed_conditions:
                logger.warning("LLM 解析失败，使用默认条件")
                criteria = StockSelectionCriteria(
                    strategy_type=strategy_type,
                    risk_level=RiskLevel.MODERATE
                )
            else:
                # 2. 转换为选股标准
                criteria = self._convert_parsed_to_criteria(parsed_conditions, strategy_type)
            
            # 3. 执行选股
            result = await self.select_stocks_with_explanation(
                strategy_id=strategy_type.value,
                criteria=criteria
            )
            
            # 4. 添加自然语言输入到结果
            result.overall_explanation = f"基于自然语言需求 '{user_input}' 的选股结果：\n{result.overall_explanation}"
            
            return result
            
        except Exception as e:
            logger.error(f"自然语言选股失败: {e}")
            raise
    
    def _convert_parsed_to_criteria(
        self,
        parsed: Dict[str, Any],
        default_strategy: SelectionStrategy
    ) -> StockSelectionCriteria:
        """将 LLM 解析结果转换为选股标准
        
        Args:
            parsed: LLM 解析结果
            default_strategy: 默认策略类型
            
        Returns:
            选股标准
        """
        # 映射风险等级
        risk_level_map = {
            "conservative": RiskLevel.CONSERVATIVE,
            "moderate": RiskLevel.MODERATE,
            "aggressive": RiskLevel.AGGRESSIVE
        }
        
        # 映射策略类型
        strategy_map = {
            "momentum": SelectionStrategy.MOMENTUM_BASED,
            "value": SelectionStrategy.VALUE_BASED,
            "growth": SelectionStrategy.GROWTH_BASED,
            "quality": SelectionStrategy.QUALITY_BASED,
            "technical": SelectionStrategy.TECH_ANALYSIS,
            "quantitative": SelectionStrategy.QUANTITATIVE,
            "hybrid": SelectionStrategy.HYBRID
        }
        
        # 创建选股标准
        criteria = StockSelectionCriteria(
            strategy_type=strategy_map.get(
                parsed.get('strategy_type'),
                default_strategy
            ),
            risk_level=risk_level_map.get(
                parsed.get('risk_level'),
                RiskLevel.MODERATE
            ),
            market_cap_min=parsed.get('market_cap_min'),
            market_cap_max=parsed.get('market_cap_max'),
            pe_ratio_min=parsed.get('pe_ratio_min'),
            pe_ratio_max=parsed.get('pe_ratio_max'),
            pb_ratio_min=parsed.get('pb_ratio_min'),
            pb_ratio_max=parsed.get('pb_ratio_max'),
            roe_min=parsed.get('roe_min'),
            roe_max=parsed.get('roe_max'),
            industries=parsed.get('industries'),
            themes=parsed.get('themes')
        )
        
        return criteria
        
    def _register_default_strategies(self):
        """注册默认选股策略"""
        self._strategies = {
            SelectionStrategy.MOMENTUM_BASED: self._momentum_strategy,
            SelectionStrategy.VALUE_BASED: self._value_strategy,
            SelectionStrategy.GROWTH_BASED: self._growth_strategy,
            SelectionStrategy.QUALITY_BASED: self._quality_strategy,
            SelectionStrategy.TECH_ANALYSIS: self._technical_strategy,
            SelectionStrategy.QUANTITATIVE: self._quantitative_strategy,
            SelectionStrategy.HYBRID: self._hybrid_strategy
        }
        
    async def create_selection_strategy(
        self,
        name: str,
        description: str,
        criteria: StockSelectionCriteria,
        user_id: Optional[str] = None
    ) -> str:
        """创建选股策略
        
        Args:
            name: 策略名称
            description: 策略描述
            criteria: 选股标准
            user_id: 用户ID
            
        Returns:
            策略ID
        """
        strategy_id = str(uuid.uuid4())
        
        # 保存策略到数据库
        strategy_data = {
            "strategy_id": strategy_id,
            "name": name,
            "description": description,
            "criteria": asdict(criteria),
            "user_id": user_id,
            "created_at": datetime.now(),
            "is_active": True,
            "performance_metrics": {},
            "backtest_result": {}
        }
        
        try:
            # 使用DatabaseService保存策略
            if hasattr(self._database_service, 'save_ai_strategy'):
                await self._database_service.save_ai_strategy(strategy_data)
            else:
                # 如果DatabaseService没有相应方法，直接保存到数据库
                await self._save_strategy_to_db(strategy_data)
                
            logger.info(f"选股策略创建成功: {name} (ID: {strategy_id})")
            return strategy_id
            
        except Exception as e:
            logger.error(f"创建选股策略失败: {e}")
            raise
    
    async def select_stocks_with_explanation(
        self,
        strategy_id: str,
        criteria: Optional[StockSelectionCriteria] = None,
        error_collector: Optional[ErrorCollector] = None,
        progress_callback: Optional[callable] = None
    ) -> StockSelectionResult:
        """执行选股并生成解释
        
        Args:
            strategy_id: 策略ID
            criteria: 选股标准（可选，如果为None则使用策略中保存的标准）
            error_collector: 错误收集器
            progress_callback: 进度回调函数 callback(progress_percent, status_message)
            
        Returns:
            选股结果
        """
        start_time = datetime.now()
        
        # 初始化错误收集器
        if error_collector is None:
            error_collector = ErrorCollector()
        
        try:
            # 获取策略信息
            if progress_callback:
                progress_callback(5, "获取策略信息...")
            try:
                strategy_data = await self._get_strategy_by_id(strategy_id)
                if not strategy_data:
                    raise ValueError(f"策略 {strategy_id} 不存在")
            except Exception as e:
                error_collector.add_error(
                    error_type=ErrorType.DATABASE,
                    error_message=f"获取策略信息失败: {str(e)}",
                    severity=ErrorSeverity.HIGH
                )
                raise
                
            # 准备选股标准
            selection_criteria = criteria or StockSelectionCriteria(**strategy_data["criteria"])
            
            # 检查缓存
            if progress_callback:
                progress_callback(8, "检查缓存...")
            cache_key = f"{strategy_id}_{selection_criteria.selection_date.strftime('%Y%m%d')}"
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                logger.info("返回缓存的选股结果")
                if progress_callback:
                    progress_callback(100, "完成（使用缓存）")
                return cached_result
            
            # 发布事件：开始选股
            self._event_bus.publish("ai_selection.started",
                strategy_id=strategy_id,
                criteria=asdict(selection_criteria)
            )
            
            # 执行选股
            result = await self._execute_selection(strategy_id, selection_criteria, error_collector, progress_callback)
            
            # 保存结果到数据库（必须在生成解释之前，确保 result_id 存在于数据库中）
            if progress_callback:
                progress_callback(92, "保存选股结果...")
            await self._save_selection_result(result)
            
            # 生成解释
            if progress_callback:
                progress_callback(95, "生成选股解释...")
            result.explanations = await self._generate_explanations(result, error_collector)
            result.overall_explanation = await self._generate_overall_explanation(result)
            
            # 计算性能指标
            if progress_callback:
                progress_callback(98, "计算组合指标...")
            result.portfolio_metrics = await self._calculate_portfolio_metrics(result)
            
            # 缓存结果
            self._cache_result(cache_key, result)
            
            # 发布事件：选股完成
            self._event_bus.publish("ai_selection.completed",
                strategy_id=strategy_id,
                result_id=result.result_id,
                selected_stocks=result.selected_stocks
            )
            
            result.computation_time = (datetime.now() - start_time).total_seconds()
            
            if progress_callback:
                progress_callback(100, "选股完成")
            
            logger.info(f"选股完成: {strategy_id}, 选中 {len(result.selected_stocks)} 只股票")
            return result
            
        except Exception as e:
            logger.error(f"选股失败: {e}")
            
            # 记录到错误收集器
            error_collector.add_error(
                error_type=ErrorType.STRATEGY,
                error_message=f"选股失败: {str(e)}",
                error_detail=traceback.format_exc(),
                severity=ErrorSeverity.CRITICAL
            )
            
            # 发布失败事件
            self._event_bus.publish("ai_selection.failed",
                strategy_id=strategy_id,
                error=str(e)
            )
            raise
    
    async def _execute_selection(
        self,
        strategy_id: str,
        criteria: StockSelectionCriteria,
        error_collector: ErrorCollector,
        progress_callback: Optional[callable] = None
    ) -> StockSelectionResult:
        """执行具体的选股逻辑
        
        Args:
            strategy_id: 策略ID
            criteria: 选股标准
            error_collector: 错误收集器
            progress_callback: 进度回调函数 callback(progress_percent, status_message)
        """
        result_id = str(uuid.uuid4())
        
        # 获取候选股票列表
        if progress_callback:
            progress_callback(10, "获取候选股票列表...")
        candidate_stocks = await self._get_candidate_stocks(criteria, error_collector)
        
        if not candidate_stocks:
            return StockSelectionResult(
                result_id=result_id,
                strategy_id=strategy_id,
                selection_date=criteria.selection_date,
                status=SelectionStatus.COMPLETED,
                criteria=criteria,
                selected_stocks=[],
                stock_scores={},
                weights={},
                explanations=[],
                overall_explanation="没有找到符合条件的股票",
                portfolio_metrics={}
            )
        
        # 获取股票数据
        if progress_callback:
            progress_callback(20, f"获取 {len(candidate_stocks)} 只股票的数据...")
        stock_data = await self._get_stock_data_batch(candidate_stocks, criteria, error_collector)
        
        # 执行策略计算
        if progress_callback:
            progress_callback(50, "执行选股策略...")
        strategy_func = self._strategies.get(criteria.strategy_type, self._quantitative_strategy)
        selected_stocks, scores, detailed_scores = await self._run_strategy(strategy_func, stock_data, criteria, error_collector)
        
        # 计算权重
        if progress_callback:
            progress_callback(80, "计算权重分配...")
        weights = self._calculate_weights(selected_stocks, scores, criteria)
        
        # 保存详细评分到结果
        if progress_callback:
            progress_callback(90, "整理选股结果...")
        
        result = StockSelectionResult(
            result_id=result_id,
            strategy_id=strategy_id,
            selection_date=criteria.selection_date,
            status=SelectionStatus.COMPLETED,
            criteria=criteria,
            selected_stocks=selected_stocks,
            stock_scores=dict(zip(selected_stocks, [scores[stock] for stock in selected_stocks])),
            weights=weights,
            explanations=[],  # 将在后续步骤中填充
            overall_explanation="",  # 将在后续步骤中填充
            portfolio_metrics={}  # 将在后续步骤中更新
        )
        
        # 将详细评分存储到 result 的 metadata 中
        result.portfolio_metrics = {
            "detailed_scores": detailed_scores,
            "computation_time": 0.0  # 将在后续更新
        }
        
        return result
    
    async def _get_candidate_stocks(self, criteria: StockSelectionCriteria, error_collector: ErrorCollector) -> List[str]:
        """获取候选股票列表"""
        if criteria.stock_codes:
            return criteria.stock_codes
            
        # 使用实际数据服务获取候选股票
        try:
            candidate_stocks = []
            
            # 如果指定了行业筛选，使用行业股票列表
            if criteria.industries:
                for industry in criteria.industries:
                    try:
                        # 从数据库或数据服务获取行业股票
                        industry_stocks = await self._get_industry_stocks(industry)
                        candidate_stocks.extend(industry_stocks)
                    except Exception as e:
                        error_collector.add_error(
                            error_type=ErrorType.DATA_FETCH,
                            error_message=f"获取行业 {industry} 股票列表失败",
                            error_detail=str(e),
                            severity=ErrorSeverity.MEDIUM
                        )
                        continue
            
            # 如果没有指定行业，获取主要股票池
            if not candidate_stocks:
                candidate_stocks = await self._get_main_stock_pool(criteria, error_collector)
            
            # 应用市值筛选
            if criteria.market_cap_min or criteria.market_cap_max:
                candidate_stocks = await self._filter_stocks_by_market_cap(
                    candidate_stocks, criteria.market_cap_min, criteria.market_cap_max, error_collector
                )
            
            # 去重
            candidate_stocks = list(set(candidate_stocks))
            
            logger.info(f"获取候选股票 {len(candidate_stocks)} 只")
            return candidate_stocks
            
        except Exception as e:
            error_collector.add_error(
                error_type=ErrorType.DATA_FETCH,
                error_message="获取候选股票失败",
                error_detail=str(e),
                severity=ErrorSeverity.HIGH
            )
            # 返回基础股票池作为后备
            return await self._get_main_stock_pool(criteria, error_collector)
    
    async def _get_industry_stocks(self, industry: str) -> List[str]:
        """获取指定行业的股票列表"""
        try:
            # 使用数据库服务获取行业股票
            if hasattr(self._database_service, 'get_stocks_by_industry'):
                stocks = await self._database_service.get_stocks_by_industry(industry)
                return [stock.get('code', '') for stock in stocks if stock.get('code')]
            
            # 使用数据管理器获取行业股票
            if hasattr(self._data_manager, 'get_industry_stocks'):
                stocks = await self._data_manager.get_industry_stocks(industry)
                return [stock for stock in stocks if stock]
            
            # 如果无法获取行业股票，返回空列表
            logger.warning(f"无法获取行业 {industry} 的股票列表")
            return []
            
        except Exception as e:
            logger.error(f"获取行业 {industry} 股票列表失败: {e}")
            return []
    
    async def _get_main_stock_pool(self, criteria: StockSelectionCriteria, error_collector: ErrorCollector) -> List[str]:
        """获取主要股票池"""
        try:
            # 使用UnifiedDataManager获取主要股票
            if hasattr(self._data_manager, 'get_main_stock_pool'):
                stocks = await self._data_manager.get_main_stock_pool()
                return [stock for stock in stocks if stock]
            
            # 使用StockService获取股票列表
            if hasattr(self._data_manager, 'get_stock_list'):
                stock_list = self._data_manager.get_stock_list()
                if stock_list is not None and not stock_list.empty:
                    return stock_list['code'].tolist() if 'code' in stock_list.columns else []
            
            # 如果无法获取主要股票池，返回空列表
            logger.warning("无法获取主要股票池")
            return []
            
        except Exception as e:
            error_collector.add_error(
                error_type=ErrorType.DATA_FETCH,
                error_message="获取主要股票池失败",
                error_detail=str(e),
                severity=ErrorSeverity.HIGH
            )
            return []
    
    async def _filter_stocks_by_market_cap(self, stocks: List[str], 
                                         market_cap_min: Optional[float], 
                                         market_cap_max: Optional[float],
                                         error_collector: ErrorCollector) -> List[str]:
        """根据市值筛选股票"""
        try:
            filtered_stocks = []
            
            # 批量获取股票市值数据
            stock_data_batch = await self._get_stock_data_batch(stocks, 
                StockSelectionCriteria(selection_date=datetime.now()), error_collector)
            
            for stock_code in stocks:
                if stock_code in stock_data_batch:
                    stock_info = stock_data_batch[stock_code]
                    price_data = stock_info.get('price_data')
                    
                    if price_data is not None and not price_data.empty:
                        # 获取最新市值数据
                        latest_data = price_data.iloc[-1]
                        market_cap = latest_data.get('total_market_cap', 0)
                        
                        # 检查是否符合市值范围
                        if market_cap_min and market_cap < market_cap_min:
                            continue
                        if market_cap_max and market_cap > market_cap_max:
                            continue
                        
                        filtered_stocks.append(stock_code)
            
            logger.info(f"市值筛选后保留 {len(filtered_stocks)} 只股票")
            return filtered_stocks
            
        except Exception as e:
            error_collector.add_error(
                error_type=ErrorType.CALCULATION,
                error_message="市值筛选失败",
                error_detail=str(e),
                severity=ErrorSeverity.MEDIUM
            )
            return stocks  # 筛选失败时返回原列表
    
    async def _get_stock_data_batch(
        self,
        stock_codes: List[str],
        criteria: StockSelectionCriteria,
        error_collector: ErrorCollector
    ) -> Dict[str, Dict[str, Any]]:
        """批量获取股票数据（优化版 - 使用asyncio.gather并行获取）"""
        # 设置数据获取参数
        time_range = 365  # 获取一年的数据
        period = "D"
        
        # 创建获取任务列表
        tasks = []
        for stock_code in stock_codes:
            task = self._get_single_stock_data(stock_code, time_range, period, error_collector)
            tasks.append((stock_code, task))
        
        # 使用asyncio.gather并行执行
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        # 处理结果
        stock_data = {}
        for (stock_code, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                # 错误已经在_get_single_stock_data中记录
                continue
            elif result is not None:
                stock_data[stock_code] = result
                
        logger.info(f"成功获取 {len(stock_data)} 只股票的数据")
        return stock_data
    
    async def _get_single_stock_data(
        self,
        stock_code: str,
        time_range: int,
        period: str,
        error_collector: ErrorCollector
    ) -> Optional[Dict[str, Any]]:
        """获取单个股票数据"""
        try:
            # 使用UnifiedDataManager获取数据
            data_request = {
                "symbol": stock_code,
                "asset_type": AssetType.STOCK_A,
                "data_type": "kdata",
                "period": period,
                "time_range": time_range
            }
            
            # 异步获取数据
            data = await self._data_manager.get_data_async(**data_request)
            if data is not None and not data.empty:
                return {
                    "price_data": data,
                    "fetched_at": datetime.now()
                }
            return None
                    
        except Exception as e:
            error_collector.add_error(
                error_type=ErrorType.DATA_FETCH,
                error_message=f"获取股票 {stock_code} 数据失败",
                error_detail=str(e),
                stock_code=stock_code,
                severity=ErrorSeverity.MEDIUM
            )
            return None
    
    async def _run_strategy(
        self,
        strategy_func,
        stock_data: Dict[str, Dict[str, Any]],
        criteria: StockSelectionCriteria,
        error_collector: ErrorCollector
    ) -> Tuple[List[str], Dict[str, float], Dict[str, Dict[str, float]]]:
        """运行选股策略
        
        Returns:
            selected_stocks: 选中的股票列表
            scores: 股票评分
            detailed_scores: 详细评分（如果策略支持）
        """
        
        # 在线程池中执行策略计算
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            lambda: strategy_func(stock_data, criteria)
        )
        
        # 处理不同的返回值格式
        if len(result) == 3:
            # 新格式：返回三个值
            selected_stocks, scores, detailed_scores = result
        else:
            # 旧格式：返回两个值
            selected_stocks, scores = result
            detailed_scores = {}
        
        return selected_stocks, scores, detailed_scores
    
    def _quantitative_strategy(
        self,
        stock_data: Dict[str, Dict[str, Any]],
        criteria: StockSelectionCriteria
    ) -> Tuple[List[str], Dict[str, float], Dict[str, Dict[str, float]]]:
        """量化策略实现
        
        Returns:
            selected_stocks: 选中的股票列表
            stock_scores: 股票综合评分 {股票代码: 综合评分}
            detailed_scores: 详细评分 {股票代码: {技术评分, 动量评分, 波动性评分, 流动性评分}}
        """
        
        stock_scores = {}
        detailed_scores = {}
        
        for stock_code, data in stock_data.items():
            try:
                price_data = data["price_data"]
                if price_data.empty or len(price_data) < 30:
                    continue
                    
                score = 0.0
                
                # 技术指标评分 (40%)
                tech_score = self._calculate_technical_score(price_data, criteria)
                score += tech_score * 0.4
                
                # 动量指标评分 (30%)
                momentum_score = self._calculate_momentum_score(price_data)
                score += momentum_score * 0.3
                
                # 波动性评分 (20%)
                volatility_score = self._calculate_volatility_score(price_data)
                score += volatility_score * 0.2
                
                # 流动性评分 (10%)
                liquidity_score = self._calculate_liquidity_score(price_data)
                score += liquidity_score * 0.1
                
                # 风险调整
                if criteria.risk_level == RiskLevel.CONSERVATIVE:
                    score *= 0.9  # 保守型降低评分
                elif criteria.risk_level == RiskLevel.AGGRESSIVE:
                    score *= 1.1  # 激进型提升评分
                
                final_score = min(score, 100.0)  # 限制在0-100之间
                stock_scores[stock_code] = final_score
                
                # 保存详细评分
                detailed_scores[stock_code] = {
                    "technical_score": tech_score,
                    "momentum_score": momentum_score,
                    "volatility_score": volatility_score,
                    "liquidity_score": liquidity_score,
                    "risk_adjusted_score": final_score
                }
                
            except Exception as e:
                logger.warning(f"计算股票 {stock_code} 评分失败: {e}")
                continue
        
        # 选择评分最高的股票
        sorted_stocks = sorted(stock_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 根据风险等级确定选择数量
        if criteria.risk_level == RiskLevel.CONSERVATIVE:
            top_n = min(10, len(sorted_stocks))
        elif criteria.risk_level == RiskLevel.MODERATE:
            top_n = min(20, len(sorted_stocks))
        else:  # AGGRESSIVE
            top_n = min(30, len(sorted_stocks))
        
        selected_stocks = [stock for stock, _ in sorted_stocks[:top_n]]
        selected_scores = {stock: stock_scores[stock] for stock in selected_stocks}
        
        return selected_stocks, selected_scores, detailed_scores
    
    def _calculate_technical_score(
        self,
        price_data: pd.DataFrame,
        criteria: StockSelectionCriteria
    ) -> float:
        """计算技术指标评分"""
        try:
            if price_data.empty or len(price_data) < criteria.sma_period:
                return 0.0
                
            # 计算移动平均线
            sma_20 = price_data['close'].rolling(window=20).mean()
            sma_50 = price_data['close'].rolling(window=50).mean()
            
            # 价格相对于移动平均线的位置
            current_price = price_data['close'].iloc[-1]
            sma_20_current = sma_20.iloc[-1]
            sma_50_current = sma_50.iloc[-1]
            
            score = 0.0
            
            # 价格在移动平均线之上
            if current_price > sma_20_current:
                score += 20
            if current_price > sma_50_current:
                score += 20
            
            # 移动平均线向上趋势
            if len(sma_20) >= 2 and sma_20.iloc[-1] > sma_20.iloc[-2]:
                score += 15
            
            if len(sma_50) >= 2 and sma_50.iloc[-1] > sma_50.iloc[-2]:
                score += 15
            
            # RSI指标
            if len(price_data) >= 14:
                rsi = self._calculate_rsi(price_data['close'], 14)
                rsi_current = rsi.iloc[-1] if not rsi.empty else 50
                
                # RSI在合理范围内
                if 30 <= rsi_current <= 70:
                    score += 20
                elif 20 <= rsi_current <= 80:
                    score += 10
            
            # MACD信号
            macd_signal = self._calculate_macd_signal(price_data['close'])
            if macd_signal == "buy":
                score += 10
            
            return min(score, 100.0)
            
        except Exception as e:
            logger.warning(f"计算技术评分失败: {e}")
            return 0.0
    
    def _calculate_momentum_score(self, price_data: pd.DataFrame) -> float:
        """计算动量评分"""
        try:
            if price_data.empty or len(price_data) < 20:
                return 0.0
                
            # 计算不同周期的收益率
            returns_5d = price_data['close'].pct_change(5).iloc[-1]
            returns_20d = price_data['close'].pct_change(20).iloc[-1]
            returns_60d = price_data['close'].pct_change(60).iloc[-1]
            
            score = 0.0
            
            # 正收益得分
            if returns_5d > 0:
                score += min(returns_5d * 100, 25)  # 最多25分
            if returns_20d > 0:
                score += min(returns_20d * 100, 25)  # 最多25分
            if returns_60d > 0:
                score += min(returns_60d * 100, 25)  # 最多25分
            
            # 动量一致性
            if returns_5d > returns_20d > returns_60d:
                score += 25
            
            return min(score, 100.0)
            
        except Exception as e:
            logger.warning(f"计算动量评分失败: {e}")
            return 0.0
    
    def _calculate_volatility_score(self, price_data: pd.DataFrame) -> float:
        """计算波动性评分"""
        try:
            if price_data.empty or len(price_data) < 20:
                return 0.0
                
            # 计算收益率波动性
            returns = price_data['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # 年化波动率
            
            score = 0.0
            
            # 适中的波动性得分最高
            if 0.15 <= volatility <= 0.35:
                score = 100  # 优秀
            elif 0.10 <= volatility < 0.15 or 0.35 < volatility <= 0.50:
                score = 75   # 良好
            elif 0.05 <= volatility < 0.10 or 0.50 < volatility <= 0.70:
                score = 50   # 一般
            else:
                score = 25   # 较差
            
            return score
            
        except Exception as e:
            logger.warning(f"计算波动性评分失败: {e}")
            return 0.0
    
    def _calculate_liquidity_score(self, price_data: pd.DataFrame) -> float:
        """计算流动性评分"""
        try:
            if price_data.empty or 'volume' not in price_data.columns:
                return 50.0  # 默认中等评分
                
            # 计算平均成交量
            avg_volume = price_data['volume'].tail(20).mean()
            
            # 根据成交量大小评分（这里使用相对评分）
            if avg_volume > price_data['volume'].quantile(0.8):
                return 100
            elif avg_volume > price_data['volume'].quantile(0.6):
                return 75
            elif avg_volume > price_data['volume'].quantile(0.4):
                return 50
            else:
                return 25
                
        except Exception as e:
            logger.warning(f"计算流动性评分失败: {e}")
            return 50.0
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd_signal(self, prices: pd.Series) -> str:
        """计算MACD信号"""
        try:
            if len(prices) < 26:
                return "hold"
                
            # 简化的MACD计算
            ema_12 = prices.ewm(span=12).mean()
            ema_26 = prices.ewm(span=26).mean()
            macd_line = ema_12 - ema_26
            
            if len(macd_line) < 9:
                return "hold"
                
            signal_line = macd_line.ewm(span=9).mean()
            
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            
            if current_macd > current_signal:
                return "buy"
            else:
                return "sell"
                
        except Exception as e:
            logger.warning(f"计算MACD信号失败: {e}")
            return "hold"
    
    def _calculate_weights(
        self,
        selected_stocks: List[str],
        scores: Dict[str, float],
        criteria: StockSelectionCriteria
    ) -> Dict[str, float]:
        """计算权重分配"""
        if not selected_stocks:
            return {}
        
        # 根据评分计算权重
        total_score = sum(scores[stock] for stock in selected_stocks)
        
        if total_score == 0:
            # 平均分配
            weight = 1.0 / len(selected_stocks)
            return {stock: weight for stock in selected_stocks}
        
        weights = {}
        for stock in selected_stocks:
            weights[stock] = scores[stock] / total_score
        
        # 根据风险等级调整权重分散度
        if criteria.risk_level == RiskLevel.CONSERVATIVE:
            # 保守型：更均匀的权重分布
            avg_weight = 1.0 / len(selected_stocks)
            for stock in selected_stocks:
                weights[stock] = (weights[stock] + avg_weight) / 2
        
        return weights
    
    async def _generate_explanations(
        self,
        result: StockSelectionResult,
        error_collector: ErrorCollector
    ) -> List[SelectionExplanation]:
        """生成选股解释"""
        explanations = []
        
        # 使用AIExplainabilityService生成解释
        if self._explainability_service:
            for stock_code in result.selected_stocks:
                try:
                    explanation = await self._generate_explanation_with_service(stock_code, result)
                    explanations.append(explanation)
                except Exception as e:
                    error_collector.add_error(
                        error_type=ErrorType.EXPLANATION,
                        error_message=f"生成股票 {stock_code} 解释失败",
                        error_detail=str(e),
                        stock_code=stock_code,
                        severity=ErrorSeverity.MEDIUM
                    )
                    # 回退到原有实现
                    try:
                        explanation = await self._generate_single_explanation(stock_code, result)
                        explanations.append(explanation)
                    except Exception as fallback_error:
                        error_collector.add_error(
                            error_type=ErrorType.EXPLANATION,
                            error_message=f"回退解释生成失败: {stock_code}",
                            error_detail=str(fallback_error),
                            stock_code=stock_code,
                            severity=ErrorSeverity.MEDIUM
                        )
                        continue
        else:
            # 回退到原有实现
            for stock_code in result.selected_stocks:
                try:
                    explanation = await self._generate_single_explanation(stock_code, result)
                    explanations.append(explanation)
                except Exception as e:
                    error_collector.add_error(
                        error_type=ErrorType.EXPLANATION,
                        error_message=f"生成股票 {stock_code} 解释失败",
                        error_detail=str(e),
                        stock_code=stock_code,
                        severity=ErrorSeverity.MEDIUM
                    )
                    continue
        
        return explanations
    
    async def _generate_explanation_with_service(
        self,
        stock_code: str,
        result: StockSelectionResult
    ) -> SelectionExplanation:
        """使用AIExplainabilityService生成解释"""
        try:
            from .ai_explainability_service import ExplanationLevel
            
            # 获取股票数据
            stock_data = await self._get_stock_data_for_explanation(stock_code)
            
            # 构建选股数据
            selection_data = {
                'score': result.stock_scores.get(stock_code, 0.0),
                'criteria': asdict(result.criteria),
                'strategy': result.strategy_id,
                'selection_date': result.selection_date
            }
            
            # 确定解释级别
            explanation_level = ExplanationLevel.DETAILED
            
            # 调用AIExplainabilityService
            # selection_result_id 格式为 {result_id}_{stock_code}
            selection_result_id = f"{result.result_id}_{stock_code}"
            explanation_data = self._explainability_service.generate_explanation(
                stock_code=stock_code,
                stock_data=stock_data,
                selection_data=selection_data,
                explanation_level=explanation_level,
                selection_result_id=selection_result_id
            )
            
            # 转换为SelectionExplanation
            return self._convert_to_selection_explanation(explanation_data)
            
        except Exception as e:
            logger.error(f"使用AIExplainabilityService生成解释失败: {e}")
            raise
    
    async def _get_stock_data_for_explanation(self, stock_code: str) -> Dict[str, Any]:
        """获取用于解释的股票数据"""
        try:
            data_request = {
                "symbol": stock_code,
                "asset_type": AssetType.STOCK_A,
                "data_type": "kdata",
                "period": "D",
                "time_range": 365
            }
            
            price_data = await self._data_manager.get_data_async(**data_request)
            
            # 计算技术指标
            indicator_data = {}
            if price_data is not None and not price_data.empty:
                # RSI
                rsi = self._calculate_rsi(price_data['close'], 14)
                if not rsi.empty:
                    indicator_data['RSI'] = float(rsi.iloc[-1])
                
                # MACD
                macd_signal = self._calculate_macd_signal(price_data['close'])
                indicator_data['MACD'] = macd_signal
                
                # SMA
                sma_20 = price_data['close'].rolling(window=20).mean()
                if not sma_20.empty:
                    sma_20_current = float(sma_20.iloc[-1])
                    current_price = float(price_data['close'].iloc[-1])
                    indicator_data['SMA_20'] = round(current_price / sma_20_current, 2) if sma_20_current > 0 else 0
                
                # 成交量比率
                if 'volume' in price_data.columns:
                    avg_volume = price_data['volume'].tail(20).mean()
                    current_volume = float(price_data['volume'].iloc[-1])
                    indicator_data['Volume_Ratio'] = round(current_volume / avg_volume, 2) if avg_volume > 0 else 0
                
                # 价格趋势
                if len(price_data) >= 5:
                    price_change = (price_data['close'].iloc[-1] - price_data['close'].iloc[-5]) / price_data['close'].iloc[-5]
                    indicator_data['price_trend'] = "up" if price_change > 0 else "down"
                
                # 成交量趋势
                if 'volume' in price_data.columns and len(price_data) >= 5:
                    volume_change = (price_data['volume'].iloc[-1] - price_data['volume'].iloc[-5]) / price_data['volume'].iloc[-5]
                    indicator_data['volume_trend'] = "increasing" if volume_change > 0 else "decreasing"
            
            # 获取基本面数据
            fundamental_data = {}
            try:
                fundamental = await self._data_manager.get_fundamental_data(stock_code)
                if fundamental:
                    if 'pe_ratio' in fundamental:
                        fundamental_data['PE_RATIO'] = float(fundamental['pe_ratio'])
                    if 'pb_ratio' in fundamental:
                        fundamental_data['PB_RATIO'] = float(fundamental['pb_ratio'])
                    if 'roe' in fundamental:
                        fundamental_data['ROE'] = float(fundamental['roe'])
                    if 'debt_ratio' in fundamental:
                        fundamental_data['DEBT_RATIO'] = float(fundamental['debt_ratio'])
            except Exception as e:
                logger.warning(f"获取股票 {stock_code} 基本面数据失败: {e}")
            
            return {
                'name': stock_code,
                'price_data': price_data,
                'indicators': indicator_data,
                'fundamentals': fundamental_data
            }
            
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 数据失败: {e}")
            return {
                'name': stock_code,
                'price_data': None,
                'indicators': {},
                'fundamentals': {}
            }
    
    def _convert_to_selection_explanation(
        self,
        explanation_data
    ) -> SelectionExplanation:
        """转换解释数据为SelectionExplanation"""
        try:
            # 提取因子贡献
            key_indicators = {}
            technical_signals = {}
            fundamental_signals = {}
            
            for factor in explanation_data.factors:
                factor_name = factor.factor_name
                factor_value = factor.value
                
                key_indicators[factor_name] = factor_value
                
                if factor.category.value == 'technical':
                    technical_signals[factor_name] = {
                        'value': factor_value,
                        'contribution': factor.contribution_score,
                        'importance_rank': factor.importance_rank,
                        'weight': factor.weight
                    }
                elif factor.category.value == 'fundamental':
                    fundamental_signals[factor_name] = {
                        'value': factor_value,
                        'contribution': factor.contribution_score,
                        'importance_rank': factor.importance_rank,
                        'weight': factor.weight
                    }
            
            # 风险评估
            risk_assessment = {
                'overall_risk': 'moderate',
                'volatility': 'moderate',
                'liquidity': 'good'
            }
            
            # 推荐强度
            if explanation_data.confidence_score >= 0.8:
                recommendation_strength = "strong"
            elif explanation_data.confidence_score >= 0.6:
                recommendation_strength = "moderate"
            else:
                recommendation_strength = "weak"
            
            return SelectionExplanation(
                stock_code=explanation_data.stock_code,
                selection_reason=explanation_data.summary_text,
                score=explanation_data.selection_score,
                key_indicators=key_indicators,
                technical_signals=technical_signals,
                fundamental_signals=fundamental_signals,
                risk_assessment=risk_assessment,
                recommendation_strength=recommendation_strength
            )
            
        except Exception as e:
            logger.error(f"转换解释数据失败: {e}")
            raise

    
    async def _generate_single_explanation(
        self,
        stock_code: str,
        result: StockSelectionResult
    ) -> SelectionExplanation:
        """生成单个股票的选股解释"""
        
        score = result.stock_scores.get(stock_code, 0.0)
        
        # 生成选股原因
        if score >= 80:
            reason = f"技术指标表现优秀，综合评分{score:.1f}分"
            strength = "strong"
        elif score >= 60:
            reason = f"技术指标表现良好，综合评分{score:.1f}分"
            strength = "moderate"
        else:
            reason = f"符合基本选股条件，综合评分{score:.1f}分"
            strength = "weak"
        
        # 获取股票数据
        key_indicators = {}
        technical_signals = {}
        fundamental_signals = {}
        
        try:
            # 使用 EnhancedIndicatorService 获取技术指标
            data_request = {
                "symbol": stock_code,
                "asset_type": AssetType.STOCK_A,
                "data_type": "kdata",
                "period": "D",
                "time_range": 365
            }
            
            price_data = await self._data_manager.get_data_async(**data_request)
            
            if price_data is not None and not price_data.empty:
                # 计算真实的技术指标
                # RSI
                rsi = self._calculate_rsi(price_data['close'], 14)
                if not rsi.empty:
                    key_indicators["RSI"] = float(rsi.iloc[-1])
                
                # MACD
                macd_signal = self._calculate_macd_signal(price_data['close'])
                technical_signals["macd_signal"] = macd_signal
                
                # SMA
                sma_20 = price_data['close'].rolling(window=20).mean()
                if not sma_20.empty:
                    sma_20_current = float(sma_20.iloc[-1])
                    current_price = float(price_data['close'].iloc[-1])
                    key_indicators["SMA_20"] = round(current_price / sma_20_current, 2) if sma_20_current > 0 else 0
                
                # 成交量比率
                if 'volume' in price_data.columns:
                    avg_volume = price_data['volume'].tail(20).mean()
                    current_volume = float(price_data['volume'].iloc[-1])
                    key_indicators["Volume_Ratio"] = round(current_volume / avg_volume, 2) if avg_volume > 0 else 0
                
                # 价格趋势
                if len(price_data) >= 5:
                    price_change = (price_data['close'].iloc[-1] - price_data['close'].iloc[-5]) / price_data['close'].iloc[-5]
                    technical_signals["price_trend"] = "up" if price_change > 0 else "down"
                else:
                    technical_signals["price_trend"] = "neutral"
                
                # 成交量趋势
                if 'volume' in price_data.columns and len(price_data) >= 5:
                    volume_change = (price_data['volume'].iloc[-1] - price_data['volume'].iloc[-5]) / price_data['volume'].iloc[-5]
                    technical_signals["volume_trend"] = "increasing" if volume_change > 0 else "decreasing"
                else:
                    technical_signals["volume_trend"] = "neutral"
                
                # 支撑位和阻力位
                if len(price_data) >= 20:
                    recent_low = price_data['close'].tail(20).min()
                    recent_high = price_data['close'].tail(20).max()
                    current_price = float(price_data['close'].iloc[-1])
                    
                    distance_to_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
                    distance_to_high = (recent_high - current_price) / recent_high if recent_high > 0 else 0
                    
                    if distance_to_low < 0.05:
                        technical_signals["support_level"] = "strong"
                    elif distance_to_low < 0.10:
                        technical_signals["support_level"] = "moderate"
                    else:
                        technical_signals["support_level"] = "weak"
                    
                    if distance_to_high < 0.05:
                        technical_signals["resistance_level"] = "strong"
                    elif distance_to_high < 0.10:
                        technical_signals["resistance_level"] = "moderate"
                    else:
                        technical_signals["resistance_level"] = "weak"
                else:
                    technical_signals["support_level"] = "unknown"
                    technical_signals["resistance_level"] = "unknown"
            
            # 获取基本面数据
            try:
                fundamental_data = await self._data_manager.get_fundamental_data(stock_code)
                if fundamental_data:
                    if 'pe_ratio' in fundamental_data:
                        fundamental_signals["pe_ratio"] = float(fundamental_data['pe_ratio'])
                    if 'pb_ratio' in fundamental_data:
                        fundamental_signals["pb_ratio"] = float(fundamental_data['pb_ratio'])
                    if 'roe' in fundamental_data:
                        fundamental_signals["roe"] = float(fundamental_data['roe'])
                    if 'debt_ratio' in fundamental_data:
                        fundamental_signals["debt_ratio"] = float(fundamental_data['debt_ratio'])
            except Exception as e:
                logger.warning(f"获取股票 {stock_code} 基本面数据失败: {e}")
                
        except Exception as e:
            logger.warning(f"获取股票 {stock_code} 技术指标失败: {e}")
        
        # 如果没有获取到指标，使用默认值
        if not key_indicators:
            key_indicators = {
                "RSI": 50.0,
                "MACD": 0.0,
                "SMA_20": 1.0,
                "Volume_Ratio": 1.0
            }
        
        if not technical_signals:
            technical_signals = {
                "price_trend": "neutral",
                "volume_trend": "neutral",
                "support_level": "unknown",
                "resistance_level": "unknown"
            }
        
        if not fundamental_signals:
            fundamental_signals = {
                "pe_ratio": 0.0,
                "pb_ratio": 0.0,
                "roe": 0.0,
                "debt_ratio": 0.0
            }
        
        # 风险评估
        risk_assessment = {
            "volatility": "moderate",
            "liquidity": "good",
            "sector_risk": "low",
            "overall_risk": result.criteria.risk_level.value
        }
        
        # 计算波动性
        try:
            if price_data is not None and not price_data.empty and len(price_data) >= 20:
                returns = price_data['close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)
                
                if volatility < 0.15:
                    risk_assessment["volatility"] = "low"
                elif volatility < 0.35:
                    risk_assessment["volatility"] = "moderate"
                else:
                    risk_assessment["volatility"] = "high"
        except Exception:
            pass
        
        # 计算流动性
        try:
            if 'volume' in key_indicators and key_indicators["Volume_Ratio"] > 0:
                if key_indicators["Volume_Ratio"] >= 1.5:
                    risk_assessment["liquidity"] = "excellent"
                elif key_indicators["Volume_Ratio"] >= 1.0:
                    risk_assessment["liquidity"] = "good"
                else:
                    risk_assessment["liquidity"] = "moderate"
        except Exception:
            pass
        
        return SelectionExplanation(
            stock_code=stock_code,
            selection_reason=reason,
            score=score,
            key_indicators=key_indicators,
            technical_signals=technical_signals,
            fundamental_signals=fundamental_signals,
            risk_assessment=risk_assessment,
            recommendation_strength=strength
        )
    
    async def _generate_overall_explanation(
        self,
        result: StockSelectionResult
    ) -> str:
        """生成整体解释"""
        stock_count = len(result.selected_stocks)
        avg_score = np.mean(list(result.stock_scores.values())) if result.stock_scores else 0
        
        strategy_desc = {
            SelectionStrategy.MOMENTUM_BASED: "动量策略",
            SelectionStrategy.VALUE_BASED: "价值策略",
            SelectionStrategy.GROWTH_BASED: "成长策略",
            SelectionStrategy.QUALITY_BASED: "质量策略",
            SelectionStrategy.TECH_ANALYSIS: "技术分析策略",
            SelectionStrategy.QUANTITATIVE: "量化策略",
            SelectionStrategy.HYBRID: "混合策略"
        }
        
        strategy_name = strategy_desc.get(result.criteria.strategy_type, "量化策略")
        risk_name = result.criteria.risk_level.value
        
        explanation = f"""
本次选股采用{strategy_name}，风险偏好为{risk_name}。
共选出{stock_count}只股票，平均评分{avg_score:.1f}分。
选股主要基于技术指标分析、动量分析、波动性评估和流动性分析。
        """.strip()
        
        return explanation
    
    async def _calculate_portfolio_metrics(
        self,
        result: StockSelectionResult
    ) -> Dict[str, Any]:
        """计算组合指标"""
        if not result.selected_stocks:
            return {}
        
        weights = list(result.weights.values())
        
        metrics = {
            "stock_count": len(result.selected_stocks),
            "total_weight": sum(weights),
            "weight_concentration": max(weights) if weights else 0,
            "average_score": np.mean(list(result.stock_scores.values())),
            "score_std": np.std(list(result.stock_scores.values())),
            "top_weight_stock": result.selected_stocks[0] if result.selected_stocks else None,
            "top_weight": max(weights) if weights else 0
        }
        
        return metrics
    
    async def _save_strategy_to_db(self, strategy_data: Dict[str, Any]):
        """保存策略到数据库"""
        try:
            # 使用DatabaseService的save_ai_strategy方法
            if hasattr(self._database_service, 'save_ai_strategy'):
                await self._database_service.save_ai_strategy(strategy_data)
                logger.info(f"策略保存成功: {strategy_data['strategy_id']}")
            else:
                # 如果DatabaseService没有save_ai_strategy方法，使用通用保存方法
                await self._database_service.save_data(
                    'ai_strategies',
                    strategy_data
                )
                logger.info(f"策略保存成功（通用方法）: {strategy_data['strategy_id']}")
        except Exception as e:
            logger.error(f"保存策略到数据库失败: {e}")
            raise
    
    async def _get_strategy_by_id(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """根据ID或策略类型获取策略"""
        try:
            # 使用DatabaseService的get_ai_strategy方法
            if hasattr(self._database_service, 'get_ai_strategy'):
                strategy = await self._database_service.get_ai_strategy(strategy_id)
                return strategy
            else:
                # 如果DatabaseService没有get_ai_strategy方法，使用通用查询方法
                # 判断传入的是策略ID（UUID）还是策略类型
                # 策略ID通常是36字符的UUID，策略类型是简短的字符串
                if len(strategy_id) == 36 and '-' in strategy_id:
                    # 传入的是策略ID，使用id字段查询
                    query = "SELECT * FROM ai_strategies WHERE id = ?"
                else:
                    # 传入的是策略类型，使用strategy_type字段查询
                    query = "SELECT * FROM ai_strategies WHERE strategy_type = ?"
                
                strategy = self._database_service.fetch_one(query, [strategy_id])
                
                # 如果找不到策略，且传入的是策略类型，则创建默认策略配置
                if not strategy and len(strategy_id) != 36:
                    logger.info(f"未找到策略 {strategy_id}，创建默认策略配置")
                    strategy = self._create_default_strategy(strategy_id)
                
                return strategy
        except Exception as e:
            logger.error(f"从数据库获取策略失败: {e}")
            return None
    
    def _create_default_strategy(self, strategy_type: str) -> Dict[str, Any]:
        """创建默认策略配置
        
        Args:
            strategy_type: 策略类型
            
        Returns:
            默认策略配置字典
        """
        # 根据策略类型创建默认配置
        default_strategies = {
            "technical": {
                "id": strategy_type,
                "name": "技术分析策略",
                "description": "基于技术指标的分析策略",
                "strategy_type": strategy_type,
                "parameters": {},
                "criteria": {
                    "strategy_type": "technical",
                    "risk_level": "moderate",
                    "max_stocks": 50
                }
            },
            "momentum": {
                "id": strategy_type,
                "name": "动量策略",
                "description": "基于价格动量的选股策略",
                "strategy_type": strategy_type,
                "parameters": {},
                "criteria": {
                    "strategy_type": "momentum",
                    "risk_level": "moderate",
                    "max_stocks": 50
                }
            },
            "value": {
                "id": strategy_type,
                "name": "价值策略",
                "description": "基于价值投资的选股策略",
                "strategy_type": strategy_type,
                "parameters": {},
                "criteria": {
                    "strategy_type": "value",
                    "risk_level": "conservative",
                    "max_stocks": 50
                }
            },
            "growth": {
                "id": strategy_type,
                "name": "成长策略",
                "description": "基于成长性的选股策略",
                "strategy_type": strategy_type,
                "parameters": {},
                "criteria": {
                    "strategy_type": "growth",
                    "risk_level": "aggressive",
                    "max_stocks": 50
                }
            },
            "quality": {
                "id": strategy_type,
                "name": "质量策略",
                "description": "基于公司质量的选股策略",
                "strategy_type": strategy_type,
                "parameters": {},
                "criteria": {
                    "strategy_type": "quality",
                    "risk_level": "moderate",
                    "max_stocks": 50
                }
            },
            "dividend": {
                "id": strategy_type,
                "name": "股息策略",
                "description": "基于股息收益的选股策略",
                "strategy_type": strategy_type,
                "parameters": {},
                "criteria": {
                    "strategy_type": "dividend",
                    "risk_level": "conservative",
                    "max_stocks": 50
                }
            },
            "quantitative": {
                "id": strategy_type,
                "name": "量化策略",
                "description": "基于量化模型的选股策略",
                "strategy_type": strategy_type,
                "parameters": {},
                "criteria": {
                    "strategy_type": "quantitative",
                    "risk_level": "moderate",
                    "max_stocks": 50
                }
            },
            "hybrid": {
                "id": strategy_type,
                "name": "混合策略",
                "description": "综合多种策略的选股策略",
                "strategy_type": strategy_type,
                "parameters": {},
                "criteria": {
                    "strategy_type": "hybrid",
                    "risk_level": "moderate",
                    "max_stocks": 50
                }
            }
        }
        
        # 返回默认策略配置，如果策略类型未知，则使用量化策略作为默认
        return default_strategies.get(strategy_type, default_strategies["quantitative"])
    
    async def _save_selection_result(self, result: StockSelectionResult):
        """保存选股结果"""
        try:
            # 将 StockSelectionResult 转换为多条单只股票的记录
            results_to_save = []
            
            for stock_code in result.selected_stocks:
                stock_result = {
                    'id': f"{result.result_id}_{stock_code}",  # 使用 result_id + stock_code 作为唯一ID
                    'strategy_id': result.strategy_id,
                    'selection_date': result.selection_date,
                    'stock_code': stock_code,
                    'stock_name': '',  # 可以从其他数据源获取
                    'industry': '',  # 可以从其他数据源获取
                    'selection_reason': {
                        'overall_explanation': result.overall_explanation,
                        'criteria': asdict(result.criteria)
                    },
                    'score': result.stock_scores.get(stock_code, 0.0),
                    'weight': result.weights.get(stock_code, 0.0),
                    'confidence': 0.0,  # 可以从其他数据源获取
                    'risk_level': result.criteria.risk_level.value if result.criteria.risk_level else 'moderate',
                    'expected_return': 0.0,  # 可以从其他数据源获取
                    'volatility': 0.0,  # 可以从其他数据源获取
                    'sharpe_ratio': 0.0,  # 可以从其他数据源获取
                    'max_drawdown': 0.0,  # 可以从其他数据源获取
                    'market_cap': 0.0,  # 可以从其他数据源获取
                    'pe_ratio': 0.0,  # 可以从其他数据源获取
                    'pb_ratio': 0.0,  # 可以从其他数据源获取
                    'turnover_rate': 0.0,  # 可以从其他数据源获取
                    'backtested': False
                }
                results_to_save.append(stock_result)
            
            # 保存所有股票的选股结果
            if results_to_save:
                self._database_service.save_ai_selection_results(results_to_save)
            
            logger.info(f"成功保存选股结果: {result.result_id}, 共 {len(results_to_save)} 只股票")
        except Exception as e:
            logger.error(f"保存选股结果失败: {e}")
            raise
    
    def _get_cached_result(self, cache_key: str) -> Optional[StockSelectionResult]:
        """获取缓存结果"""
        return self._cache_service.get(cache_key)
    
    def _cache_result(self, cache_key: str, result: StockSelectionResult):
        """缓存结果"""
        self._cache_service.set(cache_key, result, ttl=timedelta(hours=1))
    
    # 其他策略实现方法
    def _momentum_strategy(
        self,
        stock_data: Dict[str, Dict[str, Any]],
        criteria: StockSelectionCriteria
    ) -> Tuple[List[str], Dict[str, float]]:
        """动量策略实现
        
        基于价格动量和趋势的选股策略
        """
        stock_scores = {}
        
        for stock_code, data in stock_data.items():
            try:
                price_data = data["price_data"]
                if price_data.empty or len(price_data) < 30:
                    continue
                
                score = 0.0
                
                # 短期动量 (30%)
                momentum_5d = price_data['close'].pct_change(5)
                momentum_10d = price_data['close'].pct_change(10)
                momentum_20d = price_data['close'].pct_change(20)
                
                if not momentum_5d.empty:
                    score += min(momentum_5d.iloc[-1] * 100, 30) * 0.3
                if not momentum_10d.empty:
                    score += min(momentum_10d.iloc[-1] * 100, 30) * 0.15
                if not momentum_20d.empty:
                    score += min(momentum_20d.iloc[-1] * 100, 30) * 0.15
                
                # 趋势强度 (25%)
                sma_20 = price_data['close'].rolling(window=20).mean()
                sma_60 = price_data['close'].rolling(window=60).mean()
                
                if not sma_20.empty and not sma_60.empty:
                    current_price = price_data['close'].iloc[-1]
                    sma_20_current = sma_20.iloc[-1]
                    sma_60_current = sma_60.iloc[-1]
                    
                    # 价格在均线之上
                    if current_price > sma_20_current:
                        score += 10
                    if current_price > sma_60_current:
                        score += 10
                    
                    # 均线多头排列
                    if sma_20_current > sma_60_current:
                        score += 5
                
                # 动量一致性 (20%)
                if not momentum_5d.empty and not momentum_10d.empty:
                    if momentum_5d.iloc[-1] > 0 and momentum_10d.iloc[-1] > 0:
                        score += 10
                    if momentum_5d.iloc[-1] > momentum_10d.iloc[-1]:
                        score += 10
                
                # 成交量动量 (15%)
                if 'volume' in price_data.columns:
                    volume_sma_20 = price_data['volume'].rolling(window=20).mean()
                    if not volume_sma_20.empty:
                        current_volume = price_data['volume'].iloc[-1]
                        volume_ratio = current_volume / volume_sma_20.iloc[-1]
                        score += min(volume_ratio * 5, 15)
                
                # 相对强弱 (10%)
                rsi = self._calculate_rsi(price_data['close'], 14)
                if not rsi.empty:
                    rsi_current = rsi.iloc[-1]
                    # RSI 在 50-70 之间表示强势但不超买
                    if 50 <= rsi_current <= 70:
                        score += 10
                    elif 40 <= rsi_current < 50:
                        score += 5
                
                stock_scores[stock_code] = min(score, 100.0)
                
            except Exception as e:
                logger.warning(f"计算股票 {stock_code} 动量评分失败: {e}")
                continue
        
        # 选择评分最高的股票
        sorted_stocks = sorted(stock_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 根据风险等级确定选择数量
        if criteria.risk_level == RiskLevel.CONSERVATIVE:
            top_n = min(10, len(sorted_stocks))
        elif criteria.risk_level == RiskLevel.MODERATE:
            top_n = min(20, len(sorted_stocks))
        else:  # AGGRESSIVE
            top_n = min(30, len(sorted_stocks))
        
        selected_stocks = [stock for stock, _ in sorted_stocks[:top_n]]
        selected_scores = {stock: stock_scores[stock] for stock in selected_stocks}
        
        return selected_stocks, selected_scores
    
    def _value_strategy(
        self,
        stock_data: Dict[str, Dict[str, Any]],
        criteria: StockSelectionCriteria
    ) -> Tuple[List[str], Dict[str, float]]:
        """价值策略实现
        
        基于估值指标的选股策略
        """
        stock_scores = {}
        
        for stock_code, data in stock_data.items():
            try:
                fundamental_data = data.get("fundamental_data", {})
                
                score = 0.0
                
                # PE 估值 (30%)
                pe_ratio = fundamental_data.get('pe_ratio', 0)
                if pe_ratio > 0:
                    # PE 越低越好，10-20 为合理区间
                    if pe_ratio < 10:
                        score += 30
                    elif pe_ratio < 15:
                        score += 25
                    elif pe_ratio < 20:
                        score += 20
                    elif pe_ratio < 30:
                        score += 10
                    elif pe_ratio < 50:
                        score += 5
                
                # PB 估值 (25%)
                pb_ratio = fundamental_data.get('pb_ratio', 0)
                if pb_ratio > 0:
                    # PB 越低越好，1-3 为合理区间
                    if pb_ratio < 1:
                        score += 25
                    elif pb_ratio < 2:
                        score += 20
                    elif pb_ratio < 3:
                        score += 15
                    elif pb_ratio < 5:
                        score += 10
                    elif pb_ratio < 8:
                        score += 5
                
                # 股息率 (20%)
                dividend_yield = fundamental_data.get('dividend_yield', 0)
                if dividend_yield > 0:
                    # 股息率越高越好
                    if dividend_yield > 0.05:  # > 5%
                        score += 20
                    elif dividend_yield > 0.03:  # > 3%
                        score += 15
                    elif dividend_yield > 0.02:  # > 2%
                        score += 10
                    elif dividend_yield > 0.01:  # > 1%
                        score += 5
                
                # 市净率相对行业 (15%)
                industry_pb = fundamental_data.get('industry_pb', 0)
                if industry_pb > 0 and pb_ratio > 0:
                    pb_ratio_to_industry = pb_ratio / industry_pb
                    if pb_ratio_to_industry < 0.8:
                        score += 15
                    elif pb_ratio_to_industry < 1.0:
                        score += 10
                    elif pb_ratio_to_industry < 1.2:
                        score += 5
                
                # 自由现金流 (10%)
                fcf_yield = fundamental_data.get('fcf_yield', 0)
                if fcf_yield > 0:
                    if fcf_yield > 0.05:  # > 5%
                        score += 10
                    elif fcf_yield > 0.03:  # > 3%
                        score += 7
                    elif fcf_yield > 0.02:  # > 2%
                        score += 5
                
                stock_scores[stock_code] = min(score, 100.0)
                
            except Exception as e:
                logger.warning(f"计算股票 {stock_code} 价值评分失败: {e}")
                continue
        
        # 选择评分最高的股票
        sorted_stocks = sorted(stock_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 根据风险等级确定选择数量
        if criteria.risk_level == RiskLevel.CONSERVATIVE:
            top_n = min(10, len(sorted_stocks))
        elif criteria.risk_level == RiskLevel.MODERATE:
            top_n = min(20, len(sorted_stocks))
        else:  # AGGRESSIVE
            top_n = min(30, len(sorted_stocks))
        
        selected_stocks = [stock for stock, _ in sorted_stocks[:top_n]]
        selected_scores = {stock: stock_scores[stock] for stock in selected_stocks}
        
        return selected_stocks, selected_scores
    
    def _growth_strategy(
        self,
        stock_data: Dict[str, Dict[str, Any]],
        criteria: StockSelectionCriteria
    ) -> Tuple[List[str], Dict[str, float]]:
        """成长策略实现
        
        基于成长性指标的选股策略
        """
        stock_scores = {}
        
        for stock_code, data in stock_data.items():
            try:
                fundamental_data = data.get("fundamental_data", {})
                price_data = data.get("price_data")
                
                score = 0.0
                
                # 营收增长率 (30%)
                revenue_growth = fundamental_data.get('revenue_growth', 0)
                if revenue_growth > 0:
                    if revenue_growth > 0.30:  # > 30%
                        score += 30
                    elif revenue_growth > 0.20:  # > 20%
                        score += 25
                    elif revenue_growth > 0.15:  # > 15%
                        score += 20
                    elif revenue_growth > 0.10:  # > 10%
                        score += 15
                    elif revenue_growth > 0.05:  # > 5%
                        score += 10
                
                # 净利润增长率 (30%)
                profit_growth = fundamental_data.get('profit_growth', 0)
                if profit_growth > 0:
                    if profit_growth > 0.30:  # > 30%
                        score += 30
                    elif profit_growth > 0.20:  # > 20%
                        score += 25
                    elif profit_growth > 0.15:  # > 15%
                        score += 20
                    elif profit_growth > 0.10:  # > 10%
                        score += 15
                    elif profit_growth > 0.05:  # > 5%
                        score += 10
                
                # ROE (20%)
                roe = fundamental_data.get('roe', 0)
                if roe > 0:
                    if roe > 0.20:  # > 20%
                        score += 20
                    elif roe > 0.15:  # > 15%
                        score += 15
                    elif roe > 0.10:  # > 10%
                        score += 10
                    elif roe > 0.05:  # > 5%
                        score += 5
                
                # 价格动量 (10%)
                if price_data is not None and not price_data.empty:
                    momentum_20d = price_data['close'].pct_change(20)
                    if not momentum_20d.empty and momentum_20d.iloc[-1] > 0:
                        score += min(momentum_20d.iloc[-1] * 100, 10)
                
                # 行业成长性 (10%)
                industry_growth = fundamental_data.get('industry_growth', 0)
                if industry_growth > 0:
                    if industry_growth > 0.20:  # > 20%
                        score += 10
                    elif industry_growth > 0.15:  # > 15%
                        score += 7
                    elif industry_growth > 0.10:  # > 10%
                        score += 5
                
                stock_scores[stock_code] = min(score, 100.0)
                
            except Exception as e:
                logger.warning(f"计算股票 {stock_code} 成长评分失败: {e}")
                continue
        
        # 选择评分最高的股票
        sorted_stocks = sorted(stock_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 根据风险等级确定选择数量
        if criteria.risk_level == RiskLevel.CONSERVATIVE:
            top_n = min(10, len(sorted_stocks))
        elif criteria.risk_level == RiskLevel.MODERATE:
            top_n = min(20, len(sorted_stocks))
        else:  # AGGRESSIVE
            top_n = min(30, len(sorted_stocks))
        
        selected_stocks = [stock for stock, _ in sorted_stocks[:top_n]]
        selected_scores = {stock: stock_scores[stock] for stock in selected_stocks}
        
        return selected_stocks, selected_scores
    
    def _quality_strategy(
        self,
        stock_data: Dict[str, Dict[str, Any]],
        criteria: StockSelectionCriteria
    ) -> Tuple[List[str], Dict[str, float]]:
        """质量策略实现
        
        基于财务质量的选股策略
        """
        stock_scores = {}
        
        for stock_code, data in stock_data.items():
            try:
                fundamental_data = data.get("fundamental_data", {})
                
                score = 0.0
                
                # ROE (25%)
                roe = fundamental_data.get('roe', 0)
                if roe > 0:
                    if roe > 0.20:  # > 20%
                        score += 25
                    elif roe > 0.15:  # > 15%
                        score += 20
                    elif roe > 0.10:  # > 10%
                        score += 15
                    elif roe > 0.05:  # > 5%
                        score += 10
                
                # ROA (20%)
                roa = fundamental_data.get('roa', 0)
                if roa > 0:
                    if roa > 0.10:  # > 10%
                        score += 20
                    elif roa > 0.08:  # > 8%
                        score += 15
                    elif roa > 0.05:  # > 5%
                        score += 10
                    elif roa > 0.03:  # > 3%
                        score += 5
                
                # 资产负债率 (20%)
                debt_ratio = fundamental_data.get('debt_ratio', 1.0)
                if debt_ratio < 0.3:  # < 30%
                    score += 20
                elif debt_ratio < 0.5:  # < 50%
                    score += 15
                elif debt_ratio < 0.7:  # < 70%
                    score += 10
                elif debt_ratio < 0.8:  # < 80%
                    score += 5
                
                # 现金流 (15%)
                operating_cash_flow = fundamental_data.get('operating_cash_flow', 0)
                if operating_cash_flow > 0:
                    if operating_cash_flow > 1000000000:  # > 10亿
                        score += 15
                    elif operating_cash_flow > 500000000:  # > 5亿
                        score += 10
                    elif operating_cash_flow > 100000000:  # > 1亿
                        score += 5
                
                # 利润质量 (10%)
                net_profit = fundamental_data.get('net_profit', 0)
                gross_profit = fundamental_data.get('gross_profit', 0)
                if gross_profit > 0:
                    profit_margin = net_profit / gross_profit
                    if profit_margin > 0.30:  # > 30%
                        score += 10
                    elif profit_margin > 0.20:  # > 20%
                        score += 7
                    elif profit_margin > 0.10:  # > 10%
                        score += 5
                
                # 分红稳定性 (10%)
                dividend_growth = fundamental_data.get('dividend_growth', 0)
                if dividend_growth > 0:
                    if dividend_growth > 0.10:  # > 10%
                        score += 10
                    elif dividend_growth > 0.05:  # > 5%
                        score += 7
                    elif dividend_growth > 0.02:  # > 2%
                        score += 5
                
                stock_scores[stock_code] = min(score, 100.0)
                
            except Exception as e:
                logger.warning(f"计算股票 {stock_code} 质量评分失败: {e}")
                continue
        
        # 选择评分最高的股票
        sorted_stocks = sorted(stock_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 根据风险等级确定选择数量
        if criteria.risk_level == RiskLevel.CONSERVATIVE:
            top_n = min(10, len(sorted_stocks))
        elif criteria.risk_level == RiskLevel.MODERATE:
            top_n = min(20, len(sorted_stocks))
        else:  # AGGRESSIVE
            top_n = min(30, len(sorted_stocks))
        
        selected_stocks = [stock for stock, _ in sorted_stocks[:top_n]]
        selected_scores = {stock: stock_scores[stock] for stock in selected_stocks}
        
        return selected_stocks, selected_scores
    
    def _technical_strategy(self, stock_data: Dict[str, Dict[str, Any]], criteria: StockSelectionCriteria) -> Tuple[List[str], Dict[str, float]]:
        """技术分析策略实现"""
        return self._quantitative_strategy(stock_data, criteria)
    
    def _hybrid_strategy(self, stock_data: Dict[str, Dict[str, Any]], criteria: StockSelectionCriteria) -> Tuple[List[str], Dict[str, float]]:
        """混合策略实现"""
        return self._quantitative_strategy(stock_data, criteria)
    
    def select_stocks(
        self,
        criteria: StockSelectionCriteria,
        strategy: SelectionStrategy,
        error_collector: Optional[ErrorCollector] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        同步选股方法，用于UI调用
        
        Args:
            criteria: 选股标准
            strategy: 选股策略
            error_collector: 错误收集器
            progress_callback: 进度回调函数 callback(progress_percent, status_message)
            
        Returns:
            选股结果字典
        """
        try:
            import asyncio
            
            logger.info(f"开始选股: 策略={strategy.value}, 日期={criteria.selection_date}")
            
            result = asyncio.run(
                self.select_stocks_with_explanation(
                    strategy_id=strategy.value,
                    criteria=criteria,
                    error_collector=error_collector,
                    progress_callback=progress_callback
                )
            )
            
            # 获取详细评分数据
            detailed_scores = {}
            if result.portfolio_metrics and isinstance(result.portfolio_metrics, dict):
                detailed_scores = result.portfolio_metrics.get("detailed_scores", {})
            
            return {
                "success": True,
                "data": {
                    "result_id": result.result_id,
                    "strategy_id": result.strategy_id,
                    "selection_date": result.selection_date,
                    "status": result.status.value if result.status else "completed",
                    "selected_stocks": result.selected_stocks,
                    "stock_scores": result.stock_scores,
                    "detailed_scores": detailed_scores,
                    "weights": result.weights,
                    "explanations": [
                        {
                            "stock_code": exp.stock_code,
                            "selection_reason": exp.selection_reason,
                            "score": exp.score,
                            "key_indicators": exp.key_indicators,
                            "technical_signals": exp.technical_signals,
                            "fundamental_signals": exp.fundamental_signals,
                            "risk_assessment": exp.risk_assessment,
                            "recommendation_strength": exp.recommendation_strength
                        }
                        for exp in result.explanations
                    ],
                    "overall_explanation": result.overall_explanation,
                    "portfolio_metrics": result.portfolio_metrics,
                    "computation_time": result.computation_time,
                    "error_summary": error_collector.get_summary() if error_collector else None
                }
            }
        except Exception as e:
            logger.error(f"选股失败: {e}")
            logger.error(traceback.format_exc())
            
            # 记录到错误收集器
            if error_collector:
                error_collector.add_error(
                    error_type=ErrorType.STRATEGY,
                    error_message=f"选股失败: {str(e)}",
                    error_detail=traceback.format_exc(),
                    severity=ErrorSeverity.CRITICAL
                )
            
            return {
                "success": False,
                "error": str(e),
                "error_summary": error_collector.get_summary() if error_collector else None
            }
    
    def shutdown(self):
        """关闭服务"""
        if self._executor:
            self._executor.shutdown(wait=True)
        logger.info("AI选股集成服务已关闭")


# 便捷函数
def get_ai_selection_service() -> Optional[AISelectionIntegrationService]:
    """获取AI选股服务实例"""
    try:
        container = get_service_container()
        if container and container.is_registered(AISelectionIntegrationService):
            return container.resolve(AISelectionIntegrationService)
        return None
    except Exception as e:
        logger.error(f"获取AI选股服务失败: {e}")
        return None