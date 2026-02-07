#!/usr/bin/env python3
"""
FactorWeave-Quant  主程序入口

使用重构后的架构：
- 主窗口协调器 (MainWindowCoordinator)
- 服务容器 (ServiceContainer)
- 事件总线 (EventBus)
- 模块化UI面板
- WebGPU硬件加速渲染

版本: 2.0 (重构版本)
作者: FactorWeave-Quant  Team
"""

import sys
import asyncio
import traceback
from pathlib import Path
import os

from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.exception_handler import setup_exception_handler
from utils.warning_suppressor import suppress_warnings
from core.coordinators import MainWindowCoordinator
from core.events import EventBus, get_event_bus
from core.containers import ServiceContainer, get_service_container
from core.containers.service_registry import ServiceScope
from core.services.service_bootstrap import bootstrap_services
from core.graceful_shutdown import shutdown_manager  # 优雅关闭管理器
logger.info("所有模块导入完成")
logger.info("开始导入Qt相关模块...")
try:
    logger.info("导入 PyQt5.QtWidgets...")
    from PyQt5.QtWidgets import QApplication, QMessageBox
    logger.info("✓ PyQt5.QtWidgets 导入完成")
    
    logger.info("导入 PyQt5.QtCore...")
    from PyQt5.QtCore import Qt
    logger.info("✓ PyQt5.QtCore 导入完成")
    
    logger.info("导入 PyQt5.QtGui...")
    from PyQt5.QtGui import QIcon
    logger.info("✓ PyQt5.QtGui 导入完成")
    
    logger.info("导入 qasync...")
    from qasync import QEventLoop
    logger.info("✓ qasync 导入完成")
    
    logger.info("✓ Qt相关模块导入完成")
    
    # 设置Qt应用程序属性
    logger.info("设置Qt应用程序属性...")
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # 设置OpenGL上下文共享，解决QtWebEngineWidgets问题
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    logger.info("✓ Qt应用程序属性设置完成")

except ImportError as e:
    logger.info(f"PyQt5导入失败: {e}")
    logger.info("请安装PyQt5: pip install PyQt5")
    QEventLoop = None

