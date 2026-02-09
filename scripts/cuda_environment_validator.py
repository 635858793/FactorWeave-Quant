#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CUDA环境自动验证和配置脚本

功能：
1. 自动检测CUDA安装和配置
2. 验证TensorFlow GPU版本兼容性
3. 提供详细的诊断报告
4. 自动安装建议和故障排除

使用方法：
python scripts/cuda_environment_validator.py [--auto-install] [--verbose]

作者: FactorWeave-Quant团队
版本: 1.0
"""

import os
import sys
import subprocess
import platform
import urllib.request
import tempfile
import zipfile
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CUDAEnvironmentValidator:
    """CUDA环境验证器"""
    
    def __init__(self):
        self.system = platform.system()
        self.python_version = sys.version_info
        self.cuda_info = {}
        self.tensorflow_info = {}
        self.gpu_info = {}
        self.compatibility_matrix = self._load_compatibility_matrix()
        
    def _load_compatibility_matrix(self) -> Dict:
        """加载CUDA-TensorFlow兼容性矩阵"""
        return {
            "tensorflow": {
                "2.12.0": {"cuda": "11.8", "cudnn": "8.6"},
                "2.13.0": {"cuda": "11.8", "cudnn": "8.6"},
                "2.14.0": {"cuda": "12.1", "cudnn": "8.8"},
                "2.15.0": {"cuda": "12.1", "cudnn": "8.9"},
                "2.16.0": {"cuda": "12.3", "cudnn": "8.9"}
            },
            "cuda_versions": ["11.0", "11.2", "11.4", "11.6", "11.8", "12.0", "12.1", "12.2", "12.3"],
            "cudnn_versions": ["8.0", "8.2", "8.4", "8.6", "8.8", "8.9"]
        }
    
    def detect_python_environment(self) -> Dict:
        """检测Python环境"""
        logger.info("检测Python环境...")
        
        info = {
            "version": f"{self.python_version.major}.{self.python_version.minor}.{self.python_version.micro}",
            "architecture": platform.architecture()[0],
            "machine": platform.machine(),
            "platform": platform.platform(),
            "virtual_env": os.environ.get('VIRTUAL_ENV') is not None,
            "conda_env": os.environ.get('CONDA_DEFAULT_ENV') is not None
        }
        
        # 检查是否在虚拟环境中
        if info["virtual_env"]:
            info["virtual_env_path"] = os.environ.get('VIRTUAL_ENV')
        elif info["conda_env"]:
            info["conda_env_name"] = os.environ.get('CONDA_DEFAULT_ENV')
        
        logger.info(f"  Python版本: {info['version']}")
        logger.info(f"  架构: {info['architecture']}")
        logger.info(f"  平台: {info['platform']}")
        
        return info
    
    def detect_cuda_installation(self) -> Dict:
        """检测CUDA安装"""
        logger.info("检测CUDA安装...")
        
        cuda_info = {
            "installed": False,
            "version": "unknown",
            "path": "unknown",
            "nvcc_available": False,
            "libraries": [],
            "driver_version": "unknown"
        }
        
        try:
            # 1. 检查环境变量
            cuda_paths = [
                os.environ.get('CUDA_PATH'),
                os.environ.get('CUDA_HOME'),
                os.environ.get('CUDA_ROOT'),
                "/usr/local/cuda",  # Linux默认路径
                "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v11.8",  # Windows默认路径
            ]
            
            for path in cuda_paths:
                if path and Path(path).exists():
                    cuda_info["path"] = path
                    logger.info(f"  找到CUDA路径: {path}")
                    break
            
            # 2. 检查nvcc命令
            try:
                result = subprocess.run(['nvcc', '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    cuda_info["nvcc_available"] = True
                    # 解析版本信息
                    output = result.stdout
                    for line in output.split('\n'):
                        if 'release' in line.lower():
                            version = line.split('release')[1].strip().split(',')[0]
                            cuda_info["version"] = version
                            logger.info(f"  NVCC版本: {version}")
                            break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                logger.warning("  NVCC命令不可用")
            
            # 3. 检查CUDA库文件
            if self.system == "Windows":
                cuda_libs = ["cudart64_110.dll", "cudart64_118.dll", "cudart64_120.dll"]
            else:
                cuda_libs = ["libcudart.so.11.0", "libcudart.so.11.8", "libcudart.so.12.0"]
            
            for lib in cuda_libs:
                try:
                    if self.system == "Windows":
                        import ctypes
                        ctypes.WinDLL(lib)
                    else:
                        import ctypes
                        ctypes.CDLL(lib)
                    cuda_info["libraries"].append(lib)
                    logger.info(f"  找到CUDA库: {lib}")
                except (OSError, ImportError):
                    continue
            
            cuda_info["installed"] = len(cuda_info["libraries"]) > 0 or cuda_info["nvcc_available"]
            
        except Exception as e:
            logger.error(f"CUDA检测失败: {e}")
        
        return cuda_info
    
    def detect_cudnn_installation(self) -> Dict:
        """检测cuDNN安装"""
        logger.info("检测cuDNN安装...")
        
        cudnn_info = {
            "installed": False,
            "version": "unknown",
            "libraries": [],
            "header_files": []
        }
        
        try:
            # 1. 检查cuDNN库文件
            if self.system == "Windows":
                cudnn_libs = ["cudnn64_8.dll", "cudnn.lib"]
            else:
                cudnn_libs = ["libcudnn.so.8", "libcudnn.so", "libcudnn.so.8.0.0"]
            
            for lib in cudnn_libs:
                try:
                    if self.system == "Windows":
                        import ctypes
                        ctypes.WinDLL(lib)
                    else:
                        import ctypes
                        ctypes.CDLL(lib)
                    cudnn_info["libraries"].append(lib)
                    logger.info(f"  找到cuDNN库: {lib}")
                except (OSError, ImportError):
                    continue
            
            # 2. 检查头文件
            if self.system == "Windows":
                cudnn_path = os.environ.get('CUDNN_PATH')
                if cudnn_path:
                    include_path = Path(cudnn_path) / "include"
                    if include_path.exists():
                        cudnn_info["header_files"] = list(include_path.glob("cudnn.h"))
                        logger.info(f"  找到cuDNN头文件: {len(cudnn_info['header_files'])}个")
            else:
                include_paths = ["/usr/include", "/usr/local/include"]
                for include_path in include_paths:
                    cudnn_header = Path(include_path) / "cudnn.h"
                    if cudnn_header.exists():
                        cudnn_info["header_files"].append(cudnn_header)
                        logger.info(f"  找到cuDNN头文件: {cudnn_header}")
            
            cudnn_info["installed"] = len(cudnn_info["libraries"]) > 0
            
        except Exception as e:
            logger.error(f"cuDNN检测失败: {e}")
        
        return cudnn_info
    
    def detect_nvidia_driver(self) -> Dict:
        """检测NVIDIA驱动"""
        logger.info("检测NVIDIA驱动...")
        
        driver_info = {
            "installed": False,
            "version": "unknown",
            "gpu_count": 0,
            "gpus": []
        }
        
        try:
            # 使用nvidia-smi检测
            result = subprocess.run(['nvidia-smi', '--query-gpu=driver_version,name,memory.total', 
                                   '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                driver_info["installed"] = True
                lines = result.stdout.strip().split('\n')
                driver_info["gpu_count"] = len(lines)
                
                for line in lines:
                    gpu_data = line.split(', ')
                    if len(gpu_data) >= 3:
                        gpu = {
                            "name": gpu_data[0],
                            "memory_total": int(gpu_data[2]),
                            "driver_version": gpu_data[1]
                        }
                        driver_info["gpus"].append(gpu)
                        logger.info(f"  GPU: {gpu['name']} ({gpu['memory_total']}MB)")
                
                driver_info["version"] = driver_info["gpus"][0]["driver_version"]
                logger.info(f"  驱动版本: {driver_info['version']}")
            
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("nvidia-smi命令不可用")
        
        return driver_info
    
    def detect_tensorflow(self) -> Dict:
        """检测TensorFlow安装"""
        logger.info("检测TensorFlow安装...")
        
        tf_info = {
            "installed": False,
            "version": "unknown",
            "is_gpu_version": False,
            "gpu_available": False,
            "build_info": {},
            "devices": []
        }
        
        try:
            import tensorflow as tf
            tf_info["installed"] = True
            tf_info["version"] = tf.__version__
            tf_info["build_info"] = tf.sysconfig.get_build_info()
            
            # 检查是否是GPU版本
            tf_info["is_gpu_version"] = "gpu" in tf.__version__.lower() or \
                                       tf_info["build_info"].get("is_cuda_build", False)
            
            # 检查GPU可用性
            try:
                gpus = tf.config.list_physical_devices('GPU')
                tf_info["gpu_available"] = len(gpus) > 0
                tf_info["devices"] = [str(gpu) for gpu in gpus]
                
                logger.info(f"  TensorFlow版本: {tf_info['version']}")
                logger.info(f"  GPU版本: {'是' if tf_info['is_gpu_version'] else '否'}")
                logger.info(f"  GPU可用: {'是' if tf_info['gpu_available'] else '否'}")
                
            except Exception as e:
                logger.warning(f"  GPU检测失败: {e}")
                
        except ImportError:
            logger.warning("  TensorFlow未安装")
        
        return tf_info
    
    def check_compatibility(self) -> Dict:
        """检查兼容性"""
        logger.info("检查兼容性...")
        
        compatibility = {
            "overall_status": "unknown",
            "python_compatible": False,
            "cuda_compatible": False,
            "cudnn_compatible": False,
            "tensorflow_compatible": False,
            "issues": [],
            "recommendations": []
        }
        
        try:
            # 检查Python版本兼容性
            if self.python_version >= (3, 8) and self.python_version < (3, 13):
                compatibility["python_compatible"] = True
                logger.info("  Python版本兼容")
            else:
                compatibility["issues"].append("Python版本不兼容，建议使用Python 3.8-3.12")
                compatibility["recommendations"].append("升级到Python 3.8-3.12")
                logger.warning("  ❌ Python版本不兼容")
            
            # 检查CUDA版本兼容性
            if self.cuda_info.get("version") != "unknown":
                cuda_version = self.cuda_info["version"]
                compatible_versions = self.compatibility_matrix["cuda_versions"]
                if cuda_version in compatible_versions:
                    compatibility["cuda_compatible"] = True
                    logger.info("  CUDA版本兼容")
                else:
                    compatibility["issues"].append(f"CUDA版本 {cuda_version} 不在兼容列表中")
                    compatibility["recommendations"].append("升级到CUDA 11.8或12.1")
            else:
                compatibility["issues"].append("CUDA未安装或版本未知")
                compatibility["recommendations"].append("安装CUDA 11.8或12.1")
            
            # 检查TensorFlow-GPU兼容性
            if self.tensorflow_info.get("is_gpu_version"):
                compatibility["tensorflow_compatible"] = True
                logger.info("  TensorFlow GPU版本已安装")
            else:
                compatibility["issues"].append("TensorFlow不是GPU版本")
                compatibility["recommendations"].append("安装tensorflow-gpu或 tensorflow[and-cuda]")
            
            # 总体状态
            if compatibility["python_compatible"] and compatibility["cuda_compatible"] and \
               compatibility["tensorflow_compatible"]:
                compatibility["overall_status"] = "compatible"
                logger.info("  环境完全兼容")
            elif compatibility["python_compatible"]:
                compatibility["overall_status"] = "partial"
                logger.info("  ⚠️ 环境部分兼容")
            else:
                compatibility["overall_status"] = "incompatible"
                logger.info("  ❌ 环境不兼容")
                
        except Exception as e:
            logger.error(f"兼容性检查失败: {e}")
            compatibility["issues"].append(f"兼容性检查失败: {e}")
        
        return compatibility
    
    def generate_install_recommendations(self) -> List[str]:
        """生成安装建议"""
        recommendations = []
        
        # 基于当前环境生成建议
        if not self.cuda_info.get("installed"):
            if self.system == "Windows":
                recommendations.append(
                    "1. 下载CUDA 11.8或12.1安装包\n. 运行"
                    "2安装程序，选择默认安装路径\n"
                    "3. 重启计算机\n"
                    "4. 验证CUDA安装: nvcc --version"
                )
            else:
                recommendations.append(
                    "1. Ubuntu: sudo apt install nvidia-cuda-toolkit\n"
                    "2. 或从NVIDIA官网下载CUDA安装包\n"
                    "3. 验证安装: nvcc --version"
                )
        
        if not self.gpu_info.get("installed"):
            recommendations.append(
                "1. 安装NVIDIA GPU驱动\n"
                "2. 重启计算机\n"
                "3. 验证驱动: nvidia-smi"
            )
        
        if not self.tensorflow_info.get("is_gpu_version"):
            recommendations.append(
                "1. 卸载当前TensorFlow: pip uninstall tensorflow\n"
                "2. 安装TensorFlow GPU版本: pip install tensorflow[and-cuda]\n"
                "3. 或安装指定版本: pip install tensorflow-gpu==2.15.0"
            )
        
        return recommendations
    
    def generate_report(self) -> str:
        """生成详细报告"""
        report = []
        report.append("=" * 80)
        report.append("CUDA环境验证报告")
        report.append("=" * 80)
        report.append("")
        
        # 系统信息
        report.append("系统信息:")
        report.append(f"  操作系统: {platform.system()} {platform.release()}")
        report.append(f"  Python版本: {self.python_version}")
        report.append(f"  架构: {platform.machine()}")
        report.append("")
        
        # CUDA信息
        report.append("CUDA安装状态:")
        report.append(f"  已安装: {self.cuda_info.get('installed', False)}")
        report.append(f"  版本: {self.cuda_info.get('version', 'unknown')}")
        report.append(f"  NVCC可用: {self.cuda_info.get('nvcc_available', False)}")
        report.append(f"  库文件: {len(self.cuda_info.get('libraries', []))}个")
        report.append("")
        
        # cuDNN信息
        report.append("cuDNN安装状态:")
        report.append(f"  已安装: {self.cudnn_info.get('installed', False)}")
        report.append(f"  库文件: {len(self.cudnn_info.get('libraries', []))}个")
        report.append(f"  头文件: {len(self.cudnn_info.get('header_files', []))}个")
        report.append("")
        
        # GPU信息
        report.append("GPU驱动状态:")
        report.append(f"  驱动已安装: {self.gpu_info.get('installed', False)}")
        report.append(f"  驱动版本: {self.gpu_info.get('version', 'unknown')}")
        report.append(f"  GPU数量: {self.gpu_info.get('gpu_count', 0)}")
        if self.gpu_info.get("gpus"):
            for gpu in self.gpu_info["gpus"]:
                report.append(f"  GPU: {gpu['name']} ({gpu['memory_total']}MB)")
        report.append("")
        
        # TensorFlow信息
        report.append("TensorFlow状态:")
        report.append(f"  已安装: {self.tensorflow_info.get('installed', False)}")
        report.append(f"  版本: {self.tensorflow_info.get('version', 'unknown')}")
        report.append(f"  GPU版本: {self.tensorflow_info.get('is_gpu_version', False)}")
        report.append(f"  GPU可用: {self.tensorflow_info.get('gpu_available', False)}")
        report.append("")
        
        # 兼容性状态
        report.append("兼容性检查:")
        compatibility = self.compatibility
        report.append(f"  总体状态: {compatibility.get('overall_status', 'unknown')}")
        report.append(f"  Python兼容: {compatibility.get('python_compatible', False)}")
        report.append(f"  CUDA兼容: {compatibility.get('cuda_compatible', False)}")
        report.append(f"  TensorFlow兼容: {compatibility.get('tensorflow_compatible', False)}")
        report.append("")
        
        # 问题和建议
        if compatibility.get("issues"):
            report.append("发现的问题:")
            for issue in compatibility["issues"]:
                report.append(f"  • {issue}")
            report.append("")
        
        if compatibility.get("recommendations"):
            report.append("建议:")
            for rec in compatibility["recommendations"]:
                report.append(f"  • {rec}")
            report.append("")
        
        # 安装建议
        install_recs = self.generate_install_recommendations()
        if install_recs:
            report.append("安装建议:")
            for i, rec in enumerate(install_recs, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def run_full_validation(self) -> bool:
        """运行完整验证"""
        logger.info("开始CUDA环境完整验证...")
        
        try:
            # 1. 检测各个组件
            self.python_info = self.detect_python_environment()
            self.cuda_info = self.detect_cuda_installation()
            self.cudnn_info = self.detect_cudnn_installation()
            self.gpu_info = self.detect_nvidia_driver()
            self.tensorflow_info = self.detect_tensorflow()
            
            # 2. 检查兼容性
            self.compatibility = self.check_compatibility()
            
            # 3. 生成报告
            report = self.generate_report()
            print(report)
            
            # 4. 保存报告到文件
            report_file = Path("cuda_environment_report.txt")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"报告已保存到: {report_file}")
            
            # 5. 返回验证结果
            success = self.compatibility["overall_status"] in ["compatible", "partial"]
            return success
            
        except Exception as e:
            logger.error(f"验证过程失败: {e}")
            return False
    
    def save_config_template(self):
        """保存配置模板"""
        config = {
            "cuda_version": "11.8",
            "tensorflow_version": "2.15.0",
            "python_version": f"{self.python_version.major}.{self.python_version.minor}",
            "install_commands": {
                "cuda": "conda install -c conda-forge cudatoolkit=11.8 -y",
                "tensorflow": "pip install tensorflow[and-cuda]==2.15.0",
                "validation": "python scripts/cuda_environment_validator.py"
            },
            "environment_variables": {
                "CUDA_PATH": "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v11.8",
                "CUDNN_PATH": "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v11.8"
            }
        }
        
        config_file = Path("cuda_config_template.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"配置模板已保存到: {config_file}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="CUDA环境验证工具")
    parser.add_argument("--auto-install", action="store_true", help="自动安装建议")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--save-config", action="store_true", help="保存配置模板")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 创建验证器并运行
    validator = CUDAEnvironmentValidator()
    success = validator.run_full_validation()
    
    # 保存配置模板
    if args.save_config:
        validator.save_config_template()
    
    # 返回状态码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()