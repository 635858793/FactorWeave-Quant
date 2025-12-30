from loguru import logger
"""
FactorWeave-Quant  增强插件管理器

提供插件的加载、管理、生命周期控制和生态系统集成功能。
"""

from .plugin_types import PluginType, PluginCategory
import os
import sys
import json
import importlib
import importlib.util
import threading
from typing import Dict, List, Any, Optional, Type, Callable
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict, field
from PyQt5.QtCore import QObject, pyqtSignal
import traceback
from datetime import datetime

# 添加项目根目录到Python路径，确保可以导入plugins包
current_dir = Path(__file__).parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入统一的插件类型定义

# 尝试从plugins包导入接口定义
IPlugin = None
PluginMetadata = None
PluginMarket = None

# 只导入必要的插件接口，将插件市场的导入延迟到需要时再进行
try:
    # 首先尝试直接导入插件接口（不导入市场模块）
    from plugins.plugin_interface import IPlugin, PluginType, PluginCategory, PluginMetadata
    logger.info("成功直接导入插件接口")
except ImportError:
    # 如果直接导入失败，尝试使用相对路径
    try:
        sys.path.append(str(project_root))
        from plugins.plugin_interface import IPlugin, PluginType, PluginCategory, PluginMetadata
        logger.info("成功导入插件接口")
    except ImportError:
        # 尝试使用绝对路径
        try:
            plugins_path = project_root / "plugins"
            sys.path.append(str(plugins_path))

            # 尝试直接从文件导入插件接口
            spec_interface = importlib.util.spec_from_file_location(
                "plugin_interface",
                project_root / "plugins" / "plugin_interface.py"
            )
            if spec_interface and spec_interface.loader:
                plugin_interface_module = importlib.util.module_from_spec(
                    spec_interface)
                sys.modules["plugin_interface"] = plugin_interface_module
                spec_interface.loader.exec_module(plugin_interface_module)
                IPlugin = plugin_interface_module.IPlugin
                PluginType = plugin_interface_module.PluginType
                PluginCategory = plugin_interface_module.PluginCategory
                PluginMetadata = plugin_interface_module.PluginMetadata
                logger.info("成功通过spec导入插件接口")

        except Exception as e:
            logger.error(f"通过spec导入插件接口失败: {e}")

            # 如果仍然失败，尝试最后的方法
            try:
                # 直接导入
                import plugin_interface
                IPlugin = plugin_interface.IPlugin
                PluginType = plugin_interface.PluginType
                PluginCategory = plugin_interface.PluginCategory
                PluginMetadata = plugin_interface.PluginMetadata
                logger.info("成功通过直接导入加载插件接口")
            except ImportError as e:
                logger.error(f"导入插件接口失败: {e}")

                # 如果仍然失败，创建占位类
                class IPlugin:
                    """插件接口占位类"""
                    pass


def get_plugin_market() -> Optional[Any]:
    """
    延迟导入并返回插件市场实例
    
    Returns:
        PluginMarket实例或None
    """
    global PluginMarket
    if PluginMarket is None:
        try:
            # 尝试多种导入方式
            try:
                from plugins.plugin_market import PluginMarket
                logger.info("成功导入插件市场模块")
            except ImportError:
                # 尝试使用相对路径
                sys.path.append(str(project_root))
                from plugins.plugin_market import PluginMarket
                logger.info("成功通过项目路径导入插件市场模块")
        except Exception as e:
            logger.error(f"导入插件市场失败: {e}")
            return None
    return PluginMarket

# 如果仍然失败，创建占位类
class PluginMetadata:
    """插件元数据占位类"""
    pass

class PluginMarket:
    """插件市场占位类"""
    pass


class PluginStatus(Enum):
    """插件状态"""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str
    description: str
    author: str
    path: str
    status: PluginStatus
    config: Dict[str, Any]
    dependencies: List[str]
    plugin_type: Optional[PluginType] = None
    category: Optional[PluginCategory] = None
    capabilities: Dict[str, Any] = field(default_factory=dict)  # 添加capabilities参数

    @property
    def enabled(self) -> bool:
        """检查插件是否启用"""
        return self.status == PluginStatus.ENABLED

    @enabled.setter
    def enabled(self, value: bool):
        """设置插件启用状态"""
        if value:
            self.status = PluginStatus.ENABLED
        else:
            self.status = PluginStatus.DISABLED

    @property
    def type(self) -> Optional[PluginType]:
        """获取插件类型（兼容性属性）"""
        return self.plugin_type

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['status'] = self.status.value
        if self.plugin_type:
            result['plugin_type'] = self.plugin_type.value
        if self.category:
            result['category'] = self.category.value
        return result


