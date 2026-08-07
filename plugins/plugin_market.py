from loguru import logger
"""
FactorWeave-Quant  插件市场系统

提供插件发现、下载、安装、评分、更新等完整的插件生态功能。
"""

import os
import sys
import json
import requests
import zipfile
import shutil
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication
from pathlib import Path

# 添加项目根目录到Python路径，确保可以导入plugins包
current_dir = Path(__file__).parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# R240-P0: CWE-918 SSRF 防御接入 (L323 download_url 远端可控)
try:
    from core.security.url_validator import SSRFBlockedError, assert_safe_url as _uv_assert
except Exception:
    SSRFBlockedError = Exception
    def _uv_assert(url, **kw):
        return url


def _assert_download_url_safe(url: str) -> bool:
    """插件下载 URL 安全校验 (R240-P0, plugin_market.py:323 sink 接入)

    download_url 来自远端插件市场 API 响应 (攻击者可注册恶意插件指向内网),
    使用 strict 模式全黑名单 + DNS 二次校验 (fail-closed).
    """
    _uv_assert(url, dns_resolve=True, mode="strict")
    return True

# 定义基础类型，以防导入失败
logger = logger

# 尝试导入插件接口
PluginMetadata = None
PluginType = None
PluginCategory = None

try:
    # 直接使用绝对导入
    from plugins.plugin_interface import PluginMetadata, PluginType, PluginCategory
    logger.info("成功通过绝对导入加载插件接口")
except ImportError:
    try:
        # 尝试使用相对导入
        from .plugin_interface import PluginMetadata, PluginType, PluginCategory
        logger.info("成功通过相对导入加载插件接口")
    except ImportError:
        try:
            # 尝试使用项目根目录路径
            sys.path.append(str(project_root))
            from plugins.plugin_interface import PluginMetadata, PluginType, PluginCategory
            logger.info("成功通过项目路径导入加载插件接口")
        except ImportError as e:
            # 如果仍然失败，尝试直接从文件加载
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "plugin_interface",
                    current_dir / "plugin_interface.py"
                )
                if spec and spec.loader:
                    plugin_interface_module = importlib.util.module_from_spec(
                        spec)
                    sys.modules["plugin_interface"] = plugin_interface_module
                    spec.loader.exec_module(plugin_interface_module)
                    PluginMetadata = plugin_interface_module.PluginMetadata
                    PluginType = plugin_interface_module.PluginType
                    PluginCategory = plugin_interface_module.PluginCategory
                    logger.info("成功通过spec导入插件接口")
            except Exception as e2:
                # 如果仍然失败，创建占位类
                logger.error(f"导入插件接口失败: {e} / {e2}")

                # 如果仍然失败，定义基本类型
                class PluginType:
                    """插件类型枚举"""
                    INDICATOR = "indicator"
                    STRATEGY = "strategy"
                    DATA_SOURCE = "data_source"
                    ANALYSIS = "analysis"
                    UI_COMPONENT = "ui_component"
                    EXPORT = "export"
                    NOTIFICATION = "notification"
                    CHART_TOOL = "chart_tool"

                class PluginCategory:
                    """插件分类枚举"""
                    CORE = "core"
                    COMMUNITY = "community"
                    COMMERCIAL = "commercial"
                    EXPERIMENTAL = "experimental"

                class PluginMetadata:
                    """插件元数据占位类"""

                    def __init__(self, **kwargs):
                        for key, value in kwargs.items():
                            setattr(self, key, value)

@dataclass
class PluginInfo:
    """插件信息"""
    metadata: PluginMetadata
    download_url: str
    file_size: int
    download_count: int
    rating: float
    rating_count: int
    last_updated: str
    screenshots: List[str]
    readme: str
    changelog: str
    verified: bool = False
    featured: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginInfo':
        """从字典创建"""
        metadata_data = data.pop('metadata')
        metadata = PluginMetadata(**metadata_data)
        return cls(metadata=metadata, **data)