class FactorWeaveQuantApplication:
    """
    FactorWeave-Quant  应用程序主类

    负责：
    1. 应用程序初始化
    2. 服务容器配置
    3. 主窗口创建
    4. 生命周期管理
    """

    def __init__(self):
        """初始化应用程序"""
        self.app = None
        self.main_window_coordinator = None
        self.service_container = None
        self.event_bus = None
        self.qt_handler = None

    def initialize(self) -> bool:
        """
        初始化应用程序

        Returns:
            初始化是否成功
        """
        try:
            logger.info("=" * 60)
            logger.info("FactorWeave-Quant 2.0 启动中...")
            logger.info("=" * 60)

            # 1. 创建Qt应用程序
            self._create_qt_application()

            # 1.5. 设置Qt日志处理器
            self._setup_qt_logging()
            logger.info("Qt日志设置完成")

            # 2. 抑制警告
            suppress_warnings()

            # 抑制TensorFlow/Keras警告
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'

            # 3. 设置异常处理器
            setup_exception_handler(self.app)

            # 4. 初始化核心组件
            self._initialize_core_components()
            logger.info("核心组件初始化完成")

            # 5. 注册服务
            if not self._register_services():
                logger.error("服务注册失败")
                return False
            logger.info("服务注册完成")

            # 6. 创建主窗口协调器
            self._create_main_window()
            logger.info("主窗口创建完成")

            logger.info("FactorWeave-Quant  2.0 初始化完成")
            return True

        except Exception as e:
            logger.error(f" 应用程序初始化失败: {e}")
            logger.error(traceback.format_exc())
            self._show_error_message("初始化失败", str(e))
            return False

    def _create_qt_application(self) -> None:
        """创建Qt应用程序"""
        logger.info("1. 创建Qt应用程序...")

        # 检查是否已经存在QApplication实例
        if QApplication.instance() is not None:
            self.app = QApplication.instance()
            logger.info("使用已存在的QApplication实例")
            return

        # 设置QtWebEngine缓存目录，避免创建缓存失败
        cache_dir = os.path.join(os.path.expanduser("~"), ".factorweave", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"--user-data-dir={cache_dir}"

        # 创建应用程序实例
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("FactorWeave-Quant")
        self.app.setApplicationVersion("2.0")
        self.app.setOrganizationName("FactorWeave 团队")

        # 设置应用程序图标
        icon_path = project_root / "icons" / "logo.png"
        if icon_path.exists():
            self.app.setWindowIcon(QIcon(str(icon_path)))

        # 初始化显示优化管理器（响应式UI支持）
        try:
            from gui.utils.display_optimization import setup_high_dpi_support
            setup_high_dpi_support()
            logger.info("✓ 显示优化管理器已初始化")
        except Exception as e:
            logger.warning(f"显示优化管理器初始化失败: {e}")

        # 初始化全局字体管理器（字体缩放功能）
        try:
            from gui.utils.global_font_manager import get_global_font_manager
            self.font_manager = get_global_font_manager()
            logger.info(f"✓ 全局字体管理器已初始化，当前字体大小: {self.font_manager.get_font_size()}")
        except Exception as e:
            logger.warning(f"全局字体管理器初始化失败: {e}")
            self.font_manager = None

        logger.info("Qt应用程序创建完成")


    def _setup_qt_logging(self) -> None:
        """设置Qt日志处理器"""
        try:
            # 导入Qt日志处理器
            from gui.loguru_qt_handler import get_qt_handler

            # 获取Qt日志处理器实例
            self.qt_handler = get_qt_handler()

            # 延迟设置处理定时器，等待事件循环准备好
            # 在事件循环启动后再设置定时器
            def setup_timer_later():
                if self.qt_handler:
                    self.qt_handler.setup_processing_timer()
                    logger.info("Qt日志处理定时器已启动")

            # 使用QTimer.singleShot在事件循环启动后设置定时器
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, setup_timer_later)

            logger.info("Qt日志处理器初始化完成")
        except Exception as e:
            logger.warning(f"Qt日志处理器初始化失败: {e}")
            self.qt_handler = None

    def _initialize_core_components(self) -> None:
        """初始化核心组件"""
        logger.info("2. 初始化核心组件...")

        # 获取全局服务容器和事件总线
        self.service_container = get_service_container()
        self.event_bus = get_event_bus()

        logger.info(f" 服务容器: {type(self.service_container).__name__}")
        logger.info(f" 事件总线: {type(self.event_bus).__name__}")

    def _register_services(self) -> bool:
        """
        注册服务

        Returns:
            注册是否成功
        """
        logger.info("3. 注册服务...")

        # 使用服务引导器注册所有服务
        try:
            if not bootstrap_services():
                logger.error("服务注册失败")
                return False
        except Exception as e:
            logger.error(f"服务注册过程中发生错误: {e}")
            logger.error(traceback.format_exc())
            return False

        logger.info("所有服务注册完成")

        # 4. 初始化JIT系统
        logger.info("4. 初始化JIT系统...")
        try:
            from backtest.jit_system_initializer import initialize_jit_system
            if initialize_jit_system():
                logger.info("JIT系统初始化成功")
            else:
                logger.warning("JIT系统初始化失败")
        except Exception as e:
            logger.warning(f"JIT系统初始化失败: {e}")

        return True

    def _create_main_window(self) -> None:
        """创建主窗口协调器"""
        logger.info("5. 创建主窗口...")

        try:
            # 创建主窗口协调器
            logger.info("正在创建主窗口协调器实例...")
            self.main_window_coordinator = MainWindowCoordinator(
                service_container=self.service_container,
                event_bus=self.event_bus
            )
            logger.info("主窗口协调器实例创建完成")

            # 初始化协调器
            logger.info("正在初始化主窗口协调器...")
            self.main_window_coordinator.initialize()
            logger.info("主窗口协调器初始化完成")

            logger.info("主窗口协调器创建完成")
        except Exception as e:
            logger.error(f" 主窗口协调器创建失败: {e}")
            logger.error(traceback.format_exc())
            raise

    def run(self) -> int:
        """
        运行应用程序

        Returns:
            应用程序退出代码
        """
        try:
            logger.info("开始运行应用程序...")
            
            if not self.initialize():
                logger.error("应用程序初始化失败")
                return 1

            logger.info("6. 启动主窗口...")

            # 启动主窗口
            self.main_window_coordinator.run()

            logger.info("主窗口已启动")
            logger.info("7. 事件循环将由外部管理...")
            return 0  # 成功

        except Exception as e:
            logger.error(f"运行时错误: {e}")
            logger.error(traceback.format_exc())
            self._show_error_message("运行时错误", str(e))
            return 1

    def _cleanup(self) -> None:
        """清理资源"""
        try:
            logger.info("正在清理资源...")

            if self.main_window_coordinator:
                self.main_window_coordinator.dispose()

            if self.service_container:
                # 清理所有服务
                self.service_container.dispose()
                logger.info("服务容器已清理")

            # 关闭Qt日志处理器
            if self.qt_handler:
                self.qt_handler.shutdown()
                logger.info("Qt日志处理器已关闭")

            # 停止事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()

            logger.info("资源清理完成")

        except Exception as e:
            logger.error(f"清理资源时出错: {e}")

    def _show_error_message(self, title: str, message: str) -> None:
        """显示错误消息"""
        if self.app:
            QMessageBox.critical(None, title, message)
        else:
            logger.info(f"错误: {title} - {message}")