class PluginManager(QObject):
    """增强插件管理器"""

    # 信号定义
    plugin_loaded = pyqtSignal(str)  # 插件加载
    plugin_enabled = pyqtSignal(str)  # 插件启用
    plugin_disabled = pyqtSignal(str)  # 插件禁用
    plugin_error = pyqtSignal(str, str)  # 插件错误

    def __init__(self,
                 plugin_dir: str = "plugins",
                 main_window=None,
                 data_manager=None,
                 config_manager=None):
        """
        初始化增强插件管理器

        Args:
            plugin_dir: 插件目录路径
            main_window: 主窗口
            data_manager: 数据管理器
            config_manager: 配置管理器
            # log_manager: 已迁移到Loguru日志系统
        """
        super().__init__()

        self.plugin_dir = Path(plugin_dir)
        self.loaded_plugins = {}
        self.plugin_instances = {}
        self.plugin_metadata = {}
        self.plugin_hooks: Dict[str, List[Callable]] = {}
        self.enhanced_plugins: Dict[str, PluginInfo] = {}

        # 插件生态系统组件
        self.main_window = main_window
        self.data_manager = data_manager
        self.config_manager = config_manager
        # 纯Loguru架构，移除log_manager依赖

        # 按类型分类插件
        self.plugins_by_type: Dict[PluginType, List[str]] = {
            plugin_type: [] for plugin_type in PluginType
        }

        # 新增：数据源插件管理（Task 1.3 扩展）
        self.data_source_plugins: Dict[str, PluginInfo] = {}
        self._data_source_lock = threading.RLock()

        # 数据库服务集成
        self.db_service = None
        self._init_database_service()

    def _init_database_service(self):
        """初始化数据库服务"""
        try:
            from core.services.plugin_database_service import PluginDatabaseService
            self.db_service = PluginDatabaseService()
            logger.info("插件数据库服务初始化成功")

            # 加载数据库中已启用的插件
            self._load_enabled_plugins_from_db()

        except Exception as e:
            logger.warning(f" 插件数据库服务初始化失败: {e}")

    def _load_enabled_plugins_from_db(self):
        """从数据库加载已启用的插件"""
        if not self.db_service:
            return

        try:
            # 获取所有插件信息
            all_plugins = self.db_service.get_all_plugins()
            enabled_count = 0

            for plugin_data in all_plugins:
                plugin_name = plugin_data.get('name', '')
                plugin_status = plugin_data.get('status', '')

                if plugin_status == 'enabled':
                    # 解析依赖列表
                    dependencies_str = plugin_data.get('dependencies', '[]')
                    try:
                        import json
                        dependencies = json.loads(dependencies_str) if dependencies_str else []
                    except:
                        dependencies = []

                    # 创建插件信息对象 - 使用正确的字段名称
                    plugin_info = PluginInfo(
                        name=plugin_name,
                        version=plugin_data.get('version', '1.0.0'),
                        description=plugin_data.get('description', ''),
                        author=plugin_data.get('author', ''),
                        path=plugin_data.get('install_path', ''),
                        status=PluginStatus.ENABLED,
                        config={},  # 空配置字典
                        dependencies=dependencies,
                        plugin_type=PluginType.ANALYSIS,  # 默认类型
                        category=PluginCategory.COMMUNITY  # 默认分类
                    )

                    # 添加到enhanced_plugins
                    self.enhanced_plugins[plugin_name] = plugin_info

                    # 尝试加载插件实例（如果路径存在）
                    try:
                        self._load_plugin_instance(plugin_name, plugin_info)
                        enabled_count += 1
                    except Exception as e:
                        logger.warning(f" 加载插件实例失败 {plugin_name}: {e}")

            if enabled_count > 0:
                logger.info(f" 从数据库加载了 {enabled_count} 个已启用的插件")
            else:
                logger.info("数据库中没有已启用的插件")

        except Exception as e:
            logger.error(f" 从数据库加载插件失败: {e}")

    def _load_plugin_instance(self, plugin_name: str, plugin_info: PluginInfo):
        """加载插件实例"""
        try:
            # 对于数据源插件，尝试加载真实的插件实例
            if self._should_load_real_plugin_instance(plugin_name):
                real_instance = self._load_real_plugin_instance(plugin_name)
                if real_instance:
                    self.plugin_instances[plugin_name] = real_instance
                    logger.info(f" 加载真实插件实例成功: {plugin_name}")
                    return True
                else:
                    logger.warning(f" 加载真实插件实例失败，使用虚拟实例: {plugin_name}")

            # 对于情绪数据源插件，创建虚拟实例
            if 'sentiment_data_sources' in plugin_name:
                # 创建一个简单的插件实例对象
                class VirtualSentimentPlugin:
                    def __init__(self, name, info):
                        self.name = name
                        self.info = info
                        self.enabled = True

                    def get_name(self):
                        return self.name

                    def get_info(self):
                        return self.info

                virtual_instance = VirtualSentimentPlugin(plugin_name, plugin_info)
                self.plugin_instances[plugin_name] = virtual_instance
                logger.debug(f" 创建虚拟插件实例: {plugin_name}")
                return True
            
            # 对于指标插件，创建虚拟实例（如果加载真实实例失败）
            if 'indicators' in plugin_name:
                # 创建一个简单的指标插件实例对象
                class VirtualIndicatorPlugin:
                    def __init__(self, name, info):
                        self.name = name
                        self.info = info
                        self.enabled = True

                    def get_name(self):
                        return self.name

                    def get_info(self):
                        return self.info

                    def get_supported_indicators(self):
                        return []

                    def calculate_indicator(self, *args, **kwargs):
                        return None

                virtual_instance = VirtualIndicatorPlugin(plugin_name, plugin_info)
                self.plugin_instances[plugin_name] = virtual_instance
                logger.debug(f" 创建虚拟指标插件实例: {plugin_name}")
                return True

            # 对于其他插件类型，可以添加更多的加载逻辑
            # 这里暂时创建一个基本的插件实例
            self.plugin_instances[plugin_name] = plugin_info
            return True

        except Exception as e:
            logger.warning(f" 创建插件实例失败 {plugin_name}: {e}")
            return False

    def _should_load_real_plugin_instance(self, plugin_name: str) -> bool:
        """判断是否应该加载真实的插件实例"""
        # 数据源插件和指标插件需要加载真实实例
        data_source_keywords = [
            'akshare', 'wind', 'tushare', 'yahoo', 'bond', 'forex',
            'mysteel', 'wenhua', 'tongdaxin', 'custom_data', 'factorweave_data',
            'eastmoney', 'sina'  # 添加eastmoney和sina关键字
        ]
        indicator_keywords = ['talib', 'indicator', 'indicators']

        plugin_name_lower = plugin_name.lower()
        return any(keyword in plugin_name_lower for keyword in data_source_keywords) or any(keyword in plugin_name_lower for keyword in indicator_keywords)

    def _load_real_plugin_instance(self, plugin_name: str):
        """加载真实的插件实例"""
        try:
            # 根据插件名称推断文件路径
            plugin_path = self._get_plugin_file_path(plugin_name)
            if not plugin_path or not os.path.exists(plugin_path):
                logger.warning(f" 插件文件不存在: {plugin_path}")
                return None

            # 加载插件模块
            plugin_module = self._load_plugin_module(plugin_path, plugin_name)
            if not plugin_module:
                return None

            # 获取插件类
            plugin_class = self._get_plugin_class_from_module(plugin_module, plugin_name)
            if not plugin_class:
                return None

            # 创建插件实例
            plugin_instance = plugin_class()
            logger.info(f" 成功创建插件实例: {plugin_name} -> {type(plugin_instance)}")
            return plugin_instance

        except Exception as e:
            logger.error(f" 加载真实插件实例异常 {plugin_name}: {e}")
            return None

    def _get_plugin_file_path(self, plugin_name: str) -> str:
        """根据插件名称获取文件路径"""
        # 移除前缀并转换为文件路径
        if plugin_name.startswith('examples.'):
            # 移除前缀，然后将所有点替换为斜杠
            relative_path = plugin_name.replace('examples.', 'plugins/examples/', 1).replace('.', '/')
        elif plugin_name.startswith('data_sources.'):
            # 移除前缀，然后将所有点替换为斜杠
            relative_path = plugin_name.replace('data_sources.', 'plugins/data_sources/', 1).replace('.', '/')
        elif plugin_name.startswith('sentiment_data_sources.'):
            # 处理情感数据源插件
            relative_path = plugin_name.replace('sentiment_data_sources.', 'plugins/sentiment_data_sources/', 1).replace('.', '/')
        else:
            # 默认在plugins目录下，将所有点替换为斜杠
            relative_path = f"plugins/{plugin_name.replace('.', '/')}"

        return f"{relative_path}.py"

    def _load_plugin_module(self, plugin_path: str, plugin_name: str):
        """加载插件模块"""
        try:
            import importlib.util
            import sys

            # 生成模块名
            module_name = f"plugin_{plugin_name.replace('.', '_')}"

            # 加载模块
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if not spec or not spec.loader:
                logger.error(f" 无法创建模块规范: {plugin_path}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            logger.debug(f" 成功加载插件模块: {plugin_path}")
            return module

        except Exception as e:
            logger.error(f" 加载插件模块失败 {plugin_path}: {e}")
            return None

    def _get_plugin_class_from_module(self, module, plugin_name: str):
        """从模块中获取插件类"""
        try:
            # 常见的插件类名模式
            possible_class_names = []

            # 基于插件名称推断类名
            if 'akshare' in plugin_name.lower():
                possible_class_names.extend(['AKShareStockPlugin', 'AkshareStockPlugin', 'AKSharePlugin'])
            elif 'wind' in plugin_name.lower():
                possible_class_names.extend(['WindDataPlugin', 'WindPlugin'])
            elif 'yahoo' in plugin_name.lower():
                possible_class_names.extend(['YahooFinanceDataSource', 'YahooFinancePlugin'])
            elif 'bond' in plugin_name.lower():
                possible_class_names.extend(['BondDataPlugin', 'BondPlugin'])
            elif 'forex' in plugin_name.lower():
                possible_class_names.extend(['ForexDataPlugin', 'ForexPlugin'])
            elif 'mysteel' in plugin_name.lower():
                possible_class_names.extend(['MysteelDataPlugin', 'MysteelPlugin'])
            elif 'wenhua' in plugin_name.lower():
                possible_class_names.extend(['WenhuaDataPlugin', 'WenhuaPlugin'])
            elif 'custom_data' in plugin_name.lower():
                possible_class_names.extend(['CustomDataPlugin', 'CustomPlugin'])
            elif 'factorweave_data' in plugin_name.lower():
                possible_class_names.extend(['FactorWeaveDataPlugin', 'FactorWeavePlugin'])
            elif 'talib' in plugin_name.lower():
                possible_class_names.extend(['TALibIndicatorsPlugin', 'TalibIndicatorsPlugin', 'TalibPlugin'])
            elif 'indicator' in plugin_name.lower() or 'indicators' in plugin_name.lower():
                possible_class_names.extend(['IndicatorPlugin', 'IndicatorsPlugin', 'CustomIndicatorPlugin'])

            # 通用模式
            possible_class_names.extend(['Plugin', 'DataPlugin', 'DataSource'])

            # 尝试找到插件类
            for class_name in possible_class_names:
                if hasattr(module, class_name):
                    plugin_class = getattr(module, class_name)
                    logger.info(f" 找到插件类: {class_name}")
                    return plugin_class

            # 如果没有找到，尝试查找所有类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    attr.__module__ == module.__name__ and
                        'Plugin' in attr.__name__):
                    logger.info(f" 找到插件类（通用搜索）: {attr.__name__}")
                    return attr

            # 尝试查找实现IIndicatorPlugin接口的类
            try:
                from core.indicator_extensions import IIndicatorPlugin
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        attr.__module__ == module.__name__):
                        # 检查是否是IIndicatorPlugin的子类
                        try:
                            if issubclass(attr, IIndicatorPlugin):
                                logger.info(f" 找到指标插件类: {attr.__name__}")
                                return attr
                        except TypeError:
                            # 如果attr不是类，issubclass会抛出TypeError
                            continue
                logger.info(f" 未找到实现IIndicatorPlugin接口的类")
            except ImportError as e:
                logger.error(f"IIndicatorPlugin 导入失败: {e}")

            logger.warning(f" 未找到插件类，模块属性: {[name for name in dir(module) if not name.startswith('_')]}")
            return None

        except Exception as e:
            logger.error(f" 获取插件类失败: {e}")
            return None

    def _sync_plugin_state_with_db(self, plugin_name: str, plugin_info: PluginInfo):
        """同步插件状态与数据库"""
        if not self.db_service:
            return

        try:
            # 从数据库获取插件状态
            db_status = self.db_service.get_plugin_status(plugin_name)

            if db_status:
                # 根据数据库状态设置插件状态
                from db.models.plugin_models import PluginStatus as DbPluginStatus
                if db_status == DbPluginStatus.ENABLED:
                    plugin_info.status = PluginStatus.ENABLED
                elif db_status == DbPluginStatus.DISABLED:
                    plugin_info.status = PluginStatus.DISABLED
                elif db_status == DbPluginStatus.LOADED:
                    plugin_info.status = PluginStatus.LOADED
                else:
                    # 保持当前状态
                    pass
            else:
                # 插件在数据库中不存在，注册它
                self._register_plugin_to_db(plugin_name, plugin_info)

        except Exception as e:
            logger.warning(f" 同步插件状态失败 {plugin_name}: {e}")

    def _register_plugin_to_db(self, plugin_name: str, plugin_info: PluginInfo):
        """将插件注册到数据库"""
        if not self.db_service:
            return

        try:
            from db.models.plugin_models import PluginRecord, PluginType as DbPluginType

            # 转换插件类型
            db_plugin_type = DbPluginType.ANALYSIS  # 默认类型
            if plugin_info.plugin_type:
                type_mapping = {
                    'INDICATOR': DbPluginType.INDICATOR,
                    'STRATEGY': DbPluginType.STRATEGY,
                    'DATA_SOURCE': DbPluginType.DATA_SOURCE,
                    'SENTIMENT': DbPluginType.SENTIMENT,  # 新增情绪分析插件类型映射
                    'ANALYSIS': DbPluginType.ANALYSIS,
                    'UI_COMPONENT': DbPluginType.UI_COMPONENT
                }
                db_plugin_type = type_mapping.get(str(plugin_info.plugin_type).upper(), DbPluginType.ANALYSIS)

                # 创建插件元数据
            plugin_metadata = {
                'name': plugin_name,
                'display_name': plugin_info.name,
                'version': plugin_info.version,
                'plugin_type': db_plugin_type.value,
                'status': plugin_info.status.value,
                'description': plugin_info.description,
                'author': plugin_info.author,
                'install_path': plugin_info.path,
                'dependencies': plugin_info.dependencies
            }

            self.db_service.register_plugin_from_metadata(plugin_name, plugin_metadata)
            logger.info(f" 插件已注册到数据库: {plugin_name}")

        except Exception as e:
            logger.warning(f" 注册插件到数据库失败 {plugin_name}: {e}")

    def _update_plugin_status_in_db(self, plugin_name: str, new_status: PluginStatus, reason: str = ""):
        """更新数据库中的插件状态"""
        if not self.db_service:
            return

        try:
            from db.models.plugin_models import PluginStatus as DbPluginStatus

            # 转换状态
            status_mapping = {
                PluginStatus.ENABLED: DbPluginStatus.ENABLED,
                PluginStatus.DISABLED: DbPluginStatus.DISABLED,
                PluginStatus.LOADED: DbPluginStatus.LOADED,
                PluginStatus.UNLOADED: DbPluginStatus.UNLOADED,
                PluginStatus.ERROR: DbPluginStatus.ERROR
            }

            db_status = status_mapping.get(new_status, DbPluginStatus.LOADED)
            self.db_service.update_plugin_status(plugin_name, db_status, reason)

        except Exception as e:
            logger.warning(f" 更新数据库插件状态失败 {plugin_name}: {e}")

    def _sync_all_plugins_with_db(self):
        """同步所有插件的状态与数据库"""
        if not self.db_service:
            return

        try:
            for plugin_name, plugin_info in self.enhanced_plugins.items():
                try:
                    # 从数据库获取插件状态
                    db_status = self.db_service.get_plugin_status(plugin_name)
                    if db_status and db_status != PluginStatus.UNLOADED:
                        # 更新插件状态
                        plugin_info.status = db_status
                        plugin_info.enabled = (db_status == PluginStatus.ENABLED)
                        logger.debug(f"从数据库同步插件状态: {plugin_name} -> {db_status.value}")

                except Exception as e:
                    logger.warning(f"同步插件 {plugin_name} 状态失败: {e}")

        except Exception as e:
            logger.error(f"同步所有插件状态失败: {e}")

    def initialize(self) -> None:
        """
        初始化插件管理器

        包括：
        1. 创建插件目录
        2. 加载所有插件
        3. 从数据库加载数据源配置
        4. 同步插件状态到数据库
        """
        try:
            # 确保插件目录存在
            self.plugin_dir.mkdir(parents=True, exist_ok=True)

            # 加载所有插件
            self.load_all_plugins()

            # 从数据库加载数据源配置
            self._load_data_source_configs_from_db()

            # 同步插件状态到数据库（新增/更新/删除孤儿）
            try:
                sync_result = self.sync_db_with_real_plugins()
                logger.info(f"插件状态已同步到数据库，共 {len(sync_result)} 项")
            except Exception as e:
                logger.error(f"同步插件状态到数据库失败: {e}")

            logger.info(f"插件管理器初始化完成，已加载 {len(self.enhanced_plugins)} 个插件")

        except Exception as e:
            logger.error(f"插件管理器初始化失败: {e}")

    def discover_and_register_plugins(self) -> None:
        """
        发现并注册所有插件
        在服务引导完成后调用，确保所有依赖服务都已可用
        """
        try:
            logger.info("开始发现和注册插件...")

            # 1. 重新扫描插件目录
            self._scan_plugin_directory()

            # 2. 加载新发现的插件
            self._load_discovered_plugins()

            # 3. 注册数据源插件到统一数据管理器
            self._register_data_source_plugins_to_manager()

            logger.info(f" 插件发现和注册完成，共管理 {len(self.enhanced_plugins)} 个插件")

        except Exception as e:
            logger.error(f" 插件发现和注册失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _scan_plugin_directory(self) -> None:
        """扫描插件目录，发现新插件"""
        try:
            plugin_files = []

            # 排除的目录列表
            excluded_dirs = {'examples', 'templates', '__pycache__', 'test', 'tests', '.git'}

            # 扫描插件目录
            for plugin_path in self.plugin_dir.rglob("*.py"):
                # 检查是否在排除目录中
                if any(excluded in plugin_path.parts for excluded in excluded_dirs):
                    continue

                if plugin_path.name != "__init__.py" and not plugin_path.name.startswith("_"):
                    plugin_files.append(plugin_path)

            logger.info(f"发现 {len(plugin_files)} 个潜在插件文件（已排除 examples/templates 等目录）")

        except Exception as e:
            logger.error(f"扫描插件目录失败: {e}")

    def _load_discovered_plugins(self) -> None:
        """加载发现的插件"""
        try:
            # 重新加载所有插件
            self.load_all_plugins()

        except Exception as e:
            logger.error(f"加载发现的插件失败: {e}")

    def _register_data_source_plugins_to_manager(self, data_manager=None) -> None:
        """将数据源插件注册到统一数据管理器"""
        try:
            # 使用传入的数据管理器或现有的数据管理器
            target_manager = data_manager or self.data_manager

            # 如果没有数据管理器，尝试获取
            if not target_manager:
                try:
                    from .services.unified_data_manager import get_unified_data_manager
                    target_manager = get_unified_data_manager()
                    if target_manager:
                        logger.info("成功获取统一数据管理器")
                        # 保存引用
                        if not self.data_manager:
                            self.data_manager = target_manager
                    else:
                        logger.warning("无法获取统一数据管理器，跳过数据源插件注册")
                        return
                except Exception as e:
                    logger.warning(f"获取统一数据管理器失败: {e}，跳过数据源插件注册")
                    return

            registered_count = 0

            # 遍历所有插件，找出数据源插件
            for plugin_name, plugin_info in self.enhanced_plugins.items():
                try:
                    # 从plugin_instances中获取插件实例
                    plugin_instance = self.plugin_instances.get(plugin_name)

                    if plugin_instance and self._is_data_source_plugin_instance(plugin_instance):
                        if hasattr(target_manager, 'register_data_source_plugin'):
                            success = target_manager.register_data_source_plugin(
                                plugin_name,
                                plugin_instance,
                                priority=getattr(plugin_instance, 'priority', 50),
                                weight=getattr(plugin_instance, 'weight', 1.0)
                            )

                            if success:
                                registered_count += 1
                                logger.info(f" 数据源插件注册成功: {plugin_name}")
                            else:
                                logger.warning(f" 数据源插件注册失败: {plugin_name}")
                        else:
                            logger.warning(f" 数据管理器缺少register_data_source_plugin方法")
                    else:
                        if plugin_instance:
                            logger.debug(f"插件 {plugin_name} 不是数据源插件")
                        else:
                            logger.debug(f"插件 {plugin_name} 实例不存在")

                except Exception as e:
                    logger.warning(f" 注册数据源插件失败 {plugin_name}: {e}")

            if registered_count > 0:
                logger.info(f" 成功注册了 {registered_count} 个数据源插件到统一数据管理器")
            else:
                logger.info("未发现可注册的数据源插件")

        except Exception as e:
            logger.error(f"注册数据源插件到管理器失败: {e}")

    def _is_data_source_plugin(self, plugin_info: PluginInfo) -> bool:
        """检查插件是否是数据源插件"""
        try:
            # 检查插件类型
            if plugin_info.plugin_type and 'DATA_SOURCE' in str(plugin_info.plugin_type).upper():
                return True

            # 检查插件实例是否实现了数据源接口
            if plugin_info.instance:
                from .data_source_extensions import IDataSourcePlugin
                if isinstance(plugin_info.instance, IDataSourcePlugin):
                    return True

                # 检查是否有必要的数据源方法
                required_methods = ['get_asset_list', 'get_kdata', 'health_check']
                if all(hasattr(plugin_info.instance, method) for method in required_methods):
                    return True

        except Exception as e:
            logger.warning(f"检查数据源插件时出错: {e}")

        return False

    def _is_data_source_plugin_instance(self, plugin_instance) -> bool:
        """检查插件实例是否是数据源插件"""
        try:
            # 检查插件实例是否实现了数据源接口
            from .data_source_extensions import IDataSourcePlugin
            if isinstance(plugin_instance, IDataSourcePlugin):
                return True

            # 检查是否有必要的数据源方法
            required_methods = ['get_asset_list', 'get_kdata', 'health_check']
            if all(hasattr(plugin_instance, method) for method in required_methods):
                return True

        except Exception as e:
            logger.warning(f"检查数据源插件实例时出错: {e}")

        return False

    def _load_data_source_configs_from_db(self):
        """从数据库加载数据源配置"""
        try:
            from db.models.plugin_models import get_data_source_config_manager
            config_manager = get_data_source_config_manager()

            # 加载插件配置
            plugin_configs = config_manager.get_all_plugin_configs()
            logger.info(f"从数据库加载了 {len(plugin_configs)} 个数据源插件配置")

            # 加载路由配置
            routing_configs = config_manager.get_all_routing_configs()
            logger.info(f"从数据库加载了 {len(routing_configs)} 个路由配置")

            # 应用路由配置到统一数据管理器
            try:
                from .services.unified_data_manager import get_unified_data_manager
                from .plugin_types import AssetType

                unified_manager = get_unified_data_manager()
                if unified_manager and hasattr(unified_manager, 'data_source_router'):
                    router = unified_manager.data_source_router

                    for asset_type_str, priorities in routing_configs.items():
                        try:
                            asset_type = AssetType(asset_type_str)
                            router.set_asset_priorities(asset_type, priorities)
                            logger.info(f"已应用路由配置: {asset_type_str} -> {priorities}")
                        except ValueError:
                            logger.warning(f"无效的资产类型: {asset_type_str}")
                        except Exception as e:
                            logger.error(f"应用路由配置失败 {asset_type_str}: {e}")

            except Exception as e:
                logger.error(f"应用路由配置到统一数据管理器失败: {e}")

        except Exception as e:
            logger.error(f"从数据库加载数据源配置失败: {e}")

    def load_data_source_plugin(self, plugin_path: str) -> bool:
        """
        加载数据源插件（Task 1.3 新增方法）

        Args:
            plugin_path: 插件文件路径

        Returns:
            bool: 加载是否成功
        """
        try:
            with self._data_source_lock:
                # 导入新的插件类型定义
                from .plugin_types import PluginType, is_data_source_plugin
                from .data_source_extensions import IDataSourcePlugin, validate_plugin_interface, DataSourcePluginAdapter

                # 复用现有的插件加载机制
                plugin_info = self._load_plugin_from_path(plugin_path)

                if plugin_info is None:
                    logger.error(f"无法加载插件: {plugin_path}")
                    return False

                # 检查是否为数据源插件类型
                if not is_data_source_plugin(plugin_info.plugin_type):
                    logger.error(f"插件类型不是数据源插件: {plugin_info.plugin_type}")
                    return False

                # 验证插件是否实现了IDataSourcePlugin接口
                if not isinstance(plugin_info.instance, IDataSourcePlugin):
                    logger.error(f"插件未实现IDataSourcePlugin接口: {plugin_info.id}")
                    return False

                # 验证插件接口
                if not validate_plugin_interface(plugin_info.instance):
                    logger.error(f"插件接口验证失败: {plugin_info.id}")
                    return False

                # 注册到数据管理器
                if self.data_manager:
                    if not self.data_manager.register_plugin_data_source(
                            plugin_info.id, plugin_info.instance):
                        logger.error(f"插件注册到数据管理器失败: {plugin_info.id}")
                        return False

                # 新增：同时注册到统一数据管理器的路由器
                try:
                    from .services.unified_data_manager import get_unified_data_manager
                    from .data_source_extensions import DataSourcePluginAdapter, IDataSourcePlugin

                    unified_manager = get_unified_data_manager()
                    if unified_manager and hasattr(unified_manager, 'register_data_source_plugin'):
                        # 严格限制：仅对实现 IDataSourcePlugin 的实例注册到路由器
                        if not isinstance(plugin_info.instance, IDataSourcePlugin):
                            logger.debug(f"跳过路由器注册（非IDataSourcePlugin）: {plugin_info.id}")
                            pass
                        else:
                            # 创建适配器
                            adapter = DataSourcePluginAdapter(plugin_info.instance, plugin_info.id)

                            # 优化：跳过同步连接，避免阻塞主线程
                            # 连接将在后台线程或首次使用时自动建立
                            logger.info(f" 数据源插件适配器已创建（延迟连接）: {plugin_info.id}")

                            # 使用正确的注册方法：register_data_source_plugin
                            success = unified_manager.register_data_source_plugin(
                                plugin_info.id,
                                adapter,
                                priority=0,
                                weight=1.0
                            )

                            if success:
                                logger.info(f" 数据源插件注册到统一数据管理器成功: {plugin_info.id}")
                            else:
                                logger.warning(f" 数据源插件注册到统一数据管理器失败: {plugin_info.id}")

                        # 可观测性：如果实现了接口但未注册成功，明确报警
                        if isinstance(plugin_info.instance, IDataSourcePlugin) and not success:
                            logger.error(f" 已实现IDataSourcePlugin但未注册成功: id={plugin_info.id}, class={type(plugin_info.instance).__name__}")
                        else:
                            logger.debug(f"统一数据管理器不可用或缺少register_data_source_plugin方法，跳过路由器注册: {plugin_info.id}")

                except Exception as e:
                    logger.error(f" 注册到统一数据管理器异常 {plugin_info.id}: {e}")

                # 存储到数据源插件字典
                self.data_source_plugins[plugin_info.id] = plugin_info

                # 添加到按类型分类的插件列表
                if plugin_info.plugin_type not in self.plugins_by_type:
                    self.plugins_by_type[plugin_info.plugin_type] = []
                self.plugins_by_type[plugin_info.plugin_type].append(plugin_info.id)

                logger.info(f"数据源插件加载成功: {plugin_info.id}")
                return True

        except Exception as e:
            logger.error(f"加载数据源插件失败 {plugin_path}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def unload_data_source_plugin(self, plugin_id: str) -> bool:
        """
        卸载数据源插件（支持热插拔）

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 卸载是否成功
        """
        try:
            with self._data_source_lock:
                if plugin_id not in self.data_source_plugins:
                    logger.warning(f"数据源插件不存在: {plugin_id}")
                    return False

                plugin_info = self.data_source_plugins[plugin_id]

                logger.info(f"开始卸载数据源插件: {plugin_id}")

                # 1. 断开插件连接
                try:
                    if hasattr(plugin_info.instance, 'disconnect'):
                        plugin_info.instance.disconnect()
                        logger.info(f"插件连接已断开: {plugin_id}")
                except Exception as e:
                    logger.warning(f"断开插件连接失败 {plugin_id}: {str(e)}")

                # 2. 从TET框架注销
                try:
                    from .services.unified_data_manager import get_unified_data_manager
                    unified_manager = get_unified_data_manager()
                    if unified_manager and hasattr(unified_manager, 'tet_pipeline') and unified_manager.tet_pipeline:
                        unified_manager.tet_pipeline.unregister_plugin(plugin_id)
                        logger.info(f"插件从TET框架注销成功: {plugin_id}")
                except Exception as e:
                    logger.warning(f"从TET框架注销失败 {plugin_id}: {str(e)}")

                # 3. 从统一数据管理器注销
                try:
                    if unified_manager and hasattr(unified_manager, 'unregister_data_source_plugin'):
                        unified_manager.unregister_data_source_plugin(plugin_id)
                        logger.info(f"插件从统一数据管理器注销成功: {plugin_id}")
                except Exception as e:
                    logger.warning(f"从统一数据管理器注销失败 {plugin_id}: {str(e)}")

                # 4. 从数据管理器注销
                if self.data_manager:
                    try:
                        self.data_manager.unregister_plugin_data_source(plugin_id)
                        logger.info(f"插件从数据管理器注销成功: {plugin_id}")
                    except Exception as e:
                        logger.warning(f"从数据管理器注销失败 {plugin_id}: {str(e)}")

                # 5. 清理插件实例
                try:
                    if hasattr(plugin_info.instance, 'cleanup'):
                        plugin_info.instance.cleanup()
                        logger.info(f"插件资源清理完成: {plugin_id}")
                except Exception as e:
                    logger.warning(f"插件资源清理失败 {plugin_id}: {str(e)}")

                # 6. 从插件字典中移除
                del self.data_source_plugins[plugin_id]

                # 7. 从分类列表中移除
                if plugin_info.plugin_type in self.plugins_by_type:
                    if plugin_id in self.plugins_by_type[plugin_info.plugin_type]:
                        self.plugins_by_type[plugin_info.plugin_type].remove(plugin_id)

                # 8. 从其他插件存储中移除
                if plugin_id in self.loaded_plugins:
                    del self.loaded_plugins[plugin_id]
                if plugin_id in self.plugin_instances:
                    del self.plugin_instances[plugin_id]
                if plugin_id in self.enhanced_plugins:
                    del self.enhanced_plugins[plugin_id]

                # 9. 发送插件卸载事件
                try:
                    if self.event_bus:
                        self.event_bus.emit('plugin_unloaded', {
                            'plugin_id': plugin_id,
                            'plugin_type': plugin_info.plugin_type.value if hasattr(plugin_info.plugin_type, 'value') else str(plugin_info.plugin_type),
                            'timestamp': datetime.now().isoformat()
                        })
                except Exception as e:
                    logger.warning(f"发送插件卸载事件失败 {plugin_id}: {str(e)}")

                logger.info(f" 数据源插件卸载成功: {plugin_id}")
                return True

        except Exception as e:
            logger.error(f" 卸载数据源插件失败 {plugin_id}: {str(e)}")
            return False

    def reload_data_source_plugin(self, plugin_id: str) -> bool:
        """
        重新加载数据源插件（热重载）

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 重载是否成功
        """
        try:
            logger.info(f"开始重新加载数据源插件: {plugin_id}")

            # 保存插件信息
            if plugin_id not in self.data_source_plugins:
                logger.error(f"数据源插件不存在: {plugin_id}")
                return False

            plugin_info = self.data_source_plugins[plugin_id]
            plugin_path = getattr(plugin_info, 'path', None)

            # 卸载现有插件
            if not self.unload_data_source_plugin(plugin_id):
                logger.error(f"卸载插件失败: {plugin_id}")
                return False

            # 重新加载插件
            if plugin_path:
                return self.load_data_source_plugin_from_file(plugin_path)
            else:
                # 尝试从默认位置重新加载
                plugin_file = f"plugins/data_sources/{plugin_id}.py"
                if os.path.exists(plugin_file):
                    return self.load_data_source_plugin_from_file(plugin_file)
                else:
                    logger.error(f"找不到插件文件: {plugin_id}")
                    return False

        except Exception as e:
            logger.error(f"重新加载数据源插件失败 {plugin_id}: {str(e)}")
            return False

    def switch_data_source_plugin(self, from_plugin_id: str, to_plugin_id: str) -> bool:
        """
        切换数据源插件

        Args:
            from_plugin_id: 当前插件ID
            to_plugin_id: 目标插件ID

        Returns:
            bool: 切换是否成功
        """
        try:
            logger.info(f"切换数据源插件: {from_plugin_id} -> {to_plugin_id}")

            # 检查目标插件是否存在
            if to_plugin_id not in self.data_source_plugins:
                logger.error(f"目标数据源插件不存在: {to_plugin_id}")
                return False

            # 获取统一数据管理器
            try:
                from .services.unified_data_manager import get_unified_data_manager
                unified_manager = get_unified_data_manager()

                if not unified_manager:
                    logger.error("统一数据管理器不可用")
                    return False

                # 切换数据源优先级
                if hasattr(unified_manager, 'set_data_source_priority'):
                    # 将目标插件设为最高优先级
                    current_priorities = unified_manager.get_data_source_priorities()
                    stock_priorities = current_priorities.get('stock', [])

                    # 移除目标插件（如果存在）
                    if to_plugin_id in stock_priorities:
                        stock_priorities.remove(to_plugin_id)

                    # 将目标插件设为第一优先级
                    new_priorities = [to_plugin_id] + stock_priorities
                    unified_manager.set_data_source_priority('stock', new_priorities)

                    logger.info(f"数据源优先级已更新: {new_priorities}")

                # 发送切换事件
                if self.event_bus:
                    self.event_bus.emit('data_source_switched', {
                        'from_plugin': from_plugin_id,
                        'to_plugin': to_plugin_id,
                        'timestamp': datetime.now().isoformat()
                    })

                return True

            except Exception as e:
                logger.error(f"切换数据源失败: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"切换数据源插件失败: {str(e)}")
            return False

    def health_check_data_source_plugins(self) -> Dict[str, Dict[str, Any]]:
        """
        检查所有数据源插件的健康状态

        Returns:
            Dict[str, Dict[str, Any]]: 插件健康状态字典
        """
        try:
            health_results = {}

            for plugin_id, plugin_info in self.data_source_plugins.items():
                try:
                    if hasattr(plugin_info.instance, 'health_check'):
                        health_result = plugin_info.instance.health_check()
                        health_results[plugin_id] = {
                            'is_healthy': health_result.is_healthy,
                            'status_code': health_result.status_code,
                            'message': health_result.message,
                            'response_time_ms': health_result.response_time_ms,
                            'last_check_time': health_result.last_check_time.isoformat() if health_result.last_check_time else None,
                            'details': health_result.details or {}
                        }
                    else:
                        health_results[plugin_id] = {
                            'is_healthy': False,
                            'status_code': 501,
                            'message': '插件不支持健康检查',
                            'response_time_ms': 0.0,
                            'last_check_time': datetime.now().isoformat(),
                            'details': {}
                        }

                except Exception as e:
                    health_results[plugin_id] = {
                        'is_healthy': False,
                        'status_code': 500,
                        'message': f'健康检查异常: {str(e)}',
                        'response_time_ms': 0.0,
                        'last_check_time': datetime.now().isoformat(),
                        'details': {'error': str(e)}
                    }

            return health_results

        except Exception as e:
            logger.error(f"检查数据源插件健康状态失败: {str(e)}")
            return {}

    def get_data_source_plugin_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有数据源插件的统计信息

        Returns:
            Dict[str, Dict[str, Any]]: 插件统计信息字典
        """
        try:
            stats_results = {}

            for plugin_id, plugin_info in self.data_source_plugins.items():
                try:
                    if hasattr(plugin_info.instance, 'get_statistics'):
                        stats = plugin_info.instance.get_statistics()
                        stats_results[plugin_id] = stats
                    else:
                        stats_results[plugin_id] = {
                            'total_requests': 0,
                            'successful_requests': 0,
                            'failed_requests': 0,
                            'average_response_time': 0.0,
                            'last_request_time': None,
                            'uptime': 0.0
                        }

                except Exception as e:
                    logger.warning(f"获取插件统计信息失败 {plugin_id}: {str(e)}")
                    stats_results[plugin_id] = {'error': str(e)}

            return stats_results

        except Exception as e:
            logger.error(f"获取数据源插件统计信息失败: {str(e)}")
            return {}

    def enable_data_source_plugin(self, plugin_id: str) -> bool:
        """
        启用数据源插件

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 启用是否成功
        """
        try:
            if plugin_id not in self.data_source_plugins:
                logger.error(f"数据源插件不存在: {plugin_id}")
                return False

            plugin_info = self.data_source_plugins[plugin_id]

            # 连接插件
            if hasattr(plugin_info.instance, 'connect'):
                if plugin_info.instance.connect():
                    logger.info(f"数据源插件已启用: {plugin_id}")

                    # 发送启用事件
                    if self.event_bus:
                        self.event_bus.emit('plugin_enabled', {
                            'plugin_id': plugin_id,
                            'timestamp': datetime.now().isoformat()
                        })

                    return True
                else:
                    logger.error(f"数据源插件连接失败: {plugin_id}")
                    return False
            else:
                logger.warning(f"数据源插件不支持连接操作: {plugin_id}")
                return True  # 认为已启用

        except Exception as e:
            logger.error(f"启用数据源插件失败 {plugin_id}: {str(e)}")
            return False

    def disable_data_source_plugin(self, plugin_id: str) -> bool:
        """
        禁用数据源插件

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 禁用是否成功
        """
        try:
            if plugin_id not in self.data_source_plugins:
                logger.error(f"数据源插件不存在: {plugin_id}")
                return False

            plugin_info = self.data_source_plugins[plugin_id]

            # 断开插件连接
            if hasattr(plugin_info.instance, 'disconnect'):
                if plugin_info.instance.disconnect():
                    logger.info(f"数据源插件已禁用: {plugin_id}")

                    # 发送禁用事件
                    if self.event_bus:
                        self.event_bus.emit('plugin_disabled', {
                            'plugin_id': plugin_id,
                            'timestamp': datetime.now().isoformat()
                        })

                    return True
                else:
                    logger.error(f"数据源插件断开失败: {plugin_id}")
                    return False
            else:
                logger.warning(f"数据源插件不支持断开操作: {plugin_id}")
                return True  # 认为已禁用

        except Exception as e:
            logger.error(f"禁用数据源插件失败 {plugin_id}: {str(e)}")
            return False

    def get_data_source_plugins(self) -> Dict[str, PluginInfo]:
        """
        获取所有数据源插件

        Returns:
            Dict[str, PluginInfo]: 数据源插件字典
        """
        with self._data_source_lock:
            return self.data_source_plugins.copy()

    def get_plugins_by_asset_type(self, asset_type: str) -> List[PluginInfo]:
        """
        根据资产类型获取数据源插件

        Args:
            asset_type: 资产类型（stock, futures, crypto等）

        Returns:
            List[PluginInfo]: 支持该资产类型的插件列表
        """
        try:
            from .plugin_types import AssetType

            # 转换资产类型
            try:
                target_asset_type = AssetType(asset_type)
            except ValueError:
                logger.warning(f"未知的资产类型: {asset_type}")
                return []

            matching_plugins = []

            with self._data_source_lock:
                for plugin_info in self.data_source_plugins.values():
                    try:
                        # 获取插件支持的资产类型
                        plugin_asset_types = plugin_info.instance.get_supported_asset_types()

                        # 检查是否支持目标资产类型
                        for supported_type in plugin_asset_types:
                            if (supported_type.value == target_asset_type.value or
                                    supported_type == target_asset_type):
                                matching_plugins.append(plugin_info)
                                break

                    except Exception as e:
                        logger.error(f"检查插件资产类型失败 {plugin_info.id}: {str(e)}")
                        continue

            return matching_plugins

        except Exception as e:
            logger.error(f"根据资产类型获取插件失败: {str(e)}")
            return []

    def enable_data_source_plugin(self, plugin_id: str) -> bool:
        """
        启用数据源插件

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 启用是否成功
        """
        try:
            with self._data_source_lock:
                if plugin_id not in self.data_source_plugins:
                    logger.error(f"数据源插件不存在: {plugin_id}")
                    return False

                plugin_info = self.data_source_plugins[plugin_id]

                # 更新插件状态
                plugin_info.enabled = True

                # 如果数据管理器中已注册，确保其健康状态（使用异步连接）
                if self.data_manager and plugin_id in self.data_manager._plugin_data_sources:
                    adapter = self.data_manager._plugin_data_sources[plugin_id]
                    if not adapter.is_connected():
                        # 异步连接，不阻塞主线程
                        plugin = adapter.plugin
                        if hasattr(plugin, 'connect_async'):
                            plugin.connect_async()
                            logger.info(f"数据源插件 {plugin_id} 已启动异步连接")

                # 发送启用信号
                self.plugin_enabled.emit(plugin_id)

                logger.info(f"数据源插件已启用: {plugin_id}")
                return True

        except Exception as e:
            logger.error(f"启用数据源插件失败 {plugin_id}: {str(e)}")
            return False

    def disable_data_source_plugin(self, plugin_id: str) -> bool:
        """
        禁用数据源插件

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 禁用是否成功
        """
        try:
            with self._data_source_lock:
                if plugin_id not in self.data_source_plugins:
                    logger.error(f"数据源插件不存在: {plugin_id}")
                    return False

                plugin_info = self.data_source_plugins[plugin_id]

                # 更新插件状态
                plugin_info.enabled = False

                # 如果数据管理器中已注册，断开连接
                if self.data_manager and plugin_id in self.data_manager._plugin_data_sources:
                    adapter = self.data_manager._plugin_data_sources[plugin_id]
                    adapter.disconnect()

                # 发送禁用信号
                self.plugin_disabled.emit(plugin_id)

                logger.info(f"数据源插件已禁用: {plugin_id}")
                return True

        except Exception as e:
            logger.error(f"禁用数据源插件失败 {plugin_id}: {str(e)}")
            return False

    def get_plugin_health_status(self, plugin_id: str) -> Dict[str, Any]:
        """
        获取插件健康状态

        Args:
            plugin_id: 插件ID

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            if plugin_id not in self.data_source_plugins:
                return {"error": "插件不存在"}

            if not self.data_manager or plugin_id not in self.data_manager._plugin_data_sources:
                return {"error": "插件未注册到数据管理器"}

            adapter = self.data_manager._plugin_data_sources[plugin_id]
            health_result = adapter.health_check()
            statistics = adapter.get_statistics()

            return {
                "is_healthy": health_result.is_healthy,
                "response_time_ms": health_result.response_time_ms,
                "error_message": health_result.error_message,
                "timestamp": health_result.timestamp.isoformat(),
                "statistics": statistics
            }

        except Exception as e:
            logger.error(f"获取插件健康状态失败 {plugin_id}: {str(e)}")
            return {"error": str(e)}

    def _get_data_manager(self):
        """获取数据管理器实例（内部方法）"""
        return self.data_manager

    def load_all_plugins(self) -> None:
        """加载所有插件"""
        try:
            if not self.plugin_dir.exists():
                logger.warning(f"插件目录不存在: {self.plugin_dir}")
                return

            # 需要排除的文件和模块
            excluded_files = ["plugin_interface.py",
                              "plugin_market.py", "__init__.py"]
            excluded_modules = ["plugin_interface", "plugin_market"]

            # 加载插件目录中的插件
            loaded_count = 0

            # 扫描插件目录
            for plugin_path in self.plugin_dir.glob("*.py"):
                if plugin_path.name in excluded_files or plugin_path.name.startswith("__"):
                    logger.debug(f"跳过非插件文件: {plugin_path.name}")
                    continue

                plugin_name = plugin_path.stem
                if plugin_name in excluded_modules:
                    logger.info(f"跳过非插件模块: {plugin_name}")
                    continue

                if self.load_plugin(plugin_name, plugin_path):
                    loaded_count += 1

            # 加载sentiment_data_sources目录中的情绪数据源插件
            sentiment_dir = self.plugin_dir / "sentiment_data_sources"
            if sentiment_dir.exists():
                # 确保sentiment_data_sources目录是一个包
                init_file = sentiment_dir / "__init__.py"
                if not init_file.exists():
                    with open(init_file, 'w') as f:
                        f.write('"""情绪数据源插件包"""')
                    logger.info(f"创建sentiment_data_sources包的__init__.py文件")

                for plugin_path in sentiment_dir.glob("*.py"):
                    if plugin_path.name in excluded_files or plugin_path.name.startswith("__"):
                        logger.debug(f"跳过非插件文件: {plugin_path.name}")
                        continue

                    plugin_name = f"sentiment_data_sources.{plugin_path.stem}"
                    if self.load_plugin(plugin_name, plugin_path):
                        loaded_count += 1

            # 加载data_sources目录中的数据源插件（包括分类子目录）
            data_sources_dir = self.plugin_dir / "data_sources"
            if data_sources_dir.exists():
                # 确保data_sources目录是一个包
                init_file = data_sources_dir / "__init__.py"
                if not init_file.exists():
                    with open(init_file, 'w') as f:
                        f.write('"""数据源插件包"""')
                    logger.info(f"创建data_sources包的__init__.py文件")

                # 1. 加载data_sources根目录的插件（向后兼容）
                for plugin_path in data_sources_dir.glob("*.py"):
                    if plugin_path.name in excluded_files or plugin_path.name.startswith("__"):
                        logger.debug(f"跳过非插件文件: {plugin_path.name}")
                        continue

                    plugin_name = f"data_sources.{plugin_path.stem}"
                    if self.load_plugin(plugin_name, plugin_path):
                        loaded_count += 1

                # 2. 加载data_sources分类子目录中的插件（新架构）
                # 分类目录：stock、crypto、futures、forex、bond、commodity、custom、stock_international
                # 排除目录：templates、examples、__pycache__、test、tests
                excluded_subdirs = {'templates', 'examples', '__pycache__', 'test', 'tests', '.git'}
                category_dirs = ["stock", "crypto", "futures", "forex", "bond", "commodity", "custom", "stock_international"]

                for category in category_dirs:
                    if category in excluded_subdirs:
                        continue

                    category_dir = data_sources_dir / category
                    if not category_dir.exists() or not category_dir.is_dir():
                        continue

                    # 确保分类目录是一个包
                    category_init = category_dir / "__init__.py"
                    if not category_init.exists():
                        with open(category_init, 'w', encoding='utf-8') as f:
                            f.write(f'"""数据源插件 - {category} 分类"""')
                        logger.info(f"创建data_sources/{category}包的__init__.py文件")

                    # 加载该分类目录下的所有插件
                    for plugin_path in category_dir.glob("*_plugin.py"):
                        if plugin_path.name in excluded_files or plugin_path.name.startswith("__"):
                            continue

                        plugin_name = f"data_sources.{category}.{plugin_path.stem}"
                        logger.info(f"🔍 发现分类插件: {plugin_name}")
                        if self.load_plugin(plugin_name, plugin_path):
                            loaded_count += 1
                            logger.info(f"✅ 成功加载分类插件: {plugin_name}")
                        else:
                            logger.warning(f"❌ 加载分类插件失败: {plugin_name}")

            # 加载indicators目录中的指标插件
            indicators_dir = self.plugin_dir / "indicators"
            if indicators_dir.exists():
                # 确保indicators目录是一个包
                init_file = indicators_dir / "__init__.py"
                if not init_file.exists():
                    with open(init_file, 'w') as f:
                        f.write('"""指标插件包"""')
                    logger.info(f"创建indicators包的__init__.py文件")

                for plugin_path in indicators_dir.glob("*.py"):
                    if plugin_path.name in excluded_files or plugin_path.name.startswith("__"):
                        logger.debug(f"跳过非插件文件: {plugin_path.name}")
                        continue

                    plugin_name = f"indicators.{plugin_path.stem}"
                    if self.load_plugin(plugin_name, plugin_path):
                        loaded_count += 1

            # 加载strategies目录中的策略插件
            strategies_dir = self.plugin_dir / "strategies"
            if strategies_dir.exists():
                # 确保strategies目录是一个包
                init_file = strategies_dir / "__init__.py"
                if not init_file.exists():
                    with open(init_file, 'w') as f:
                        f.write('"""策略插件包"""')
                    logger.info(f"创建strategies包的__init__.py文件")

                for plugin_path in strategies_dir.glob("*.py"):
                    if plugin_path.name in excluded_files or plugin_path.name.startswith("__"):
                        logger.debug(f"跳过非插件文件: {plugin_path.name}")
                        continue

                    plugin_name = f"strategies.{plugin_path.stem}"
                    if self.load_plugin(plugin_name, plugin_path):
                        loaded_count += 1

            logger.info(
                f"已加载 {loaded_count} 个插件 [core.plugin_manager::load_all_plugins]")

        except Exception as e:
            logger.error(f"加载插件失败: {e}")
            logger.error(traceback.format_exc())

    def load_plugin(self, plugin_name: str, plugin_path: Path) -> bool:
        """
        加载指定插件

        Args:
            plugin_name: 插件名称
            plugin_path: 插件文件路径

        Returns:
            bool: 是否加载成功
        """
        try:
            # 检查插件是否已加载
            if plugin_name in self.loaded_plugins:
                logger.warning(f"插件已加载: {plugin_name}")
                return True

            # 加载插件模块
            spec = importlib.util.spec_from_file_location(
                plugin_name, plugin_path)
            if spec is None or spec.loader is None:
                logger.error(f"无法创建插件规范: {plugin_name}")
                return False

            module = importlib.util.module_from_spec(spec)

            # 处理相对导入问题（支持多层嵌套）
            if "." in plugin_name:  # 如果是子包中的模块
                # 确保所有祖先包都在sys.modules中
                parts = plugin_name.split(".")
                current_path = plugin_path.parent

                # 从最深层往上遍历，确保每一层父包都已加载
                for i in range(len(parts) - 1, 0, -1):
                    parent_name = ".".join(parts[:i])
                    if parent_name not in sys.modules:
                        parent_init = current_path / "__init__.py"
                        if parent_init.exists():
                            parent_spec = importlib.util.spec_from_file_location(
                                parent_name, parent_init)
                            if parent_spec and parent_spec.loader:
                                parent_module = importlib.util.module_from_spec(parent_spec)
                                sys.modules[parent_name] = parent_module
                                try:
                                    parent_spec.loader.exec_module(parent_module)
                                except Exception as e:
                                    logger.warning(f"加载父包 {parent_name} 时出错: {e}")
                    current_path = current_path.parent

            sys.modules[plugin_name] = module  # 将模块添加到sys.modules，确保可以被导入

            # 执行模块前修正相对导入问题
            # 为模块设置__package__属性
            if "." in plugin_name:
                module.__package__ = plugin_name.rsplit(".", 1)[0]

            # 执行模块
            spec.loader.exec_module(module)

            # 查找插件类
            plugin_class = self._find_plugin_class(module)
            if plugin_class is None:
                logger.error(f"未找到插件类: {plugin_name}")
                return False

            # 获取插件元数据
            metadata = self._get_plugin_metadata(plugin_class)

            # 创建插件实例
            try:
                plugin_instance = plugin_class()
            except Exception as e:
                # 如果是抽象类或接口，跳过
                if "Can't instantiate abstract class" in str(e):
                    logger.debug(f"跳过抽象类或接口: {plugin_name}")
                    return False
                else:
                    logger.error(f"创建插件实例失败 {plugin_name}: {e}")
                    logger.error(f"错误详情: {type(e).__name__}: {e}")
                    import traceback
                    logger.error(f"堆栈跟踪: {traceback.format_exc()}")
                    return False

            # 优先：V2 插件元信息
            v2_info = None
            if hasattr(plugin_instance, 'get_plugin_info'):
                try:
                    v2_info = plugin_instance.get_plugin_info()
                except Exception as e:
                    logger.warning(f"获取插件信息失败（get_plugin_info）{plugin_name}: {e}")

            if v2_info is not None:
                # 兼容：某些 v2_info 没有 plugin_type 字段
                _v2_type = getattr(v2_info, 'plugin_type', None)
                if _v2_type is None:
                    _v2_type = getattr(plugin_instance, 'plugin_type', None)
                try:
                    _v2_type_str = _v2_type.value if hasattr(_v2_type, 'value') else (str(_v2_type) if _v2_type is not None else 'unknown')
                except Exception:
                    _v2_type_str = 'unknown'

                metadata = {
                    'name': v2_info.name,
                    'version': getattr(v2_info, 'version', '1.0.0'),
                    'description': getattr(v2_info, 'description', ''),
                    'author': getattr(v2_info, 'author', ''),
                    'plugin_type': _v2_type_str,
                    'display_name': v2_info.name,
                    'path': str(plugin_path),
                }
            else:
                # 兼容：旧方式提取元数据
                metadata = self._get_plugin_metadata(plugin_class)

            # 保存插件信息
            self.loaded_plugins[plugin_name] = module
            self.plugin_instances[plugin_name] = plugin_instance
            self.plugin_metadata[plugin_name] = metadata

            # 初始化（V2：使用 DB 配置 JSON；否则保持旧逻辑）
            if hasattr(plugin_instance, 'initialize'):
                try:
                    if v2_info is not None:
                        # 从数据库获取配置（按 module 名称作为唯一键）
                        if self.db_service:
                            cfg = self.db_service.get_plugin_config_json(plugin_name) or {}
                        else:
                            cfg = {}
                        ok = plugin_instance.initialize(cfg)
                        if not ok:
                            logger.warning(f"插件初始化返回失败: {plugin_name}")
                    else:
                        # 旧逻辑：不再传入 PluginContext，直接尝试无参
                        try:
                            plugin_instance.initialize()
                        except TypeError:
                            # 某些旧插件需要 context，这里不再支持，标记加载但未初始化
                            logger.warning(f"旧式插件需要上下文，已跳过初始化: {plugin_name}")
                except Exception as e:
                    logger.error(f"插件初始化失败 {plugin_name}: {e}")
                    return False

            # 检查是否有plugin_info模块
            try:
                plugin_info = None
                if hasattr(module, 'plugin_info'):
                    plugin_info = module.plugin_info

                    # 检查是否有register_indicators函数，如果有则调用它注册指标
                    if hasattr(plugin_info, 'register_indicators'):
                        try:
                            from core.indicator_service import IndicatorService
                            indicator_service = IndicatorService()

                            # 调用register_indicators获取指标列表
                            indicators_list = plugin_info.register_indicators()

                            # 注册指标
                            if indicators_list:
                                if hasattr(indicator_service, 'register_indicators'):
                                    indicator_ids = indicator_service.register_indicators(
                                        indicators_list, plugin_name)
                                    logger.info(
                                        f"插件 {plugin_name} 成功注册了 {len(indicator_ids)} 个指标")
                                else:
                                    logger.warning(
                                        f"IndicatorService缺少register_indicators方法，无法注册插件 {plugin_name} 的指标")
                        except ImportError:
                            logger.warning(
                                f"无法导入IndicatorService，跳过插件 {plugin_name} 的指标注册")
                        except Exception as e:
                            logger.error(f"注册插件 {plugin_name} 的指标时发生错误: {e}")
                            logger.error(traceback.format_exc())
            except ImportError:
                logger.info(f"插件 {plugin_name} 没有plugin_info模块")
            except Exception as e:
                logger.warning(f"加载插件 {plugin_name} 的plugin_info模块时发生错误: {e}")

            # 创建并添加到enhanced_plugins（如果尚未存在）
            try:
                # 从插件实例获取信息
                plugin_type = None
                category = None

                # 尝试从插件实例获取类型信息
                if hasattr(plugin_instance, 'plugin_type'):
                    try:
                        if isinstance(plugin_instance.plugin_type, str):
                            plugin_type = PluginType(plugin_instance.plugin_type)
                        else:
                            plugin_type = plugin_instance.plugin_type
                    except (ValueError, AttributeError):
                        pass

                # 尝试从元数据获取类型信息
                if not plugin_type and metadata and 'plugin_type' in metadata:
                    try:
                        plugin_type = PluginType(metadata['plugin_type'])
                    except ValueError:
                        pass

                # 创建PluginInfo对象
                # 优先使用V2插件信息或metadata中的中文名称和描述
                plugin_display_name = plugin_name  # 默认使用插件模块名
                plugin_description = '无描述'
                plugin_author = '未知作者'
                plugin_version = '1.0.0'

                if v2_info is not None:
                    # 使用V2插件信息（包含中文名称）
                    plugin_display_name = v2_info.name
                    plugin_description = getattr(v2_info, 'description', '无描述')
                    plugin_author = getattr(v2_info, 'author', '未知作者')
                    plugin_version = getattr(v2_info, 'version', '1.0.0')
                elif metadata and 'display_name' in metadata:
                    # 使用metadata中的显示名称
                    plugin_display_name = metadata['display_name']
                    plugin_description = metadata.get('description', '无描述')
                    plugin_author = metadata.get('author', '未知作者')
                    plugin_version = metadata.get('version', '1.0.0')
                elif metadata and 'name' in metadata:
                    # 使用metadata中的名称
                    plugin_display_name = metadata['name']
                    plugin_description = metadata.get('description', '无描述')
                    plugin_author = metadata.get('author', '未知作者')
                    plugin_version = metadata.get('version', '1.0.0')
                else:
                    # 后备方案：从插件实例获取
                    plugin_display_name = getattr(plugin_instance, 'name', plugin_name)
                    plugin_description = getattr(plugin_instance, 'description', '无描述')
                    plugin_author = getattr(plugin_instance, 'author', '未知作者')
                    plugin_version = getattr(plugin_instance, 'version', '1.0.0')

                plugin_info = PluginInfo(
                    name=plugin_display_name,  # 使用中文显示名称
                    version=plugin_version,
                    description=plugin_description,
                    author=plugin_author,
                    path=str(plugin_path),
                    status=PluginStatus.LOADED,  # 插件加载完成后状态为LOADED
                    config=metadata or {},
                    dependencies=getattr(plugin_instance, 'dependencies', []),
                    plugin_type=plugin_type,
                    category=category
                )

                self.enhanced_plugins[plugin_name] = plugin_info

                # 检查是否为数据源插件并添加到data_source_plugins
                if self._is_data_source_plugin(plugin_instance, plugin_type):
                    with self._data_source_lock:
                        try:
                            self.data_source_plugins[plugin_name] = plugin_info
                            logger.info(f" 已识别数据源插件: {plugin_name} (类型: {plugin_type})")
                        except Exception as e:
                            logger.warning(f" 标记数据源插件失败 {plugin_name}: {e}")

                        # 如果有数据管理器，尝试注册插件
                        if self.data_manager and hasattr(self.data_manager, 'register_plugin_data_source'):
                            try:
                                success = self.data_manager.register_plugin_data_source(plugin_name, plugin_instance)
                                if success:
                                    logger.info(f" 数据源插件注册到数据管理器成功: {plugin_name}")
                                else:
                                    logger.warning(f" 数据源插件注册到数据管理器失败: {plugin_name}")
                            except Exception as e:
                                logger.error(f" 数据源插件注册到数据管理器异常 {plugin_name}: {e}")

                        # 同时注册到统一数据管理器的路由器
                        try:
                            from .services.unified_data_manager import get_unified_data_manager
                            from .data_source_extensions import DataSourcePluginAdapter, IDataSourcePlugin

                            unified_manager = get_unified_data_manager()
                            if unified_manager and hasattr(unified_manager, 'register_data_source_plugin'):
                                # 严格限制：仅对实现 IDataSourcePlugin 的实例注册到路由器
                                if not isinstance(plugin_instance, IDataSourcePlugin):
                                    logger.debug(f"跳过路由器注册（非IDataSourcePlugin）: {plugin_name}")
                                    pass
                                else:
                                    # 创建适配器
                                    adapter = DataSourcePluginAdapter(plugin_instance, plugin_name)

                                    # 优化：启动异步连接，避免阻塞主线程
                                    # 连接在后台线程中进行
                                    if hasattr(plugin_instance, 'connect_async'):
                                        plugin_instance.connect_async()
                                        logger.info(f" 数据源插件适配器已创建，异步连接已启动: {plugin_name}")
                                    else:
                                        logger.info(f" 数据源插件适配器已创建（延迟连接）: {plugin_name}")

                                    # 使用正确的注册方法：register_data_source_plugin
                                    success = unified_manager.register_data_source_plugin(
                                        plugin_name,
                                        adapter,
                                        priority=0,
                                        weight=1.0
                                    )

                                    if success:
                                        logger.info(f" 数据源插件注册到统一数据管理器成功: {plugin_name}")
                                    else:
                                        logger.warning(f" 数据源插件注册到统一数据管理器失败: {plugin_name}")

                                # 可观测性：如果实现了接口但未注册成功，明确报警
                                if isinstance(plugin_instance, IDataSourcePlugin) and not success:
                                    logger.error(f" 已实现IDataSourcePlugin但未注册成功: id={plugin_name}, class={type(plugin_instance).__name__}")
                                else:
                                    logger.debug(f"统一数据管理器不可用或缺少register_data_source_plugin方法，跳过路由器注册: {plugin_name}")

                        except Exception as e:
                            logger.error(f" 注册到统一数据管理器路由器异常 {plugin_name}: {e}")

                # 同步到数据库
                self._sync_plugin_state_with_db(plugin_name, plugin_info)

                # 按类型分类
                if plugin_type:
                    if plugin_type not in self.plugins_by_type:
                        self.plugins_by_type[plugin_type] = []
                    if plugin_name not in self.plugins_by_type[plugin_type]:
                        self.plugins_by_type[plugin_type].append(plugin_name)

                logger.debug(f"已创建插件信息对象: {plugin_name}, 类型: {plugin_type}")

            except Exception as e:
                logger.warning(f"创建插件信息对象失败 {plugin_name}: {e}")

            logger.info(f"插件加载成功: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"加载插件失败 {plugin_name}: {e}")
            return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载指定插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否卸载成功
        """
        try:
            if plugin_name not in self.loaded_plugins:
                logger.warning(f"插件未加载: {plugin_name}")
                return True

            # 清理插件实例
            if plugin_name in self.plugin_instances:
                plugin_instance = self.plugin_instances[plugin_name]
                if hasattr(plugin_instance, 'cleanup'):
                    plugin_instance.cleanup()

            # 移除插件信息
            self.loaded_plugins.pop(plugin_name, None)
            self.plugin_instances.pop(plugin_name, None)
            self.plugin_metadata.pop(plugin_name, None)

            logger.info(f"插件卸载成功: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"卸载插件失败 {plugin_name}: {e}")
            return False

    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        """
        获取插件实例

        Args:
            plugin_name: 插件名称

        Returns:
            插件实例或None
        """
        return self.plugin_instances.get(plugin_name)

    def get_all_plugins(self) -> Dict[str, Any]:
        """获取所有插件实例"""
        return self.plugin_instances.copy()

    def get_all_enhanced_plugins(self) -> Dict[str, PluginInfo]:
        """获取所有增强插件信息"""
        return self.enhanced_plugins.copy()

    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """获取指定插件的信息"""
        return self.enhanced_plugins.get(plugin_name)

    def get_plugin_metadata(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        获取插件元数据

        Args:
            plugin_name: 插件名称

        Returns:
            插件元数据或None
        """
        return self.plugin_metadata.get(plugin_name)

    def get_all_plugin_metadata(self) -> Dict[str, Dict[str, Any]]:
        """获取所有插件元数据"""
        return self.plugin_metadata.copy()

    def is_plugin_loaded(self, plugin_name: str) -> bool:
        """
        检查插件是否已加载

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否已加载
        """
        return plugin_name in self.loaded_plugins

    def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否重新加载成功
        """
        try:
            # 先卸载插件
            if not self.unload_plugin(plugin_name):
                return False

            # 重新加载插件
            plugin_path = self.plugin_dir / f"{plugin_name}.py"
            return self.load_plugin(plugin_name, plugin_path)

        except Exception as e:
            logger.error(f"重新加载插件失败 {plugin_name}: {e}")
            return False

    def _find_plugin_class(self, module) -> Optional[Type]:
        """
        在模块中查找插件类

        Args:
            module: 插件模块

        Returns:
            插件类或None
        """
        try:
            # 需要排除的类型名称
            excluded_class_names = [
                "IPlugin", "PluginType", "PluginCategory", "PluginMetadata", "PluginContext",
                "PluginConfig", "EastMoneyConfig", "SinaConfig", "StandardDataSourcePlugin"]

            # 首先检查是否有使用装饰器标记的插件类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    hasattr(attr, '_plugin_metadata') and
                        attr.__name__ not in excluded_class_names):
                    logger.info(f"找到带有_plugin_metadata属性的插件类: {attr.__name__}")
                    return attr

            # 检查是否有策略类（使用@register_strategy装饰器）
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    hasattr(attr, '_strategy_name') and
                        attr.__name__ not in excluded_class_names):
                    logger.info(f"找到策略类: {attr.__name__} (策略名: {attr._strategy_name})")
                    return attr

            # 查找继承自BaseStrategy的类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    hasattr(attr, '__bases__') and
                        attr.__name__ not in excluded_class_names):
                    # 检查基类名称
                    for base in attr.__bases__:
                        if base.__name__ == 'BaseStrategy':
                            logger.info(f"找到继承自BaseStrategy的类: {attr.__name__}")
                            return attr

            # 查找继承自IPlugin的类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    hasattr(attr, '__bases__') and
                        attr.__name__ not in excluded_class_names):
                    # 检查基类名称
                    for base in attr.__bases__:
                        if base.__name__ == 'IPlugin' or 'Plugin' in base.__name__:
                            # 检查是否是抽象类
                            if hasattr(attr, '__abstractmethods__') and attr.__abstractmethods__:
                                # logger.info(
                                #     f"跳过抽象类: {attr.__name__}, 抽象方法: {attr.__abstractmethods__}")
                                continue

                            logger.info(
                                f"找到继承自插件基类的类: {attr.__name__}, 基类: {[b.__name__ for b in attr.__bases__]}")
                            return attr

            # 查找名称符合插件特征的类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    'Plugin' in attr.__name__ and
                        attr.__name__ not in excluded_class_names):
                    # 检查是否是枚举类型
                    if hasattr(attr, '__members__'):
                        # logger.info(f"跳过枚举类型: {attr.__name__}")
                        continue

                    logger.info(f"找到名称符合插件特征的类: {attr.__name__}")
                    return attr

            return None

        except Exception as e:
            logger.error(f"查找插件类时出错: {e}")
            return None

    def _get_plugin_metadata(self, plugin_class: Type) -> Dict[str, Any]:
        """
        获取插件元数据

        Args:
            plugin_class: 插件类

        Returns:
            插件元数据
        """
        try:
            # 首先尝试从_plugin_metadata属性获取完整元数据
            if hasattr(plugin_class, '_plugin_metadata'):
                metadata_obj = plugin_class._plugin_metadata

                # 将PluginMetadata对象转换为字典
                metadata = {
                    'name': metadata_obj.name,
                    'version': metadata_obj.version,
                    'description': metadata_obj.description,
                    'author': metadata_obj.author,
                    'email': getattr(metadata_obj, 'email', ''),
                    'website': getattr(metadata_obj, 'website', ''),
                    'license': getattr(metadata_obj, 'license', ''),
                    'plugin_type': metadata_obj.plugin_type.value if hasattr(metadata_obj.plugin_type, 'value') else str(metadata_obj.plugin_type),
                    'category': metadata_obj.category.value if hasattr(metadata_obj.category, 'value') else str(metadata_obj.category),
                    'dependencies': metadata_obj.dependencies,
                    'min_framework_version': getattr(metadata_obj, 'min_framework_version', '1.0.0'),
                    'max_framework_version': getattr(metadata_obj, 'max_framework_version', '2.0.0'),
                    'tags': getattr(metadata_obj, 'tags', []),
                    'icon_path': getattr(metadata_obj, 'icon_path', None),
                    'documentation_url': getattr(metadata_obj, 'documentation_url', None),
                    'support_url': getattr(metadata_obj, 'support_url', None),
                    'changelog_url': getattr(metadata_obj, 'changelog_url', None),
                    'class_name': plugin_class.__name__
                }

                return metadata

            # 如果没有_plugin_metadata属性，则使用基本信息（向后兼容）
            metadata = {
                'name': getattr(plugin_class, 'name', plugin_class.__name__),
                'version': getattr(plugin_class, 'version', '1.0.0'),
                'description': getattr(plugin_class, 'description', ''),
                'author': getattr(plugin_class, 'author', ''),
                'email': '',
                'website': '',
                'license': '',
                'plugin_type': 'unknown',  # 默认为unknown
                'category': 'unknown',
                'dependencies': getattr(plugin_class, 'dependencies', []),
                'min_framework_version': '1.0.0',
                'max_framework_version': '2.0.0',
                'tags': [],
                'icon_path': None,
                'documentation_url': None,
                'support_url': None,
                'changelog_url': None,
                'class_name': plugin_class.__name__
            }

            return metadata

        except Exception as e:
            logger.error(f"获取插件元数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'name': plugin_class.__name__,
                'version': '1.0.0',
                'description': '',
                'author': '',
                'plugin_type': 'unknown',
                'category': 'unknown',
                'dependencies': [],
                'class_name': plugin_class.__name__
            }

    def call_plugin_method(self, plugin_name: str, method_name: str, *args, **kwargs) -> Any:
        """
        调用插件方法

        Args:
            plugin_name: 插件名称
            method_name: 方法名称
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            方法返回值
        """
        try:
            plugin = self.get_plugin(plugin_name)
            if plugin is None:
                logger.error(f"插件未找到: {plugin_name}")
                return None

            if not hasattr(plugin, method_name):
                logger.error(f"插件方法未找到: {plugin_name}.{method_name}")
                return None

            method = getattr(plugin, method_name)
            return method(*args, **kwargs)

        except Exception as e:
            logger.error(f"调用插件方法失败 {plugin_name}.{method_name}: {e}")
            return None

    def broadcast_event(self, event_name: str, *args, **kwargs) -> None:
        """
        向所有插件广播事件

        Args:
            event_name: 事件名称
            *args: 位置参数
            **kwargs: 关键字参数
        """
        try:
            for plugin_name, plugin in self.plugin_instances.items():
                try:
                    if hasattr(plugin, 'on_event'):
                        plugin.on_event(event_name, *args, **kwargs)

                    # 检查是否有特定的事件处理方法
                    event_method_name = f'on_{event_name}'
                    if hasattr(plugin, event_method_name):
                        method = getattr(plugin, event_method_name)
                        method(*args, **kwargs)

                except Exception as e:
                    logger.error(f"插件事件处理失败 {plugin_name}.{event_name}: {e}")

        except Exception as e:
            logger.error(f"广播事件失败 {event_name}: {e}")

    def get_plugins_by_type(self, plugin_type: str) -> List[Any]:
        """
        根据类型获取插件

        Args:
            plugin_type: 插件类型

        Returns:
            插件实例列表
        """
        try:
            matching_plugins = []

            for plugin_name, plugin in self.plugin_instances.items():
                metadata = self.plugin_metadata.get(plugin_name, {})
                # 检查两种可能的字段名
                plugin_meta_type = metadata.get('plugin_type') or metadata.get('type')

                # 支持字符串和枚举值的比较
                if plugin_meta_type:
                    if isinstance(plugin_meta_type, str):
                        type_value = plugin_meta_type
                    else:
                        # 处理枚举类型
                        type_value = getattr(plugin_meta_type, 'value', str(plugin_meta_type))

                    # 检查是否匹配（支持enum和字符串匹配）
                    if (type_value == plugin_type or
                            type_value == getattr(plugin_type, 'value', str(plugin_type))):
                        matching_plugins.append(plugin)

            return matching_plugins

        except Exception as e:
            logger.error(f"获取插件失败 {plugin_type}: {e}")
            return []

    def cleanup(self) -> None:
        """清理资源"""
        try:
            for plugin_name, plugin_instance in self.plugin_instances.items():
                if hasattr(plugin_instance, 'cleanup'):
                    plugin_instance.cleanup()

            self.loaded_plugins.clear()
            self.plugin_instances.clear()
            self.plugin_metadata.clear()

            logger.info("插件管理器清理完成")

        except Exception as e:
            logger.error(f"插件管理器清理失败: {e}")

    def enable_plugin(self, plugin_name: str) -> bool:
        """
        启用插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否启用成功
        """
        try:
            if plugin_name not in self.plugin_instances:
                logger.error(f"插件未加载: {plugin_name}")
                return False

            plugin_instance = self.plugin_instances[plugin_name]

            # 调用插件的启用方法
            if hasattr(plugin_instance, 'enable'):
                try:
                    plugin_instance.enable()
                except Exception as enable_error:
                    logger.error(f"插件启用方法执行失败 {plugin_name}: {enable_error}")
                    # 设置插件状态为错误
                    if plugin_name in self.enhanced_plugins:
                        self.enhanced_plugins[plugin_name].status = PluginStatus.ERROR
                        self.enhanced_plugins[plugin_name].enabled = False
                        self._update_plugin_status_in_db(plugin_name, PluginStatus.ERROR, f"启用失败: {str(enable_error)}")

                    self.plugin_error.emit(plugin_name, str(enable_error))
                    return False

            # 更新插件状态
            if plugin_name in self.enhanced_plugins:
                self.enhanced_plugins[plugin_name].status = PluginStatus.ENABLED
                self.enhanced_plugins[plugin_name].enabled = True

                # 同步到数据库
                self._update_plugin_status_in_db(plugin_name, PluginStatus.ENABLED, "用户启用")

            # 发送启用信号
            self.plugin_enabled.emit(plugin_name)

            logger.info(f"插件已启用: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"启用插件失败 {plugin_name}: {e}")
            # 设置插件状态为错误
            if plugin_name in self.enhanced_plugins:
                self.enhanced_plugins[plugin_name].status = PluginStatus.ERROR
                self.enhanced_plugins[plugin_name].enabled = False
                self._update_plugin_status_in_db(plugin_name, PluginStatus.ERROR, f"启用失败: {str(e)}")

            self.plugin_error.emit(plugin_name, str(e))
            return False

    def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否禁用成功
        """
        try:
            if plugin_name not in self.plugin_instances:
                logger.error(f"插件未加载: {plugin_name}")
                return False

            plugin_instance = self.plugin_instances[plugin_name]

            # 调用插件的禁用方法
            if hasattr(plugin_instance, 'disable'):
                plugin_instance.disable()

            # 更新插件状态
            if plugin_name in self.enhanced_plugins:
                self.enhanced_plugins[plugin_name].status = PluginStatus.DISABLED
                self.enhanced_plugins[plugin_name].enabled = False

                # 同步到数据库
                self._update_plugin_status_in_db(plugin_name, PluginStatus.DISABLED, "用户禁用")

            # 发送禁用信号
            self.plugin_disabled.emit(plugin_name)

            logger.info(f"插件已禁用: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"禁用插件失败 {plugin_name}: {e}")
            self.plugin_error.emit(plugin_name, str(e))
            return False

    def update_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        更新插件配置

        Args:
            plugin_name: 插件名称
            config: 新配置

        Returns:
            bool: 是否更新成功
        """
        try:
            if plugin_name not in self.plugin_instances:
                logger.error(f"插件未加载: {plugin_name}")
                return False

            plugin_instance = self.plugin_instances[plugin_name]

            # 更新插件实例的配置
            if hasattr(plugin_instance, 'update_config'):
                plugin_instance.update_config(config)

            # 更新元数据中的配置
            if plugin_name in self.plugin_metadata:
                self.plugin_metadata[plugin_name]['config'] = config

            # 更新增强插件信息中的配置
            if plugin_name in self.enhanced_plugins:
                self.enhanced_plugins[plugin_name].config.update(config)

            logger.info(f"插件配置已更新: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"更新插件配置失败 {plugin_name}: {e}")
            return False

    def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """
        获取插件状态

        Args:
            plugin_name: 插件名称

        Returns:
            PluginStatus: 插件状态
        """
        if plugin_name in self.enhanced_plugins:
            return self.enhanced_plugins[plugin_name].status
        elif plugin_name in self.plugin_instances:
            return PluginStatus.LOADED
        else:
            return PluginStatus.UNLOADED

    def get_plugin_performance_stats(self, plugin_name: str) -> Dict[str, Any]:
        """
        获取插件性能统计

        Args:
            plugin_name: 插件名称

        Returns:
            Dict: 性能统计数据
        """
        try:
            if plugin_name not in self.plugin_instances:
                return {}

            plugin_instance = self.plugin_instances[plugin_name]

            # 获取插件性能统计
            if hasattr(plugin_instance, 'get_performance_stats'):
                return plugin_instance.get_performance_stats()

            # 返回基本统计信息
            return {
                'status': self.get_plugin_status(plugin_name).value,
                'memory_usage': 0,  # 可以通过系统监控获取
                'cpu_usage': 0,
                'response_time': 0,
                'error_count': 0
            }

        except Exception as e:
            logger.error(f"获取插件性能统计失败 {plugin_name}: {e}")
            return {}

    def check_plugin_dependencies(self, plugin_name: str) -> bool:
        """
        检查插件依赖

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 依赖是否满足
        """
        try:
            if plugin_name not in self.plugin_metadata:
                return False

            metadata = self.plugin_metadata[plugin_name]
            dependencies = metadata.get('dependencies', [])

            for dep in dependencies:
                if not self.is_plugin_loaded(dep):
                    logger.warning(f"插件 {plugin_name} 依赖 {dep} 未满足")
                    return False

            return True

        except Exception as e:
            logger.error(f"检查插件依赖失败 {plugin_name}: {e}")
            return False

    def get_system_stats(self) -> Dict[str, Any]:
        """
        获取插件系统统计信息

        Returns:
            Dict: 系统统计信息
        """
        try:
            total_plugins = len(self.enhanced_plugins)
            enabled_plugins = sum(1 for p in self.enhanced_plugins.values()
                                  if p.status == PluginStatus.ENABLED)
            disabled_plugins = sum(1 for p in self.enhanced_plugins.values()
                                   if p.status == PluginStatus.DISABLED)
            error_plugins = sum(1 for p in self.enhanced_plugins.values()
                                if p.status == PluginStatus.ERROR)

            return {
                'total_plugins': total_plugins,
                'enabled_plugins': enabled_plugins,
                'disabled_plugins': disabled_plugins,
                'error_plugins': error_plugins,
                'loaded_plugins': len(self.plugin_instances),
                'plugin_types': {
                    plugin_type.value: len(plugins)
                    for plugin_type, plugins in self.plugins_by_type.items()
                }
            }

        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {}

    def discover_enhanced_plugins(self) -> List[PluginInfo]:
        """
        发现增强插件（支持plugin.json配置）

        Returns:
            发现的插件列表
        """
        discovered = []

        for plugin_dir in self.plugin_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith('.'):
                plugin_json = plugin_dir / "plugin.json"
                if plugin_json.exists():
                    try:
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            config = json.load(f)

                        # 解析插件类型和分类
                        plugin_type = None
                        category = None

                        if 'plugin_type' in config:
                            try:
                                plugin_type = PluginType(config['plugin_type'])
                            except ValueError:
                                logger.warning(
                                    f"未知插件类型: {config['plugin_type']}")

                        if 'category' in config:
                            try:
                                category = PluginCategory(config['category'])
                            except ValueError:
                                logger.warning(f"未知插件分类: {config['category']}")

                        plugin_info = PluginInfo(
                            name=config.get('name', plugin_dir.name),
                            version=config.get('version', '1.0.0'),
                            description=config.get('description', ''),
                            author=config.get('author', ''),
                            path=str(plugin_dir),
                            status=PluginStatus.UNLOADED,
                            config=config,
                            dependencies=config.get('dependencies', []),
                            plugin_type=plugin_type,
                            category=category
                        )

                        discovered.append(plugin_info)
                        self.enhanced_plugins[plugin_info.name] = plugin_info

                        # 按类型分类
                        if plugin_type:
                            self.plugins_by_type[plugin_type].append(
                                plugin_info.name)

                    except Exception as e:
                        logger.error(f"发现插件失败 {plugin_dir}: {e}")

        return discovered

    def get_plugins_by_type_enhanced(self, plugin_type: PluginType) -> List[PluginInfo]:
        """
        按类型获取插件

        Args:
            plugin_type: 插件类型

        Returns:
            指定类型的插件列表
        """
        plugin_names = self.plugins_by_type.get(plugin_type, [])
        return [self.enhanced_plugins[name] for name in plugin_names if name in self.enhanced_plugins]

    def call_plugin_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        调用插件钩子

        Args:
            hook_name: 钩子名称
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            钩子返回值列表
        """
        results = []

        if hook_name in self.plugin_hooks:
            for callback in self.plugin_hooks[hook_name]:
                try:
                    result = callback(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f"调用插件钩子失败 {hook_name}: {e}")

        return results

    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """
        注册钩子

        Args:
            hook_name: 钩子名称
            callback: 回调函数
        """
        if hook_name not in self.plugin_hooks:
            self.plugin_hooks[hook_name] = []

        self.plugin_hooks[hook_name].append(callback)

    def _is_data_source_plugin(self, plugin_instance, plugin_type=None) -> bool:
        """
        检查插件是否为数据源插件

        Args:
            plugin_instance: 插件实例
            plugin_type: 插件类型（可选）

        Returns:
            bool: 是否为数据源插件
        """
        try:
            # 方法1：检查plugin_type字符串
            if plugin_type:
                plugin_type_str = str(plugin_type).lower()
                if 'data_source' in plugin_type_str:
                    return True

            # 方法2：检查插件实例的plugin_type属性
            if hasattr(plugin_instance, 'plugin_type'):
                instance_type = str(plugin_instance.plugin_type).lower()
                if 'data_source' in instance_type:
                    return True

            # 方法3：检查是否实现了IDataSourcePlugin接口
            try:
                from .data_source_extensions import IDataSourcePlugin
                if isinstance(plugin_instance, IDataSourcePlugin):
                    return True
            except ImportError:
                pass

            # 方法4：检查插件类名
            class_name = plugin_instance.__class__.__name__.lower()
            if any(keyword in class_name for keyword in ['datasource', 'data_source']):
                return True

            # 方法5：检查是否有数据源相关方法
            data_source_methods = ['get_stock_data', 'get_kline_data', 'fetch_data', 'get_data', 'get_plugin_info']
            if any(hasattr(plugin_instance, method) for method in data_source_methods):
                return True

            return False

        except Exception as e:
            logger.warning(f"检查数据源插件失败: {e}")
            return False

    def sync_data_sources_to_unified_manager(self) -> bool:
        """
        将已加载的数据源插件同步到统一数据管理器的路由器

        Returns:
            bool: 同步是否成功
        """
        try:
            from .services.unified_data_manager import get_unified_data_manager
            from .data_source_extensions import DataSourcePluginAdapter

            unified_manager = get_unified_data_manager()
            if not unified_manager or not hasattr(unified_manager, 'register_data_source_plugin'):
                logger.warning("统一数据管理器不可用，无法同步数据源")
                return False

            sync_count = 0
            error_count = 0

            with self._data_source_lock:
                for plugin_id, plugin_info in self.data_source_plugins.items():
                    try:
                        # 创建适配器
                        adapter = DataSourcePluginAdapter(plugin_info.instance, plugin_id)

                        # 注册到统一数据管理器的路由器
                        success = unified_manager.register_data_source_plugin(
                            plugin_id,
                            adapter,
                            priority=0,
                            weight=1.0
                        )

                        if success:
                            sync_count += 1
                            logger.info(f"数据源同步成功: {plugin_id}")
                        else:
                            error_count += 1
                            logger.warning(f"数据源同步失败: {plugin_id}")

                    except Exception as e:
                        error_count += 1
                        logger.error(f"同步数据源插件失败 {plugin_id}: {str(e)}")

            logger.info(f"数据源同步完成: 成功 {sync_count}, 失败 {error_count}")
            return error_count == 0

        except Exception as e:
            logger.error(f"数据源同步异常: {str(e)}")
            return False

    def sync_db_with_real_plugins(self) -> Dict[str, bool]:
        """调用数据库服务的全量同步（新增、删除、更新），用于立即触发清理孤儿记录。"""
        try:
            from .services.plugin_database_service import get_plugin_database_service
            dbs = get_plugin_database_service()
            return dbs.sync_plugin_statuses(self)
        except Exception as e:
            logger.error(f"同步插件状态到数据库失败: {e}")
            return {}

# BasePlugin 类已移除 - 未被使用，请使用 IPlugin 接口
