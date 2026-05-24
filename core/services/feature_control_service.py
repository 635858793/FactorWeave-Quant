"""
高级功能控制服务
管理BettaFish等高级功能的启用/禁用状态
确保即使高级功能不可用，系统核心功能仍然正常
"""

import asyncio
import json
from loguru import logger
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import os


class FeatureStatus(Enum):
    """功能状态枚举"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"  # 不可用（如依赖缺失）
    MAINTENANCE = "maintenance"  # 维护中


class FeatureLevel(Enum):
    """功能级别枚举"""
    CORE = "core"  # 核心功能（不可禁用）
    ADVANCED = "advanced"  # 高级功能（可禁用）
    PREMIUM = "premium"  # 高级功能（需付费）


@dataclass
class FeatureConfig:
    """功能配置"""
    name: str
    description: str
    level: FeatureLevel
    status: FeatureStatus
    dependencies: List[str]
    config: Dict[str, Any]
    last_updated: float
    enabled_by_default: bool
    require_restart: bool = False


class FeatureControlService:
    """高级功能控制服务"""
    
    def __init__(self, config_path: str = "config/feature_config.json"):
        self.config_path = config_path
        self.logger = logger
        
        # 功能配置
        self.features = {}
        self.user_overrides = {}  # 用户自定义配置
        
        # 功能状态变更监听器
        self.status_change_listeners = []
        
        # 配置文件目录
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # 加载配置
        self._load_feature_configs()
    
    def _load_feature_configs(self):
        """加载功能配置"""
        # 默认功能配置
        default_features = {
            "bettafish": FeatureConfig(
                name="bettafish",
                description="BettaFish多智能体舆情分析系统",
                level=FeatureLevel.ADVANCED,
                status=FeatureStatus.ENABLED,
                dependencies=["event_bus", "data_provider"],
                config={
                    "max_concurrent_analyses": 10,
                    "analysis_timeout": 30,
                    "enable_cache": True,
                    "cache_ttl": 300,
                    "fusion_strategy": "adaptive",
                    "performance_monitoring": True
                },
                last_updated=time.time(),
                enabled_by_default=True,
                require_restart=False
            ),
            "smart_recommendation": FeatureConfig(
                name="smart_recommendation",
                description="智能推荐系统",
                level=FeatureLevel.ADVANCED,
                status=FeatureStatus.ENABLED,
                dependencies=["user_behavior_db", "stock_data"],
                config={
                    "collaborative_filtering": True,
                    "content_based": True,
                    "popular_recommendations": True,
                    "personalization_level": "medium"
                },
                last_updated=time.time(),
                enabled_by_default=True,
                require_restart=False
            ),
            "advanced_charts": FeatureConfig(
                name="advanced_charts",
                description="高级图表分析功能",
                level=FeatureLevel.ADVANCED,
                status=FeatureStatus.ENABLED,
                dependencies=["chart_engine"],
                config={
                    "enable_3d_charts": True,
                    "enable_technical_indicators": True,
                    "enable_drawing_tools": True
                },
                last_updated=time.time(),
                enabled_by_default=False,
                require_restart=True
            ),
            "real_time_analysis": FeatureConfig(
                name="real_time_analysis",
                description="实时市场分析",
                level=FeatureLevel.ADVANCED,
                status=FeatureStatus.ENABLED,
                dependencies=["market_data_stream"],
                config={
                    "update_frequency": 1000,  # 毫秒
                    "max_concurrent_streams": 5,
                    "enable_alerts": True
                },
                last_updated=time.time(),
                enabled_by_default=True,
                require_restart=False
            ),
            "risk_management": FeatureConfig(
                name="risk_management",
                description="风险管理功能",
                level=FeatureLevel.CORE,
                status=FeatureStatus.ENABLED,
                dependencies=["portfolio_data"],
                config={
                    "max_position_size": 0.1,  # 10%
                    "stop_loss_threshold": 0.05,  # 5%
                    "enable_position_sizing": True
                },
                last_updated=time.time(),
                enabled_by_default=True,
                require_restart=False
            ),
            "portfolio_optimization": FeatureConfig(
                name="portfolio_optimization",
                description="投资组合优化",
                level=FeatureLevel.ADVANCED,
                status=FeatureStatus.ENABLED,
                dependencies=["optimization_engine"],
                config={
                    "optimization_algorithm": "markowitz",
                    "rebalance_frequency": "daily",
                    "enable_constraints": True
                },
                last_updated=time.time(),
                enabled_by_default=False,
                require_restart=False
            )
        }
        
        # 加载保存的配置
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved_configs = json.load(f)
                
                # 合并默认配置和保存的配置
                for feature_name, default_config in default_features.items():
                    if feature_name in saved_configs:
                        saved_config_data = saved_configs[feature_name]
                        # 保持默认值，但覆盖保存的设置
                        self.features[feature_name] = FeatureConfig(
                            **default_config.__dict__,
                            status=FeatureStatus(saved_config_data.get("status", default_config.status.value)),
                            config={**default_config.config, **saved_config_data.get("config", {})},
                            last_updated=saved_config_data.get("last_updated", time.time())
                        )
                    else:
                        self.features[feature_name] = default_config
                        
            except Exception as e:
                self.logger.error(f"Failed to load feature config: {e}")
                self.features = default_features
        else:
            self.features = default_features
        
        # 检查依赖和可用性
        self._check_feature_availability()
    
    def _save_feature_configs(self):
        """保存功能配置"""
        try:
            config_data = {}
            for name, feature in self.features.items():
                config_data[name] = asdict(feature)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Failed to save feature config: {e}")
    
    def _check_feature_availability(self):
        """检查功能可用性"""
        for name, feature in self.features.items():
            if not self._check_dependencies(feature.dependencies):
                feature.status = FeatureStatus.UNAVAILABLE
                self.logger.info(f"Feature {name} marked as unavailable due to missing dependencies")
    
    def _check_dependencies(self, dependencies: List[str]) -> bool:
        """检查依赖是否满足"""
        # 这里应该检查实际的依赖服务是否可用
        # 暂时简化处理，返回True
        return True
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """检查功能是否启用"""
        if feature_name not in self.features:
            return False
        
        feature = self.features[feature_name]
        
        # 核心功能始终启用
        if feature.level == FeatureLevel.CORE:
            return True
        
        # 检查状态
        if feature.status != FeatureStatus.ENABLED:
            return False
        
        # 检查依赖
        if not self._check_dependencies(feature.dependencies):
            return False
        
        return True
    
    def enable_feature(self, feature_name: str, user_id: str = None) -> bool:
        """启用功能"""
        if feature_name not in self.features:
            self.logger.warning(f"Unknown feature: {feature_name}")
            return False
        
        feature = self.features[feature_name]
        
        # 核心功能不能禁用，但可以重新启用
        if feature.level == FeatureLevel.CORE:
            self.logger.info(f"Core feature {feature_name} is always enabled")
        
        # 检查依赖
        if not self._check_dependencies(feature.dependencies):
            feature.status = FeatureStatus.UNAVAILABLE
            self.logger.warning(f"Cannot enable {feature_name}: dependencies not met")
            return False
        
        old_status = feature.status
        feature.status = FeatureStatus.ENABLED
        feature.last_updated = time.time()
        
        # 保存配置
        self._save_feature_configs()
        
        # 通知状态变更
        self._notify_status_change(feature_name, old_status, feature.status, user_id)
        
        self.logger.info(f"Feature {feature_name} enabled by {user_id or 'system'}")
        return True
    
    def disable_feature(self, feature_name: str, user_id: str = None) -> bool:
        """禁用功能"""
        if feature_name not in self.features:
            self.logger.warning(f"Unknown feature: {feature_name}")
            return False
        
        feature = self.features[feature_name]
        
        # 核心功能不能禁用
        if feature.level == FeatureLevel.CORE:
            self.logger.warning(f"Cannot disable core feature: {feature_name}")
            return False
        
        old_status = feature.status
        feature.status = FeatureStatus.DISABLED
        feature.last_updated = time.time()
        
        # 保存配置
        self._save_feature_configs()
        
        # 通知状态变更
        self._notify_status_change(feature_name, old_status, feature.status, user_id)
        
        self.logger.info(f"Feature {feature_name} disabled by {user_id or 'system'}")
        return True
    
    def get_feature_config(self, feature_name: str) -> Optional[FeatureConfig]:
        """获取功能配置"""
        return self.features.get(feature_name)
    
    def get_all_features(self) -> Dict[str, FeatureConfig]:
        """获取所有功能配置"""
        return self.features.copy()
    
    def get_enabled_features(self) -> List[str]:
        """获取已启用的功能列表"""
        return [name for name, feature in self.features.items() 
                if self.is_feature_enabled(name)]
    
    def get_feature_status_summary(self) -> Dict[str, Any]:
        """获取功能状态摘要"""
        summary = {
            "total_features": len(self.features),
            "enabled_features": 0,
            "disabled_features": 0,
            "unavailable_features": 0,
            "core_features": 0,
            "advanced_features": 0,
            "premium_features": 0,
            "features": {}
        }
        
        for name, feature in self.features.items():
            # 统计数量
            if feature.status == FeatureStatus.ENABLED:
                summary["enabled_features"] += 1
            elif feature.status == FeatureStatus.DISABLED:
                summary["disabled_features"] += 1
            elif feature.status == FeatureStatus.UNAVAILABLE:
                summary["unavailable_features"] += 1
            
            if feature.level == FeatureLevel.CORE:
                summary["core_features"] += 1
            elif feature.level == FeatureLevel.ADVANCED:
                summary["advanced_features"] += 1
            elif feature.level == FeatureLevel.PREMIUM:
                summary["premium_features"] += 1
            
            # 详细信息
            summary["features"][name] = {
                "status": feature.status.value,
                "level": feature.level.value,
                "enabled": self.is_feature_enabled(name),
                "description": feature.description,
                "require_restart": feature.require_restart,
                "dependencies": feature.dependencies
            }
        
        return summary
    
    def update_feature_config(self, feature_name: str, config_updates: Dict[str, Any], 
                            user_id: str = None) -> bool:
        """更新功能配置"""
        if feature_name not in self.features:
            return False
        
        feature = self.features[feature_name]
        old_config = feature.config.copy()
        
        # 更新配置
        feature.config.update(config_updates)
        feature.last_updated = time.time()
        
        # 保存配置
        self._save_feature_configs()
        
        # 检查是否需要重启
        if feature.require_restart:
            self.logger.info(f"Feature {feature_name} config updated, restart required")
        
        self.logger.info(f"Feature {feature_name} config updated by {user_id or 'system'}")
        return True
    
    def register_status_change_listener(self, listener_func):
        """注册状态变更监听器"""
        self.status_change_listeners.append(listener_func)
    
    def _notify_status_change(self, feature_name: str, old_status: FeatureStatus, 
                            new_status: FeatureStatus, user_id: str = None):
        """通知功能状态变更"""
        change_event = {
            "feature_name": feature_name,
            "old_status": old_status.value,
            "new_status": new_status.value,
            "user_id": user_id,
            "timestamp": time.time()
        }
        
        # 调用所有监听器
        for listener in self.status_change_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    asyncio.create_task(listener(change_event))
                else:
                    listener(change_event)
            except Exception as e:
                self.logger.error(f"Status change listener failed: {e}")
        
        # 发布事件到事件总线
        # 这里可以集成到现有的事件系统中
    
    def reset_to_defaults(self, feature_name: str = None, user_id: str = None):
        """重置为默认配置"""
        if feature_name:
            # 重置单个功能
            if feature_name in self.features:
                feature = self.features[feature_name]
                feature.status = FeatureStatus.ENABLED if feature.enabled_by_default else FeatureStatus.DISABLED
                feature.last_updated = time.time()
                self.logger.info(f"Feature {feature_name} reset to defaults by {user_id or 'system'}")
        else:
            # 重置所有功能
            for name, feature in self.features.items():
                feature.status = FeatureStatus.ENABLED if feature.enabled_by_default else FeatureStatus.DISABLED
                feature.last_updated = time.time()
            self.logger.info(f"All features reset to defaults by {user_id or 'system'}")
        
        # 保存配置
        self._save_feature_configs()
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """获取用户偏好设置"""
        return self.user_overrides.get(user_id, {})
    
    def set_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """设置用户偏好"""
        self.user_overrides[user_id] = preferences
        self.logger.info(f"User preferences updated for {user_id}")
    
    def create_feature_toggle_ui_config(self) -> Dict[str, Any]:
        """创建功能切换UI配置"""
        ui_config = {
            "sections": [
                {
                    "title": "核心功能",
                    "description": "系统核心功能，无法禁用",
                    "features": []
                },
                {
                    "title": "高级功能",
                    "description": "可选的高级功能，可以根据需要启用或禁用",
                    "features": []
                },
                {
                    "title": "Premium功能",
                    "description": "需要付费订阅的高级功能",
                    "features": []
                }
            ]
        }
        
        for name, feature in self.features.items():
            feature_info = {
                "name": name,
                "title": name.replace("_", " ").title(),
                "description": feature.description,
                "status": feature.status.value,
                "enabled": self.is_feature_enabled(name),
                "level": feature.level.value,
                "require_restart": feature.require_restart,
                "dependencies": feature.dependencies,
                "config": feature.config
            }
            
            # 根据级别添加到不同section
            if feature.level == FeatureLevel.CORE:
                ui_config["sections"][0]["features"].append(feature_info)
            elif feature.level == FeatureLevel.ADVANCED:
                ui_config["sections"][1]["features"].append(feature_info)
            elif feature.level == FeatureLevel.PREMIUM:
                ui_config["sections"][2]["features"].append(feature_info)
        
        return ui_config


# 全局实例
_feature_control_service = None

def get_feature_control_service() -> FeatureControlService:
    """获取全局功能控制服务实例"""
    global _feature_control_service
    if _feature_control_service is None:
        _feature_control_service = FeatureControlService()
    return _feature_control_service