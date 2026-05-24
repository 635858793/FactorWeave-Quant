from loguru import logger
"""
GPU兼容性检查器模块

负责：
1. 硬件兼容性检测
2. 驱动程序版本检查
3. 已知问题识别
4. 自动降级决策
"""

import re
import platform
import subprocess
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, replace
from enum import Enum
from .environment import GPUSupportLevel, GPUCapabilities


class CompatibilityLevel(Enum):
    """兼容性级别"""
    EXCELLENT = "excellent"     # 完全兼容，推荐使用
    GOOD = "good"              # 兼容性良好
    FAIR = "fair"              # 兼容性一般，可能有小问题
    POOR = "poor"              # 兼容性差，不推荐
    INCOMPATIBLE = "incompatible"  # 不兼容

@dataclass
class CompatibilityIssue:
    """兼容性问题"""
    issue_type: str
    severity: str  # critical, warning, info
    description: str
    workaround: Optional[str] = None
    affects_performance: bool = False

@dataclass
class CompatibilityReport:
    """兼容性报告"""
    level: CompatibilityLevel
    recommended_backend: GPUSupportLevel
    issues: List[CompatibilityIssue]
    performance_score: float  # 0-100
    recommendations: List[str]

class GPUCompatibilityChecker:
    """GPU兼容性检查器"""

    def __init__(self):
        # 已知问题数据库
        self.known_issues = self._load_known_issues()

        # GPU黑名单
        self.gpu_blacklist = {
            "Intel(R) HD Graphics 3000",
            "Intel(R) HD Graphics 2000",
            "AMD Radeon HD 5000",  # 系列
        }

        # 驱动版本要求
        self.driver_requirements = {
            "nvidia": {
                "min_version": "450.0",
                "recommended_version": "470.0"
            },
            "amd": {
                "min_version": "21.0",
                "recommended_version": "22.0"
            },
            "intel": {
                "min_version": "27.0",
                "recommended_version": "30.0"
            }
        }

    def _load_known_issues(self) -> Dict[str, List[CompatibilityIssue]]:
        """加载已知问题数据库"""
        return {
            "intel_hd": [
                CompatibilityIssue(
                    issue_type="driver",
                    severity="warning",
                    description="Intel集成显卡在某些驱动版本下可能出现渲染问题",
                    workaround="更新到最新驱动或使用OpenGL后备",
                    affects_performance=True
                )
            ],
            "amd_gcn1": [
                CompatibilityIssue(
                    issue_type="hardware",
                    severity="critical",
                    description="第一代GCN架构显卡不支持某些WebGPU特性",
                    workaround="自动降级到WebGL",
                    affects_performance=True
                )
            ],
            "nvidia_kepler": [
                CompatibilityIssue(
                    issue_type="performance",
                    severity="warning",
                    description="Kepler架构显卡性能可能不佳",
                    workaround="降低渲染质量设置",
                    affects_performance=True
                )
            ]
        }

    def check_compatibility(self, capabilities: GPUCapabilities, support_level: GPUSupportLevel) -> CompatibilityReport:
        """检查兼容性 - 以显存为核心的评分算法"""
        logger.info(f"开始兼容性检查: {capabilities.adapter_name}")

        issues = []
        performance_score = 100.0
        recommendations = []

        corrected_capabilities = self._normalize_capabilities(capabilities)

        # 1. 检查内存容量（作为主要评分标准）
        memory_issues, memory_score = self._check_memory_capacity(corrected_capabilities)
        issues.extend(memory_issues)
        performance_score = min(performance_score, memory_score)

        # 2. 检查GPU型号兼容性
        gpu_issues, gpu_score = self._check_gpu_model(corrected_capabilities)
        issues.extend(gpu_issues)
        # GPU型号对评分影响较小，只降低最多10分
        performance_score = max(performance_score - (100.0 - gpu_score) * 0.1, 0)

        # 3. 检查纹理支持
        texture_issues, texture_score = self._check_texture_support(corrected_capabilities)
        issues.extend(texture_issues)
        # 纹理支持对评分影响中等，降低最多20分
        performance_score = max(performance_score - (100.0 - texture_score) * 0.2, 0)

        # 4. 驱动版本检查已删除 - 完全基于显存容量评分

        # 5. 确定兼容性级别
        compatibility_level = self._determine_compatibility_level(
            issues, performance_score, support_level)

        # 6. 推荐后端（使用修正后的capabilities确保显存估算值正确传递）
        recommended_backend = self._recommend_backend(
            compatibility_level, support_level, issues, corrected_capabilities)

        # 7. 生成建议
        recommendations = self._generate_recommendations(
            issues, corrected_capabilities, support_level)

        report = CompatibilityReport(
            level=compatibility_level,
            recommended_backend=recommended_backend,
            issues=issues,
            performance_score=performance_score,
            recommendations=recommendations
        )

        logger.info(f"兼容性检查完成: {compatibility_level.value}, 性能评分: {performance_score:.1f}")
        logger.info(f"显存评分: {memory_score}, GPU型号评分: {gpu_score}, 纹理评分: {texture_score}")
        return report

    def _normalize_capabilities(self, capabilities: GPUCapabilities) -> GPUCapabilities:
        """规范化capabilities，修正异常的显存检测值"""
        memory_mb = capabilities.memory_mb
        if memory_mb <= 0 or memory_mb < 256:
            estimated = self._estimate_gpu_memory(capabilities.adapter_name, capabilities.vendor)
            if estimated > 0:
                logger.warning(f"显存检测异常 ({memory_mb}MB)，使用估算值: {estimated}MB")
                return replace(capabilities, memory_mb=estimated)
        return capabilities

    def _check_gpu_model(self, capabilities: GPUCapabilities) -> Tuple[List[CompatibilityIssue], float]:
        """检查GPU型号"""
        issues = []
        score = 100.0

        adapter_name = capabilities.adapter_name.lower()

        # 检查黑名单
        for blacklisted_gpu in self.gpu_blacklist:
            if blacklisted_gpu.lower() in adapter_name:
                issues.append(CompatibilityIssue(
                    issue_type="hardware",
                    severity="critical",
                    description=f"GPU型号 {capabilities.adapter_name} 已知存在兼容性问题",
                    workaround="建议使用软件渲染",
                    affects_performance=True
                ))
                score = 20.0
                break

        # 检查已知问题
        if "intel" in adapter_name and "hd" in adapter_name:
            if "intel_hd" in self.known_issues:
                issues.extend(self.known_issues["intel_hd"])
                score = min(score, 70.0)

        elif "amd" in adapter_name or "radeon" in adapter_name:
            # 检查AMD GCN架构
            if any(gcn1_gpu in adapter_name for gcn1_gpu in ["hd 7000", "hd 6000", "r9 200"]):
                if "amd_gcn1" in self.known_issues:
                    issues.extend(self.known_issues["amd_gcn1"])
                    score = min(score, 60.0)

        elif "nvidia" in adapter_name or "geforce" in adapter_name:
            # 检查Kepler架构
            if any(kepler_gpu in adapter_name for kepler_gpu in ["gtx 600", "gtx 700", "gt 600"]):
                if "nvidia_kepler" in self.known_issues:
                    issues.extend(self.known_issues["nvidia_kepler"])
                    score = min(score, 80.0)

        return issues, score

    def _check_memory_capacity(self, capabilities: GPUCapabilities) -> Tuple[List[CompatibilityIssue], float]:
        """检查内存容量 - 以显存为核心的评分"""
        issues = []
        score = 100.0

        memory_mb = capabilities.memory_mb
        gpu_name = capabilities.adapter_name.lower()

        logger.info(f"GPU显存容量检查: {memory_mb}MB (GPU: {capabilities.adapter_name})")

        # 针对GTX 1660 SUPER (6GB)的特殊优化
        if "gtx 1660" in gpu_name and memory_mb >= 6000:
            score = 95.0
            logger.info("检测到GTX 1660 SUPER (6GB)，高性能评分")
            return issues, score

        # 主要基于显存容量的评分
        if memory_mb < 512:
            issues.append(CompatibilityIssue(
                issue_type="memory",
                severity="critical",
                description=f"GPU内存容量过低: {memory_mb}MB",
                workaround="降低渲染质量或使用软件渲染",
                affects_performance=True
            ))
            score = 20.0
        elif memory_mb < 1024:  # 1GB
            issues.append(CompatibilityIssue(
                issue_type="memory",
                severity="warning",
                description=f"GPU内存容量较低: {memory_mb}MB",
                workaround="限制同时显示的数据点数量",
                affects_performance=True
            ))
            score = 50.0
        elif memory_mb < 2048:  # 2GB
            score = 70.0
        elif memory_mb < 4096:  # 4GB
            score = 85.0
        elif memory_mb < 6144:  # 6GB
            score = 90.0
        elif memory_mb < 8192:  # 8GB
            score = 95.0
        else:  # 8GB及以上
            score = 100.0

        logger.info(f"显存容量评分: {score:.1f}分 (实际: {memory_mb}MB)")
        return issues, score

    def _estimate_gpu_memory(self, gpu_name: str, vendor: str) -> int:
        """估算GPU显存容量"""
        gpu_name_lower = gpu_name.lower()
        
        # NVIDIA显卡显存估算
        if "nvidia" in vendor.lower() or "geforce" in gpu_name_lower:
            # GTX 16系列
            if "gtx 1660" in gpu_name_lower:
                return 6144  # 6GB
            elif "gtx 1650" in gpu_name_lower:
                return 4096  # 4GB
            
            # RTX 20系列
            elif "rtx 2060" in gpu_name_lower:
                return 6144  # 6GB
            elif "rtx 2070" in gpu_name_lower:
                return 8192  # 8GB
            elif "rtx 2080" in gpu_name_lower:
                return 8192  # 8GB
            
            # RTX 30系列
            elif "rtx 3060" in gpu_name_lower:
                return 12288  # 12GB
            elif "rtx 3070" in gpu_name_lower:
                return 8192   # 8GB
            elif "rtx 3080" in gpu_name_lower:
                return 10240  # 10GB
        
        # AMD显卡显存估算
        elif "amd" in vendor.lower() or "radeon" in gpu_name_lower:
            if "rx 580" in gpu_name_lower:
                return 8192   # 8GB
            elif "rx 5700" in gpu_name_lower:
                return 8192   # 8GB
            elif "rx 6600" in gpu_name_lower:
                return 8192   # 8GB
        
        # Intel集成显卡
        elif "intel" in vendor.lower():
            if "uhd" in gpu_name_lower:
                return 1024   # 1GB共享内存
            elif "iris" in gpu_name_lower:
                return 2048   # 2GB共享内存
        
        # 默认估算
        logger.warning(f"未知的GPU型号进行默认显存估算: {gpu_name}")
        return 2048  # 默认2GB

    def _check_texture_support(self, capabilities: GPUCapabilities) -> Tuple[List[CompatibilityIssue], float]:
        """检查纹理支持"""
        issues = []
        score = 100.0

        max_texture_size = capabilities.max_texture_size

        if max_texture_size < 2048:
            issues.append(CompatibilityIssue(
                issue_type="texture",
                severity="critical",
                description=f"纹理大小支持不足: {max_texture_size}",
                workaround="使用图块渲染",
                affects_performance=True
            ))
            score = 40.0
        elif max_texture_size < 4096:
            issues.append(CompatibilityIssue(
                issue_type="texture",
                severity="warning",
                description=f"纹理大小支持有限: {max_texture_size}",
                workaround="限制图表尺寸",
                affects_performance=False
            ))
            score = 70.0

        return issues, score

    def _check_driver_version(self, capabilities: GPUCapabilities) -> Tuple[List[CompatibilityIssue], float]:
        """检查驱动版本 - 作为辅助参考，权重较低"""
        issues = []
        score = 100.0

        try:
            driver_version = self._detect_driver_version(capabilities.vendor)
            
            if not driver_version:
                issues.append(CompatibilityIssue(
                    issue_type="driver",
                    severity="info",
                    description="无法检测GPU驱动版本",
                    workaround="建议更新到最新驱动，但不影响当前使用",
                    affects_performance=False
                ))
                return issues, score  # 返回100分，不影响性能评分

            vendor_key = capabilities.vendor.lower()
            if "nvidia" in vendor_key:
                requirements = self.driver_requirements.get("nvidia", {})
                version_score, version_issues = self._check_nvidia_version(driver_version, requirements)
            elif "amd" in vendor_key or "advanced micro devices" in vendor_key:
                requirements = self.driver_requirements.get("amd", {})
                version_score, version_issues = self._check_amd_version(driver_version, requirements)
            elif "intel" in vendor_key:
                requirements = self.driver_requirements.get("intel", {})
                version_score, version_issues = self._check_intel_version(driver_version, requirements)
            else:
                # 未知厂商，使用通用检查
                version_score, version_issues = self._check_generic_version(driver_version)
            
            issues.extend(version_issues)
            
            # 驱动版本检查结果不再直接影响主要性能评分
            # 只在版本异常低时才作为警告信息
            if version_score < 30.0:
                # 只有在极端情况下才轻微影响评分（最多5分）
                score = 95.0
            else:
                # 正常情况下不影响主要评分
                score = 100.0
            
        except Exception as e:
            logger.warning(f"驱动版本检查失败: {e}")
            # 驱动检查异常不影响性能评分
            score = 100.0

        return issues, score

    def _detect_driver_version(self, vendor: str) -> Optional[str]:
        """检测驱动版本"""
        try:
            if platform.system() == "Windows":
                return self._get_windows_driver_version(vendor)
            elif platform.system() == "Linux":
                return self._get_linux_driver_version(vendor)
            else:
                return self._get_macos_driver_version(vendor)
        except Exception as e:
            logger.warning(f"驱动版本检测失败: {e}")
            return None

    def _get_windows_driver_version(self, vendor: str) -> Optional[str]:
        """Windows系统驱动版本检测"""
        import subprocess
        
        try:
            # 使用wmic获取驱动信息
            result = subprocess.run([
                'wmic', 'path', 'win32_VideoController', 
                'get', 'DriverVersion,Name'
            ], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                for line in lines:
                    if vendor.lower() in line.lower():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            return parts[0]  # 返回版本号
        except Exception:
            pass
        
        return None

    def _get_linux_driver_version(self, vendor: str) -> Optional[str]:
        """Linux系统驱动版本检测"""
        try:
            # 检查nvidia-smi
            if "nvidia" in vendor.lower():
                result = subprocess.run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader,nounits'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            
            # 检查lspci
            result = subprocess.run(['lspci', '-v'], capture_output=True, text=True)
            if result.returncode == 0:
                # 简单的版本提取逻辑
                return "unknown"
        except Exception:
            pass
        
        return None

    def _get_macos_driver_version(self, vendor: str) -> Optional[str]:
        """macOS系统驱动版本检测"""
        # macOS驱动版本检测逻辑
        try:
            result = subprocess.run(['system_profiler', 'SPDisplaysDataType', '-xml'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return "unknown"  # 简化实现
        except Exception:
            pass
        
        return None

    def _check_nvidia_version(self, version: str, requirements: Dict[str, str]) -> Tuple[float, List[CompatibilityIssue]]:
        """NVIDIA驱动版本检查 - 支持传统和新格式驱动"""
        issues = []
        score = 100.0
        
        try:
            # 智能版本号解析 - 支持多种格式
            version_num = self._parse_nvidia_version(version)
            
            if version_num is None:
                issues.append(CompatibilityIssue(
                    issue_type="driver",
                    severity="warning",
                    description=f"NVIDIA驱动版本格式异常: {version}",
                    workaround="建议验证驱动版本格式，但系统仍可正常使用",
                    affects_performance=False
                ))
                score = 85.0
                return score, issues
            
            # 检测是否为新格式驱动（GTX 16系列及更新的DCH驱动）
            is_modern_driver = self._is_modern_nvidia_driver(version)
            
            if is_modern_driver:
                # 对于新格式驱动，使用较低的版本要求
                min_version = 30.0  # DCH驱动最低要求
                rec_version = 32.0  # DCH驱动推荐版本
            else:
                # 传统驱动格式，使用原有要求
                min_version = float(requirements.get("min_version", "450.0"))
                rec_version = float(requirements.get("recommended_version", "470.0"))
                
            logger.info(f"NVIDIA驱动版本解析: {version} -> {version_num:.1f} (要求: {min_version}, 推荐: {rec_version})")
            
            if version_num < min_version:
                severity = "warning" if is_modern_driver else "critical"
                issues.append(CompatibilityIssue(
                    issue_type="driver",
                    severity=severity,
                    description=f"NVIDIA驱动版本可能过旧: {version} (检测版本: {version_num:.1f})",
                    workaround="建议更新到最新NVIDIA驱动程序",
                    affects_performance=True
                ))
                score = 80.0 if is_modern_driver else 40.0
            elif version_num < rec_version:
                issues.append(CompatibilityIssue(
                    issue_type="driver",
                    severity="info",
                    description=f"NVIDIA驱动版本可优化: {version}",
                    workaround="更新到推荐版本以获得更好性能",
                    affects_performance=False
                ))
                score = 90.0
            else:
                # 版本良好，添加性能加分
                score = 95.0
                    
        except Exception as e:
            logger.warning(f"NVIDIA版本解析异常: {e}")
            issues.append(CompatibilityIssue(
                issue_type="driver",
                severity="warning",
                description=f"NVIDIA版本解析失败: {str(e)}",
                workaround="系统将使用通用兼容性设置",
                affects_performance=False
            ))
            score = 85.0
            
        return score, issues

    def _parse_nvidia_version(self, version: str) -> Optional[float]:
        """解析NVIDIA驱动版本号"""
        try:
            # 移除可能的后缀
            version = version.strip()
            
            # 检查是否为DCH驱动格式 (如: 32.0.15.8115)
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', version):
                parts = version.split('.')
                if len(parts) >= 2:
                    major = int(parts[0])
                    minor = int(parts[1])
                    return float(major) + float(minor) / 10.0
            
            # 检查传统格式 (如: 472.12)
            elif re.match(r'^\d+\.\d+$', version):
                parts = version.split('.')
                major = int(parts[0])
                minor = int(parts[1])
                return float(major) + float(minor) / 10.0
            
            # 检查简化版本号 (如: 472)
            elif re.match(r'^\d+$', version):
                return float(version)
                
            return None
            
        except Exception:
            return None
    
    def _is_modern_nvidia_driver(self, version: str) -> bool:
        """判断是否为现代NVIDIA驱动格式"""
        # DCH驱动通常以30+开始（如32.0.x.x）
        try:
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', version):
                major = int(version.split('.')[0])
                return major >= 30
            return False
        except Exception:
            return False

    def _check_amd_version(self, version: str, requirements: Dict[str, str]) -> Tuple[float, List[CompatibilityIssue]]:
        """AMD驱动版本检查"""
        issues = []
        score = 100.0
        
        try:
            # 解析AMD版本号格式
            version_parts = re.findall(r'\d+', version)
            if version_parts:
                major = int(version_parts[0])
                version_num = major
                
                min_version = float(requirements.get("min_version", "21.0"))
                rec_version = float(requirements.get("recommended_version", "22.0"))
                
                if version_num < min_version:
                    issues.append(CompatibilityIssue(
                        issue_type="driver",
                        severity="critical",
                        description=f"AMD驱动版本过低: {version} (要求: {min_version})",
                        workaround="请更新AMD驱动程序",
                        affects_performance=True
                    ))
                    score = 45.0
                elif version_num < rec_version:
                    issues.append(CompatibilityIssue(
                        issue_type="driver",
                        severity="warning",
                        description=f"AMD驱动版本建议更新: {version} (推荐: {rec_version})",
                        workaround="更新到推荐版本以获得更好性能",
                        affects_performance=True
                    ))
                    score = 80.0
                else:
                    score = 95.0
                    
        except Exception as e:
            issues.append(CompatibilityIssue(
                issue_type="driver",
                severity="warning",
                description=f"AMD版本解析失败: {str(e)}",
                workaround="建议手动验证驱动版本",
                affects_performance=False
            ))
            score = 85.0
            
        return score, issues

    def _check_intel_version(self, version: str, requirements: Dict[str, str]) -> Tuple[float, List[CompatibilityIssue]]:
        """Intel驱动版本检查"""
        issues = []
        score = 100.0
        
        try:
            # Intel版本号通常格式比较复杂，简化处理
            version_parts = re.findall(r'\d+', version)
            if version_parts:
                major = int(version_parts[0])
                version_num = major / 10.0
                
                min_version = float(requirements.get("min_version", "27.0"))
                rec_version = float(requirements.get("recommended_version", "30.0"))
                
                if version_num < min_version:
                    issues.append(CompatibilityIssue(
                        issue_type="driver",
                        severity="critical",
                        description=f"Intel驱动版本过低: {version} (要求: {min_version})",
                        workaround="请更新Intel显卡驱动程序",
                        affects_performance=True
                    ))
                    score = 50.0
                elif version_num < rec_version:
                    issues.append(CompatibilityIssue(
                        issue_type="driver",
                        severity="warning",
                        description=f"Intel驱动版本建议更新: {version} (推荐: {rec_version})",
                        workaround="更新到推荐版本以获得更好性能",
                        affects_performance=True
                    ))
                    score = 85.0
                else:
                    score = 95.0
                    
        except Exception as e:
            issues.append(CompatibilityIssue(
                issue_type="driver",
                severity="warning",
                description=f"Intel版本解析失败: {str(e)}",
                workaround="建议手动验证驱动版本",
                affects_performance=False
            ))
            score = 85.0
            
        return score, issues

    def _check_generic_version(self, version: str) -> Tuple[float, List[CompatibilityIssue]]:
        """通用驱动版本检查"""
        issues = []
        score = 90.0
        
        if not version:
            issues.append(CompatibilityIssue(
                issue_type="driver",
                severity="info",
                description="未知厂商的驱动版本",
                workaround="建议检查制造商推荐的驱动版本",
                affects_performance=False
            ))
            score = 85.0
        else:
            # 简单的版本合理性检查
            if len(version.split('.')) >= 2:
                score = 90.0
            else:
                issues.append(CompatibilityIssue(
                    issue_type="driver",
                    severity="warning",
                    description=f"驱动版本格式异常: {version}",
                    workaround="建议验证驱动版本格式",
                    affects_performance=False
                ))
                score = 80.0
                
        return score, issues

    def _determine_compatibility_level(self, issues: List[CompatibilityIssue],
                                       performance_score: float,
                                       support_level: GPUSupportLevel) -> CompatibilityLevel:
        """确定兼容性级别"""

        # 检查是否有关键问题
        has_critical_issues = any(issue.severity == "critical" for issue in issues)

        if has_critical_issues:
            return CompatibilityLevel.INCOMPATIBLE

        if support_level == GPUSupportLevel.NONE:
            return CompatibilityLevel.INCOMPATIBLE

        # 根据性能评分确定级别
        if performance_score >= 90:
            return CompatibilityLevel.EXCELLENT
        elif performance_score >= 75:
            return CompatibilityLevel.GOOD
        elif performance_score >= 60:
            return CompatibilityLevel.FAIR
        else:
            return CompatibilityLevel.POOR

    def _recommend_backend(self, compatibility_level: CompatibilityLevel,
                           current_support: GPUSupportLevel,
                           issues: List[CompatibilityIssue],
                           capabilities: GPUCapabilities = None) -> GPUSupportLevel:
        """推荐后端 - 基于显存容量的智能选择"""
        
        # 如果有硬件不兼容问题，直接降级
        if compatibility_level == CompatibilityLevel.INCOMPATIBLE:
            return GPUSupportLevel.BASIC

        # 检查是否有特定的硬件问题
        hardware_issues = [issue for issue in issues if issue.issue_type == "hardware"]
        if hardware_issues:
            for issue in hardware_issues:
                if "不支持" in issue.description or "不兼容" in issue.description:
                    return GPUSupportLevel.BASIC

        # 如果没有GPU能力信息，使用兼容性级别判断
        if capabilities is None:
            if compatibility_level in [CompatibilityLevel.EXCELLENT, CompatibilityLevel.GOOD]:
                return current_support
            elif compatibility_level == CompatibilityLevel.FAIR:
                return GPUSupportLevel.WEBGL if current_support == GPUSupportLevel.WEBGPU else current_support
            else:  # POOR
                return GPUSupportLevel.BASIC

        # 基于显存容量的智能后端选择
        memory_mb = capabilities.memory_mb

        logger.info(f"使用显存容量 {memory_mb}MB 进行后端选择")

        # 显存容量决定后端选择
        if memory_mb >= 6000:  # 6GB及以上（GTX 1660 SUPER级别）
            # 高性能GPU，优先使用WebGPU
            if current_support == GPUSupportLevel.WEBGPU:
                logger.info(f"高性能GPU ({memory_mb}MB)，推荐使用WebGPU")
                return GPUSupportLevel.WEBGPU
            elif current_support == GPUSupportLevel.WEBGL:
                return GPUSupportLevel.WEBGL
            else:
                return GPUSupportLevel.NATIVE
                
        elif memory_mb >= 4096:  # 4GB-6GB（中等性能GPU）
            # 中等性能GPU，根据兼容性选择
            if compatibility_level in [CompatibilityLevel.EXCELLENT, CompatibilityLevel.GOOD]:
                return current_support if current_support in [GPUSupportLevel.WEBGPU, GPUSupportLevel.WEBGL] else GPUSupportLevel.WEBGL
            else:
                return GPUSupportLevel.WEBGL
                
        elif memory_mb >= 2048:  # 2GB-4GB（入门级GPU）
            # 入门级GPU，使用WebGL
            return GPUSupportLevel.WEBGL
            
        else:  # 2GB以下
            # 低性能GPU，使用基础渲染
            return GPUSupportLevel.BASIC

    def _generate_recommendations(self, issues: List[CompatibilityIssue],
                                  capabilities: GPUCapabilities,
                                  support_level: GPUSupportLevel) -> List[str]:
        """生成优化建议"""
        recommendations = []

        # 基于问题生成建议
        for issue in issues:
            if issue.workaround:
                recommendations.append(issue.workaround)

        # 基于硬件能力生成建议
        if capabilities.memory_mb < 1024:
            recommendations.append("建议限制同时显示的数据点数量以节省内存")

        if capabilities.max_texture_size < 4096:
            recommendations.append("建议使用较小的图表尺寸以避免纹理限制")

        if not capabilities.supports_compute:
            recommendations.append("设备不支持计算着色器，某些高级功能可能不可用")

        # 通用优化建议
        if support_level == GPUSupportLevel.WEBGL:
            recommendations.append("使用WebGL后备，考虑启用降采样以提高性能")
        elif support_level == GPUSupportLevel.BASIC:
            recommendations.append("使用软件渲染，建议减少数据复杂度")

        # 去重
        return list(set(recommendations))

    def get_fallback_chain(self, report: CompatibilityReport) -> List[GPUSupportLevel]:
        """获取降级链"""
        chain = []

        if report.level in [CompatibilityLevel.EXCELLENT, CompatibilityLevel.GOOD]:
            # 高兼容性：首选推荐后端
            chain = [report.recommended_backend]
        else:
            # 低兼容性：提供完整降级链
            chain = [GPUSupportLevel.WEBGPU, GPUSupportLevel.WEBGL,
                     GPUSupportLevel.NATIVE, GPUSupportLevel.BASIC]

        # 根据具体问题调整降级链
        has_hardware_issues = any(issue.issue_type == "hardware" for issue in report.issues)
        if has_hardware_issues:
            # 硬件问题：跳过GPU渲染
            chain = [GPUSupportLevel.BASIC]

        return chain

    def should_auto_fallback(self, report: CompatibilityReport) -> bool:
        """是否应该自动降级"""
        return (report.level in [CompatibilityLevel.POOR, CompatibilityLevel.INCOMPATIBLE] or
                any(issue.severity == "critical" for issue in report.issues))

    def get_performance_settings(self, report: CompatibilityReport) -> Dict[str, Any]:
        """获取性能优化设置"""
        settings = {
            'max_points_per_batch': 10000,
            'enable_anti_aliasing': True,
            'enable_transparency': True,
            'texture_quality': 'high',
            'animation_fps': 60
        }

        # 根据兼容性级别调整
        if report.level == CompatibilityLevel.POOR:
            settings.update({
                'max_points_per_batch': 5000,
                'enable_anti_aliasing': False,
                'texture_quality': 'medium',
                'animation_fps': 30
            })
        elif report.level == CompatibilityLevel.FAIR:
            settings.update({
                'max_points_per_batch': 7500,
                'texture_quality': 'medium',
                'animation_fps': 45
            })

        # 根据内存容量调整
        if report.performance_score < 60:
            settings.update({
                'max_points_per_batch': settings['max_points_per_batch'] // 2,
                'enable_transparency': False
            })

        return settings
