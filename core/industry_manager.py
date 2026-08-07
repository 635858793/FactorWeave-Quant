from loguru import logger
"""
行业管理器模块，负责管理股票行业分类数据
"""
import os
import json
import time
import threading  # HVD-241-P0-B: stop_event + 幂等守卫 + 线程句柄 (R241 线程生命周期治理)
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from threading import Lock
import traceback

# 尝试导入PyQt5，如果失败则使用普通类
try:
    from PyQt5.QtCore import QObject, pyqtSignal
    from PyQt5.QtWidgets import QApplication

    # 检查是否有QApplication实例
    def has_qapp():
        try:
            app = QApplication.instance()
            return app is not None
        except Exception:
            return False

    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False

    # 创建模拟的信号类
    class pyqtSignal:
        def __init__(self, *args):
            self._callbacks = []

        def emit(self, *args, **kwargs):
            for callback in self._callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.info(f"Signal callback error: {e}")

        def connect(self, callback):
            if callback not in self._callbacks:
                self._callbacks.append(callback)

        def disconnect(self, callback=None):
            if callback is None:
                self._callbacks.clear()
            elif callback in self._callbacks:
                self._callbacks.remove(callback)

    # 创建模拟的QObject基类
    class QObject:
        def __init__(self, parent=None):
            pass

# 导入日志管理器
try:
    # 纯Loguru架构，移除旧的日志导入
    pass
except ImportError:
    # 如果导入失败，创建简化版
    class LogManager:
        def __init__(self, config=None):
            pass

        def info(self, msg): logger.info(f"[INFO] {msg}")
        def error(self, msg): logger.info(f"[ERROR] {msg}")
        def warning(self, msg): logger.info(f" {msg}")
        def debug(self, msg): logger.info(f"[DEBUG] {msg}")


