from loguru import logger
"""
api_server.py
RESTful API主服务

用法示例：
    # 启动API服务
    python api_server.py
    # 获取股票列表
    curl http://localhost:8000/api/stock/list
    # 回测
    curl -X POST http://localhost:8000/api/backtest -H "Content-Type: application/json" -d '{"code": "sh600000", "strategy": "MA"}'
    # 获取板块资金流排行榜
    curl http://localhost:8000/api/sector/fund-flow/ranking?date_range=today&sort_by=main_net_inflow
    # 获取板块历史趋势
    curl http://localhost:8000/api/sector/fund-flow/trend/BK0001?period=30
    # 获取板块分时资金流
    curl http://localhost:8000/api/sector/fund-flow/intraday/BK0001?date=2024-01-01
    # 混合推荐
    curl -X POST http://localhost:8000/api/hybrid/recommendation -H "Content-Type: application/json" -d '{"user_id": "user_1", "context": {"risk_level": "medium"}, "stock_codes": ["000001", "000002"]}'
"""
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import uvicorn
import asyncio
import time
from core.services.ai_stock_selector_service import AIStockSelector
import pandas as pd
from datetime import datetime
from core.services.unified_data_manager import UnifiedDataManager
from utils.data_preprocessing import kdata_preprocess as _kdata_preprocess
import numpy as np

# 假设有全局data_manager实例
from core.services.unified_data_manager import get_unified_data_manager
from core.services.hybrid_recommendation_engine import HybridRecommendationEngine
from core.containers import get_service_container
from core.services.strategy_service import StrategyService

data_manager = get_unified_data_manager()

# 获取混合推荐引擎实例
async def get_hybrid_engine():
    """获取混合推荐引擎实例"""
    try:
        container = get_service_container()
        if container:
            engine = container.get_service('hybrid_recommendation_engine')
            if engine and hasattr(engine, 'is_initialized') and engine.is_initialized:
                return engine
        return None
    except Exception as e:
        logger.error(f"获取混合推荐引擎失败: {e}")
        return None

# 获取策略服务实例
def get_strategy_service() -> Optional[StrategyService]:
    """获取策略服务实例"""
    try:
        container = get_service_container()
        if container:
            service = container.get_service('strategy_service')
            if service:
                return service
        return None
    except Exception as e:
        logger.error(f"获取策略服务失败: {e}")
        return None

app = FastAPI(title="FactorWeave-Quant量化交易API", version="1.0.0")


@app.get("/")
def read_root():
    return {"message": "FactorWeave-Quant量化交易API服务"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "FactorWeave-Quant UI API"}


@app.get("/api/stock/list", response_model=List[Dict[str, Any]])
def get_stock_list():
    """
    获取股票列表
    返回：
        List[Dict]，每个dict包含code、name、market等字段
    """
    df = data_manager.get_stock_list()
    if df is not None and not df.empty:
        return df.to_dict(orient="records")
    return []


@app.post("/api/backtest")
def run_backtest(params: Dict[str, Any]):
    """
    执行回测
    参数：
        params: 包含code、strategy、参数等
    返回：
        dict，包含回测结果和性能指标
    """
    # TODO: 调用回测引擎
    return {"result": "success", "metrics": {}}


@app.post("/api/analyze")
def run_analysis(params: Dict[str, Any]):
    """
    执行分析
    参数：
        params: 分析参数
    返回：
        dict，包含分析结果
    """
    # TODO: 调用分析引擎
    return {"result": "success", "analysis": {}}


@app.post("/api/ai/select_stocks")
def ai_select_stocks(params: Dict[str, Any]):
    """
    AI智能选股API
    参数：
        params: {
            'stock_data': List[Dict],  # 股票特征数据（DataFrame转dict）
            'criteria': Dict,          # 选股条件
            'model_type': str          # 选股模型类型，可选
        }
    返回：
        dict: {'selected': [股票代码], 'explanations': {代码: 理由}}
    """
    stock_data = params.get('stock_data', [])
    criteria = params.get('criteria', {})
    model_type = params.get('model_type', 'ml')
    if not stock_data:
        return {"selected": [], "explanations": {}}
    df = pd.DataFrame(stock_data)
    df = _kdata_preprocess(df, context="API选股")
    if df is None or df.empty:
        return {"selected": [], "explanations": {}, "error": "数据全部无效或缺失关键字段"}
    selector = AIStockSelector(model_type=model_type)
    selected = selector.select_stocks(df, criteria)
    explanations = {code: selector.explain_selection(
        code) for code in selected}
    return {"selected": selected, "explanations": explanations}