def main():
    """主程序入口"""
    try:
        logger.info("主程序入口开始执行...")
        
        # 确保日志目录存在
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        logger.info("日志目录已创建")

        # 注册DuckDB清理到优雅关闭管理器
        try:
            from core.database.duckdb_manager import cleanup_duckdb_manager
            shutdown_manager.register_cleanup_handler(
                cleanup_duckdb_manager,
                name="DuckDB连接管理器"
            )
            logger.info("已注册DuckDB优雅关闭处理器")
        except Exception as e:
            logger.warning(f"注册DuckDB清理失败: {e}")

        # 创建并运行应用程序
        if QEventLoop is not None:
            logger.info("开始创建QApplication实例...")
            
            # 创建QApplication实例
            app = QApplication(sys.argv)
            logger.info("QApplication实例创建完成")
            
            # WebGPU硬件加速渲染初始化（在QApplication创建后进行）
            try:
                from optimization.webgpu_chart_renderer import get_webgpu_chart_renderer
                # 初始化WebGPU图表渲染器（包含自动降级功能）
                webgpu_renderer = get_webgpu_chart_renderer(
                    enable_webgpu=True,
                    enable_progressive=True,
                    max_workers=os.cpu_count()
                )
                logger.info("WebGPU硬件加速渲染系统初始化成功")
            except ImportError:
                logger.warning("WebGPU模块导入失败，将使用标准渲染")
                logger.warning("如需WebGPU硬件加速，请确保已安装相关依赖")
                webgpu_renderer = None
            except Exception as e:
                logger.error(f"WebGPU初始化失败: {e}")
                webgpu_renderer = None

            # 创建事件循环
            logger.info("创建事件循环...")
            event_loop = QEventLoop(app)
            asyncio.set_event_loop(event_loop)
            logger.info("事件循环创建完成")
            
            logger.info("创建FactorWeaveQuantApplication实例...")
            factorweave_app = FactorWeaveQuantApplication()
            factorweave_app.app = app  # Pass app instance
            logger.info("FactorWeaveQuantApplication实例创建完成")

            # 优雅地退出
            app.aboutToQuit.connect(event_loop.stop)

            logger.info("开始运行应用程序...")
            if factorweave_app.run() != 0:
                logger.error("Application setup failed. Exiting.")
                sys.exit(1)

            logger.info("应用程序运行完成，开始事件循环...")
            event_loop.run_forever()  # 运行事件循环

            logger.info("事件循环结束，开始清理...")
            factorweave_app._cleanup()
            logger.info("Application shutdown complete.")
            sys.exit(0) # Let the application exit naturally

        else:
            # Fallback for systems without qasync
            logger.error(
                "qasync is not installed. Please install it with 'pip install qasync'")
            app = FactorWeaveQuantApplication()
            # This part will likely not work correctly without an event loop manager.
            exit_code = app.run()
            sys.exit(exit_code)

    except Exception as e:
        logger.info(f"程序启动失败: {e}")
        logger.info(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
