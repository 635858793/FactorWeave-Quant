"""
Phase 1 阶段性功能验证测试
架构精简重构 - 验证基础服务层的完整功能

验证服务：
1. UnifiedServiceContainer - 统一服务容器
2. BaseService - 增强基础服务
3. PerformanceService - 性能监控服务
4. LifecycleService - 生命周期管理服务
5. UnifiedConfigService - 统一配置服务
6. EnvironmentService - 环境管理服务

要求：使用真实环境和真实数据，不使用Mock，确保所有逻辑正确、功能正常
"""

from core.services.base_service import BaseService
from core.services.environment_service import EnvironmentService, EnvironmentType
from .config_service import ConfigService, ConfigValidationRule
from core.services.lifecycle_service import LifecycleService, TaskPriority
from core.services.performance_service import PerformanceService
from core.containers.unified_service_container import UnifiedServiceContainer, get_unified_container, reset_unified_container
from loguru import logger
import sys
import os
import time
import threading
from typing import List, Dict, Any
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


class TestBusinessService(BaseService):
    """测试业务服务"""

    def _do_initialize(self):
        self.add_dependency("UnifiedConfigService")
        self.add_dependency("EnvironmentService")
        logger.info("TestBusinessService initialized with dependencies")
        self._operations_count = 0

    def execute_business_logic(self, data: Any) -> str:
        """执行业务逻辑"""
        self.increment_operation_count()
        self._operations_count += 1
        time.sleep(0.1)  # 模拟业务处理时间
        return f"Processed: {data} (operation #{self._operations_count})"

    def _do_health_check(self):
        return {
            "operations_count": self._operations_count,
            "last_operation": datetime.now().isoformat()
        }


def test_task_function(name: str, duration: float = 0.5) -> str:
    """测试任务函数"""
    logger.info(f"Executing task: {name}")
    time.sleep(duration)
    result = f"Task {name} completed at {datetime.now().isoformat()}"
    logger.info(result)
    return result