@app.post("/api/ai/recommend_strategy")
def ai_recommend_strategy(params: Dict[str, Any]):
    """
    AI策略推荐API - 基于历史性能和市场条件的智能推荐
    
    参数：
        params: {
            'candidate_strategies': List[str],  # 候选策略列表（可选，默认使用所有可用策略）
            'market_condition': str,            # 市场条件（可选）：'bull', 'bear', 'sideways'
            'risk_preference': str,             # 风险偏好（可选）：'conservative', 'moderate', 'aggressive'
            'time_horizon': str,                # 投资周期（可选）：'short', 'medium', 'long'
        }
    返回：
        dict: {
            'recommended': 策略名,
            'confidence': 置信度(0-1),
            'reason': 推荐理由,
            'market_analysis': 市场分析,
            'strategy_scores': 各策略评分,
            'risk_metrics': 风险指标
        }
    """
    try:
        logger.info("开始AI策略推荐...")
        
        # 获取策略服务
        strategy_service = get_strategy_service()
        if not strategy_service:
            logger.warning("策略服务不可用，使用默认推荐")
            strategies = params.get('candidate_strategies', ['MA', 'MACD', 'RSI'])
            recommended = strategies[0] if strategies else 'MA'
            return {
                "recommended": recommended,
                "confidence": 0.5,
                "reason": "策略服务不可用，返回默认策略",
                "market_analysis": "无法分析",
                "strategy_scores": {},
                "risk_metrics": {}
            }
        
        # 获取候选策略列表
        candidate_strategies = params.get('candidate_strategies')
        if not candidate_strategies:
            # 如果没有指定候选策略，获取所有可用策略
            all_strategies = []
            try:
                # 从策略服务获取所有策略ID
                if hasattr(strategy_service, '_strategy_configs'):
                    all_strategies = list(strategy_service._strategy_configs.keys())
                logger.info(f"获取到 {len(all_strategies)} 个可用策略")
            except Exception as e:
                logger.error(f"获取策略列表失败: {e}")
            
            candidate_strategies = all_strategies if all_strategies else ['MA', 'MACD', 'RSI']
        
        logger.info(f"候选策略: {candidate_strategies}")
        
        # 评估每个候选策略的性能
        strategy_scores = {}
        strategy_evaluations = {}
        
        for strategy_id in candidate_strategies:
            try:
                evaluation = strategy_service.evaluate_strategy_performance(strategy_id)
                if evaluation:
                    strategy_evaluations[strategy_id] = evaluation
                    
                    # 计算综合评分
                    perf_stats = evaluation.get('performance_stats', {})
                    avg_return = perf_stats.get('avg_total_return', 0)
                    avg_sharpe = perf_stats.get('avg_sharpe_ratio', 0)
                    avg_drawdown = perf_stats.get('avg_max_drawdown', 0)
                    consistency = evaluation.get('consistency_score', 0)
                    risk_adj_return = evaluation.get('risk_adjusted_return', 0)
                    
                    # 综合评分公式（可调整权重）
                    score = (
                        0.3 * avg_return +
                        0.25 * avg_sharpe +
                        0.2 * consistency +
                        0.25 * risk_adj_return
                    )
                    
                    # 考虑最大回撤的惩罚
                    if avg_drawdown > 0.3:  # 如果最大回撤超过30%
                        score *= 0.7
                    
                    strategy_scores[strategy_id] = {
                        'score': round(score, 4),
                        'avg_return': round(avg_return, 4),
                        'sharpe_ratio': round(avg_sharpe, 4),
                        'max_drawdown': round(avg_drawdown, 4),
                        'consistency': round(consistency, 4),
                        'risk_adjusted_return': round(risk_adj_return, 4)
                    }
                    
                    logger.info(f"策略 {strategy_id} 评分: {score:.4f}")
                else:
                    # 如果没有历史数据，给一个基础评分
                    strategy_scores[strategy_id] = {
                        'score': 0.5,
                        'avg_return': 0,
                        'sharpe_ratio': 0,
                        'max_drawdown': 0,
                        'consistency': 0.5,
                        'risk_adjusted_return': 0,
                        'note': '无历史数据'
                    }
            except Exception as e:
                logger.error(f"评估策略 {strategy_id} 失败: {e}")
                strategy_scores[strategy_id] = {
                    'score': 0.3,
                    'error': str(e)
                }
        
        # 根据风险偏好调整评分
        risk_preference = params.get('risk_preference', 'moderate')
        if risk_preference == 'conservative':
            # 保守型：更看重稳定性和低回撤
            for strategy_id, scores in strategy_scores.items():
                if 'max_drawdown' in scores and scores['max_drawdown'] < 0.15:
                    scores['score'] *= 1.2
                elif 'max_drawdown' in scores and scores['max_drawdown'] > 0.25:
                    scores['score'] *= 0.7
        elif risk_preference == 'aggressive':
            # 激进型：更看重收益
            for strategy_id, scores in strategy_scores.items():
                if 'avg_return' in scores and scores['avg_return'] > 0.2:
                    scores['score'] *= 1.2
                elif 'avg_return' in scores and scores['avg_return'] < 0.1:
                    scores['score'] *= 0.8
        
        # 选择得分最高的策略
        if not strategy_scores:
            logger.warning("所有策略评估失败，返回默认策略")
            recommended = candidate_strategies[0] if candidate_strategies else 'MA'
            confidence = 0.3
            reason = "所有策略评估失败，返回默认策略"
        else:
            # 按评分排序
            sorted_strategies = sorted(
                strategy_scores.items(),
                key=lambda x: x[1].get('score', 0),
                reverse=True
            )
            
            recommended = sorted_strategies[0][0]
            recommended_score = sorted_strategies[0][1].get('score', 0)
            
            # 计算置信度
            max_score = max(s.get('score', 0) for s in strategy_scores.values())
            min_score = min(s.get('score', 0) for s in strategy_scores.values())
            score_range = max_score - min_score
            
            if score_range > 0:
                confidence = (recommended_score - min_score) / score_range
            else:
                confidence = 0.5
            
            # 生成推荐理由
            top_scores = sorted_strategies[:3]
            reason_parts = []
            reason_parts.append(f"基于 {len(candidate_strategies)} 个候选策略的综合评估")
            
            if recommended_score > 0.8:
                reason_parts.append(f"策略 {recommended} 表现优异，综合评分 {recommended_score:.2f}")
            elif recommended_score > 0.6:
                reason_parts.append(f"策略 {recommended} 表现良好，综合评分 {recommended_score:.2f}")
            else:
                reason_parts.append(f"策略 {recommended} 相对较优，综合评分 {recommended_score:.2f}")
            
            # 添加关键指标
            rec_metrics = strategy_scores[recommended]
            if 'avg_return' in rec_metrics:
                reason_parts.append(f"平均收益率 {rec_metrics['avg_return']*100:.2f}%")
            if 'sharpe_ratio' in rec_metrics:
                reason_parts.append(f"夏普比率 {rec_metrics['sharpe_ratio']:.2f}")
            if 'max_drawdown' in rec_metrics:
                reason_parts.append(f"最大回撤 {rec_metrics['max_drawdown']*100:.2f}%")
            
            reason = "，".join(reason_parts) + "。"
            
            logger.info(f"推荐策略: {recommended}, 置信度: {confidence:.2f}")
        
        # 市场分析（简化版）
        market_condition = params.get('market_condition', 'unknown')
        market_analysis = {
            'condition': market_condition,
            'timestamp': datetime.now().isoformat(),
            'note': '市场条件分析功能待完善'
        }
        
        # 风险指标
        risk_metrics = {}
        if recommended in strategy_evaluations:
            eval_data = strategy_evaluations[recommended]
            perf_stats = eval_data.get('performance_stats', {})
            risk_metrics = {
                'max_drawdown': perf_stats.get('avg_max_drawdown', 0),
                'volatility': perf_stats.get('std_total_return', 0),
                'consistency': eval_data.get('consistency_score', 0)
            }
        
        return {
            "recommended": recommended,
            "confidence": round(confidence, 2),
            "reason": reason,
            "market_analysis": market_analysis,
            "strategy_scores": strategy_scores,
            "risk_metrics": risk_metrics,
            "recommendation_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI策略推荐失败: {e}")
        # 返回默认推荐
        strategies = params.get('candidate_strategies', ['MA', 'MACD', 'RSI'])
        recommended = strategies[0] if strategies else 'MA'
        return {
            "recommended": recommended,
            "confidence": 0.3,
            "reason": f"推荐过程出错: {str(e)}，返回默认策略",
            "market_analysis": {},
            "strategy_scores": {},
            "risk_metrics": {},
            "error": str(e)
        }


