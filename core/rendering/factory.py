"""
统一渲染器工厂

提供统一的渲染器创建和管理接口，支持多种渲染后端的动态选择。
实现工厂模式，简化渲染器实例化过程，支持配置管理和回退机制。
"""

import os
from loguru import logger
from typing import Dict, Any, List, Optional, Type, Union

from .interfaces import IChartRenderer, IRendererFactory
from .base_renderer import BaseChartRenderer
from .matplotlib_renderer import MatplotlibChartRenderer


class ChartRendererFactory(IRendererFactory):
    """
    图表渲染器工厂
    
    统一管理所有图表渲染器的创建和配置：
    1. 支持多种渲染器类型（matplotlib、WebGPU等）
    2. 自动回退机制（WebGPU → matplotlib）
    3. 配置管理和参数传递
    4. 单例模式（对于性能敏感的渲染器）
    5. 性能统计和监控
    """
    
    def __init__(self):
        """初始化渲染器工厂"""
        self._renderers = {}
        self._renderer_classes = {}
        self._default_config = {}
        self._logger = logger
        
        # 注册默认渲染器
        self._register_default_renderers()
        
        self._logger.info("渲染器工厂初始化完成")
    
    def _register_default_renderers(self):
        """注册默认渲染器类型"""
        self._renderer_classes = {
            'matplotlib': MatplotlibChartRenderer,
            # WebGPU渲染器将在后续步骤中注册
            # 'webgpu': WebGPUChartRenderer,
        }
        
        self._logger.debug(f"已注册渲染器类型: {list(self._renderer_classes.keys())}")
    
    def get_renderer(self, renderer_type: str = "auto", 
                    config: Dict[str, Any] = None) -> IChartRenderer:
        """
        获取渲染器实例
        
        Args:
            renderer_type: 渲染器类型 ("matplotlib", "webgpu", "auto")
            config: 配置参数字典
            
        Returns:
            IChartRenderer: 渲染器实例
            
        Raises:
            ValueError: 不支持的渲染器类型
            RuntimeError: 渲染器创建失败
        """
        try:
            # 合并配置
            merged_config = self._get_merged_config(config)
            
            # 自动选择渲染器类型
            if renderer_type == "auto":
                renderer_type = self._select_best_renderer_type(merged_config)
            
            # 检查渲染器类是否存在
            if renderer_type not in self._renderer_classes:
                raise ValueError(f"不支持的渲染器类型: {renderer_type}")
            
            # 获取渲染器类
            renderer_class = self._renderer_classes[renderer_type]
            
            # 创建渲染器实例
            renderer = self._create_renderer_instance(renderer_class, merged_config)
            
            self._logger.info(f"成功创建渲染器: {renderer_type}")
            return renderer
            
        except Exception as e:
            self._logger.error(f"创建渲染器失败: {str(e)}")
            raise RuntimeError(f"渲染器创建失败: {str(e)}")
    
    def _select_best_renderer_type(self, config: Dict[str, Any]) -> str:
        """
        自动选择最佳渲染器类型
        
        Args:
            config: 配置参数
            
        Returns:
            str: 推荐的渲染器类型
        """
        # 检查是否启用WebGPU
        enable_webgpu = config.get('enable_webgpu', False)
        
        if enable_webgpu:
            # 优先尝试WebGPU，如果不可用则回退到matplotlib
            try:
                # 这里可以添加WebGPU可用性检查
                return "webgpu"
            except Exception:
                self._logger.warning("WebGPU不可用，回退到matplotlib")
                return "matplotlib"
        else:
            return "matplotlib"
    
    def _create_renderer_instance(self, renderer_class: Type[IChartRenderer], 
                                config: Dict[str, Any]) -> IChartRenderer:
        """
        创建渲染器实例
        
        Args:
            renderer_class: 渲染器类
            config: 配置参数
            
        Returns:
            IChartRenderer: 渲染器实例
        """
        try:
            # 提取渲染器初始化参数
            init_params = self._extract_renderer_init_params(config)
            
            # 创建实例
            renderer = renderer_class(**init_params)
            
            # 初始化渲染器
            if not renderer.initialize(config):
                raise RuntimeError("渲染器初始化失败")
            
            return renderer
            
        except Exception as e:
            self._logger.error(f"创建渲染器实例失败: {str(e)}")
            raise
    
    def _extract_renderer_init_params(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        从配置中提取渲染器初始化参数
        
        Args:
            config: 完整配置
            
        Returns:
            Dict[str, Any]: 渲染器初始化参数字典
        """
        return {
            'enable_logging': config.get('enable_logging', True),
            'enable_performance_monitoring': config.get('enable_performance_monitoring', True)
        }
    
    def _get_merged_config(self, user_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        合并用户配置和默认配置
        
        Args:
            user_config: 用户配置
            
        Returns:
            Dict[str, Any]: 合并后的配置
        """
        merged = self._default_config.copy()
        if user_config:
            merged.update(user_config)
        
        return merged
    
    def register_renderer(self, renderer_type: str, 
                         renderer_class: Type[IChartRenderer]) -> bool:
        """
        注册渲染器类型
        
        Args:
            renderer_type: 渲染器类型标识
            renderer_class: 渲染器类
            
        Returns:
            bool: 注册成功返回True，失败返回False
        """
        try:
            if not issubclass(renderer_class, BaseChartRenderer):
                self._logger.error(f"渲染器类 {renderer_class} 必须继承自BaseChartRenderer")
                return False
            
            self._renderer_classes[renderer_type] = renderer_class
            self._logger.info(f"成功注册渲染器类型: {renderer_type}")
            return True
            
        except Exception as e:
            self._logger.error(f"注册渲染器类型失败: {str(e)}")
            return False
    
    def get_available_renderers(self) -> List[str]:
        """
        获取可用的渲染器类型列表
        
        Returns:
            List[str]: 可用的渲染器类型列表
        """
        return list(self._renderer_classes.keys())
    
    def get_renderer_info(self, renderer_type: str) -> Dict[str, Any]:
        """
        获取渲染器类型信息
        
        Args:
            renderer_type: 渲染器类型
            
        Returns:
            Dict[str, Any]: 渲染器类型信息
        """
        if renderer_type not in self._renderer_classes:
            return {"error": f"渲染器类型 {renderer_type} 不存在"}
        
        renderer_class = self._renderer_classes[renderer_type]
        
        # 创建临时实例获取信息（不推荐在生产环境使用）
        try:
            temp_renderer = renderer_class()
            info = temp_renderer.get_renderer_info()
            temp_renderer.cleanup()
            return info
        except Exception as e:
            return {"error": f"获取渲染器信息失败: {str(e)}"}
    
    def set_default_config(self, config: Dict[str, Any]):
        """
        设置默认配置
        
        Args:
            config: 默认配置字典
        """
        self._default_config.update(config)
        self._logger.debug(f"更新默认配置: {config}")
    
    def get_factory_info(self) -> Dict[str, Any]:
        """
        获取工厂信息
        
        Returns:
            Dict[str, Any]: 工厂信息字典
        """
        return {
            'factory_type': 'ChartRendererFactory',
            'available_renderers': list(self._renderer_classes.keys()),
            'default_config': self._default_config,
            'registered_renderers_count': len(self._renderer_classes)
        }


# 全局渲染器工厂实例
_global_factory = None


def get_chart_renderer_factory() -> ChartRendererFactory:
    """
    获取全局渲染器工厂实例（单例模式）
    
    Returns:
        ChartRendererFactory: 全局渲染器工厂实例
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = ChartRendererFactory()
    return _global_factory


def create_chart_renderer(renderer_type: str = "auto", 
                         config: Dict[str, Any] = None) -> IChartRenderer:
    """
    便捷函数：创建图表渲染器
    
    Args:
        renderer_type: 渲染器类型
        config: 配置参数
        
    Returns:
        IChartRenderer: 渲染器实例
    """
    factory = get_chart_renderer_factory()
    return factory.get_renderer(renderer_type, config)