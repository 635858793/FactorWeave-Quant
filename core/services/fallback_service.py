"""
降级服务和系统稳定性保护
确保当BettaFish功能不可用时，系统能够正常运行
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import json


class ServiceStatus(Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"


class FallbackStrategy(Enum):
    """降级策略枚举"""
    TRADITIONAL_ONLY = "traditional_only"
    POPULAR_RECOMMENDATIONS = "popular_recommendations"
    BASIC_FUNCTIONALITY = "basic_functionality"
    READ_ONLY_MODE = "read_only_mode"


@dataclass
class ServiceHealth:
    """服务健康状态"""
    service_name: str
    status: ServiceStatus
    last_check_time: float
    response_time: float
    error_count: int
    success_count: int
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = None


class FallbackService:
    """降级服务和系统稳定性保护"""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        
        # 服务状态管理
        self.service_status = {
            "bettafish": ServiceStatus.HEALTHY,
            "traditional_recommendation": ServiceStatus.HEALTHY,
            "data_provider": ServiceStatus.HEALTHY,
            "analysis_service": ServiceStatus.HEALTHY
        }
        
        # 健康检查记录
        self.health_history = {}
        
        # 降级策略配置
        self.fallback_config = {
            "bettafish": {
                "enabled": True,
                "timeout": 30.0,  # 30秒超时
                "max_retries": 3,
                "circuit_breaker_threshold": 5,
                "circuit_breaker_timeout": 300  # 5分钟
            },
            "traditional_recommendation": {
                "enabled": True,
                "timeout": 15.0,
                "max_retries": 2,
                "fallback_strategy": FallbackStrategy.POPULAR_RECOMMENDATIONS
            },
            "analysis_service": {
                "enabled": True,
                "timeout": 45.0,
                "max_retries": 1,
                "fallback_strategy": FallbackStrategy.BASIC_FUNCTIONALITY
            }
        }
        
        # 熔断器状态
        self.circuit_breakers = {
            service: {
                "failure_count": 0,
                "last_failure_time": None,
                "state": "closed"  # closed, open, half-open
            }
            for service in self.service_status.keys()
        }
        
        # 监控指标
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "fallback_activations": 0,
            "circuit_breaker_trips": 0
        }
        
    async def check_service_health(self, service_name: str) -> ServiceHealth:
        """检查服务健康状态"""
        if service_name not in self.service_status:
            return ServiceHealth(
                service_name=service_name,
                status=ServiceStatus.FAILED,
                last_check_time=time.time(),
                response_time=0,
                error_count=0,
                success_count=0,
                last_error=f"Unknown service: {service_name}"
            )
        
        start_time = time.time()
        
        try:
            # 执行健康检查
            health_result = await self._execute_health_check(service_name)
            response_time = time.time() - start_time
            
            # 更新服务状态
            if health_result["healthy"]:
                self.service_status[service_name] = ServiceStatus.HEALTHY
                self.circuit_breakers[service_name]["failure_count"] = 0
            else:
                self.service_status[service_name] = ServiceStatus.DEGRADED
                await self._handle_service_degradation(service_name, health_result)
            
            # 记录健康状态
            health_record = ServiceHealth(
                service_name=service_name,
                status=self.service_status[service_name],
                last_check_time=time.time(),
                response_time=response_time,
                error_count=health_result.get("error_count", 0),
                success_count=health_result.get("success_count", 0),
                last_error=health_result.get("error_message"),
                metadata=health_result.get("metadata", {})
            )
            
            # 更新历史记录
            if service_name not in self.health_history:
                self.health_history[service_name] = []
            
            self.health_history[service_name].append(health_record)
            
            # 保持最近100条记录
            if len(self.health_history[service_name]) > 100:
                self.health_history[service_name] = self.health_history[service_name][-100:]
            
            return health_record
            
        except Exception as e:
            self.logger.error(f"Service health check failed for {service_name}: {e}")
            return ServiceHealth(
                service_name=service_name,
                status=ServiceStatus.FAILED,
                last_check_time=time.time(),
                response_time=time.time() - start_time,
                error_count=0,
                success_count=0,
                last_error=str(e)
            )
    
    async def _execute_health_check(self, service_name: str) -> Dict[str, Any]:
        """执行具体的健康检查"""
        if service_name == "bettafish":
            return await self._check_bettafish_health()
        elif service_name == "traditional_recommendation":
            return await self._check_traditional_recommendation_health()
        elif service_name == "data_provider":
            return await self._check_data_provider_health()
        elif service_name == "analysis_service":
            return await self._check_analysis_service_health()
        else:
            return {"healthy": False, "error_message": f"Unknown service: {service_name}"}
    
    async def _check_bettafish_health(self) -> Dict[str, Any]:
        """检查BettaFish服务健康"""
        try:
            # 检查BettaFishAgent是否可用
            from core.agents.bettafish_agent import BettaFishAgent
            
            # 创建测试实例
            test_agent = BettaFishAgent()
            
            # 执行简单的健康检查（不执行完整分析）
            if hasattr(test_agent, '_initialized'):
                return {
                    "healthy": True,
                    "error_count": 0,
                    "success_count": 1,
                    "metadata": {"agent_available": True}
                }
            else:
                return {
                    "healthy": False,
                    "error_message": "BettaFishAgent initialization failed",
                    "error_count": 1,
                    "success_count": 0
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "error_message": f"BettaFish health check failed: {str(e)}",
                "error_count": 1,
                "success_count": 0
            }
    
    async def _check_traditional_recommendation_health(self) -> Dict[str, Any]:
        """检查传统推荐服务健康"""
        try:
            from core.services.smart_recommendation_engine import SmartRecommendationEngine
            
            # 创建测试实例
            test_engine = SmartRecommendationEngine()
            
            # 检查基本方法是否可用
            if hasattr(test_engine, 'get_recommendations'):
                return {
                    "healthy": True,
                    "error_count": 0,
                    "success_count": 1,
                    "metadata": {"engine_available": True}
                }
            else:
                return {
                    "healthy": False,
                    "error_message": "SmartRecommendationEngine methods missing",
                    "error_count": 1,
                    "success_count": 0
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "error_message": f"Traditional recommendation health check failed: {str(e)}",
                "error_count": 1,
                "success_count": 0
            }
    
    async def _check_data_provider_health(self) -> Dict[str, Any]:
        """检查数据提供器健康"""
        try:
            # 模拟数据提供器健康检查
            return {
                "healthy": True,
                "error_count": 0,
                "success_count": 1,
                "metadata": {"data_source": "simulation"}
            }
        except Exception as e:
            return {
                "healthy": False,
                "error_message": f"Data provider health check failed: {str(e)}",
                "error_count": 1,
                "success_count": 0
            }
    
    async def _check_analysis_service_health(self) -> Dict[str, Any]:
        """检查分析服务健康"""
        try:
            # 模拟分析服务健康检查
            return {
                "healthy": True,
                "error_count": 0,
                "success_count": 1,
                "metadata": {"analysis_capability": "available"}
            }
        except Exception as e:
            return {
                "healthy": False,
                "error_message": f"Analysis service health check failed: {str(e)}",
                "error_count": 1,
                "success_count": 0
            }
    
    async def _handle_service_degradation(self, service_name: str, health_result: Dict[str, Any]):
        """处理服务降级"""
        self.logger.warning(f"Service {service_name} is degraded: {health_result.get('error_message')}")
        
        # 更新熔断器
        await self._update_circuit_breaker(service_name)
        
        # 发送降级事件
        if self.event_bus:
            self.event_bus.publish("service_degradation",
                service_name=service_name,
                health_result=health_result,
                timestamp=time.time()
            )
    
    async def _update_circuit_breaker(self, service_name: str):
        """更新熔断器状态"""
        circuit = self.circuit_breakers[service_name]
        config = self.fallback_config[service_name]
        
        circuit["failure_count"] += 1
        circuit["last_failure_time"] = time.time()
        
        # 检查是否需要开启熔断器
        if (circuit["failure_count"] >= config["circuit_breaker_threshold"] and 
            circuit["state"] == "closed"):
            
            circuit["state"] = "open"
            self.service_status[service_name] = ServiceStatus.FAILED
            self.metrics["circuit_breaker_trips"] += 1
            
            self.logger.error(f"Circuit breaker opened for {service_name}")
            
            # 安排熔断器恢复检查
            asyncio.create_task(self._schedule_circuit_breaker_check(service_name))
    
    async def _schedule_circuit_breaker_check(self, service_name: str):
        """安排熔断器恢复检查"""
        await asyncio.sleep(self.fallback_config[service_name]["circuit_breaker_timeout"])
        
        # 尝试恢复
        circuit = self.circuit_breakers[service_name]
        circuit["state"] = "half-open"
        
        self.logger.info(f"Circuit breaker for {service_name} moved to half-open state")
        
        # 执行测试请求
        try:
            health = await self.check_service_health(service_name)
            if health.status == ServiceStatus.HEALTHY:
                circuit["state"] = "closed"
                circuit["failure_count"] = 0
                self.service_status[service_name] = ServiceStatus.HEALTHY
                self.logger.info(f"Circuit breaker for {service_name} closed successfully")
            else:
                circuit["state"] = "open"
                self.logger.warning(f"Circuit breaker for {service_name} still open")
        except Exception as e:
            circuit["state"] = "open"
            self.logger.error(f"Circuit breaker check failed for {service_name}: {e}")
    
    async def execute_with_fallback(self, service_name: str, 
                                  primary_func, 
                                  fallback_func=None,
                                  *args, **kwargs) -> Any:
        """执行带降级的功能"""
        self.metrics["total_requests"] += 1
        
        # 检查服务是否被熔断器阻断
        if self._is_service_blocked(service_name):
            self.logger.warning(f"Service {service_name} is blocked by circuit breaker")
            if fallback_func:
                return await self._execute_fallback(fallback_func, service_name, *args, **kwargs)
            else:
                raise Exception(f"Service {service_name} is unavailable and no fallback provided")
        
        try:
            # 尝试执行主要功能
            result = await asyncio.wait_for(
                primary_func(*args, **kwargs),
                timeout=self.fallback_config[service_name]["timeout"]
            )
            
            self.metrics["successful_requests"] += 1
            return result
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Service {service_name} timed out")
            if fallback_func:
                return await self._execute_fallback(fallback_func, service_name, *args, **kwargs)
            else:
                raise Exception(f"Service {service_name} timeout and no fallback provided")
                
        except Exception as e:
            self.logger.error(f"Service {service_name} failed: {e}")
            self.metrics["failed_requests"] += 1
            
            if fallback_func:
                return await self._execute_fallback(fallback_func, service_name, *args, **kwargs)
            else:
                raise
    
    def _is_service_blocked(self, service_name: str) -> bool:
        """检查服务是否被熔断器阻断"""
        if service_name not in self.circuit_breakers:
            return True
        
        circuit = self.circuit_breakers[service_name]
        return circuit["state"] == "open"
    
    async def _execute_fallback(self, fallback_func, service_name: str, *args, **kwargs) -> Any:
        """执行降级功能"""
        self.metrics["fallback_activations"] += 1
        self.logger.info(f"Activating fallback for {service_name}")
        
        try:
            result = await fallback_func(*args, **kwargs)
            self.logger.info(f"Fallback executed successfully for {service_name}")
            return result
        except Exception as e:
            self.logger.error(f"Fallback failed for {service_name}: {e}")
            raise Exception(f"Both primary service {service_name} and fallback failed")
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统整体状态"""
        healthy_services = sum(1 for status in self.service_status.values() 
                             if status == ServiceStatus.HEALTHY)
        total_services = len(self.service_status)
        
        return {
            "overall_status": "healthy" if healthy_services == total_services else "degraded",
            "service_count": total_services,
            "healthy_services": healthy_services,
            "service_details": {
                name: {
                    "status": status.value,
                    "circuit_breaker": self.circuit_breakers[name]["state"]
                }
                for name, status in self.service_status.items()
            },
            "metrics": self.metrics,
            "timestamp": time.time()
        }
    
    async def reset_service(self, service_name: str):
        """重置指定服务状态"""
        if service_name in self.service_status:
            self.service_status[service_name] = ServiceStatus.HEALTHY
            
            if service_name in self.circuit_breakers:
                self.circuit_breakers[service_name] = {
                    "failure_count": 0,
                    "last_failure_time": None,
                    "state": "closed"
                }
            
            self.logger.info(f"Service {service_name} has been reset")
            
            if self.event_bus:
                self.event_bus.publish("service_reset",
                    service_name=service_name,
                    timestamp=time.time()
                )
    
    def is_bettafish_enabled(self) -> bool:
        """检查BettaFish功能是否启用"""
        return (self.service_status.get("bettafish") == ServiceStatus.HEALTHY and
                self.fallback_config["bettafish"]["enabled"] and
                not self._is_service_blocked("bettafish"))
    
    def get_fallback_strategy(self, service_name: str) -> FallbackStrategy:
        """获取服务的降级策略"""
        config = self.fallback_config.get(service_name, {})
        return config.get("fallback_strategy", FallbackStrategy.BASIC_FUNCTIONALITY)
    
    async def run_periodic_health_check(self):
        """运行定期健康检查"""
        while True:
            try:
                for service_name in self.service_status.keys():
                    await self.check_service_health(service_name)
                
                # 等待下次检查（每5分钟）
                await asyncio.sleep(300)
                
            except Exception as e:
                self.logger.error(f"Periodic health check failed: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再试