@app.post("/api/ai/optimize_params")
def ai_optimize_params(params: Dict[str, Any]):
    """
    AI参数优化API
    参数：
        params: {
            'strategy': str,           # 策略名
            'param_space': Dict,       # 参数空间（如{'fast': [5,10,20], 'slow': [20,50,100]}）
            'history': List[Dict]      # 历史数据
        }
    返回：
        dict: {'best_params': 最优参数, 'history': 优化过程}
    """
    # TODO: 实现AI参数优化逻辑（如网格搜索、贝叶斯优化等）
    # 这里简单返回第一个参数组合
    param_space = params.get(
        'param_space', {'fast': [5, 10], 'slow': [20, 50]})
    best_params = {k: v[0]
                   for k, v in param_space.items() if isinstance(v, list) and v}
    return {"best_params": best_params, "history": [best_params]}


@app.post("/api/ai/diagnosis")
def ai_diagnosis(params: Dict[str, Any]):
    """
    AI智能诊断API
    参数：
        params: {
            'result': Dict,    # 策略回测/分析结果
            'context': Dict    # 其他上下文信息（可选）
        }
    返回：
        dict: {'diagnosis': 诊断结论, 'suggestion': 改进建议}
    """
    # TODO: 实现AI诊断逻辑（如异常检测、因果分析、自动建议等）
    diagnosis = "策略表现正常，无明显异常。"
    suggestion = "可尝试调整参数或更换策略以提升收益。"
    return {"diagnosis": diagnosis, "suggestion": suggestion}

# ===========================================
# 性能监控API
# ===========================================

