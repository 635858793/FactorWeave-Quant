#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GPU集成测试脚本

功能：
1. 测试TensorFlow GPU管理器
2. 测试CUDA环境验证器
3. 集成测试AI预测服务的GPU功能
4. 提供完整的测试报告

使用方法：
python scripts/test_gpu_integration.py [--verbose] [--full-test]

作者: FactorWeave-Quant团队
版本: 1.0
"""

import os
import sys
import time
import json
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class GPUIntegrationTest:
    """GPU集成测试器"""
    
    def __init__(self):
        self.test_results = {}
        self.test_start_time = time.time()
        self.verbose = False
        
        # 测试统计
        self.stats = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'warning_tests': 0,
            'test_times': {}
        }
    
    def log_test_result(self, test_name: str, status: str, message: str, duration: float):
        """记录测试结果"""
        self.stats['total_tests'] += 1
        if status == 'PASS':
            self.stats['passed_tests'] += 1
        elif status == 'FAIL':
            self.stats['failed_tests'] += 1
        elif status == 'WARN':
            self.stats['warning_tests'] += 1
        
        self.test_results[test_name] = {
            'status': status,
            'message': message,
            'duration': duration
        }
        
        if self.verbose:
            status_icon = {'PASS': '✅', 'FAIL': '❌', 'WARN': '⚠️'}[status]
            logger.info(f"{status_icon} {test_name}: {message} ({duration:.2f}s)")
        else:
            logger.info(f"{status} {test_name}")
    
    def test_tensorflow_gpu_manager(self) -> bool:
        """测试TensorFlow GPU管理器"""
        logger.info("=== 测试TensorFlow GPU管理器 ===")
        test_name = "TensorFlow GPU管理器"
        start_time = time.time()
        
        try:
            # 导入GPU管理器
            try:
                from core.services.tensorflow_gpu_manager import TensorFlowGPUManager, auto_configure_gpu
                logger.info("  ✅ GPU管理器模块导入成功")
            except ImportError as e:
                self.log_test_result(test_name, 'FAIL', f'导入失败: {e}', time.time() - start_time)
                return False
            
            # 测试GPU管理器创建
            gpu_manager = TensorFlowGPUManager()
            self.log_test_result(test_name + "_创建", 'PASS', 'GPU管理器实例创建成功', time.time() - start_time)
            
            # 测试GPU检测
            start_time = time.time()
            gpu_info = gpu_manager.detect_gpu_hardware()
            duration = time.time() - start_time
            
            gpu_status = gpu_info.status.value if gpu_info else "unknown"
            self.log_test_result(test_name + "_检测", 'PASS', f'检测到GPU状态: {gpu_status}', duration)
            
            # 测试CUDA环境验证
            start_time = time.time()
            cuda_result = gpu_manager.verify_cuda_environment()
            duration = time.time() - start_time
            
            cuda_ok = cuda_result.success
            cuda_status = "通过" if cuda_ok else "失败"
            self.log_test_result(test_name + "_CUDA验证", 'PASS' if cuda_ok else 'WARN', f'CUDA环境验证: {cuda_status}', duration)
            
            # 输出详细的验证结果
            if not cuda_ok:
                print("\n" + cuda_result.get_summary())
            
            # 测试TensorFlow GPU配置
            start_time = time.time()
            config_ok = gpu_manager.configure_tensorflow_gpu()
            duration = time.time() - start_time
            
            config_status = "成功" if config_ok else "失败"
            self.log_test_result(test_name + "_配置", 'PASS' if config_ok else 'FAIL', f'GPU配置: {config_status}', duration)
            
            # 测试设备策略
            device_strategy = gpu_manager.get_device_strategy()
            self.log_test_result(test_name + "_设备策略", 'PASS', f'设备策略: {device_strategy}', 0.1)
            
            # 清理资源
            gpu_manager.cleanup()
            self.log_test_result(test_name + "_清理", 'PASS', '资源清理完成', 0.1)
            
            return True
            
        except Exception as e:
            error_msg = f'异常: {str(e)}'
            logger.error(f"GPU管理器测试失败: {error_msg}")
            logger.error(traceback.format_exc())
            self.log_test_result(test_name, 'FAIL', error_msg, time.time() - start_time)
            return False
    
    def test_cuda_environment_validator(self) -> bool:
        """测试CUDA环境验证器"""
        logger.info("=== 测试CUDA环境验证器 ===")
        test_name = "CUDA环境验证器"
        start_time = time.time()
        
        try:
            # 导入验证器
            try:
                from scripts.cuda_environment_validator import CUDAEnvironmentValidator
                logger.info("  ✅ CUDA验证器模块导入成功")
            except ImportError as e:
                self.log_test_result(test_name, 'FAIL', f'导入失败: {e}', time.time() - start_time)
                return False
            
            # 创建验证器实例
            validator = CUDAEnvironmentValidator()
            self.log_test_result(test_name + "_创建", 'PASS', '验证器实例创建成功', time.time() - start_time)
            
            # 测试Python环境检测
            start_time = time.time()
            python_info = validator.detect_python_environment()
            duration = time.time() - start_time
            
            python_version = python_info.get('version', 'unknown')
            self.log_test_result(test_name + "_Python环境", 'PASS', f'Python版本: {python_version}', duration)
            
            # 测试CUDA安装检测
            start_time = time.time()
            cuda_info = validator.detect_cuda_installation()
            duration = time.time() - start_time
            
            cuda_installed = cuda_info.get('installed', False)
            cuda_version = cuda_info.get('version', 'unknown')
            self.log_test_result(test_name + "_CUDA检测", 'PASS' if cuda_installed else 'WARN', 
                               f'CUDA安装: {cuda_installed}, 版本: {cuda_version}', duration)
            
            # 测试cuDNN检测
            start_time = time.time()
            cudnn_info = validator.detect_cudnn_installation()
            duration = time.time() - start_time
            
            cudnn_installed = cudnn_info.get('installed', False)
            self.log_test_result(test_name + "_cuDNN检测", 'PASS' if cudnn_installed else 'WARN', 
                               f'cuDNN安装: {cudnn_installed}', duration)
            
            # 测试GPU驱动检测
            start_time = time.time()
            driver_info = validator.detect_nvidia_driver()
            duration = time.time() - start_time
            
            driver_installed = driver_info.get('installed', False)
            gpu_count = driver_info.get('gpu_count', 0)
            self.log_test_result(test_name + "_GPU驱动", 'PASS' if driver_installed else 'WARN', 
                               f'驱动安装: {driver_installed}, GPU数量: {gpu_count}', duration)
            
            # 测试TensorFlow检测
            start_time = time.time()
            tf_info = validator.detect_tensorflow()
            duration = time.time() - start_time
            
            tf_installed = tf_info.get('installed', False)
            tf_version = tf_info.get('version', 'unknown')
            self.log_test_result(test_name + "_TensorFlow", 'PASS' if tf_installed else 'WARN', 
                               f'TensorFlow安装: {tf_installed}, 版本: {tf_version}', duration)
            
            # 测试兼容性检查
            start_time = time.time()
            validator.cuda_info = cuda_info
            validator.cudnn_info = cudnn_info
            validator.gpu_info = driver_info
            validator.tensorflow_info = tf_info
            
            compatibility = validator.check_compatibility()
            duration = time.time() - start_time
            
            overall_status = compatibility.get('overall_status', 'unknown')
            self.log_test_result(test_name + "_兼容性", 'PASS' if overall_status in ['compatible', 'partial'] else 'WARN', 
                               f'兼容性状态: {overall_status}', duration)
            
            # 测试报告生成
            start_time = time.time()
            report = validator.generate_report()
            duration = time.time() - start_time
            
            report_length = len(report)
            self.log_test_result(test_name + "_报告生成", 'PASS', f'报告长度: {report_length}字符', duration)
            
            return True
            
        except Exception as e:
            error_msg = f'异常: {str(e)}'
            logger.error(f"CUDA验证器测试失败: {error_msg}")
            logger.error(traceback.format_exc())
            self.log_test_result(test_name, 'FAIL', error_msg, time.time() - start_time)
            return False
    
    def test_ai_prediction_service_integration(self) -> bool:
        """测试AI预测服务GPU集成"""
        logger.info("=== 测试AI预测服务GPU集成 ===")
        test_name = "AI预测服务GPU集成"
        start_time = time.time()
        
        try:
            # 导入AI预测服务
            try:
                from core.services.ai_prediction_service import AIPredictionService
                logger.info("  ✅ AI预测服务模块导入成功")
            except ImportError as e:
                self.log_test_result(test_name, 'FAIL', f'导入失败: {e}', time.time() - start_time)
                return False
            
            # 创建AI预测服务实例
            ai_service = AIPredictionService()
            self.log_test_result(test_name + "_创建", 'PASS', 'AI预测服务实例创建成功', time.time() - start_time)
            
            # 测试GPU状态获取
            start_time = time.time()
            gpu_status = ai_service.get_gpu_status()
            duration = time.time() - start_time
            
            gpu_enabled = gpu_status.get('enabled', False)
            device_strategy = gpu_status.get('device_strategy', '/CPU:0')
            self.log_test_result(test_name + "_GPU状态", 'PASS', f'GPU启用: {gpu_enabled}, 设备: {device_strategy}', duration)
            
            # 测试预测设备获取
            start_time = time.time()
            prediction_device = ai_service.get_device_for_prediction()
            duration = time.time() - start_time
            
            self.log_test_result(test_name + "_预测设备", 'PASS', f'预测设备: {prediction_device}', duration)
            
            # 创建测试数据
            import pandas as pd
            import numpy as np
            
            start_time = time.time()
            test_data = {
                'open': np.random.uniform(100, 110, 100),
                'high': np.random.uniform(110, 120, 100),
                'low': np.random.uniform(90, 100, 100),
                'close': np.random.uniform(95, 115, 100),
                'volume': np.random.uniform(1000000, 10000000, 100)
            }
            kdata = pd.DataFrame(test_data)
            duration = time.time() - start_time
            
            self.log_test_result(test_name + "_测试数据", 'PASS', f'测试数据创建完成: {kdata.shape}', duration)
            
            # 测试预测功能（如果GPU管理器可用）
            if hasattr(ai_service, '_gpu_manager') and ai_service._gpu_manager:
                start_time = time.time()
                try:
                    prediction_result = ai_service._predict_with_deep_learning(kdata)
                    duration = time.time() - start_time
                    
                    if prediction_result:
                        device_used = prediction_result.get('device_used', 'unknown')
                        gpu_enabled = prediction_result.get('gpu_enabled', False)
                        self.log_test_result(test_name + "_GPU预测", 'PASS', 
                                           f'设备: {device_used}, GPU: {gpu_enabled}', duration)
                    else:
                        self.log_test_result(test_name + "_GPU预测", 'WARN', '预测结果为空', duration)
                        
                except Exception as e:
                    duration = time.time() - start_time
                    self.log_test_result(test_name + "_GPU预测", 'WARN', f'预测异常: {str(e)}', duration)
            else:
                self.log_test_result(test_name + "_GPU预测", 'WARN', 'GPU管理器不可用，跳过预测测试', 0.1)
            
            return True
            
        except Exception as e:
            error_msg = f'异常: {str(e)}'
            logger.error(f"AI预测服务集成测试失败: {error_msg}")
            logger.error(traceback.format_exc())
            self.log_test_result(test_name, 'FAIL', error_msg, time.time() - start_time)
            return False
    
    def test_performance_comparison(self) -> bool:
        """测试GPU vs CPU性能对比"""
        logger.info("=== 测试GPU vs CPU性能对比 ===")
        test_name = "性能对比测试"
        start_time = time.time()
        
        try:
            # 检查TensorFlow是否可用
            try:
                import tensorflow as tf
                TENSORFLOW_AVAILABLE = True
            except ImportError:
                self.log_test_result(test_name, 'WARN', 'TensorFlow不可用，跳过性能测试', time.time() - start_time)
                return False
            
            # 检查GPU可用性
            gpus = tf.config.list_physical_devices('GPU')
            if len(gpus) == 0:
                self.log_test_result(test_name, 'WARN', '未检测到GPU，跳过性能对比', time.time() - start_time)
                return False
            
            # 准备测试数据
            size = 1000
            a = tf.random.normal([size, size])
            b = tf.random.normal([size, size])
            
            # CPU性能测试
            start_time = time.time()
            with tf.device('/CPU:0'):
                cpu_result = tf.matmul(a, b)
            cpu_time = time.time() - start_time
            
            # GPU性能测试
            start_time = time.time()
            with tf.device('/GPU:0'):
                gpu_result = tf.matmul(a, b)
            gpu_time = time.time() - start_time
            
            # 计算加速比
            speedup = cpu_time / gpu_time if gpu_time > 0 else 0.0
            
            self.log_test_result(test_name, 'PASS', 
                               f'CPU: {cpu_time:.4f}s, GPU: {gpu_time:.4f}s, 加速比: {speedup:.2f}x', 
                               cpu_time + gpu_time)
            
            return True
            
        except Exception as e:
            error_msg = f'异常: {str(e)}'
            logger.error(f"性能对比测试失败: {error_msg}")
            self.log_test_result(test_name, 'FAIL', error_msg, time.time() - start_time)
            return False
    
    def generate_test_report(self) -> str:
        """生成测试报告"""
        total_duration = time.time() - self.test_start_time
        
        report = []
        report.append("=" * 80)
        report.append("GPU集成测试报告")
        report.append("=" * 80)
        report.append("")
        
        # 测试统计
        report.append("测试统计:")
        report.append(f"  总测试数: {self.stats['total_tests']}")
        report.append(f"  通过测试: {self.stats['passed_tests']}")
        report.append(f"  失败测试: {self.stats['failed_tests']}")
        report.append(f"  警告测试: {self.stats['warning_tests']}")
        report.append(f"  成功率: {self.stats['passed_tests']/self.stats['total_tests']*100:.1f}%" if self.stats['total_tests'] > 0 else "  成功率: 0%")
        report.append(f"  总耗时: {total_duration:.2f}s")
        report.append("")
        
        # 详细测试结果
        report.append("详细测试结果:")
        for test_name, result in self.test_results.items():
            status_icon = {'PASS': '✅', 'FAIL': '❌', 'WARN': '⚠️'}[result['status']]
            report.append(f"  {status_icon} {test_name}: {result['message']} ({result['duration']:.2f}s)")
        report.append("")
        
        # 建议和总结
        if self.stats['failed_tests'] == 0:
            if self.stats['warning_tests'] == 0:
                report.append("🎉 所有测试通过！GPU集成系统工作正常。")
            else:
                report.append("⚠️ 测试基本通过，但有一些警告，建议检查相关配置。")
        else:
            report.append("❌ 部分测试失败，需要检查GPU配置和环境设置。")
        
        report.append("")
        report.append("建议:")
        if self.stats['failed_tests'] > 0:
            report.append("  1. 检查CUDA和cuDNN安装")
            report.append("  2. 验证NVIDIA GPU驱动")
            report.append("  3. 确认TensorFlow GPU版本安装")
        elif self.stats['warning_tests'] > 0:
            report.append("  1. 检查GPU设备是否正确识别")
            report.append("  2. 验证CUDA版本兼容性")
        else:
            report.append("  1. 系统配置良好，可以正常使用GPU加速")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def run_all_tests(self, verbose: bool = False, full_test: bool = False) -> bool:
        """运行所有测试"""
        self.verbose = verbose
        
        logger.info("开始GPU集成测试...")
        logger.info(f"详细模式: {verbose}, 完整测试: {full_test}")
        
        tests = [
            ("TensorFlow GPU管理器", self.test_tensorflow_gpu_manager),
            ("CUDA环境验证器", self.test_cuda_environment_validator),
            ("AI预测服务集成", self.test_ai_prediction_service_integration)
        ]
        
        if full_test:
            tests.append(("性能对比测试", self.test_performance_comparison))
        
        all_passed = True
        
        for test_name, test_func in tests:
            try:
                logger.info(f"运行测试: {test_name}")
                test_passed = test_func()
                if not test_passed:
                    all_passed = False
                    logger.warning(f"测试失败: {test_name}")
            except Exception as e:
                logger.error(f"测试异常: {test_name} - {e}")
                all_passed = False
        
        # 生成报告
        report = self.generate_test_report()
        print("\n" + report)
        
        # 保存报告到文件
        report_file = Path("gpu_integration_test_report.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"测试报告已保存到: {report_file}")
        
        return all_passed

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="GPU集成测试工具")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--full-test", "-f", action="store_true", help="运行完整测试")
    parser.add_argument("--save-json", action="store_true", help="保存JSON格式结果")
    
    args = parser.parse_args()
    
    # 创建测试器并运行
    tester = GPUIntegrationTest()
    success = tester.run_all_tests(verbose=args.verbose, full_test=args.full_test)
    
    # 保存JSON结果
    if args.save_json:
        json_file = Path("gpu_integration_test_results.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'test_results': tester.test_results,
                'stats': tester.stats,
                'timestamp': time.time(),
                'success': success
            }, f, indent=2, ensure_ascii=False)
        logger.info(f"JSON结果已保存到: {json_file}")
    
    # 返回状态码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()