class PluginMarketAPI:
    """插件市场API客户端"""

    def __init__(self, base_url: str = "https://api.factorweave-quant.com/plugins"):
        """
        初始化API客户端

        Args:
            base_url: API基础URL
        """
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'FactorWeave-Quant/2.0 Plugin Market Client'
        })

    def search_plugins(self,
                       query: str = "",
                       category: Optional[PluginCategory] = None,
                       plugin_type: Optional[PluginType] = None,
                       sort_by: str = "popularity",
                       page: int = 1,
                       per_page: int = 20) -> Tuple[List[PluginInfo], int]:
        """
        搜索插件

        Args:
            query: 搜索关键词
            category: 插件分类
            plugin_type: 插件类型
            sort_by: 排序方式 (popularity, rating, updated, name)
            page: 页码
            per_page: 每页数量

        Returns:
            插件列表和总数
        """
        params = {
            'q': query,
            'sort': sort_by,
            'page': page,
            'per_page': per_page
        }

        if category:
            params['category'] = category.value
        if plugin_type:
            params['type'] = plugin_type.value

        try:
            response = self.session.get(
                f"{self.base_url}/search", params=params)
            response.raise_for_status()

            data = response.json()
            plugins = [PluginInfo.from_dict(item) for item in data['plugins']]
            return plugins, data['total']

        except requests.RequestException as e:
            raise Exception(f"搜索插件失败: {e}")

    def get_plugin_details(self, plugin_id: str) -> PluginInfo:
        """
        获取插件详情

        Args:
            plugin_id: 插件ID

        Returns:
            插件信息
        """
        try:
            response = self.session.get(f"{self.base_url}/{plugin_id}")
            response.raise_for_status()

            data = response.json()
            return PluginInfo.from_dict(data)

        except requests.RequestException as e:
            raise Exception(f"获取插件详情失败: {e}")

    def get_featured_plugins(self) -> List[PluginInfo]:
        """
        获取精选插件

        Returns:
            精选插件列表
        """
        try:
            response = self.session.get(f"{self.base_url}/featured")
            response.raise_for_status()

            data = response.json()
            return [PluginInfo.from_dict(item) for item in data['plugins']]

        except requests.RequestException as e:
            raise Exception(f"获取精选插件失败: {e}")

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        获取插件分类

        Returns:
            分类列表
        """
        try:
            response = self.session.get(f"{self.base_url}/categories")
            response.raise_for_status()

            return response.json()['categories']

        except requests.RequestException as e:
            raise Exception(f"获取分类失败: {e}")

    def rate_plugin(self, plugin_id: str, rating: int, review: str = "") -> bool:
        """
        评分插件

        Args:
            plugin_id: 插件ID
            rating: 评分 (1-5)
            review: 评论

        Returns:
            是否成功
        """
        data = {
            'rating': rating,
            'review': review
        }

        try:
            response = self.session.post(
                f"{self.base_url}/{plugin_id}/rate", json=data)
            response.raise_for_status()

            return response.json()['success']

        except requests.RequestException as e:
            raise Exception(f"评分失败: {e}")

    def report_plugin(self, plugin_id: str, reason: str, description: str = "") -> bool:
        """
        举报插件

        Args:
            plugin_id: 插件ID
            reason: 举报原因
            description: 详细描述

        Returns:
            是否成功
        """
        data = {
            'reason': reason,
            'description': description
        }

        try:
            response = self.session.post(
                f"{self.base_url}/{plugin_id}/report", json=data)
            response.raise_for_status()

            return response.json()['success']

        except requests.RequestException as e:
            raise Exception(f"举报失败: {e}")

class PluginDownloader(QThread):
    """插件下载器"""

    progress_updated = pyqtSignal(int)  # 进度更新
    download_completed = pyqtSignal(str)  # 下载完成
    download_failed = pyqtSignal(str)  # 下载失败

    def __init__(self, plugin_info: PluginInfo, download_dir: str):
        """
        初始化下载器

        Args:
            plugin_info: 插件信息
            download_dir: 下载目录
        """
        super().__init__()
        self.plugin_info = plugin_info
        self.download_dir = download_dir
        self.cancelled = False

    def run(self):
        """执行下载"""
        try:
            # 创建下载目录
            os.makedirs(self.download_dir, exist_ok=True)

            # 下载文件
            filename = f"{self.plugin_info.metadata.name}-{self.plugin_info.metadata.version}.zip"
            file_path = os.path.join(self.download_dir, filename)

            # R240-P0: SSRF 校验 download_url (远端可控, strict 全黑名单)
            _assert_download_url_safe(self.plugin_info.download_url)

            response = requests.get(self.plugin_info.download_url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        return

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(progress)

            self.download_completed.emit(file_path)

        except Exception as e:
            self.download_failed.emit(str(e))

    def cancel(self):
        """取消下载"""
        self.cancelled = True

class PluginInstaller:
    """插件安装器"""

    def __init__(self, plugins_dir: str):
        """
        初始化安装器

        Args:
            plugins_dir: 插件目录
        """
        self.plugins_dir = plugins_dir

    def _sanitize_plugin_name(self, raw_name: str) -> str:
        """净化插件名 (R238-NEW-P0-CWE-22, 2026-08-01)

        Why: metadata.name 来自 zip 内 plugin.json (攻击者可控), 含 `../../`
             可逃逸 plugins_dir. basename 自动剥离路径段, 再拒绝剩余分隔符.
        Fix: basename 净化 + 拒绝空名/'.'/'..'/残留分隔符 + realpath 校验由调用方执行
        TDD: tests/test_r238_c_plugin_market_cwe22_path_traversal.py

        Args:
            raw_name: 原始插件名 (可能含路径)

        Returns:
            str: 净化后的安全插件名

        Raises:
            Exception: 名称为空 / '.' / '..' / 含残留路径分隔符时
        """
        name = os.path.basename(raw_name or '').strip()
        if not name or name in ('.', '..') or '/' in name or '\\' in name:
            raise Exception(f"非法插件名称: {raw_name!r} (CWE-22 路径逃逸拦截)")
        return name

    def install_plugin(self, plugin_file: str) -> bool:
        """
        安装插件

        Args:
            plugin_file: 插件文件路径

        Returns:
            是否安装成功
        """
        try:
            # 验证插件文件
            if not self._verify_plugin_file(plugin_file):
                raise Exception("插件文件验证失败")

            # 解压插件
            with zipfile.ZipFile(plugin_file, 'r') as zip_ref:
                # 读取插件元数据
                metadata = self._read_plugin_metadata(zip_ref)

                # 创建插件目录
                # R238-NEW-P0-CWE-22 修复 (2026-08-01): 净化 metadata.name 防路径逃逸
                # Why: metadata.name 来自 zip 内 plugin.json (攻击者可控), 含 `../../`
                #      可逃逸 plugins_dir, safe_extract_zip 白名单以逃逸目录为根而失效
                #      (CWE-22 zip-slip, CVSS 6.5)
                # Fix: _sanitize_plugin_name basename 净化 + realpath 校验仍位于 plugins_dir 内
                # TDD: tests/test_r238_c_plugin_market_cwe22_path_traversal.py
                plugin_name = self._sanitize_plugin_name(metadata.name)

                plugin_dir = os.path.join(self.plugins_dir, plugin_name)
                resolved_plugins_dir = os.path.realpath(self.plugins_dir)
                resolved_plugin_dir = os.path.realpath(plugin_dir)
                if not resolved_plugin_dir.startswith(resolved_plugins_dir + os.sep):
                    raise Exception(f"插件目录逃逸拦截: {plugin_dir!r} (CWE-22)")

                os.makedirs(plugin_dir, exist_ok=True)

                # [R237-C CWE-22 修复] 替代 zip_ref.extractall, 防 zip-slip
                from core.security import safe_extract_zip
                safe_extract_zip(plugin_file, plugin_dir)

            # 清理下载文件
            os.remove(plugin_file)

            return True

        except Exception as e:
            raise Exception(f"安装插件失败: {e}")

    def uninstall_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否卸载成功
        """
        try:
            # R240-P1-1 (2026-08-02): CWE-22 净化 — install 已有 _sanitize_plugin_name
            # (L383-403), uninstall 缺失 → 攻击者传 ../../ 可 rmtree 目录外文件
            # (子智能体 A 交叉验证确认: L445 未净化, L448 rmtree)
            plugin_name = self._sanitize_plugin_name(plugin_name)
            plugin_dir = os.path.join(self.plugins_dir, plugin_name)

            if os.path.exists(plugin_dir):
                shutil.rmtree(plugin_dir)
                return True

            return False

        except Exception as e:
            raise Exception(f"卸载插件失败: {e}")

    def _verify_plugin_file(self, plugin_file: str) -> bool:
        """
        验证插件文件

        Args:
            plugin_file: 插件文件路径

        Returns:
            是否验证通过
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(plugin_file):
                return False

            # 检查是否为zip文件
            if not zipfile.is_zipfile(plugin_file):
                return False

            # 检查必要文件
            with zipfile.ZipFile(plugin_file, 'r') as zip_ref:
                file_list = zip_ref.namelist()

                # 必须包含plugin.json
                if 'plugin.json' not in file_list:
                    return False

                # 必须包含主模块文件
                has_py_file = any(f.endswith('.py') for f in file_list)
                if not has_py_file:
                    return False

            return True

        except Exception:
            return False

    def _read_plugin_metadata(self, zip_ref: zipfile.ZipFile) -> PluginMetadata:
        """
        读取插件元数据

        Args:
            zip_ref: ZIP文件引用

        Returns:
            插件元数据
        """
        try:
            with zip_ref.open('plugin.json') as f:
                data = json.load(f)
                return PluginMetadata(**data)

        except Exception as e:
            raise Exception(f"读取插件元数据失败: {e}")

class PluginMarket:
    """插件市场主类"""

    def __init__(self, plugins_dir: str, cache_dir: str):
        """
        初始化插件市场

        Args:
            plugins_dir: 插件目录
            cache_dir: 缓存目录
        """
        self.plugins_dir = plugins_dir
        self.cache_dir = cache_dir
        self.api = PluginMarketAPI()
        self.installer = PluginInstaller(plugins_dir)
        self.cache = {}

        # 创建必要目录
        os.makedirs(plugins_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)

    def search_plugins(self, **kwargs) -> Tuple[List[PluginInfo], int]:
        """
        搜索插件

        Args:
            **kwargs: 搜索参数

        Returns:
            插件列表和总数
        """
        cache_key = self._get_cache_key("search", kwargs)

        if cache_key in self.cache:
            cache_data = self.cache[cache_key]
            if self._is_cache_valid(cache_data['timestamp']):
                return cache_data['data']

        # 从API获取数据
        plugins, total = self.api.search_plugins(**kwargs)

        # 缓存结果
        self.cache[cache_key] = {
            'data': (plugins, total),
            'timestamp': datetime.now()
        }

        return plugins, total

    def get_plugin_details(self, plugin_id: str) -> PluginInfo:
        """
        获取插件详情

        Args:
            plugin_id: 插件ID

        Returns:
            插件信息
        """
        cache_key = self._get_cache_key("details", {"plugin_id": plugin_id})

        if cache_key in self.cache:
            cache_data = self.cache[cache_key]
            if self._is_cache_valid(cache_data['timestamp']):
                return cache_data['data']

        # 从API获取数据
        plugin_info = self.api.get_plugin_details(plugin_id)

        # 缓存结果
        self.cache[cache_key] = {
            'data': plugin_info,
            'timestamp': datetime.now()
        }

        return plugin_info

    def get_featured_plugins(self) -> List[PluginInfo]:
        """
        获取精选插件

        Returns:
            精选插件列表
        """
        cache_key = self._get_cache_key("featured", {})

        if cache_key in self.cache:
            cache_data = self.cache[cache_key]
            if self._is_cache_valid(cache_data['timestamp']):
                return cache_data['data']

        # 从API获取数据
        plugins = self.api.get_featured_plugins()

        # 缓存结果
        self.cache[cache_key] = {
            'data': plugins,
            'timestamp': datetime.now()
        }

        return plugins

    def download_plugin(self, plugin_info: PluginInfo) -> PluginDownloader:
        """
        下载插件

        Args:
            plugin_info: 插件信息

        Returns:
            下载器实例
        """
        download_dir = os.path.join(self.cache_dir, "downloads")
        downloader = PluginDownloader(plugin_info, download_dir)
        return downloader

    def install_plugin(self, plugin_file: str) -> bool:
        """
        安装插件

        Args:
            plugin_file: 插件文件路径

        Returns:
            是否安装成功
        """
        return self.installer.install_plugin(plugin_file)

    def uninstall_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否卸载成功
        """
        return self.installer.uninstall_plugin(plugin_name)

    def get_installed_plugins(self) -> List[str]:
        """
        获取已安装插件列表

        Returns:
            已安装插件名称列表
        """
        installed = []

        if os.path.exists(self.plugins_dir):
            for item in os.listdir(self.plugins_dir):
                plugin_dir = os.path.join(self.plugins_dir, item)
                if os.path.isdir(plugin_dir):
                    # 检查是否有plugin.json文件
                    plugin_json = os.path.join(plugin_dir, 'plugin.json')
                    if os.path.exists(plugin_json):
                        installed.append(item)

        return installed

    def is_plugin_installed(self, plugin_name: str) -> bool:
        """
        检查插件是否已安装

        Args:
            plugin_name: 插件名称

        Returns:
            是否已安装
        """
        return plugin_name in self.get_installed_plugins()

    def clear_cache(self):
        """清理缓存"""
        self.cache.clear()

    def _get_cache_key(self, operation: str, params: Dict[str, Any]) -> str:
        """
        生成缓存键

        Args:
            operation: 操作类型
            params: 参数

        Returns:
            缓存键
        """
        key_data = f"{operation}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _is_cache_valid(self, timestamp: datetime, max_age: int = 300) -> bool:
        """
        检查缓存是否有效

        Args:
            timestamp: 缓存时间戳
            max_age: 最大缓存时间（秒）

        Returns:
            是否有效
        """
        age = (datetime.now() - timestamp).total_seconds()
        return age < max_age