@app.get("/api/strategy/performance/metrics")
def get_strategy_performance_metrics():
    """
    获取策略服务性能监控指标
    
    返回：
        dict: {
            'system_metrics': 系统资源指标（CPU、内存等）,
            'task_metrics': 任务执行统计,
            'plugin_metrics': 插件使用统计,
            'concurrency_metrics': 并发控制指标,
            'cache_metrics': 缓存统计,
            'threshold_checks': 性能阈值检查结果,
            'timestamp': 时间戳
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        metrics = strategy_service.get_performance_metrics()
        return {
            'status': 'success',
            'data': metrics
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取性能指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取性能指标失败: {str(e)}")


@app.get("/api/strategy/performance/report")
def get_strategy_performance_report():
    """
    获取策略服务性能报告
    
    返回：
        dict: {
            'overall_score': 总体评分,
            'component_scores': 各组件评分,
            'performance_grade': 性能等级,
            'metrics': 详细指标,
            'recommendations': 优化建议,
            'report_time': 报告时间
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        report = strategy_service.get_performance_report()
        return {
            'status': 'success',
            'data': report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取性能报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取性能报告失败: {str(e)}")


@app.get("/api/strategy/performance/health")
def get_strategy_health_status():
    """
    获取策略服务健康状态
    
    返回：
        dict: {
            'status': 健康状态,
            'threshold_checks': 阈值检查结果,
            'warnings': 警告列表,
            'alerts': 告警列表
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        metrics = strategy_service.get_performance_metrics()
        threshold_checks = metrics.get('threshold_checks', {})
        
        return {
            'status': threshold_checks.get('status', 'unknown'),
            'threshold_checks': threshold_checks,
            'timestamp': datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取健康状态失败: {str(e)}")

# ===========================================
# 策略模板管理API
# ===========================================

@app.get("/api/strategy/templates")
def get_strategy_templates(
    category: Optional[str] = Query(default=None, description="模板分类"),
    tags: Optional[str] = Query(default=None, description="标签，多个标签用逗号分隔")
):
    """
    获取策略模板列表
    
    参数：
        category: 模板分类（可选）
        tags: 标签（可选）
    
    返回：
        List[Dict]: 策略模板列表
    
    示例：
        GET /api/strategy/templates
        GET /api/strategy/templates?category=trend
        GET /api/strategy/templates?tags=经典,趋势
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        # 获取模板
        if category:
            templates = strategy_service.get_templates_by_category(category)
        elif tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            templates = strategy_service.get_templates_by_tags(tag_list)
        else:
            templates = strategy_service.get_all_templates()
        
        # 转换为字典格式
        result = []
        for template in templates:
            result.append({
                'template_id': template.template_id,
                'name': template.name,
                'description': template.description,
                'plugin_type': template.plugin_type,
                'default_parameters': template.default_parameters,
                'parameter_descriptions': template.parameter_descriptions,
                'tags': template.tags,
                'category': template.category,
                'is_builtin': template.is_builtin,
                'created_at': template.created_at.isoformat(),
                'updated_at': template.updated_at.isoformat()
            })
        
        return {
            'status': 'success',
            'data': result,
            'count': len(result)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略模板失败: {str(e)}")


@app.get("/api/strategy/templates/{template_id}")
def get_strategy_template(template_id: str):
    """
    获取指定策略模板
    
    参数：
        template_id: 模板ID
    
    返回：
        Dict: 策略模板详情
    
    示例：
        GET /api/strategy/templates/ma_crossover
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        template = strategy_service.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
        
        return {
            'status': 'success',
            'data': {
                'template_id': template.template_id,
                'name': template.name,
                'description': template.description,
                'plugin_type': template.plugin_type,
                'default_parameters': template.default_parameters,
                'parameter_descriptions': template.parameter_descriptions,
                'tags': template.tags,
                'category': template.category,
                'is_builtin': template.is_builtin,
                'created_at': template.created_at.isoformat(),
                'updated_at': template.updated_at.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略模板失败: {str(e)}")


@app.post("/api/strategy/templates")
def create_strategy_template(params: Dict[str, Any]):
    """
    创建策略模板
    
    参数：
        params: {
            'template_id': str,           # 模板ID
            'name': str,                  # 模板名称
            'description': str,            # 模板描述
            'plugin_type': str,           # 插件类型
            'default_parameters': Dict,     # 默认参数
            'parameter_descriptions': Dict, # 参数描述
            'tags': List[str],            # 标签
            'category': str               # 分类
        }
    
    返回：
        dict: 创建结果
    
    示例：
        POST /api/strategy/templates
        {
            "template_id": "my_template",
            "name": "我的模板",
            "description": "自定义策略模板",
            "plugin_type": "factorweave",
            "default_parameters": {"fast_period": 10},
            "tags": ["自定义"],
            "category": "custom"
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        from core.services.strategy_service import StrategyTemplate
        
        template = StrategyTemplate(
            template_id=params.get('template_id', ''),
            name=params.get('name', '未命名模板'),
            description=params.get('description', ''),
            plugin_type=params.get('plugin_type', 'factorweave'),
            default_parameters=params.get('default_parameters', {}),
            parameter_descriptions=params.get('parameter_descriptions', {}),
            tags=params.get('tags', []),
            category=params.get('category', 'general'),
            is_builtin=False
        )
        
        success = strategy_service.create_template(template)
        
        if success:
            return {
                'status': 'success',
                'message': f'模板 {template.name} 创建成功',
                'template_id': template.template_id
            }
        else:
            return {
                'status': 'error',
                'message': '模板创建失败，可能已存在'
            }
    except Exception as e:
        logger.error(f"创建策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建策略模板失败: {str(e)}")


@app.put("/api/strategy/templates/{template_id}")
def update_strategy_template(template_id: str, params: Dict[str, Any]):
    """
    更新策略模板
    
    参数：
        template_id: 模板ID
        params: 更新的模板数据
    
    返回：
        dict: 更新结果
    
    示例：
        PUT /api/strategy/templates/my_template
        {
            "name": "更新的模板名称",
            "description": "更新的描述"
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        # 获取现有模板
        existing_template = strategy_service.get_template(template_id)
        if not existing_template:
            raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
        
        # 更新模板
        from core.services.strategy_service import StrategyTemplate
        
        updated_template = StrategyTemplate(
            template_id=template_id,
            name=params.get('name', existing_template.name),
            description=params.get('description', existing_template.description),
            plugin_type=params.get('plugin_type', existing_template.plugin_type),
            default_parameters=params.get('default_parameters', existing_template.default_parameters),
            parameter_descriptions=params.get('parameter_descriptions', existing_template.parameter_descriptions),
            tags=params.get('tags', existing_template.tags),
            category=params.get('category', existing_template.category),
            is_builtin=existing_template.is_builtin,
            created_at=existing_template.created_at,
            updated_at=datetime.now()
        )
        
        success = strategy_service.update_template(template_id, updated_template)
        
        if success:
            return {
                'status': 'success',
                'message': f'模板 {updated_template.name} 更新成功'
            }
        else:
            return {
                'status': 'error',
                'message': '模板更新失败'
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新策略模板失败: {str(e)}")


@app.delete("/api/strategy/templates/{template_id}")
def delete_strategy_template(template_id: str):
    """
    删除策略模板
    
    参数：
        template_id: 模板ID
    
    返回：
        dict: 删除结果
    
    示例：
        DELETE /api/strategy/templates/my_template
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        success = strategy_service.delete_template(template_id)
        
        if success:
            return {
                'status': 'success',
                'message': f'模板 {template_id} 删除成功'
            }
        else:
            return {
                'status': 'error',
                'message': '模板删除失败，可能不存在或是内置模板'
            }
    except Exception as e:
        logger.error(f"删除策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除策略模板失败: {str(e)}")


@app.post("/api/strategy/templates/{template_id}/apply")
def apply_strategy_template(template_id: str, params: Dict[str, Any]):
    """
    应用模板创建策略配置
    
    参数：
        template_id: 模板ID
        params: {
            'strategy_id': str  # 可选，指定策略ID
        }
    
    返回：
        dict: 创建的策略配置
    
    示例：
        POST /api/strategy/templates/ma_crossover/apply
        {
            "strategy_id": "my_ma_strategy"
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        strategy_id = params.get('strategy_id')
        config = strategy_service.apply_template(template_id, strategy_id)
        
        if config:
            # 保存策略配置
            success = strategy_service.create_strategy_config(config)
            
            if success:
                return {
                    'status': 'success',
                    'message': f'基于模板创建策略成功',
                    'strategy_id': config.strategy_id,
                    'config': {
                        'strategy_id': config.strategy_id,
                        'plugin_type': config.plugin_type,
                        'parameters': config.parameters,
                        'metadata': config.metadata
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': '策略配置保存失败'
                }
        else:
            return {
                'status': 'error',
                'message': f'模板 {template_id} 不存在或应用失败'
            }
    except Exception as e:
        logger.error(f"应用策略模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"应用策略模板失败: {str(e)}")


# ===========================================
# 策略分组和标签管理API
# ===========================================

@app.get("/api/strategy/groups")
def get_strategy_groups():
    """
    获取所有策略分组
    
    返回：
        List[Dict]: 策略分组列表
    
    示例：
        GET /api/strategy/groups
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        groups = strategy_service.get_all_groups()
        
        result = []
        for group in groups:
            result.append({
                'group_id': group.group_id,
                'name': group.name,
                'description': group.description,
                'color': group.color,
                'icon': group.icon,
                'is_builtin': group.is_builtin,
                'created_at': group.created_at.isoformat()
            })
        
        return {
            'status': 'success',
            'data': result,
            'count': len(result)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略分组失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略分组失败: {str(e)}")


@app.get("/api/strategy/groups/{group_id}")
def get_strategy_group(group_id: str):
    """
    获取指定策略分组
    
    参数：
        group_id: 分组ID
    
    返回：
        Dict: 策略分组详情
    
    示例：
        GET /api/strategy/groups/trend
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        group = strategy_service.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail=f"分组 {group_id} 不存在")
        
        return {
            'status': 'success',
            'data': {
                'group_id': group.group_id,
                'name': group.name,
                'description': group.description,
                'color': group.color,
                'icon': group.icon,
                'is_builtin': group.is_builtin,
                'created_at': group.created_at.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略分组失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略分组失败: {str(e)}")


@app.get("/api/strategy/groups/{group_id}/strategies")
def get_strategies_by_group(group_id: str):
    """
    获取指定分组下的所有策略
    
    参数：
        group_id: 分组ID
    
    返回：
        List[Dict]: 策略列表
    
    示例：
        GET /api/strategy/groups/trend/strategies
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        strategies = strategy_service.get_strategies_by_group(group_id)
        
        result = []
        for strategy in strategies:
            result.append({
                'strategy_id': strategy.strategy_id,
                'plugin_type': strategy.plugin_type,
                'parameters': strategy.parameters,
                'enabled': strategy.enabled,
                'group': strategy.group,
                'tags': strategy.tags,
                'created_at': strategy.created_at.isoformat(),
                'updated_at': strategy.updated_at.isoformat()
            })
        
        return {
            'status': 'success',
            'data': result,
            'count': len(result)
        }
    except Exception as e:
        logger.error(f"获取分组策略失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取分组策略失败: {str(e)}")


@app.post("/api/strategy/groups")
def create_strategy_group(params: Dict[str, Any]):
    """
    创建策略分组
    
    参数：
        params: {
            'group_id': str,    # 分组ID
            'name': str,         # 分组名称
            'description': str,   # 分组描述
            'color': str,        # 分组颜色
            'icon': str          # 分组图标
        }
    
    返回：
        dict: 创建结果
    
    示例：
        POST /api/strategy/groups
        {
            "group_id": "my_group",
            "name": "我的分组",
            "description": "自定义分组",
            "color": "#FF5733"
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        from core.services.strategy_service import StrategyGroup
        
        group = StrategyGroup(
            group_id=params.get('group_id', ''),
            name=params.get('name', '未命名分组'),
            description=params.get('description', ''),
            color=params.get('color', '#3B82F6'),
            icon=params.get('icon'),
            is_builtin=False
        )
        
        success = strategy_service.create_group(group)
        
        if success:
            return {
                'status': 'success',
                'message': f'分组 {group.name} 创建成功',
                'group_id': group.group_id
            }
        else:
            return {
                'status': 'error',
                'message': '分组创建失败，可能已存在'
            }
    except Exception as e:
        logger.error(f"创建策略分组失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建策略分组失败: {str(e)}")


@app.put("/api/strategy/groups/{group_id}")
def update_strategy_group(group_id: str, params: Dict[str, Any]):
    """
    更新策略分组
    
    参数：
        group_id: 分组ID
        params: 更新的分组数据
    
    返回：
        dict: 更新结果
    
    示例：
        PUT /api/strategy/groups/my_group
        {
            "name": "更新的分组名称",
            "description": "更新的描述"
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        # 获取现有分组
        existing_group = strategy_service.get_group(group_id)
        if not existing_group:
            raise HTTPException(status_code=404, detail=f"分组 {group_id} 不存在")
        
        # 更新分组
        from core.services.strategy_service import StrategyGroup
        
        updated_group = StrategyGroup(
            group_id=group_id,
            name=params.get('name', existing_group.name),
            description=params.get('description', existing_group.description),
            color=params.get('color', existing_group.color),
            icon=params.get('icon', existing_group.icon),
            is_builtin=existing_group.is_builtin,
            created_at=existing_group.created_at
        )
        
        success = strategy_service.update_group(group_id, updated_group)
        
        if success:
            return {
                'status': 'success',
                'message': f'分组 {updated_group.name} 更新成功'
            }
        else:
            return {
                'status': 'error',
                'message': '分组更新失败，可能是内置分组'
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新策略分组失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新策略分组失败: {str(e)}")


@app.delete("/api/strategy/groups/{group_id}")
def delete_strategy_group(group_id: str):
    """
    删除策略分组
    
    参数：
        group_id: 分组ID
    
    返回：
        dict: 删除结果
    
    示例：
        DELETE /api/strategy/groups/my_group
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        success = strategy_service.delete_group(group_id)
        
        if success:
            return {
                'status': 'success',
                'message': f'分组 {group_id} 删除成功'
            }
        else:
            return {
                'status': 'error',
                'message': '分组删除失败，可能不存在或是内置分组'
            }
    except Exception as e:
        logger.error(f"删除策略分组失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除策略分组失败: {str(e)}")


@app.post("/api/strategy/{strategy_id}/group")
def assign_strategy_to_group(strategy_id: str, params: Dict[str, Any]):
    """
    将策略分配到分组
    
    参数：
        strategy_id: 策略ID
        params: {
            'group_id': str  # 目标分组ID
        }
    
    返回：
        dict: 分配结果
    
    示例：
        POST /api/strategy/strategy_123/group
        {
            "group_id": "trend"
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        group_id = params.get('group_id')
        success = strategy_service.assign_strategy_to_group(strategy_id, group_id)
        
        if success:
            return {
                'status': 'success',
                'message': f'策略 {strategy_id} 已分配到分组 {group_id}'
            }
        else:
            return {
                'status': 'error',
                'message': '策略分配失败，策略或分组不存在'
            }
    except Exception as e:
        logger.error(f"分配策略到分组失败: {e}")
        raise HTTPException(status_code=500, detail=f"分配策略到分组失败: {str(e)}")


@app.get("/api/strategy/tags")
def get_all_strategy_tags():
    """
    获取所有使用过的标签
    
    返回：
        List[str]: 标签列表
    
    示例：
        GET /api/strategy/tags
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        tags = strategy_service.get_all_tags()
        
        return {
            'status': 'success',
            'data': tags,
            'count': len(tags)
        }
    except Exception as e:
        logger.error(f"获取策略标签失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略标签失败: {str(e)}")


@app.get("/api/strategy/tags/statistics")
def get_tag_statistics():
    """
    获取标签使用统计
    
    返回：
        Dict[str, int]: 标签使用次数统计
    
    示例：
        GET /api/strategy/tags/statistics
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        stats = strategy_service.get_tag_statistics()
        
        return {
            'status': 'success',
            'data': stats,
            'count': len(stats)
        }
    except Exception as e:
        logger.error(f"获取标签统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取标签统计失败: {str(e)}")


@app.get("/api/strategy/by-tags")
def get_strategies_by_tags(
    tags: str = Query(description="标签，多个标签用逗号分隔"),
    match_all: bool = Query(default=False, description="是否匹配所有标签")
):
    """
    按标签获取策略
    
    参数：
        tags: 标签列表，用逗号分隔
        match_all: True表示匹配所有标签，False表示匹配任一标签
    
    返回：
        List[Dict]: 策略列表
    
    示例：
        GET /api/strategy/by-tags?tags=经典,趋势
        GET /api/strategy/by-tags?tags=经典,趋势&match_all=true
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        tag_list = [tag.strip() for tag in tags.split(',')]
        strategies = strategy_service.get_strategies_by_tags(tag_list, match_all)
        
        result = []
        for strategy in strategies:
            result.append({
                'strategy_id': strategy.strategy_id,
                'plugin_type': strategy.plugin_type,
                'parameters': strategy.parameters,
                'enabled': strategy.enabled,
                'group': strategy.group,
                'tags': strategy.tags,
                'created_at': strategy.created_at.isoformat(),
                'updated_at': strategy.updated_at.isoformat()
            })
        
        return {
            'status': 'success',
            'data': result,
            'count': len(result)
        }
    except Exception as e:
        logger.error(f"按标签获取策略失败: {e}")
        raise HTTPException(status_code=500, detail=f"按标签获取策略失败: {str(e)}")


@app.post("/api/strategy/{strategy_id}/tags")
def add_strategy_tags(strategy_id: str, params: Dict[str, Any]):
    """
    为策略添加标签
    
    参数：
        strategy_id: 策略ID
        params: {
            'tags': List[str]  # 要添加的标签列表
        }
    
    返回：
        dict: 添加结果
    
    示例：
        POST /api/strategy/strategy_123/tags
        {
            "tags": ["经典", "趋势"]
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        tags = params.get('tags', [])
        success = strategy_service.add_strategy_tags(strategy_id, tags)
        
        if success:
            return {
                'status': 'success',
                'message': f'为策略 {strategy_id} 添加标签成功',
                'tags': tags
            }
        else:
            return {
                'status': 'error',
                'message': '添加标签失败，策略不存在'
            }
    except Exception as e:
        logger.error(f"添加策略标签失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加策略标签失败: {str(e)}")


@app.delete("/api/strategy/{strategy_id}/tags")
def remove_strategy_tags(strategy_id: str, params: Dict[str, Any]):
    """
    从策略移除标签
    
    参数：
        strategy_id: 策略ID
        params: {
            'tags': List[str]  # 要移除的标签列表
        }
    
    返回：
        dict: 移除结果
    
    示例：
        DELETE /api/strategy/strategy_123/tags
        {
            "tags": ["过时"]
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        tags = params.get('tags', [])
        success = strategy_service.remove_strategy_tags(strategy_id, tags)
        
        if success:
            return {
                'status': 'success',
                'message': f'从策略 {strategy_id} 移除标签成功',
                'tags': tags
            }
        else:
            return {
                'status': 'error',
                'message': '移除标签失败，策略不存在'
            }
    except Exception as e:
        logger.error(f"移除策略标签失败: {e}")
        raise HTTPException(status_code=500, detail=f"移除策略标签失败: {str(e)}")


@app.post("/api/strategy/batch/group")
def batch_update_strategy_group(params: Dict[str, Any]):
    """
    批量更新策略分组
    
    参数：
        params: {
            'strategy_ids': List[str],  # 策略ID列表
            'group_id': str           # 目标分组ID
        }
    
    返回：
        dict: 批量更新结果
    
    示例：
        POST /api/strategy/batch/group
        {
            "strategy_ids": ["strategy_1", "strategy_2"],
            "group_id": "trend"
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        strategy_ids = params.get('strategy_ids', [])
        group_id = params.get('group_id')
        
        updated_count = strategy_service.batch_update_strategy_group(strategy_ids, group_id)
        
        return {
            'status': 'success',
            'message': f'已更新 {updated_count} 个策略的分组',
            'updated_count': updated_count
        }
    except Exception as e:
        logger.error(f"批量更新策略分组失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量更新策略分组失败: {str(e)}")


@app.post("/api/strategy/batch/tags")
def batch_add_strategy_tags(params: Dict[str, Any]):
    """
    批量为策略添加标签
    
    参数：
        params: {
            'strategy_ids': List[str],  # 策略ID列表
            'tags': List[str]           # 要添加的标签列表
        }
    
    返回：
        dict: 批量添加结果
    
    示例：
        POST /api/strategy/batch/tags
        {
            "strategy_ids": ["strategy_1", "strategy_2"],
            "tags": ["经典", "趋势"]
        }
    """
    try:
        strategy_service = get_strategy_service()
        if not strategy_service:
            raise HTTPException(status_code=503, detail="策略服务不可用")
        
        strategy_ids = params.get('strategy_ids', [])
        tags = params.get('tags', [])
        
        updated_count = strategy_service.batch_add_strategy_tags(strategy_ids, tags)
        
        return {
            'status': 'success',
            'message': f'已为 {updated_count} 个策略添加标签',
            'updated_count': updated_count,
            'tags': tags
        }
    except Exception as e:
        logger.error(f"批量添加策略标签失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量添加策略标签失败: {str(e)}")


# ===========================================
# 板块资金流数据API
# ===========================================


@app.get("/api/sector/fund-flow/ranking")
def get_sector_fund_flow_ranking(
    date_range: str = Query(default="today", description="日期范围：today, 3d, 7d, 30d等"),
    sort_by: str = Query(default="main_net_inflow", description="排序字段：main_net_inflow, super_large_inflow等")
):
    """
    获取板块资金流排行榜

    参数：
        date_range: 日期范围，支持 today, 3d, 7d, 30d 等格式
        sort_by: 排序字段，如 main_net_inflow, super_large_inflow 等

    返回：
        List[Dict]: 板块资金流排行榜数据

    示例：
        GET /api/sector/fund-flow/ranking?date_range=today&sort_by=main_net_inflow
    """
    try:
        # 通过UnifiedDataManager获取板块数据服务
        sector_service = data_manager.get_sector_fund_flow_service()
        if sector_service is None:
            raise HTTPException(status_code=503, detail="板块数据服务不可用")

        # 获取排行榜数据
        df = sector_service.get_sector_fund_flow_ranking(date_range=date_range, sort_by=sort_by)

        if df is not None and not df.empty:
            # 转换为API响应格式
            result = df.to_dict(orient="records")
            return {
                "status": "success",
                "data": result,
                "count": len(result),
                "params": {"date_range": date_range, "sort_by": sort_by}
            }
        else:
            return {
                "status": "success",
                "data": [],
                "count": 0,
                "message": "暂无数据"
            }

    except Exception as e:
        logger.error(f"获取板块资金流排行榜失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取板块资金流排行榜失败: {str(e)}")


@app.get("/api/sector/fund-flow/trend/{sector_id}")
def get_sector_historical_trend(
    sector_id: str,
    period: int = Query(default=30, description="历史天数，默认30天")
):
    """
    获取单板块历史趋势数据

    参数：
        sector_id: 板块ID，如 BK0001
        period: 历史天数，默认30天

    返回：
        List[Dict]: 板块历史趋势数据

    示例：
        GET /api/sector/fund-flow/trend/BK0001?period=30
    """
    try:
        # 通过UnifiedDataManager获取板块数据服务
        sector_service = data_manager.get_sector_fund_flow_service()
        if sector_service is None:
            raise HTTPException(status_code=503, detail="板块数据服务不可用")

        # 获取历史趋势数据
        df = sector_service.get_sector_historical_trend(sector_id=sector_id, period=period)

        if df is not None and not df.empty:
            # 转换为API响应格式
            result = df.to_dict(orient="records")
            return {
                "status": "success",
                "data": result,
                "count": len(result),
                "params": {"sector_id": sector_id, "period": period}
            }
        else:
            return {
                "status": "success",
                "data": [],
                "count": 0,
                "message": f"板块 {sector_id} 暂无 {period} 天历史数据"
            }

    except Exception as e:
        logger.error(f"获取板块历史趋势失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取板块历史趋势失败: {str(e)}")


@app.get("/api/sector/fund-flow/intraday/{sector_id}")
def get_sector_intraday_flow(
    sector_id: str,
    date: str = Query(default=None, description="查询日期，格式YYYY-MM-DD，默认今日")
):
    """
    获取板块分时资金流数据

    参数：
        sector_id: 板块ID，如 BK0001
        date: 查询日期，格式 YYYY-MM-DD，默认今日

    返回：
        List[Dict]: 板块分时资金流数据

    示例：
        GET /api/sector/fund-flow/intraday/BK0001?date=2024-01-01
    """
    try:
        # 如果没有指定日期，使用今日
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # 验证日期格式
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")

        # 通过UnifiedDataManager获取板块数据服务
        sector_service = data_manager.get_sector_fund_flow_service()
        if sector_service is None:
            raise HTTPException(status_code=503, detail="板块数据服务不可用")

        # 获取分时资金流数据
        df = sector_service.get_sector_intraday_flow(sector_id=sector_id, date=date)

        if df is not None and not df.empty:
            # 转换为API响应格式
            result = df.to_dict(orient="records")
            return {
                "status": "success",
                "data": result,
                "count": len(result),
                "params": {"sector_id": sector_id, "date": date}
            }
        else:
            return {
                "status": "success",
                "data": [],
                "count": 0,
                "message": f"板块 {sector_id} 在 {date} 暂无分时数据"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取板块分时资金流失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取板块分时资金流失败: {str(e)}")


@app.post("/api/sector/fund-flow/import")
def import_sector_historical_data(params: Dict[str, Any]):
    """
    导入板块历史数据

    参数：
        params: {
            'source': str,      # 数据源名称，如 'akshare', 'eastmoney'
            'start_date': str,  # 开始日期 YYYY-MM-DD
            'end_date': str,    # 结束日期 YYYY-MM-DD
        }

    返回：
        dict: 导入结果，包含成功状态和处理数量

    示例：
        POST /api/sector/fund-flow/import
        {
            "source": "akshare",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31"
        }
    """
    try:
        # 验证必要参数
        source = params.get('source')
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not all([source, start_date, end_date]):
            raise HTTPException(status_code=400, detail="缺少必要参数：source, start_date, end_date")

        # 验证日期格式
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")

        # 通过UnifiedDataManager获取板块数据服务
        sector_service = data_manager.get_sector_fund_flow_service()
        if sector_service is None:
            raise HTTPException(status_code=503, detail="板块数据服务不可用")

        # 执行历史数据导入
        import_result = sector_service.import_sector_historical_data(
            source=source,
            start_date=start_date,
            end_date=end_date
        )

        if import_result.get('success', False):
            return {
                "status": "success",
                "message": import_result.get('message', '导入成功'),
                "processed_count": import_result.get('processed_count', 0),
                "params": params
            }
        else:
            return {
                "status": "error",
                "message": import_result.get('error', '导入失败'),
                "processed_count": import_result.get('processed_count', 0),
                "params": params
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导入板块历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入板块历史数据失败: {str(e)}")


@app.get("/api/sector/fund-flow/status")
def get_sector_service_status():
    """
    获取板块资金流服务状态

    返回：
        dict: 服务状态信息，包括可用性、数据源等

    示例：
        GET /api/sector/fund-flow/status
    """
    try:
        # 通过UnifiedDataManager获取板块数据服务
        sector_service = data_manager.get_sector_fund_flow_service()

        if sector_service is None:
            return {
                "status": "unavailable",
                "message": "板块数据服务不可用",
                "data_sources": []
            }

        # 获取服务状态（如果SectorDataService有状态方法的话）
        status_info = {
            "status": "available",
            "message": "板块数据服务运行正常",
            "service_type": "SectorDataService",
            "timestamp": datetime.now().isoformat()
        }

        # 如果有其他状态信息，可以在这里添加
        # 例如：可用数据源、缓存状态等

        return status_info

    except Exception as e:
        logger.error(f"获取板块服务状态失败: {e}")
        return {
            "status": "error",
            "message": f"获取服务状态失败: {str(e)}",
            "data_sources": []
        }

# ===========================================
# 混合推荐API
# ===========================================

@app.post("/api/hybrid/recommendation")
async def get_hybrid_recommendation(params: Dict[str, Any]):
    """
    获取混合推荐结果
    
    参数：
        params: {
            'user_id': str,           # 用户ID
            'context': Dict,          # 推荐上下文
            'stock_codes': List[str]  # 股票代码列表（可选）
        }
        
    返回：
        dict: 包含混合推荐结果和元数据
    """
    # 获取混合推荐引擎
    engine = await get_hybrid_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="混合推荐引擎不可用")
        
    # 提取参数
    user_id = params.get('user_id')
    context = params.get('context', {})
    stock_codes = params.get('stock_codes', [])
    
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少必要参数: user_id")
        
    # 请求推荐
    request_id = await engine.request_hybrid_recommendation(user_id, context, stock_codes)
    
    # 获取结果
    result = await engine.get_recommendation_by_request_id(request_id, timeout=30)
    
    if result:
        return {
            'status': 'success',
            'request_id': request_id,
            'data': result,
            'timestamp': datetime.now().isoformat()
        }
    else:
        raise HTTPException(status_code=504, detail="获取推荐结果超时")

@app.get("/api/hybrid/recommendation/{request_id}")
async def get_hybrid_recommendation_by_id(request_id: str):
    """
    通过请求ID获取混合推荐结果
    
    参数：
        request_id: 推荐请求ID
        
    返回：
        dict: 包含混合推荐结果和元数据
    """
    # 获取混合推荐引擎
    engine = await get_hybrid_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="混合推荐引擎不可用")
        
    # 获取结果
    result = await engine.get_recommendation_by_request_id(request_id, timeout=10)
    
    if result:
        return {
            'status': 'success',
            'request_id': request_id,
            'data': result,
            'timestamp': datetime.now().isoformat()
        }
    else:
        raise HTTPException(status_code=504, detail="获取推荐结果超时")

@app.get("/api/hybrid/status")
async def get_hybrid_engine_status():
    """
    获取混合推荐引擎状态
    
    返回：
        dict: 混合推荐引擎状态信息
    """
    # 获取混合推荐引擎
    engine = await get_hybrid_engine()
    if not engine:
        return {
            "status": "unavailable",
            "message": "混合推荐引擎不可用",
            "timestamp": datetime.now().isoformat()
        }
        
    # 返回引擎状态
    return {
        "status": "available" if engine.is_initialized else "initializing",
        "message": "混合推荐引擎运行正常" if engine.is_initialized else "混合推荐引擎初始化中",
        "engine_version": getattr(engine, "version", "unknown"),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/hybrid/cache/stats")
async def get_hybrid_cache_stats():
    """
    获取混合推荐引擎缓存统计信息
    
    返回：
        dict: 缓存统计信息
    """
    # 获取混合推荐引擎
    engine = await get_hybrid_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="混合推荐引擎不可用")
        
    # 获取缓存统计信息
    cache_stats = await engine.get_cache_statistics()
    
    if cache_stats:
        return {
            'status': 'success',
            'data': cache_stats,
            'timestamp': datetime.now().isoformat()
        }
    else:
        return {
            'status': 'success',
            'data': {},
            'message': '缓存统计信息不可用',
            'timestamp': datetime.now().isoformat()
        }

@app.post("/api/hybrid/cache/warm")
async def warm_hybrid_cache(params: Dict[str, Any]):
    """
    预热混合推荐引擎缓存
    
    参数：
        params: {
            'user_ids': List[str],   # 预热用户ID列表（可选）
            'stock_codes': List[str]  # 预热股票代码列表（可选）
        }
        
    返回：
        dict: 预热结果
    """
    # 获取混合推荐引擎
    engine = await get_hybrid_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="混合推荐引擎不可用")
        
    # 提取参数
    user_ids = params.get('user_ids', None)
    stock_codes = params.get('stock_codes', None)
    
    # 执行缓存预热
    try:
        await engine.warm_cache(user_ids, stock_codes)
        return {
            'status': 'success',
            'message': '缓存预热成功',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"缓存预热失败: {e}")
        raise HTTPException(status_code=500, detail=f"缓存预热失败: {str(e)}")

@app.delete("/api/hybrid/cache")
async def clear_hybrid_cache():
    """
    清空混合推荐引擎缓存
    
    返回：
        dict: 清空结果
    """
    # 获取混合推荐引擎
    engine = await get_hybrid_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="混合推荐引擎不可用")
        
    # 清空缓存
    try:
        await engine.clear_cache()
        return {
            'status': 'success',
            'message': '缓存清空成功',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"缓存清空失败: {e}")
        raise HTTPException(status_code=500, detail=f"缓存清空失败: {str(e)}")

# 后续可扩展：用户认证、插件注册、WebHook等


def _kdata_preprocess(df, context="分析"):
    """K线数据预处理：检查并修正所有关键字段，统一处理datetime字段"""

    if not isinstance(df, pd.DataFrame):
        return df

    # 检查datetime是否在索引中或列中
    has_datetime = False
    datetime_in_index = False

    # 检查datetime是否在索引中
    if isinstance(df.index, pd.DatetimeIndex) or (hasattr(df.index, 'name') and df.index.name == 'datetime'):
        has_datetime = True
        datetime_in_index = True
    # 检查datetime是否在列中
    elif 'datetime' in df.columns:
        has_datetime = True
        datetime_in_index = False

    # 如果datetime不存在，尝试从索引推断或创建
    if not has_datetime:
        if isinstance(df.index, pd.DatetimeIndex):
            # 索引是DatetimeIndex但名称不是datetime，复制到列中
            df = df.copy()
            df['datetime'] = df.index
            has_datetime = True
            logger.info(f"[{context}] 从DatetimeIndex推断datetime字段")
        else:
            # 完全没有datetime信息，需要补全
            logger.info(f"[{context}] 缺少datetime字段，自动补全")
            df = df.copy()
            df['datetime'] = pd.date_range(
                start='2023-01-01', periods=len(df), freq='D')
            has_datetime = True

    # 检查其他必要字段
    required_cols = ['code', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.info(f"[{context}] 缺少字段: {missing_cols}，自动补全为默认值")
        df = df.copy()
        for col in missing_cols:
            if col == 'code':
                df['code'] = ''
            elif col == 'volume':
                df[col] = 0.0
            elif col in ['open', 'high', 'low', 'close']:
                # 用收盘价填充其他价格字段
                if 'close' in df.columns:
                    df[col] = df['close']
                else:
                    df[col] = 0.0
            else:
                df[col] = 0.0

    # 检查数值字段异常
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            before = len(df)
            df = df[df[col].notna() & (df[col] >= 0)]
            after = len(df)
            if after < before:
                logger.info(f"[{context}] 已过滤{before-after}行{col}异常数据")

    # 检查code字段
    if 'code' in df.columns:
        df = df[df['code'].notna() & (df['code'] != '')]

    if df.empty:
        logger.info(f"[{context}] 数据全部无效，返回空")

    return df.reset_index(drop=True)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