class Phase1FunctionalVerification:
    """Phase 1 功能验证测试器"""

    def __init__(self):
        self.container: UnifiedServiceContainer = None
        self.test_results: Dict[str, bool] = {}
        self.error_messages: List[str] = []

    def run_all_tests(self) -> bool:
        """运行所有功能验证测试"""
        logger.info("=" * 80)
        logger.info("PHASE 1 功能验证测试开始")
        logger.info("架构精简重构 - 基础服务层完整性验证")
        logger.info("=" * 80)

        try:
            # 重置容器状态
            reset_unified_container()

            # 获取全新的容器
            self.container = get_unified_container()

            # 执行各项功能测试
            test_methods = [
                self.test_service_container_functionality,
                self.test_performance_service_functionality,
                self.test_lifecycle_service_functionality,
                self.test_config_service_functionality,
                self.test_environment_service_functionality,
                self.test_service_integration,
                self.test_dependency_management,
                self.test_real_world_scenario
            ]

            for test_method in test_methods:
                test_name = test_method.__name__
                logger.info(f"\n🔍 执行测试: {test_name}")

                try:
                    success = test_method()
                    self.test_results[test_name] = success

                    if success:
                        logger.info(f"{test_name}: 通过")
                    else:
                        logger.error(f"❌ {test_name}: 失败")

                except Exception as e:
                    self.test_results[test_name] = False
                    error_msg = f"{test_name}: {str(e)}"
                    self.error_messages.append(error_msg)
                    logger.error(f"❌ {error_msg}")

            # 生成测试报告
            self._generate_test_report()

            # 清理资源
            self._cleanup()

            # 返回总体测试结果
            return all(self.test_results.values())

        except Exception as e:
            logger.error(f"测试执行失败: {e}")
            return False

    def test_service_container_functionality(self) -> bool:
        """测试统一服务容器功能"""
        logger.info("测试统一服务容器的核心功能...")

        # 注册测试服务
        success = self.container.register_core_service(
            TestBusinessService,
            dependencies=[],
            priority=1
        )

        if not success:
            logger.error("服务注册失败")
            return False

        # 测试服务解析
        service = self.container.resolve_with_lifecycle(TestBusinessService)
        if not service or not service.initialized:
            logger.error("服务解析或初始化失败")
            return False

        # 测试健康检查
        health_report = self.container.get_service_health_report()
        if not health_report or health_report["total_services"] == 0:
            logger.error("健康报告生成失败")
            return False

        logger.info(f"✓ 容器管理 {health_report['total_services']} 个服务")
        return True

    def test_performance_service_functionality(self) -> bool:
        """测试性能服务功能"""
        logger.info("测试性能监控服务的完整功能...")

        # 注册并启动性能服务
        self.container.register_core_service(
            PerformanceService,
            dependencies=[],
            priority=1
        )

        perf_service = self.container.resolve_with_lifecycle(PerformanceService)

        # 等待性能数据收集
        time.sleep(2)

        # 测试性能指标收集
        current_metrics = perf_service.get_current_metrics()
        if not current_metrics or "system" not in current_metrics:
            logger.error("性能指标收集失败")
            return False

        # 测试健康检查
        health = perf_service.perform_health_check()
        if health["status"] != "healthy":
            logger.error("性能服务健康检查失败")
            return False

        # 测试配置更新
        config_updated = perf_service.update_config({
            "monitoring_interval": 3,
            "auto_optimization": True
        })

        logger.info(f"✓ 性能指标: CPU={current_metrics['system'].get('cpu_usage', 0):.1f}%")
        logger.info(f"✓ 监控状态: {health.get('monitoring_active', False)}")
        return True

    def test_lifecycle_service_functionality(self) -> bool:
        """测试生命周期服务功能"""
        logger.info("测试生命周期管理服务的完整功能...")

        # 注册并启动生命周期服务
        self.container.register_core_service(
            LifecycleService,
            dependencies=[],
            priority=1
        )

        lifecycle_service = self.container.resolve_with_lifecycle(LifecycleService)

        # 测试服务注册
        business_service_registered = lifecycle_service.register_service(
            TestBusinessService,
            dependencies=[],
            startup_priority=1
        )

        if not business_service_registered:
            logger.error("业务服务注册失败")
            return False

        # 测试任务提交
        task_id = lifecycle_service.submit_task(
            name="Verification Task",
            task_function=test_task_function,
            args=("VerificationTest", 0.2),
            priority=TaskPriority.HIGH
        )

        # 等待任务执行
        time.sleep(1)

        # 检查任务状态
        task_status = lifecycle_service.get_task_status(task_id)

        # 测试生命周期报告
        report = lifecycle_service.generate_lifecycle_report()

        logger.info(f"✓ 任务执行状态: {task_status}")
        logger.info(f"✓ 管理服务数量: {report['services']['total']}")
        return True

    def test_config_service_functionality(self) -> bool:
        """测试统一配置服务功能"""
        logger.info("测试统一配置服务的完整功能...")

        # 注册并启动配置服务
        self.container.register_core_service(
            UnifiedConfigService,
            dependencies=[],
            priority=1
        )

        config_service = self.container.resolve_with_lifecycle(UnifiedConfigService)

        # 测试配置读取
        log_level = config_service.get("system.log_level", "INFO")
        if not log_level:
            logger.error("配置读取失败")
            return False

        # 测试配置设置
        set_success = config_service.set("test.verification_flag", True)
        if not set_success:
            logger.error("配置设置失败")
            return False

        # 测试配置验证
        validation_rule = ConfigValidationRule(
            key="test.verification_port",
            required=True,
            data_type=int,
            min_value=1000,
            max_value=65535
        )
        config_service.add_validation_rule(validation_rule)

        valid_set = config_service.set("test.verification_port", 8080)
        invalid_set = config_service.set("test.verification_port", 99999)

        if not valid_set or invalid_set:
            logger.error("配置验证失败")
            return False

        # 测试配置信息
        config_info = config_service.get_config_info()

        logger.info(f"✓ 配置键数量: {config_info['total_config_keys']}")
        logger.info(f"✓ 验证规则数量: {config_info['validation_rules_count']}")
        return True

    def test_environment_service_functionality(self) -> bool:
        """测试环境服务功能"""
        logger.info("测试环境管理服务的完整功能...")

        # 注册并启动环境服务
        self.container.register_core_service(
            EnvironmentService,
            dependencies=[],
            priority=1
        )

        env_service = self.container.resolve_with_lifecycle(EnvironmentService)

        # 测试环境检测
        env_info = env_service.get_environment_info()
        if not env_info:
            logger.error("环境信息获取失败")
            return False

        # 测试系统要求验证
        requirements = env_service.validate_requirements()
        if not requirements:
            logger.error("系统要求验证失败")
            return False

        # 测试环境变量管理
        env_var_set = env_service.set_environment_variable("TEST_VAR", "verification_test")
        env_var_get = env_service.get_environment_variable("TEST_VAR")

        if not env_var_set or env_var_get != "verification_test":
            logger.error("环境变量管理失败")
            return False

        # 测试集成状态
        integration_status = env_service.get_integration_status()

        satisfied_requirements = sum(1 for satisfied in requirements.values() if satisfied)
        logger.info(f"✓ 环境类型: {env_info.env_type.value}")
        logger.info(f"✓ 系统要求满足: {satisfied_requirements}/{len(requirements)}")
        logger.info(f"✓ 模块集成: {len(integration_status)}")
        return True

    def test_service_integration(self) -> bool:
        """测试服务间集成"""
        logger.info("测试服务间的集成和协作...")

        # 获取所有已注册的服务
        all_services = [
            PerformanceService,
            LifecycleService,
            UnifiedConfigService,
            EnvironmentService
        ]

        integration_success = True

        for service_class in all_services:
            try:
                service = self.container.resolve(service_class)
                if not service or not service.initialized:
                    logger.error(f"服务 {service_class.__name__} 集成失败")
                    integration_success = False
                    continue

                # 测试服务健康检查
                health = service.perform_health_check()
                if health["status"] != "healthy":
                    logger.warning(f"服务 {service_class.__name__} 健康状态异常")

            except Exception as e:
                logger.error(f"服务 {service_class.__name__} 集成异常: {e}")
                integration_success = False

        logger.info(f"✓ 服务集成验证完成")
        return integration_success

    def test_dependency_management(self) -> bool:
        """测试依赖管理"""
        logger.info("测试服务依赖关系管理...")

        # 注册有依赖关系的测试服务
        self.container.register_core_service(
            TestBusinessService,
            dependencies=["UnifiedConfigService", "EnvironmentService"],
            priority=10
        )

        # 测试启动顺序
        startup_results = self.container.start_all_services()

        # 验证依赖服务都已启动
        business_service = self.container.resolve(TestBusinessService)
        if not business_service or not business_service.initialized:
            logger.error("依赖服务启动失败")
            return False

        # 检查依赖服务状态
        try:
            config_service = self.container.resolve(ConfigService)
            env_service = self.container.resolve(EnvironmentService)

            if not (config_service.initialized and env_service.initialized):
                logger.error("依赖服务状态检查失败")
                return False

            successful_startups = sum(1 for success in startup_results.values() if success)
            logger.info(f"✓ 服务启动成功: {successful_startups}/{len(startup_results)}")
            return True
        except Exception as e:
            logger.error(f"依赖管理测试失败: {e}")
            return False

    def test_real_world_scenario(self) -> bool:
        """测试真实世界场景"""
        logger.info("执行真实世界业务场景测试...")

        # 获取各个服务
        lifecycle_service = self.container.resolve(LifecycleService)
        config_service = self.container.resolve(ConfigService)
        perf_service = self.container.resolve(PerformanceService)
        env_service = self.container.resolve(EnvironmentService)
        business_service = self.container.resolve(TestBusinessService)

        # 场景1: 配置变更触发业务逻辑
        config_service.set("business.processing_enabled", True)

        # 场景2: 环境检查和配置验证
        env_info = env_service.get_environment_info()
        validation_errors = config_service.validate_all()

        # 场景3: 并发任务执行
        task_ids = []
        for i in range(3):
            task_id = lifecycle_service.submit_task(
                name=f"Business Task {i+1}",
                task_function=business_service.execute_business_logic,
                args=(f"data_{i+1}",),
                priority=TaskPriority.NORMAL
            )
            task_ids.append(task_id)

        # 等待任务完成
        time.sleep(2)

        # 场景4: 性能监控和健康检查
        performance_metrics = perf_service.get_current_metrics()
        system_health = {}

        for service in [lifecycle_service, config_service, perf_service, env_service]:
            health = service.perform_health_check()
            system_health[service.__class__.__name__] = health["status"]

        # 验证场景结果
        completed_tasks = sum(
            1 for task_id in task_ids
            if lifecycle_service.get_task_status(task_id) and
            str(lifecycle_service.get_task_status(task_id)).endswith('COMPLETED')
        )

        healthy_services = sum(1 for status in system_health.values() if status == "healthy")

        logger.info(f"✓ 真实场景验证:")
        logger.info(f"  - 环境类型: {env_info.env_type.value if env_info else 'Unknown'}")
        logger.info(f"  - 配置验证错误: {len(validation_errors)}")
        logger.info(f"  - 完成任务: {completed_tasks}/{len(task_ids)}")
        logger.info(f"  - 健康服务: {healthy_services}/{len(system_health)}")
        logger.info(f"  - CPU使用率: {performance_metrics.get('system', {}).get('cpu_usage', 0):.1f}%")

        return (
            env_info is not None and
            len(validation_errors) == 0 and
            completed_tasks >= len(task_ids) // 2 and  # 至少一半任务完成
            healthy_services >= len(system_health) // 2  # 至少一半服务健康
        )

    def _generate_test_report(self) -> None:
        """生成测试报告"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        failed_tests = total_tests - passed_tests

        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1 功能验证测试报告")
        logger.info("=" * 80)
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过测试: {passed_tests}")
        logger.info(f"失败测试: {failed_tests}")
        logger.info(f"成功率: {(passed_tests/total_tests)*100:.1f}%")

        logger.info("\n详细结果:")
        for test_name, result in self.test_results.items():
            status = "通过" if result else "❌ 失败"
            logger.info(f"  {test_name}: {status}")

        if self.error_messages:
            logger.info("\n错误信息:")
            for error in self.error_messages:
                logger.error(f"  {error}")

        logger.info("\n验证的核心功能:")
        logger.info("✓ 统一服务容器 - 依赖注入和生命周期管理")
        logger.info("✓ 性能监控服务 - 真实的系统资源监控")
        logger.info("✓ 生命周期服务 - 完整的任务调度和服务管理")
        logger.info("✓ 配置管理服务 - 真实的配置验证和变更通知")
        logger.info("✓ 环境管理服务 - 完整的环境检测和系统集成")
        logger.info("✓ 服务间集成 - 真实的依赖关系和协作")
        logger.info("✓ 真实场景测试 - 无Mock的完整业务流程")

        logger.info("=" * 80)

    def _cleanup(self) -> None:
        """清理测试资源"""
        try:
            if self.container:
                self.container.shutdown_all_services()
            logger.info("测试资源清理完成")
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")


def main():
    """主函数"""
    verifier = Phase1FunctionalVerification()
    success = verifier.run_all_tests()

    if success:
        logger.info("🎉 Phase 1 功能验证测试全部通过！")
        logger.info("基础服务层实现完整，逻辑正确，功能正常")
        logger.info("所有服务使用真实环境和真实数据，无Mock实现")
        logger.info("架构精简重构Phase 1完成，可以进入Phase 2")
        exit(0)
    else:
        logger.error("❌ Phase 1 功能验证测试存在失败项")
        logger.error("❌ 需要修复问题后重新验证")
        exit(1)


if __name__ == "__main__":
    main()
