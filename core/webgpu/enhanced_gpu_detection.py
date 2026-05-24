#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced GPU Detection Module
增强GPU检测模块

提供高级GPU检测和适配器选择功能，支持WebGPU和WebGL硬件能力检测

作者: FactorWeave-Quant团队
版本: 2.0
"""

import platform
import psutil
import subprocess
import time
import threading
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger
import json

class PowerPreference(Enum):
    """GPU功耗偏好设置"""
    LOW_POWER = "low-power"
    HIGH_PERFORMANCE = "high-performance"

class GPUType(Enum):
    """GPU类型"""
    INTEGRATED = "integrated"      # 集成显卡
    DISCRETE = "discrete"          # 独立显卡
    VIRTUAL = "virtual"            # 虚拟显卡
    UNKNOWN = "unknown"            # 未知类型

@dataclass
class GPUAdapter:
    """GPU适配器信息"""
    name: str
    vendor: str
    device_id: str
    memory_mb: int
    compute_units: int
    supports_webgpu: bool
    supports_webgl: bool
    is_discrete: bool  # 是否为独立显卡
    power_preference: PowerPreference
    driver_version: str = ""
    max_texture_size: int = 4096
    max_compute_units: int = 0
    is_virtual: bool = False  # 是否为虚拟设备
    gpu_type: GPUType = GPUType.UNKNOWN  # GPU类型
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'name': self.name,
            'vendor': self.vendor,
            'device_id': self.device_id,
            'memory_mb': self.memory_mb,
            'compute_units': self.compute_units,
            'supports_webgpu': self.supports_webgpu,
            'supports_webgl': self.supports_webgl,
            'is_discrete': self.is_discrete,
            'power_preference': self.power_preference.value,
            'driver_version': self.driver_version,
            'max_texture_size': self.max_texture_size,
            'max_compute_units': self.max_compute_units,
            'is_virtual': self.is_virtual,
            'gpu_type': self.gpu_type.value
        }

class GPUDetector:
    """GPU检测器"""
    
    # 虚拟设备识别模式
    VIRTUAL_DEVICE_PATTERNS = [
        'orayidd', 'virtual', 'microsoft', 'remote', 'vnc',
        'parallels', 'vmware', 'virtualbox', 'qxl', 'cirrus',
        'standard', 'basic', 'generic', 'adapter 1', 'adapter 2'
    ]
    
    # 物理GPU指示符
    PHYSICAL_GPU_INDICATORS = [
        'nvidia', 'geforce', 'quadro', 'tesla',
        'amd', 'radeon', 'firepro',
        'intel', 'uhd', 'iris', 'xe',
        'arc', 'a770', 'a750'
    ]
    
    def __init__(self):
        self._adapters: List[GPUAdapter] = []
        self._load_balancer: Optional[GPULoadBalancer] = None
        self._detect_hardware()
    
    def _detect_hardware(self):
        """检测硬件信息"""
        try:
            # 初始化基础GPU信息
            self._detect_system_gpu()
            self._detect_webgl_capabilities()
            
            # 应用虚拟设备过滤
            self._filter_virtual_devices()
            
            logger.info(f"GPU检测完成，检测到 {len(self._adapters)} 个有效GPU适配器")
            
        except Exception as e:
            logger.error(f"GPU硬件检测失败: {e}")
            # 添加默认适配器作为回退
            self._add_fallback_adapter()
    
    def _filter_virtual_devices(self):
        """过滤虚拟设备"""
        filtered_adapters = []
        
        for adapter in self._adapters:
            is_virtual = self._is_virtual_device(adapter.name)
            adapter.is_virtual = is_virtual
            
            if not is_virtual:
                filtered_adapters.append(adapter)
            else:
                logger.info(f"过滤虚拟设备: {adapter.name}")
        
        self._adapters = filtered_adapters
    
    def _is_virtual_device(self, device_name):
        """判断是否为虚拟设备"""
        name_lower = device_name.lower()
        
        # 检查虚拟设备模式
        for pattern in self.VIRTUAL_DEVICE_PATTERNS:
            if pattern in name_lower:
                return True
        
        # 检查物理GPU指示符（更严格的标准）
        has_physical_indicator = any(indicator in name_lower 
                                    for indicator in self.PHYSICAL_GPU_INDICATORS)
        
        # 如果包含物理GPU指示符且不包含虚拟设备模式，则认为是物理设备
        if has_physical_indicator:
            return False
        
        # 默认行为：未知设备需要进一步验证
        return self._requires_verification(device_name)
    
    def _requires_verification(self, device_name):
        """需要进一步验证的设备"""
        # 名称太通用或包含"controller"的设备
        generic_patterns = ['controller', 'adapter', 'device']
        return any(pattern in device_name.lower() 
                  for pattern in generic_patterns)
    
    def _classify_gpu_capability(self, adapter):
        """GPU能力分级"""
        name_lower = adapter.name.lower()
        
        # 高端GPU (WebGPU最优)
        high_end = ['rtx 3080', 'rtx 3090', 'rtx 4070', 'rtx 4080', 'rtx 4090']
        # 中端GPU (WebGPU良好)
        mid_range = ['gtx 1660', 'rtx 3060', 'rtx 3070', 'rtx 4060']
        # 低端GPU (WebGPU基础支持)
        low_end = ['gtx 1650', 'intel arc']
        
        if any(gpu in name_lower for gpu in high_end):
            return 'high_end'
        elif any(gpu in name_lower for gpu in mid_range):
            return 'mid_range'
        elif any(gpu in name_lower for gpu in low_end):
            return 'low_end'
        else:
            return 'unknown'
    
    def _detect_system_gpu(self):
        """检测系统GPU"""
        try:
            # 检测显卡信息
            gpu_info = self._get_gpu_info_from_system()
            
            for info in gpu_info:
                adapter = GPUAdapter(
                    name=info.get('name', 'Unknown GPU'),
                    vendor=info.get('vendor', 'Unknown'),
                    device_id=info.get('device_id', ''),
                    memory_mb=info.get('memory_mb', 0),
                    compute_units=info.get('compute_units', 0),
                    supports_webgpu=self._check_webgpu_support(info),
                    supports_webgl=True,
                    is_discrete=info.get('is_discrete', False),
                    power_preference=PowerPreference.HIGH_PERFORMANCE if info.get('is_discrete') else PowerPreference.LOW_POWER,
                    driver_version=info.get('driver_version', ''),
                    max_texture_size=info.get('max_texture_size', 4096),
                    is_virtual=info.get('is_virtual', False),
                    gpu_type=self._determine_gpu_type(
                        info.get('name', ''),
                        info.get('is_discrete', False),
                        info.get('is_virtual', False)
                    )
                )
                
                self._adapters.append(adapter)
                logger.debug(f"检测到GPU适配器: {adapter.name} ({adapter.memory_mb}MB)")
                
        except Exception as e:
            logger.error(f"系统GPU检测失败: {e}")
    
    def _get_gpu_info_from_system(self) -> List[Dict[str, Any]]:
        """从系统获取GPU信息"""
        gpu_list = []
        
        try:
            # Windows系统使用wmic命令检测显卡
            if platform.system() == "Windows":
                result = subprocess.run([
                    'wmic', 'path', 'win32_VideoController', 
                    'get', 'name,AdapterRAM,DeviceID'
                ], capture_output=True, text=True, encoding='utf-8', errors='ignore')
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                    for line in lines:
                        if line.strip():
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                # 智能解析GPU名称和显存
                                if len(parts) > 2:
                                    name = ' '.join(parts[:-1])
                                    adapter_ram = parts[-1]
                                else:
                                    name = parts[0]
                                    adapter_ram = parts[1] if len(parts) > 1 else "0"
                                
                                # 解析显存大小（从字节转换为MB）
                                memory_mb = self._parse_memory_size(adapter_ram)
                                
                                # 如果内存检测失败，使用GPU型号估算作为fallback
                                if memory_mb == 0 and name:
                                    memory_mb = self._estimate_default_memory(name)
                                    logger.debug(f"内存检测失败，使用估算值: {name} -> {memory_mb}MB")
                                
                                # 检测是否为独立显卡
                                is_discrete = any(keyword in name.lower() for keyword in [
                                    'nvidia', 'geforce', 'gtx', 'rtx', 'radeon', 'rx', 'vega'
                                ])
                                
                                gpu_list.append({
                                    'name': name,
                                    'vendor': self._detect_vendor(name),
                                    'device_id': '',
                                    'memory_mb': memory_mb,
                                    'compute_units': 0,
                                    'is_discrete': is_discrete,
                                    'is_virtual': False,
                                    'driver_version': '',
                                    'max_texture_size': 4096
                                })
                                
                                logger.debug(f"检测到GPU: {name} ({memory_mb}MB)")
            
            # 如果没有检测到显卡，添加默认适配器
            if not gpu_list:
                gpu_list.append({
                    'name': 'Integrated Graphics',
                    'vendor': 'Intel',
                    'device_id': '',
                    'memory_mb': 0,
                    'compute_units': 0,
                    'is_discrete': False,
                    'is_virtual': False,
                    'driver_version': '',
                    'max_texture_size': 4096
                })
                
        except Exception as e:
            logger.warning(f"系统GPU信息获取失败: {e}")
            # 添加默认适配器
            gpu_list.append({
                'name': 'Default Graphics',
                'vendor': 'Unknown',
                'device_id': '',
                'memory_mb': 0,
                'compute_units': 0,
                'is_discrete': False,
                'is_virtual': True,
                'driver_version': '',
                'max_texture_size': 4096
            })
        
        return gpu_list
    
    def _parse_memory_size(self, memory_str):
        """解析显存大小字符串"""
        if not memory_str or memory_str.lower() in ['0', 'null', '']:
            return 0
        
        try:
            # 移除单位，提取数字
            import re
            match = re.search(r'(\d+)', memory_str)
            if match:
                bytes_val = int(match.group(1))
                # 转换为MB
                memory_mb = bytes_val // (1024 * 1024)
                # 合理性检查
                if memory_mb > 0 and memory_mb < 65536:  # 0MB到64GB之间
                    return memory_mb
        except Exception:
            pass
        
        return 0
    
    def _estimate_default_memory(self, gpu_name):
        """基于GPU型号估算显存大小"""
        name_lower = gpu_name.lower()
        
        # 常见GPU型号的默认显存估算
        memory_estimates = {
            'gtx 1660': 6144,
            'gtx 1650': 4096,
            'rtx 3060': 12288,
            'rtx 3070': 8192,
            'rtx 3080': 10240,
            'uhd 730': 1024,
            'uhd 750': 1024,
            'intel iris': 2048
        }
        
        for gpu_model, memory_mb in memory_estimates.items():
            if gpu_model in name_lower:
                return memory_mb
        
        # 未知型号返回保守估算
        return 2048  # 2GB
    
    def _determine_gpu_type(self, name: str, is_discrete: bool, is_virtual: bool) -> GPUType:
        """确定GPU类型"""
        if is_virtual:
            return GPUType.VIRTUAL
        
        if is_discrete:
            return GPUType.DISCRETE
        else:
            return GPUType.INTEGRATED

    def _detect_vendor(self, gpu_name: str) -> str:
        """检测GPU厂商 - 增强版"""
        # 清理GPU名称
        cleaned_name = self._parse_gpu_name(gpu_name)
        cleaned_lower = cleaned_name.lower()
        
        # NVIDIA系列检测
        if any(term in cleaned_lower for term in ['nvidia', 'geforce', 'quadro', 'tesla']):
            return 'NVIDIA'
        # AMD系列检测
        elif any(term in cleaned_lower for term in ['amd', 'radeon', 'firepro', 'instinct']):
            return 'AMD'
        # Intel系列检测
        elif any(term in cleaned_lower for term in ['intel', 'uhd', 'iris', 'xe', 'arc']):
            return 'Intel'
        # Microsoft系列检测
        elif 'microsoft' in cleaned_lower:
            return 'Microsoft'
        else:
            return 'Unknown'
    
    def _parse_gpu_name(self, raw_name):
        """解析和清理GPU名称"""
        import re
        
        # 移除多余空格和标点
        cleaned = re.sub(r'[^\w\s]', ' ', raw_name)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 标准化常见命名
        gpu_name_mapping = {
            'nvidia geforce gtx': 'GTX',
            'nvidia geforce rtx': 'RTX',
            'intel uhd graphics': 'Intel UHD',
            'microsoft basic render': 'Microsoft Basic Render'
        }
        
        name_lower = cleaned.lower()
        for pattern, replacement in gpu_name_mapping.items():
            if pattern in name_lower:
                cleaned = cleaned.replace(pattern.split()[-1], replacement)
        
        return cleaned
    
    def _detect_gpu_model(self, gpu_name: str) -> Dict[str, str]:
        """检测具体GPU型号信息"""
        name_lower = gpu_name.lower()
        cleaned_name = self._parse_gpu_name(gpu_name)
        
        # GPU型号数据库
        gpu_models = {
            # NVIDIA高端系列
            'RTX 4090': {'tier': 'enthusiast', 'memory': 24576, 'performance': 'ultra'},
            'RTX 4080': {'tier': 'high_end', 'memory': 16384, 'performance': 'high'},
            'RTX 4070 Ti': {'tier': 'high_end', 'memory': 12288, 'performance': 'high'},
            'RTX 4070': {'tier': 'mid_high', 'memory': 12288, 'performance': 'high'},
            'RTX 4060 Ti': {'tier': 'mid_range', 'memory': 16384, 'performance': 'medium'},
            'RTX 4060': {'tier': 'mid_range', 'memory': 8192, 'performance': 'medium'},
            'RTX 3090': {'tier': 'enthusiast', 'memory': 24576, 'performance': 'ultra'},
            'RTX 3080': {'tier': 'high_end', 'memory': 10240, 'performance': 'high'},
            'RTX 3070': {'tier': 'mid_high', 'memory': 8192, 'performance': 'high'},
            'RTX 3060 Ti': {'tier': 'mid_range', 'memory': 8192, 'performance': 'medium'},
            'RTX 3060': {'tier': 'mid_range', 'memory': 12288, 'performance': 'medium'},
            'RTX 3050': {'tier': 'entry', 'memory': 8192, 'performance': 'low'},
            'GTX 1660 Ti': {'tier': 'mid_range', 'memory': 6144, 'performance': 'medium'},
            'GTX 1660': {'tier': 'mid_range', 'memory': 6144, 'performance': 'medium'},
            'GTX 1650': {'tier': 'entry', 'memory': 4096, 'performance': 'low'},
            
            # AMD系列
            'RX 7900 XTX': {'tier': 'enthusiast', 'memory': 24576, 'performance': 'ultra'},
            'RX 7900 XT': {'tier': 'high_end', 'memory': 20480, 'performance': 'high'},
            'RX 6800 XT': {'tier': 'high_end', 'memory': 16384, 'performance': 'high'},
            'RX 6700 XT': {'tier': 'mid_high', 'memory': 12288, 'performance': 'high'},
            'RX 6600 XT': {'tier': 'mid_range', 'memory': 8192, 'performance': 'medium'},
            'RX 6600': {'tier': 'mid_range', 'memory': 8192, 'performance': 'medium'},
            'RX 580': {'tier': 'mid_range', 'memory': 8192, 'performance': 'medium'},
            'RX 570': {'tier': 'entry', 'memory': 8192, 'performance': 'low'},
            
            # Intel系列
            'Arc A770': {'tier': 'mid_high', 'memory': 16384, 'performance': 'high'},
            'Arc A750': {'tier': 'mid_range', 'memory': 8192, 'performance': 'medium'},
            'Arc A580': {'tier': 'mid_range', 'memory': 8192, 'performance': 'medium'},
            'UHD Graphics 770': {'tier': 'integrated', 'memory': 1024, 'performance': 'low'},
            'UHD Graphics 750': {'tier': 'integrated', 'memory': 1024, 'performance': 'low'},
            'UHD Graphics 730': {'tier': 'integrated', 'memory': 512, 'performance': 'low'},
            'Iris Xe': {'tier': 'integrated', 'memory': 2048, 'performance': 'medium'},
            'Iris Plus': {'tier': 'integrated', 'memory': 1024, 'performance': 'low'}
        }
        
        # 精确匹配GPU型号
        for model, specs in gpu_models.items():
            if model.lower() in name_lower:
                return {
                    'model': model,
                    'tier': specs['tier'],
                    'estimated_memory': specs['memory'],
                    'performance': specs['performance']
                }
        
        # 如果没有精确匹配，尝试模糊匹配
        if 'rtx' in name_lower and any(num in name_lower for num in ['4090', '4080', '4070', '4060']):
            # 提取数字
            import re
            numbers = re.findall(r'40\d{2}', name_lower)
            if numbers:
                model = f"RTX {numbers[0]}"
                return {
                    'model': model,
                    'tier': 'unknown',
                    'estimated_memory': 0,
                    'performance': 'unknown'
                }
        
        # 默认返回
        return {
            'model': 'Unknown',
            'tier': 'unknown',
            'estimated_memory': 0,
            'performance': 'unknown'
        }
    
    def _check_webgpu_support(self, gpu_info: Dict[str, Any]) -> bool:
        """检查WebGPU支持"""
        try:
            # 基础WebGPU支持检测
            vendor = gpu_info.get('vendor', '').lower()
            name = gpu_info.get('name', '').lower()
            
            # 简单的WebGPU支持判断逻辑
            if 'nvidia' in vendor and any(model in name for model in ['gtx', 'rtx']):
                return True
            elif 'amd' in vendor and any(model in name for model in ['rx', 'vega']):
                return True
            elif 'intel' in vendor and any(model in name for model in ['iris', 'xe']):
                return True
            else:
                # 大多数现代GPU都支持WebGL，但WebGPU支持有限
                return False
                
        except Exception as e:
            logger.warning(f"WebGPU支持检测失败: {e}")
            return False
    
    def _detect_webgl_capabilities(self):
        """检测WebGL能力"""
        try:
            # 更新适配器的WebGL支持状态
            for adapter in self._adapters:
                # 大多数现代GPU都支持WebGL
                adapter.supports_webgl = True
                
                # 更新纹理大小等WebGL特性
                if adapter.is_discrete:
                    adapter.max_texture_size = 8192  # 独立显卡通常支持更大的纹理
                else:
                    adapter.max_texture_size = 4096  # 集成显卡纹理限制
                    
        except Exception as e:
            logger.error(f"WebGL能力检测失败: {e}")
    
    def _add_fallback_adapter(self):
        """添加回退适配器"""
        fallback_adapter = GPUAdapter(
            name="Software Renderer",
            vendor="Microsoft",
            device_id="",
            memory_mb=0,
            compute_units=0,
            supports_webgpu=False,
            supports_webgl=True,
            is_discrete=False,
            power_preference=PowerPreference.LOW_POWER,
            driver_version="",
            max_texture_size=2048,
            is_virtual=True,
            gpu_type=GPUType.VIRTUAL
        )
        
        self._adapters.append(fallback_adapter)
        logger.info("添加了回退软件渲染器")
    
    def detect_all_adapters(self) -> List[GPUAdapter]:
        """检测所有适配器"""
        return self._adapters.copy()
    
    def select_best_adapter(self, power_preference: PowerPreference = PowerPreference.HIGH_PERFORMANCE, 
                          require_discrete: bool = False) -> Optional[GPUAdapter]:
        """选择最佳适配器"""
        if not self._adapters:
            return None
        
        try:
            # 根据偏好排序
            def adapter_score(adapter: GPUAdapter) -> int:
                score = 0
                
                # 功耗偏好得分
                if adapter.power_preference == power_preference:
                    score += 10
                
                # 独立显卡得分
                if adapter.is_discrete:
                    score += 5
                
                # 显存大小得分
                if adapter.memory_mb > 0:
                    score += min(adapter.memory_mb // 256, 10)
                
                # WebGPU支持得分
                if adapter.supports_webgpu:
                    score += 8
                
                # WebGL支持得分
                if adapter.supports_webgl:
                    score += 3
                
                return score
            
            # 排序并筛选
            sorted_adapters = sorted(self._adapters, key=adapter_score, reverse=True)
            
            # 如果要求独立显卡，筛选出独立显卡
            if require_discrete:
                discrete_adapters = [a for a in sorted_adapters if a.is_discrete]
                if discrete_adapters:
                    return discrete_adapters[0]
            
            return sorted_adapters[0] if sorted_adapters else None
            
        except Exception as e:
            logger.error(f"选择最佳适配器失败: {e}")
            return self._adapters[0] if self._adapters else None
    
    def get_load_balancer(self) -> Optional["GPULoadBalancer"]:
        """获取负载均衡器"""
        if self._load_balancer is None:
            if len(self._adapters) > 1:
                self._load_balancer = GPULoadBalancer([self])
        return self._load_balancer
    
    def optimize_for_multi_gpu(self):
        """为多GPU优化"""
        if len(self._adapters) > 1:
            balancer = self.get_load_balancer()
            if balancer:
                logger.info("检测到多GPU配置，启用负载均衡")
                return balancer
        return None

# 全局GPU检测器缓存
_gpu_detector_instance = None
_detector_lock = threading.Lock()
_detection_timestamp = 0
_DETECTION_CACHE_DURATION = 30  # 缓存30秒

def get_gpu_detector() -> GPUDetector:
    """获取GPU检测器实例（带缓存机制）"""
    global _gpu_detector_instance, _detection_timestamp
    current_time = time.time()
    
    with _detector_lock:
        # 检查缓存是否有效
        if (_gpu_detector_instance is not None and 
            current_time - _detection_timestamp < _DETECTION_CACHE_DURATION):
            logger.debug("使用缓存的GPU检测器")
            return _gpu_detector_instance
        
        # 创建新的检测器实例
        logger.info("创建新的GPU检测器实例")
        _gpu_detector_instance = GPUDetector()
        _detection_timestamp = current_time
        return _gpu_detector_instance

# 便捷函数
def get_best_gpu_adapter(power_preference: PowerPreference = PowerPreference.HIGH_PERFORMANCE) -> Optional[GPUAdapter]:
    """获取最佳GPU适配器"""
    detector = get_gpu_detector()
    return detector.select_best_adapter(power_preference)

def list_all_gpus() -> List[GPUAdapter]:
    """列出所有检测到的GPU"""
    detector = get_gpu_detector()
    return detector.detect_all_adapters()

def check_webgpu_support() -> bool:
    """检查系统WebGPU支持"""
    detector = get_gpu_detector()
    adapters = detector.detect_all_adapters()
    return any(adapter.supports_webgpu for adapter in adapters)


class GPULoadBalancer:
    """GPU负载均衡器"""
    
    def __init__(self, detectors: List[GPUDetector]):
        self.detectors = detectors
        self.load_history = {}
        self.performance_benchmarks = {}
        self.task_queue = []
        self.is_balancing = False
        
    def initialize_benchmarks(self):
        """初始化性能基准测试"""
        logger.info("开始GPU性能基准测试...")
        
        for i, detector in enumerate(self.detectors):
            adapter = detector.select_best_adapter()
            if adapter and adapter.supports_webgpu:
                benchmark = self._run_gpu_benchmark(adapter)
                self.performance_benchmarks[i] = benchmark
                logger.info(f"GPU {i} ({adapter.name}) 基准测试: {benchmark}")
    
    def _run_gpu_benchmark(self, adapter: GPUAdapter) -> Dict[str, float]:
        """运行GPU性能基准测试"""
        import time

        logger.warning("GPU基准测试未集成实际计算任务，使用硬件规格评分")
        start_time = time.time()
        end_time = time.time()
        
        # 基于实际性能调整分数
        performance_score = 100.0
        if adapter.memory_mb > 8192:
            performance_score += 10
        if adapter.memory_mb > 16384:
            performance_score += 10
        if adapter.is_discrete:
            performance_score += 15
            
        # WebGPU支持加成
        if adapter.supports_webgpu:
            performance_score += 20
            
        # 根据显存调整
        if adapter.memory_mb > 0:
            memory_score = min(adapter.memory_mb // 256, 20)
            performance_score += memory_score
        
        return {
            'compute_time': end_time - start_time,
            'performance_score': min(performance_score, 150.0),
            'memory_score': min(adapter.memory_mb // 128, 30) if adapter.memory_mb > 0 else 0,
            'webgpu_support': adapter.supports_webgpu,
            'vendor_bonus': self._get_vendor_bonus(adapter.vendor)
        }
    
    def _get_vendor_bonus(self, vendor: str) -> float:
        """获取厂商性能加成"""
        bonus_map = {
            'NVIDIA': 15.0,
            'AMD': 12.0,
            'Intel': 8.0,
            'Microsoft': 5.0,
            'Unknown': 0.0
        }
        return bonus_map.get(vendor, 0.0)
    
    def assign_task(self, task_complexity: float, task_type: str = 'compute') -> int:
        """分配任务到最适合的GPU"""
        if not self.performance_benchmarks:
            self.initialize_benchmarks()
        
        # 获取当前负载状态
        current_loads = self._get_current_loads()
        
        # 选择最佳GPU
        best_gpu_index = self._select_best_gpu(task_complexity, current_loads)
        
        # 更新负载记录
        self._update_load_record(best_gpu_index, task_complexity)
        
        logger.debug(f"任务分配: GPU {best_gpu_index}, 复杂度: {task_complexity}")
        return best_gpu_index
    
    def _get_current_loads(self) -> Dict[int, float]:
        """获取当前GPU负载状态"""
        current_loads = {}
        
        for gpu_id in self.performance_benchmarks.keys():
            # 计算最近1分钟的平均负载
            history = self.load_history.get(gpu_id, [])
            if history:
                recent_loads = [load for load, timestamp in history if time.time() - timestamp < 60]
                if recent_loads:
                    current_loads[gpu_id] = sum(recent_loads) / len(recent_loads)
                else:
                    current_loads[gpu_id] = 0.0
            else:
                current_loads[gpu_id] = 0.0
        
        return current_loads
    
    def _select_best_gpu(self, task_complexity: float, current_loads: Dict[int, float]) -> int:
        """选择最佳GPU"""
        best_score = -1
        best_gpu = 0
        
        for gpu_id, benchmark in self.performance_benchmarks.items():
            # 综合评分算法
            base_score = benchmark['performance_score']
            
            # 考虑当前负载
            current_load = current_loads.get(gpu_id, 0.0)
            load_penalty = current_load * 50  # 负载越高惩罚越重
            
            # 任务复杂度适应
            complexity_bonus = 0
            if task_complexity > 0.8:  # 高复杂度任务
                if benchmark['performance_score'] > 100:
                    complexity_bonus = 20
            elif task_complexity < 0.3:  # 低复杂度任务
                if benchmark['performance_score'] < 80:
                    complexity_bonus = 10
            
            # WebGPU支持加成
            webgpu_bonus = 30 if benchmark['webgpu_support'] else 0
            
            total_score = base_score + complexity_bonus + webgpu_bonus - load_penalty
            
            if total_score > best_score:
                best_score = total_score
                best_gpu = gpu_id
        
        return best_gpu
    
    def _update_load_record(self, gpu_id: int, task_complexity: float):
        """更新负载记录"""
        import time
        
        if gpu_id not in self.load_history:
            self.load_history[gpu_id] = []
        
        # 添加新的负载记录
        self.load_history[gpu_id].append((task_complexity, time.time()))
        
        # 清理旧记录（保留最近5分钟）
        cutoff_time = time.time() - 300
        self.load_history[gpu_id] = [
            (load, timestamp) for load, timestamp in self.load_history[gpu_id]
            if timestamp > cutoff_time
        ]
    
    def get_load_status(self) -> Dict[int, Dict[str, Any]]:
        """获取负载状态"""
        status = {}
        current_loads = self._get_current_loads()
        
        for gpu_id, benchmark in self.performance_benchmarks.items():
            adapter = self.detectors[gpu_id].select_best_adapter()
            
            status[gpu_id] = {
                'name': adapter.name if adapter else f"GPU {gpu_id}",
                'current_load': current_loads.get(gpu_id, 0.0),
                'performance_score': benchmark['performance_score'],
                'memory_mb': adapter.memory_mb if adapter else 0,
                'supports_webgpu': benchmark['webgpu_support'],
                'vendor': adapter.vendor if adapter else 'Unknown',
                'task_count': len(self.load_history.get(gpu_id, []))
            }
        
        return status
    
    def rebalance_loads(self):
        """重新平衡负载"""
        if self.is_balancing:
            return
        
        self.is_balancing = True
        try:
            current_loads = self._get_current_loads()
            
            # 检查是否需要重新平衡
            if len(current_loads) > 1:
                loads = list(current_loads.values())
                max_load = max(loads)
                min_load = min(loads)
                
                # 如果负载差异超过50%，触发重新平衡
                if max_load > min_load * 1.5:
                    logger.info("检测到负载不均衡，开始重新平衡...")
                    self._perform_rebalancing()
        finally:
            self.is_balancing = False
    
    def _perform_rebalancing(self):
        """执行负载重新平衡"""
        # 简化实现：输出重新平衡建议
        current_loads = self._get_current_loads()
        
        sorted_gpus = sorted(current_loads.items(), key=lambda x: x[1], reverse=True)
        
        logger.info("负载重新平衡建议:")
        for i, (gpu_id, load) in enumerate(sorted_gpus):
            adapter = self.detectors[gpu_id].select_best_adapter()
            status = "高负载" if load > 0.7 else "中等负载" if load > 0.3 else "低负载"
            logger.info(f"  GPU {gpu_id} ({adapter.name if adapter else 'Unknown'}): {status} ({load:.2f})")
    
    def optimize_for_workload(self, workload_type: str):
        """根据工作负载类型优化"""
        logger.info(f"根据工作负载类型优化: {workload_type}")
        
        if workload_type == "high_performance":
            # 高性能计算：优先使用最强GPU
            self._optimize_for_high_performance()
        elif workload_type == "balanced":
            # 平衡负载：平均分配
            self._optimize_for_balanced()
        elif workload_type == "power_efficient":
            # 节能模式：优先使用集成显卡
            self._optimize_for_power_efficient()
    
    def _optimize_for_high_performance(self):
        """高性能计算优化"""
        # 将高性能任务优先分配给最强的GPU
        best_gpu = max(self.performance_benchmarks.items(), 
                      key=lambda x: x[1]['performance_score'])[0]
        logger.info(f"高性能模式：优先使用GPU {best_gpu}")
    
    def _optimize_for_balanced(self):
        """平衡负载优化"""
        logger.info("平衡模式：启用负载均衡")
    
    def _optimize_for_power_efficient(self):
        """节能模式优化"""
        # 优先使用集成显卡
        for gpu_id, benchmark in self.performance_benchmarks.items():
            if 'Intel' in str(benchmark):  # 简化判断
                logger.info(f"节能模式：优先使用GPU {gpu_id}")
                break
    
    def _run_gpu_benchmark(self, adapter) -> Dict[str, Any]:
        """运行GPU性能基准测试"""
        import time
        
        logger.info(f"正在对GPU {adapter.name} 进行基准测试...")
        
        # 模拟基准测试过程
        # 实际实现中应该运行真实的GPU性能测试
        benchmark_start = time.time()
        
        # 基础性能评分
        performance_score = self._calculate_base_performance_score(adapter)
        
        # WebGPU支持检查
        webgpu_support = self._check_webgpu_capability(adapter)
        
        # 计算基准测试时间
        benchmark_time = time.time() - benchmark_start
        
        benchmark_result = {
            'performance_score': performance_score,
            'webgpu_support': webgpu_support,
            'benchmark_time': benchmark_time,
            'timestamp': time.time()
        }
        
        logger.info(f"GPU {adapter.name} 基准测试完成: {benchmark_result}")
        return benchmark_result
    
    def _calculate_base_performance_score(self, adapter) -> float:
        """计算基础性能评分"""
        score = 50.0  # 基础分
        
        # 根据显存调整
        if adapter.memory_mb:
            if adapter.memory_mb >= 8192:  # 8GB+
                score += 40
            elif adapter.memory_mb >= 4096:  # 4GB+
                score += 30
            elif adapter.memory_mb >= 2048:  # 2GB+
                score += 20
            elif adapter.memory_mb >= 1024:  # 1GB+
                score += 10
        
        # 根据厂商调整
        if "nvidia" in adapter.vendor.lower():
            score += 20
        elif "amd" in adapter.vendor.lower() or "advanced micro devices" in adapter.vendor.lower():
            score += 15
        elif "intel" in adapter.vendor.lower():
            score += 5
        
        return score
    
    def _check_webgpu_capability(self, adapter) -> bool:
        """检查WebGPU能力"""
        # 简化实现：基于基本要求
        min_memory = 256  # MB
        return adapter.memory_mb >= min_memory


# 便捷函数
def create_load_balancer(gpu_detectors: List[GPUDetector]) -> GPULoadBalancer:
    """创建负载均衡器"""
    return GPULoadBalancer(gpu_detectors)

def get_multi_gpu_setup() -> Tuple[List[GPUDetector], Optional[GPULoadBalancer]]:
    """获取多GPU设置"""
    detectors = []
    
    # 检测多个GPU
    main_detector = get_gpu_detector()
    detectors.append(main_detector)
    
    # 简化实现：假设只有一个主检测器
    # 实际实现中应该检测多个独立的GPU
    
    if len(detectors) > 1:
        balancer = create_load_balancer(detectors)
        return detectors, balancer
    else:
        return detectors, None

def check_webgl_support() -> bool:
    """检查系统WebGL支持"""
    detector = get_gpu_detector()
    adapters = detector.detect_all_adapters()
    return any(adapter.supports_webgl for adapter in adapters)

def get_gpu_capabilities_summary() -> Dict[str, Any]:
    """获取GPU能力摘要"""
    detector = get_gpu_detector()
    adapters = detector.detect_all_adapters()
    
    if not adapters:
        return {
            'total_gpus': 0,
            'webgpu_supported': False,
            'webgl_supported': False,
            'best_adapter': None
        }
    
    best_adapter = detector.select_best_adapter()
    
    return {
        'total_gpus': len(adapters),
        'webgpu_supported': any(adapter.supports_webgpu for adapter in adapters),
        'webgl_supported': any(adapter.supports_webgl for adapter in adapters),
        'best_adapter': best_adapter.to_dict() if best_adapter else None,
        'all_adapters': [adapter.to_dict() for adapter in adapters]
    }