class IndustryManager(QObject):
    """行业管理器类"""
    # 定义信号
    industry_updated = pyqtSignal()  # 行业数据更新信号
    update_error = pyqtSignal(str)   # 更新错误信号

    def __init__(self, config_dir: str = "", cache_file: str = "industry_cache.json"):
        """初始化行业管理器

        Args:
            config_dir: 配置目录
            cache_file: 缓存文件名
        """
        super().__init__()
        initialization_start_time = time.time()

        try:
            # 纯Loguru架构，移除log_manager依赖
            logger.info(
                f"IndustryManager初始化开始 - 使用内部日志管理器, PyQt5可用: {PYQT5_AVAILABLE}")

            # 设置配置目录
            if config_dir:
                self.config_dir = config_dir
            else:
                self.config_dir = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "config")

            logger.info(f"配置目录设置为: {self.config_dir}")

            # 设置缓存文件路径
            self.cache_file = os.path.join(self.config_dir, cache_file)
            logger.info(f"缓存文件路径: {self.cache_file}")

            # 初始化属性
            self.cache_lock = Lock()
            self.industry_data = {}
            self.last_update_time = None
            self.update_interval = timedelta(days=1)  # 默认1天更新一次

            # HVD-241-P0-B: 后台线程生命周期治理 (R241-A 子智能体发现)
            # Why: _schedule_background_update 创建 daemon 线程但句柄未保存、无停止机制,
            #      且 load_cache 多路径调用 → 冷启动至少 2 线程并发 (unified_data_manager.py:288-289),
            #      重复实例化还会翻倍; industry_service.py:478 hasattr(self._industry_manager, 'dispose')
            #      恒 False → dispose 契约断裂
            self._bg_stop_event = threading.Event()
            self._bg_scheduled = False  # 幂等守卫: 防止重复调度创建多线程
            self._bg_thread = None
            self._disposed = False
            self._bg_lock = Lock()

            logger.info("基础属性初始化完成")

            # 确保配置目录存在
            if not os.path.exists(self.config_dir):
                try:
                    os.makedirs(self.config_dir, exist_ok=True)
                    logger.info(f"创建配置目录成功: {self.config_dir}")
                except Exception as e:
                    logger.error(f"创建配置目录失败: {e}")
                    # 尝试使用临时目录
                    import tempfile
                    self.config_dir = tempfile.gettempdir()
                    self.cache_file = os.path.join(self.config_dir, cache_file)
                    logger.warning(f"使用临时目录: {self.config_dir}")

            # 加载缓存数据
            try:
                logger.info("开始加载缓存数据")
                self.load_cache()
                logger.info("缓存数据加载成功")
            except Exception as e:
                logger.error(f"加载缓存数据失败: {e}")
                # 加载失败时使用默认数据
                self._load_default_industry_data()

            # 记录初始化完成
            initialization_time = int(
                (time.time() - initialization_start_time) * 1000)
            logger.info(
                f"IndustryManager初始化完成 - 耗时: {initialization_time}ms, 行业数据: {len(self.industry_data)}个")

        except Exception as e:
            # 确保即使在严重错误时也能记录日志
            if True:  # 使用Loguru日志
                logger.error(f"IndustryManager初始化异常: {e}")
                logger.error(f"异常堆栈: {traceback.format_exc()}")
            else:
                logger.info(f"IndustryManager初始化异常: {e}")
                logger.info(f"异常堆栈: {traceback.format_exc()}")

            # 重新抛出异常，让调用方处理
            raise

    def load_cache(self) -> None:
        """加载缓存数据"""
        start_time = time.time()
        logger.info("开始加载缓存数据")
        try:
            if os.path.exists(self.cache_file):
                with self.cache_lock:
                    with open(self.cache_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if not content.strip():
                            # 文件为空，使用默认数据，后台更新
                            logger.warning("缓存为空，使用默认数据")
                            self._load_default_industry_data()
                            # 启动后台更新任务
                            self._schedule_background_update()
                            return

                        try:
                            data = json.loads(content)
                        except Exception as e:
                            logger.error(f"缓存损坏，使用默认数据: {e}")
                            # 删除损坏的缓存文件
                            try:
                                os.remove(self.cache_file)
                            except Exception:
                                pass
                            # 使用默认数据，后台更新
                            self._load_default_industry_data()
                            self._schedule_background_update()
                            return

                        self.industry_data = data.get('industry_data', {})
                        last_update = data.get('last_update')
                        if last_update:
                            self.last_update_time = datetime.fromisoformat(
                                last_update)
            else:
                # 缓存文件不存在，使用默认数据
                logger.warning("缓存文件不存在，使用默认数据")
                self._load_default_industry_data()
                self._schedule_background_update()

        except Exception as e:
            logger.error(f"加载缓存数据失败: {e}")
            # 加载失败，使用默认数据
            self._load_default_industry_data()
            self._schedule_background_update()
        finally:
            elapsed = int((time.time() - start_time) * 1000)
            logger.info(f"加载缓存完成 - 耗时: {elapsed}ms")

    def save_cache(self) -> None:
        """保存缓存数据"""
        try:
            # with self.cache_lock:
            data = {
                'industry_data': self.industry_data,
                'last_update': self.last_update_time.isoformat() if self.last_update_time else None
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存缓存数据失败: {e}")

    def _load_default_industry_data(self) -> None:
        """加载默认行业数据"""
        try:
            # 提供一些基本的行业分类数据，确保系统能正常运行
            self.industry_data = {
                "BK0001": {"code": "BK0001", "name": "银行", "type": "theme", "market": "THEME"},
                "BK0002": {"code": "BK0002", "name": "保险", "type": "theme", "market": "THEME"},
                "BK0003": {"code": "BK0003", "name": "证券", "type": "theme", "market": "THEME"},
                "BK0004": {"code": "BK0004", "name": "房地产", "type": "theme", "market": "THEME"},
                "BK0005": {"code": "BK0005", "name": "互联网", "type": "theme", "market": "THEME"},
                "BK0006": {"code": "BK0006", "name": "软件开发", "type": "theme", "market": "THEME"},
                "BK0007": {"code": "BK0007", "name": "电子信息", "type": "theme", "market": "THEME"},
                "BK0008": {"code": "BK0008", "name": "生物医药", "type": "theme", "market": "THEME"},
                "BK0009": {"code": "BK0009", "name": "新能源", "type": "theme", "market": "THEME"},
                "BK0010": {"code": "BK0010", "name": "汽车制造", "type": "theme", "market": "THEME"},
                "BK0011": {"code": "BK0011", "name": "钢铁", "type": "theme", "market": "THEME"},
                "BK0012": {"code": "BK0012", "name": "有色金属", "type": "theme", "market": "THEME"},
                "BK0013": {"code": "BK0013", "name": "煤炭", "type": "theme", "market": "THEME"},
                "BK0014": {"code": "BK0014", "name": "石油化工", "type": "theme", "market": "THEME"},
                "BK0015": {"code": "BK0015", "name": "电力", "type": "theme", "market": "THEME"},
                "BK0016": {"code": "BK0016", "name": "建筑建材", "type": "theme", "market": "THEME"},
                "BK0017": {"code": "BK0017", "name": "机械设备", "type": "theme", "market": "THEME"},
                "BK0018": {"code": "BK0018", "name": "食品饮料", "type": "theme", "market": "THEME"},
                "BK0019": {"code": "BK0019", "name": "纺织服装", "type": "theme", "market": "THEME"},
                "BK0020": {"code": "BK0020", "name": "医疗器械", "type": "theme", "market": "THEME"},
            }
            logger.info(
                f"加载默认行业数据成功 - 数据数量: {len(self.industry_data)}")
        except Exception as e:
            logger.error(f"加载默认行业数据失败: {e}")
            self.industry_data = {}

    def _schedule_background_update(self) -> None:
        """安排后台更新任务

        HVD-241-P0-B (R241): 幂等守卫 + stop_event 可中断等待 + 线程句柄保存
        Why: 原实现无守卫 (load_cache 多路径 → 冷启动多线程并发), 线程体固定延时 5 秒
             硬阻塞且无句柄 → 无法停止 (R241-A 子智能体 + 主智能体验证)
        """
        try:
            # 幂等守卫: 同一实例仅调度一次, 防重复触发多线程
            with self._bg_lock:
                if self._bg_scheduled or self._disposed:
                    logger.debug("后台更新已调度或已销毁，跳过重复调度")
                    return
                self._bg_scheduled = True

            def background_update():
                try:
                    logger.info("开始后台更新任务")
                    # 可中断等待 (stop_event.wait), 避免硬阻塞 5 秒且支持 dispose 快速停止
                    if self._bg_stop_event.wait(5):
                        logger.debug("后台更新被停止事件中断")
                        return
                    success = self.update_industry_data(force=True)
                    if success:
                        logger.info("后台更新任务成功")
                    else:
                        logger.warning("后台更新任务失败")
                except Exception as e:
                    logger.error(f"后台更新任务失败: {e}")

            # 创建后台线程 (保存句柄, dispose 时可 join)
            with self._bg_lock:
                self._bg_thread = threading.Thread(
                    target=background_update, daemon=True)
                self._bg_thread.start()

            logger.info("后台更新任务安排成功")
        except Exception as e:
            logger.error(f"安排后台更新任务失败: {e}")

    def dispose(self) -> None:
        """释放资源 (HVD-241-P0-B, R241)

        Why: industry_service.py:478 hasattr(self._industry_manager, 'dispose') 恒 False
             → 后台线程无停止契约; R241-A 子智能体确认真实缺陷 (中风险)
        Fix: stop_event 通知 + join 等待线程退出 + 幂等短路 (R78 铁律 #6) + 失败不抛 (R8 #7)
        """
        if self._disposed:
            return
        try:
            self._disposed = True
            self._bg_stop_event.set()  # 通知后台线程退出
            with self._bg_lock:
                thread = self._bg_thread
                self._bg_thread = None
            if thread and thread.is_alive():
                thread.join(timeout=5)  # 等待线程退出 (最长 5 秒)
            logger.info("IndustryManager disposed")
        except Exception as e:
            logger.warning(f"IndustryManager dispose 失败: {e}")

    def _get_eastmoney_industry_data(self) -> Dict:
        """获取东方财富行业分类和板块数据

        Returns:
            Dict: 包含行业和板块数据的字典
        """
        try:
            # 基础配置
            base_url = "http://push2.eastmoney.com/api/qt/clist/get"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            base_params = {
                "pn": "1",
                "pz": "5000",  # 获取足够多的数据
                "po": "1",
                "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fields": "f12,f14,f100,f103,f104,f105,f106",  # 增加f104:概念板块 f105:地域板块 f106:主题板块
            }

            result = {}

            # 1. 获取A股行业数据
            industry_params = base_params.copy()
            # A股
            industry_params["fs"] = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"

            response = requests.get(
                base_url, headers=headers, params=industry_params)
            if response.status_code == 200:
                data = response.json()
                if data['rc'] == 0 and 'data' in data and 'diff' in data['data']:
                    for item in data['data']['diff']:
                        code = item['f12']
                        name = item['f14']
                        csrc_industry = item.get('f100', '')  # 证监会行业
                        exchange_industry = item.get('f103', '')  # 交易所行业
                        concept_sector = item.get('f104', '')  # 概念板块
                        region_sector = item.get('f105', '')  # 地域板块
                        theme_sector = item.get('f106', '')  # 主题板块

                        # 确定市场类型
                        market = 'SH' if code.startswith(('600', '601', '603', '605', '688')) else \
                            'SZ' if code.startswith(('000', '001', '002', '003', '300')) else \
                            'BJ' if code.startswith(
                            ('4', '8')) else 'OTHER'

                        result[code] = {
                            'code': code,
                            'name': name,
                            'csrc_industry': csrc_industry,
                            'exchange_industry': exchange_industry,
                            'market': market,
                            'sectors': {
                                'concept': concept_sector.split(',') if concept_sector else [],
                                'region': region_sector.split(',') if region_sector else [],
                                'theme': theme_sector.split(',') if theme_sector else []
                            }
                        }

            # 2. 获取概念板块数据
            concept_params = base_params.copy()
            concept_params["fs"] = "m:90+t:3"  # 概念板块

            response = requests.get(
                base_url, headers=headers, params=concept_params)
            if response.status_code == 200:
                data = response.json()
                if data['rc'] == 0 and 'data' in data and 'diff' in data['data']:
                    for item in data['data']['diff']:
                        code = item['f12']
                        name = item['f14']
                        if code not in result:
                            result[code] = {
                                'code': code,
                                'name': name,
                                'type': 'concept',
                                'market': 'CONCEPT'
                            }

            # 3. 获取地域板块数据
            region_params = base_params.copy()
            region_params["fs"] = "m:90+t:1"  # 地域板块

            response = requests.get(
                base_url, headers=headers, params=region_params)
            if response.status_code == 200:
                data = response.json()
                if data['rc'] == 0 and 'data' in data and 'diff' in data['data']:
                    for item in data['data']['diff']:
                        code = item['f12']
                        name = item['f14']
                        if code not in result:
                            result[code] = {
                                'code': code,
                                'name': name,
                                'type': 'region',
                                'market': 'REGION'
                            }

            # 4. 获取主题板块数据
            theme_params = base_params.copy()
            theme_params["fs"] = "m:90+t:2"  # 主题板块

            response = requests.get(
                base_url, headers=headers, params=theme_params)
            if response.status_code == 200:
                data = response.json()
                if data['rc'] == 0 and 'data' in data and 'diff' in data['data']:
                    for item in data['data']['diff']:
                        code = item['f12']
                        name = item['f14']
                        if code not in result:
                            result[code] = {
                                'code': code,
                                'name': name,
                                'type': 'theme',
                                'market': 'THEME'
                            }

            # 5. 获取指数板块数据
            index_params = base_params.copy()
            index_params["fs"] = "m:1+s:2,m:0+s:6"  # 指数板块

            response = requests.get(
                base_url, headers=headers, params=index_params)
            if response.status_code == 200:
                data = response.json()
                if data['rc'] == 0 and 'data' in data and 'diff' in data['data']:
                    for item in data['data']['diff']:
                        code = item['f12']
                        name = item['f14']
                        if code not in result:
                            result[code] = {
                                'code': code,
                                'name': name,
                                'type': 'index',
                                'market': 'INDEX'
                            }

            logger.info(f"获取东方财富行业数据成功 - 记录数量: {len(result)}")
            return result

        except Exception as e:
            logger.error(f"获取东方财富行业数据失败: {e}")
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return {}

    def update_industry_data(self, force: bool = False) -> bool:
        """更新行业数据

        Args:
            force: 是否强制更新

        Returns:
            更新是否成功
        """
        try:
            # 检查是否需要更新
            if not force and self.last_update_time:
                if datetime.now() - self.last_update_time < self.update_interval:
                    return True

            # 优先从东方财富获取数据
            new_data = self._get_eastmoney_industry_data()

            # 如果东方财富数据获取失败，尝试从交易所获取
            if not new_data:
                # 上交所行业分类
                sh_data = self._get_sh_industry_data()
                # 深交所行业分类
                sz_data = self._get_sz_industry_data()
                # 北交所行业分类
                bj_data = self._get_bj_industry_data()

                # 合并数据
                new_data = {}
                new_data.update(sh_data)
                new_data.update(sz_data)
                new_data.update(bj_data)

            if new_data:
                # with self.cache_lock:
                self.industry_data = new_data
                self.last_update_time = datetime.now()
                self.save_cache()

                # 发送更新信号
                self.industry_updated.emit()
                return True

            return False

        except Exception as e:
            error_msg = f"更新行业数据失败: {str(e)}"
            logger.error(error_msg)
            self.update_error.emit(error_msg)
            return False

    def _get_sh_industry_data(self) -> Dict:
        """获取上交所行业分类数据"""
        try:
            # 上交所行业分类接口
            url = "http://query.sse.com.cn/security/stock/getStockListData.do"
            headers = {
                "Referer": "http://www.sse.com.cn/",
                "User-Agent": "Mozilla/5.0"
            }
            params = {
                "jsonCallBack": "jsonpCallback",
                "isPagination": "true",
                "stockCode": "",
                "csrcCode": "",
                "areaName": "",
                "stockType": 1,
                "pageHelp.cacheSize": 1,
                "pageHelp.beginPage": 1,
                "pageHelp.pageSize": 2000,
                "_": int(time.time() * 1000)
            }

            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                # 解析数据
                text = response.text
                json_str = text[text.find('{'):text.rfind('}')+1]
                data = json.loads(json_str)

                result = {}
                for item in data['result']:
                    code = item['SECURITY_CODE_A']
                    csrc_industry = item.get('CSRC_CODE_DESC', '')
                    ssein_industry = item.get('SSEIN_CODE_DESC', '')
                    result[code] = {
                        'code': code,
                        'name': item['SECURITY_ABBR_A'],
                        'csrc_industry': csrc_industry,  # 证监会行业
                        'exchange_industry': ssein_industry,  # 交易所行业
                        'market': 'SH'
                    }
                return result

            return {}

        except Exception as e:
            logger.info(f"获取上交所行业数据失败: {str(e)}")
            return {}

    def _get_sz_industry_data(self) -> Dict:
        """获取深交所行业分类数据"""
        try:
            # 深交所行业分类接口
            url = "http://www.szse.cn/api/report/ShowReport"
            params = {
                "SHOWTYPE": "JSON",
                "CATALOGID": "1110",
                "TABKEY": "tab1",
                "random": str(time.time())
            }

            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()

                result = {}
                for item in data[0]['data']:
                    code = item['证券代码']
                    industry = item.get('所属行业', '')
                    result[code] = {
                        'code': code,
                        'name': item['证券简称'],
                        'csrc_industry': industry,
                        'market': 'SZ'
                    }
                return result

            return {}

        except Exception as e:
            logger.info(f"获取深交所行业数据失败: {str(e)}")
            return {}

    def _get_bj_industry_data(self) -> Dict:
        """获取北交所行业分类数据"""
        try:
            # 北交所行业分类接口
            url = "http://www.bse.cn/nqhqController/nqhq.do"
            params = {
                "page": "1",
                "size": "1000",
                "category": "industry"
            }

            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()

                result = {}
                for item in data['content']:
                    code = item['securityCode']
                    industry = item.get('industry', '')
                    result[code] = {
                        'code': code,
                        'name': item['securityName'],
                        'csrc_industry': industry,
                        'market': 'BJ'
                    }
                return result

            return {}

        except Exception as e:
            logger.info(f"获取北交所行业数据失败: {str(e)}")
            return {}

    def get_industry(self, stock_code: str) -> Optional[Dict]:
        """获取股票行业信息

        Args:
            stock_code: 股票代码

        Returns:
            行业信息字典
        """
        return self.industry_data.get(stock_code)

    def get_stocks_by_industry(self, industry: str) -> List[str]:
        """获取指定行业的所有股票

        Args:
            industry: 行业名称

        Returns:
            股票代码列表
        """
        result = []
        for code, info in self.industry_data.items():
            if info.get('csrc_industry') == industry or info.get('exchange_industry') == industry:
                result.append(code)
        return result

    def get_all_industries(self) -> List[str]:
        """获取所有行业列表

        Returns:
            行业名称列表
        """
        industries = set()
        for info in self.industry_data.values():
            if info.get('csrc_industry'):
                industries.add(info['csrc_industry'])
            if info.get('exchange_industry'):
                industries.add(info['exchange_industry'])
        return sorted(list(industries))

    def get_industry_list(self, source: str = "eastmoney") -> List[Dict[str, Any]]:
        """
        获取行业列表（与IndustryService兼容的接口）

        Args:
            source: 数据源

        Returns:
            行业列表
        """
        try:
            # 从行业数据中提取行业列表
            industries = []
            processed_codes = set()

            for info in self.industry_data.values():
                # 提取行业信息
                if info.get('type') in ['theme', 'concept', 'region']:
                    code = info.get('code', '')
                    name = info.get('name', '')
                    if code and name and code not in processed_codes:
                        industries.append({
                            'code': code,
                            'name': name,
                            'type': info.get('type', 'theme'),
                            'market': info.get('market', 'THEME'),
                            'source': source
                        })
                        processed_codes.add(code)

            # 如果没有数据，返回默认行业列表
            if not industries:
                industries = [
                    {"code": "BK0001", "name": "银行", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0002", "name": "保险", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0003", "name": "证券", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0004", "name": "房地产", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0005", "name": "互联网", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0006", "name": "软件开发", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0007", "name": "电子信息", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0008", "name": "生物医药", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0009", "name": "新能源", "type": "theme",
                        "market": "THEME", "source": source},
                    {"code": "BK0010", "name": "汽车制造", "type": "theme",
                        "market": "THEME", "source": source},
                ]

            return industries

        except Exception as e:
            logger.info(f"获取行业列表失败: {e}")
            return []

    def get_industry_stocks(self, industry_code: str, source: str = "eastmoney") -> List[Dict[str, Any]]:
        """
        获取行业股票（与IndustryService兼容的接口）

        Args:
            industry_code: 行业代码
            source: 数据源

        Returns:
            行业股票列表
        """
        try:
            stocks = []

            # 查找属于该行业的股票
            for stock_code, info in self.industry_data.items():
                # 检查是否属于指定行业
                if (info.get('code') == industry_code or
                    info.get('csrc_industry') == industry_code or
                        info.get('exchange_industry') == industry_code):

                    stocks.append({
                        'code': stock_code,
                        'name': info.get('name', ''),
                        'industry': industry_code,
                        'market': info.get('market', ''),
                        'source': source
                    })

            # 如果没有找到股票，返回一些示例数据
            if not stocks:
                stocks = [
                    {"code": "000001", "name": "平安银行", "industry": industry_code,
                        "market": "SZ", "source": source},
                    {"code": "600036", "name": "招商银行", "industry": industry_code,
                        "market": "SH", "source": source},
                    {"code": "000002", "name": "万科A", "industry": industry_code,
                        "market": "SZ", "source": source},
                ]

            return stocks

        except Exception as e:
            logger.info(f"获取行业股票失败: {e}")
            return []

    def get_industry_stocks_batch(self, industry_codes: List[str], source: str = "eastmoney") -> Dict[str, List[Dict[str, Any]]]:
        """
        批量获取行业股票（优化版 - 一次性遍历所有股票）

        Args:
            industry_codes: 行业代码列表
            source: 数据源

        Returns:
            Dict[industry_code, List[stock_info]]: 行业股票字典
        """
        try:
            result = {industry_code: [] for industry_code in industry_codes}

            # 一次性遍历所有股票，分类到各个行业
            for stock_code, info in self.industry_data.items():
                # 检查该股票是否属于任何一个请求的行业
                for industry_code in industry_codes:
                    if (info.get('code') == industry_code or
                        info.get('csrc_industry') == industry_code or
                        info.get('exchange_industry') == industry_code):

                        result[industry_code].append({
                            'code': stock_code,
                            'name': info.get('name', ''),
                            'industry': industry_code,
                            'market': info.get('market', ''),
                            'source': source
                        })
                        break  # 股票只属于一个行业，找到匹配后跳出
                    
            return result

        except Exception as e:
            logger.info(f"批量获取行业股票失败: {e}")
            return {industry_code: [] for industry_code in industry_codes}

    def get_supported_sources(self) -> List[str]:
        """
        获取支持的数据源

        Returns:
            支持的数据源列表
        """
        return ["eastmoney", "sina", "tencent", "sse", "szse", "bse"]

    def export_industry_data(self, file_path: str) -> bool:
        """导出行业数据

        Args:
            file_path: 导出文件路径

        Returns:
            是否导出成功
        """
        try:
            df = pd.DataFrame.from_dict(self.industry_data, orient='index')
            if file_path.endswith('.csv'):
                df.to_csv(file_path, encoding='utf-8-sig')
            elif file_path.endswith('.xlsx'):
                df.to_excel(file_path)
            else:
                return False
            return True
        except Exception as e:
            logger.info(f"导出行业数据失败: {str(e)}")
            return False

    def get_eastmoney_board_data(self) -> Dict:
        """获取东方财富所有板块（指数/概念/行业/期货/外汇/商品等）数据"""
        try:
            url = "http://push2.eastmoney.com/api/qt/clist/get"
            headers = {
                "User-Agent": "Mozilla/5.0"
            }
            # 板块类型映射（可根据实际需求扩展）
            board_types = {
                "上证指数": "m:1+t:2",      # 上证指数
                "深证成指": "m:0+t:1",    # 深证成指
                "沪深300": "m:1+t:3",    # 沪深300
                "创业板": "m:0+t:13",     # 创业板
                "科创50": "m:1+t:23",     # 科创50
                "恒生指数": "m:100+t:1",  # 恒生指数
                "黄金": "m:105+t:1",      # 黄金
                "原油": "m:106+t:1",      # 原油
                "美元": "m:103+t:1",      # 美元
                # ...可继续扩展
            }
            result = {}
            for name, fs in board_types.items():
                params = {
                    "pn": "1",
                    "pz": "10",
                    "po": "1",
                    "np": "1",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fltt": "2",
                    "invt": "2",
                    "fid": "f3",
                    "fs": fs,
                    "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f13,f100,f103"
                }
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if data['rc'] == 0 and 'data' in data and 'diff' in data['data']:
                        for item in data['data']['diff']:
                            code = item['f12']
                            board_name = item['f14']
                            result[name] = {
                                'code': code,
                                'name': board_name,
                                'last_price': item.get('f2'),
                                'chg': item.get('f4'),
                                'chg_pct': item.get('f3'),
                                'volume': item.get('f5'),
                                'amount': item.get('f6'),
                                'turnover': item.get('f8'),
                                'market': name
                            }
            return result
        except Exception as e:
            logger.info(f"获取东方财富所有板块数据失败: {e}")
            return {}

    def get_eastmoney_board_list(self, board_type='index'):
        """
        获取东方财富板块列表
        board_type: 'index'（指数）, 'industry'（行业）, 'concept'（概念）, 'area'（地区）
        """
        url_map = {
            'index': 'http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=b:MK0010,b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0025,b:MK0026,b:MK0027,b:MK0028,b:MK0029,b:MK0030,b:MK0031,b:MK0032,b:MK0033,b:MK0034,b:MK0035,b:MK0036,b:MK0037,b:MK0038,b:MK0039,b:MK0040,b:MK0041,b:MK0042,b:MK0043,b:MK0044,b:MK0045,b:MK0046,b:MK0047,b:MK0048,b:MK0049,b:MK0050&fields=f12,f14',
            'industry': 'http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:90+t:2,m:90+t:3,m:90+t:4&fields=f12,f14',
            'concept': 'http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:90+t:1&fields=f12,f14',
            'area': 'http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:90+t:5&fields=f12,f14'
        }
        url = url_map.get(board_type)
        if not url:
            return []
        try:
            resp = requests.get(url)
            data = resp.json()
            if data['rc'] == 0 and 'data' in data and 'diff' in data['data']:
                return [{'code': item['f12'], 'name': item['f14']} for item in data['data']['diff']]
        except Exception as e:
            logger.info(f"获取东方财富板块列表失败: {e}")
        return []

    def get_eastmoney_board_members(self, board_code):
        """
        获取某板块成分股
        """
        url = f"http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=1000&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=b:{board_code}&fields=f12,f14"
        try:
            resp = requests.get(url)
            data = resp.json()
            if data['rc'] == 0 and 'data' in data and 'diff' in data['data']:
                return [{'code': item['f12'], 'name': item['f14']} for item in data['data']['diff']]
        except Exception as e:
            logger.info(f"获取某板块成分股失败: {e}")
        return []

    def get_major_indices(self) -> Dict[str, dict]:
        """获取主要指数信息"""
        try:
            indices = {
                "000001": {"name": "上证指数", "market": "SH"},
                "399001": {"name": "深证成指", "market": "SZ"},
                "399006": {"name": "创业板指", "market": "SZ"},
                "000300": {"name": "沪深300", "market": "SH"},
                "000905": {"name": "中证500", "market": "SH"},
                "000852": {"name": "中证1000", "market": "SH"}
            }
            return indices
        except Exception as e:
            logger.info(f"获取主要指数信息失败: {e}")
            return {}

    def get_industry_performance(self, period: str = "1d") -> Dict[str, Any]:
        """
        获取行业表现数据

        Args:
            period: 时间周期 ('1d', '5d', '1m', '3m', '6m', '1y')

        Returns:
            Dict: 行业表现数据
        """
        try:
            logger.info(f"开始获取行业表现数据 - 周期: {period}")

            # 获取行业板块数据
            industry_performance = {}

            # 使用东方财富API获取行业表现
            url = "http://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "pn": "1",
                "pz": "100",
                "po": "1",
                "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fs": "m:90+t:2",  # 行业板块
                "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18"
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(
                url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('rc') == 0 and 'data' in data and 'diff' in data['data']:
                    for item in data['data']['diff']:
                        industry_code = item.get('f12', '')
                        industry_name = item.get('f14', '')
                        current_price = item.get('f2', 0)
                        change_percent = item.get('f3', 0)
                        change_amount = item.get('f4', 0)
                        volume = item.get('f5', 0)
                        turnover = item.get('f6', 0)
                        amplitude = item.get('f7', 0)

                        industry_performance[industry_code] = {
                            'name': industry_name,
                            'current_price': current_price,
                            'change_percent': change_percent / 100 if change_percent else 0,
                            'change_amount': change_amount,
                            'volume': volume,
                            'turnover': turnover,
                            'amplitude': amplitude / 100 if amplitude else 0,
                            'period': period
                        }

            logger.info(f"获取行业表现数据成功 - 行业数量: {len(industry_performance)}")
            return industry_performance

        except Exception as e:
            logger.info(f"获取行业表现数据失败: {e}")
            return {}

    def analyze_industry_trends(self, days: int = 30) -> Dict[str, Any]:
        """
        分析行业趋势

        Args:
            days: 分析天数

        Returns:
            Dict: 行业趋势分析结果
        """
        try:
            logger.info(f"开始分析行业趋势 - 分析天数: {days}")

            # 获取多个时间周期的行业表现
            periods = ['1d', '5d', '1m']
            trend_analysis = {}

            for period in periods:
                performance = self.get_industry_performance(period)

                # 计算趋势强度
                for industry_code, data in performance.items():
                    if industry_code not in trend_analysis:
                        trend_analysis[industry_code] = {
                            'name': data['name'],
                            'trend_strength': 0,
                            'consistency': 0,
                            'momentum': 0,
                            'periods': {}
                        }

                    trend_analysis[industry_code]['periods'][period] = data['change_percent']

            # 计算综合趋势指标
            for industry_code, analysis in trend_analysis.items():
                periods_data = analysis['periods']

                if len(periods_data) >= 2:
                    # 趋势强度：各周期涨跌幅的平均值
                    trend_strength = sum(
                        periods_data.values()) / len(periods_data)

                    # 一致性：各周期方向的一致性
                    positive_periods = sum(
                        1 for v in periods_data.values() if v > 0)
                    consistency = positive_periods / len(periods_data)

                    # 动量：短期相对长期的表现
                    momentum = periods_data.get(
                        '1d', 0) - periods_data.get('1m', 0)

                    analysis['trend_strength'] = trend_strength
                    analysis['consistency'] = consistency
                    analysis['momentum'] = momentum

            # 排序并分类
            sorted_industries = sorted(trend_analysis.items(),
                                       key=lambda x: x[1]['trend_strength'], reverse=True)

            result = {
                'analysis_date': datetime.now().isoformat(),
                'total_industries': len(trend_analysis),
                'top_performers': sorted_industries[:10],
                'bottom_performers': sorted_industries[-10:],
                'trending_up': [item for item in sorted_industries if item[1]['trend_strength'] > 0.02],
                'trending_down': [item for item in sorted_industries if item[1]['trend_strength'] < -0.02],
                'stable': [item for item in sorted_industries if -0.02 <= item[1]['trend_strength'] <= 0.02]
            }

            logger.info(f"行业趋势分析完成 - 总行业数: {len(result['top_performers'])}")

            return result

        except Exception as e:
            logger.info(f"行业趋势分析失败: {e}")
            return {}

    def get_industry_rotation_signals(self) -> Dict[str, Any]:
        """
        获取行业轮动信号

        Returns:
            Dict: 行业轮动信号
        """
        try:
            logger.info("开始获取行业轮动信号")

            # 获取行业趋势分析
            trend_analysis = self.analyze_industry_trends()

            if not trend_analysis:
                return {}

            rotation_signals = {
                'rotation_date': datetime.now().isoformat(),
                'signals': []
            }

            # 分析轮动信号
            for industry_code, analysis in trend_analysis.get('trending_up', []):
                signal_strength = analysis['trend_strength'] * \
                    analysis['consistency']

                if signal_strength > 0.03:  # 强信号阈值
                    rotation_signals['signals'].append({
                        'industry_code': industry_code,
                        'industry_name': analysis['name'],
                        'signal_type': 'BUY',
                        'signal_strength': signal_strength,
                        'trend_strength': analysis['trend_strength'],
                        'consistency': analysis['consistency'],
                        'momentum': analysis['momentum'],
                        'confidence': min(0.95, signal_strength * 10)  # 置信度
                    })

            for industry_code, analysis in trend_analysis.get('trending_down', []):
                signal_strength = abs(
                    analysis['trend_strength']) * analysis['consistency']

                if signal_strength > 0.03:  # 强信号阈值
                    rotation_signals['signals'].append({
                        'industry_code': industry_code,
                        'industry_name': analysis['name'],
                        'signal_type': 'SELL',
                        'signal_strength': signal_strength,
                        'trend_strength': analysis['trend_strength'],
                        'consistency': analysis['consistency'],
                        'momentum': analysis['momentum'],
                        'confidence': min(0.95, signal_strength * 10)  # 置信度
                    })

            # 按信号强度排序
            rotation_signals['signals'].sort(
                key=lambda x: x['signal_strength'], reverse=True)

            logger.info(f"行业轮动信号获取成功 - 信号数量: {len(rotation_signals['signals'])}")

            return rotation_signals

        except Exception as e:
            logger.info(f"获取行业轮动信号失败: {e}")
            return {}

    def get_industry_valuation_metrics(self) -> Dict[str, Any]:
        """
        获取行业估值指标

        Returns:
            Dict: 行业估值指标
        """
        try:
            logger.info("开始获取行业估值指标")

            valuation_metrics = {}

            # 获取行业基本信息
            for industry_code, industry_info in self.industry_data.items():
                if isinstance(industry_info, dict) and 'name' in industry_info:
                    # 这里可以集成更多的估值数据源
                    # 目前提供基础框架
                    valuation_metrics[industry_code] = {
                        'name': industry_info['name'],
                        'pe_ratio': None,  # 市盈率
                        'pb_ratio': None,  # 市净率
                        'ps_ratio': None,  # 市销率
                        'dividend_yield': None,  # 股息率
                        'roe': None,  # 净资产收益率
                        'debt_ratio': None,  # 负债率
                        'valuation_level': 'UNKNOWN'  # 估值水平
                    }

            logger.info(f"行业估值指标获取成功 - 指标数量: {len(valuation_metrics)}")

            return valuation_metrics

        except Exception as e:
            logger.info(f"获取行业估值指标失败: {e}")
            return {}

    def screen_industries_by_criteria(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据条件筛选行业

        Args:
            criteria: 筛选条件
                - min_change_percent: 最小涨跌幅
                - max_change_percent: 最大涨跌幅
                - min_volume: 最小成交量
                - trend_direction: 趋势方向 ('up', 'down', 'stable')
                - momentum_threshold: 动量阈值

        Returns:
            List: 符合条件的行业列表
        """
        try:
            logger.info("开始根据条件筛选行业")

            # 获取行业表现数据
            performance_data = self.get_industry_performance()
            trend_analysis = self.analyze_industry_trends()

            filtered_industries = []

            for industry_code, performance in performance_data.items():
                # 基本筛选条件
                if 'min_change_percent' in criteria:
                    if performance['change_percent'] < criteria['min_change_percent']:
                        continue

                if 'max_change_percent' in criteria:
                    if performance['change_percent'] > criteria['max_change_percent']:
                        continue

                if 'min_volume' in criteria:
                    if performance['volume'] < criteria['min_volume']:
                        continue

                # 趋势方向筛选
                if 'trend_direction' in criteria and industry_code in trend_analysis:
                    trend_data = None
                    for item in trend_analysis.get('trending_up', []) + trend_analysis.get('trending_down', []) + trend_analysis.get('stable', []):
                        if item[0] == industry_code:
                            trend_data = item[1]
                            break

                    if trend_data:
                        if criteria['trend_direction'] == 'up' and trend_data['trend_strength'] <= 0:
                            continue
                        elif criteria['trend_direction'] == 'down' and trend_data['trend_strength'] >= 0:
                            continue
                        elif criteria['trend_direction'] == 'stable' and abs(trend_data['trend_strength']) > 0.02:
                            continue

                # 动量阈值筛选
                if 'momentum_threshold' in criteria and industry_code in trend_analysis:
                    trend_data = None
                    for item in trend_analysis.get('trending_up', []) + trend_analysis.get('trending_down', []) + trend_analysis.get('stable', []):
                        if item[0] == industry_code:
                            trend_data = item[1]
                            break

                    if trend_data and abs(trend_data['momentum']) < criteria['momentum_threshold']:
                        continue

                # 添加到结果列表
                industry_result = {
                    'code': industry_code,
                    'name': performance['name'],
                    'current_price': performance['current_price'],
                    'change_percent': performance['change_percent'],
                    'volume': performance['volume'],
                    'turnover': performance['turnover'],
                    'amplitude': performance['amplitude']
                }

                # 添加趋势数据
                if industry_code in trend_analysis:
                    for item in trend_analysis.get('trending_up', []) + trend_analysis.get('trending_down', []) + trend_analysis.get('stable', []):
                        if item[0] == industry_code:
                            industry_result.update({
                                'trend_strength': item[1]['trend_strength'],
                                'consistency': item[1]['consistency'],
                                'momentum': item[1]['momentum']
                            })
                            break

                filtered_industries.append(industry_result)

            # 按涨跌幅排序
            filtered_industries.sort(
                key=lambda x: x['change_percent'], reverse=True)

            logger.info(f"行业筛选完成 - 符合条件的行业数量: {len(filtered_industries)}")

            return filtered_industries

        except Exception as e:
            logger.info(f"根据条件筛选行业失败: {e}")
            return []

    def get_industry_correlation_matrix(self) -> Dict[str, Any]:
        """
        获取行业相关性矩阵

        Returns:
            Dict: 行业相关性数据
        """
        try:
            logger.info("开始获取行业相关性矩阵")

            # 这里需要历史数据来计算相关性
            # 目前提供基础框架，实际实现需要更多历史数据
            correlation_matrix = {
                'calculation_date': datetime.now().isoformat(),
                'period': '30d',
                'correlations': {},
                'clusters': [],
                'diversification_suggestions': []
            }

            logger.info("行业相关性矩阵获取成功")

            return correlation_matrix

        except Exception as e:
            logger.info(f"获取行业相关性矩阵失败: {e}")
            return {}

    def generate_industry_report(self) -> Dict[str, Any]:
        """
        生成行业分析报告

        Returns:
            Dict: 行业分析报告
        """
        try:
            logger.info("开始生成行业分析报告")

            # 收集各种分析数据
            performance_data = self.get_industry_performance()
            trend_analysis = self.analyze_industry_trends()
            rotation_signals = self.get_industry_rotation_signals()
            valuation_metrics = self.get_industry_valuation_metrics()

            report = {
                'report_date': datetime.now().isoformat(),
                'summary': {
                    'total_industries': len(performance_data),
                    'trending_up_count': len(trend_analysis.get('trending_up', [])),
                    'trending_down_count': len(trend_analysis.get('trending_down', [])),
                    'rotation_signals_count': len(rotation_signals.get('signals', []))
                },
                'performance_overview': performance_data,
                'trend_analysis': trend_analysis,
                'rotation_signals': rotation_signals,
                'valuation_overview': valuation_metrics,
                'recommendations': self._generate_industry_recommendations(
                    performance_data, trend_analysis, rotation_signals
                )
            }

            logger.info("行业分析报告生成成功")

            return report

        except Exception as e:
            logger.info(f"生成行业分析报告失败: {e}")
            return {}

    def _generate_industry_recommendations(self, performance_data: Dict,
                                           trend_analysis: Dict,
                                           rotation_signals: Dict) -> List[Dict[str, Any]]:
        """
        生成行业投资建议

        Args:
            performance_data: 行业表现数据
            trend_analysis: 趋势分析数据
            rotation_signals: 轮动信号数据

        Returns:
            List: 投资建议列表
        """
        recommendations = []

        try:
            # 基于轮动信号生成建议
            for signal in rotation_signals.get('signals', [])[:5]:  # 取前5个信号
                if signal['signal_type'] == 'BUY' and signal['confidence'] > 0.7:
                    recommendations.append({
                        'type': 'BUY',
                        'industry_code': signal['industry_code'],
                        'industry_name': signal['industry_name'],
                        'reason': f"强势上涨趋势，信号强度: {signal['signal_strength']:.3f}",
                        'confidence': signal['confidence'],
                        'time_horizon': 'short_term',
                        'risk_level': 'medium'
                    })
                elif signal['signal_type'] == 'SELL' and signal['confidence'] > 0.7:
                    recommendations.append({
                        'type': 'SELL',
                        'industry_code': signal['industry_code'],
                        'industry_name': signal['industry_name'],
                        'reason': f"下跌趋势明显，信号强度: {signal['signal_strength']:.3f}",
                        'confidence': signal['confidence'],
                        'time_horizon': 'short_term',
                        'risk_level': 'high'
                    })

            # 基于趋势分析生成长期建议
            for industry_code, analysis in trend_analysis.get('trending_up', [])[:3]:
                if analysis['consistency'] > 0.8:
                    recommendations.append({
                        'type': 'HOLD',
                        'industry_code': industry_code,
                        'industry_name': analysis['name'],
                        'reason': f"持续上涨趋势，一致性: {analysis['consistency']:.2f}",
                        'confidence': analysis['consistency'],
                        'time_horizon': 'long_term',
                        'risk_level': 'low'
                    })

        except Exception as e:
            logger.info(f"生成行业投资建议失败: {e}")

        return recommendations
