"""
增强型资产选择器组件

基于左侧面板搜索功能设计，提供高性能的资产选择体验。
支持模糊搜索、数据库验证、多资产类型等特性。
"""

from loguru import logger
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, 
    QPushButton, QLabel, QFrame, QApplication, QListWidget, 
    QListWidgetItem, QAbstractItemView, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, pyqtSlot
from PyQt5.QtGui import QFont, QPixmap, QIcon

from core.plugin_types import AssetType
from core.services.unified_data_manager import UnifiedDataManager
from core.services.asset_service import AssetService
from core.ui_asset_type_utils import UIAssetTypeUtils


class AssetSearchWorker(QObject):
    """资产搜索工作线程"""
    
    # 信号定义
    search_completed = pyqtSignal(list)  # 搜索完成信号，传递搜索结果
    error_occurred = pyqtSignal(str)     # 错误信号，传递错误信息
    
    def __init__(self, data_manager: UnifiedDataManager, asset_service: AssetService):
        super().__init__()
        self.data_manager = data_manager
        self.asset_service = asset_service
        self.is_searching = False
        
    def search_assets(self, search_text: str, asset_type: AssetType) -> None:
        """异步搜索资产"""
        if self.is_searching:
            return
            
        self.is_searching = True
        logger.info(f"开始异步搜索资产: search_text={search_text}, asset_type={asset_type.value}")
        
        # 使用 QThreadPool 和 QRunnable 来处理线程操作
        from PyQt5.QtCore import QRunnable, QThreadPool
        
        class SearchTask(QRunnable):
            def __init__(self, search_function):
                super().__init__()
                self.search_function = search_function
                
            def run(self):
                self.search_function()
        
        def _search():
            try:
                assets = self._perform_search(search_text, asset_type)
                logger.info(f"搜索完成，获取到 {len(assets)} 个资产")
                
                # 使用 QTimer 在主线程中发射信号
                from PyQt5.QtCore import QCoreApplication
                QCoreApplication.postEvent(self, pyqtEvent(0, assets))
            except Exception as e:
                logger.error(f"资产搜索失败: {e}")
                import traceback
                traceback.print_exc()
                QCoreApplication.postEvent(self, pyqtErrorEvent(0, str(e)))
            finally:
                self.is_searching = False
        
        # 自定义事件类，用于在主线程中处理搜索结果
        from PyQt5.QtCore import QEvent
        
        class pyqtEvent(QEvent):
            def __init__(self, type, data):
                super().__init__(QEvent.Type(QEvent.User + 1))
                self.data = data
        
        class pyqtErrorEvent(QEvent):
            def __init__(self, type, data):
                super().__init__(QEvent.Type(QEvent.User + 2))
                self.data = data
        
        # 重新实现event方法，处理自定义事件
        def event(self, event):
            if event.type() == QEvent.User + 1:
                # 处理搜索完成事件
                logger.info(f"收到搜索完成事件，资产数量: {len(event.data)}")
                self.search_completed.emit(event.data)
                return True
            elif event.type() == QEvent.User + 2:
                # 处理搜索错误事件
                self.error_occurred.emit(event.data)
                return True
            return super().event(event)
        
        # 动态替换event方法
        AssetSearchWorker.event = event
        
        # 执行搜索任务
        search_task = SearchTask(_search)
        QThreadPool.globalInstance().start(search_task)
        
    def _perform_search(self, search_text: str, asset_type: AssetType) -> List[Dict[str, Any]]:
        """执行资产搜索（修复版本）"""
        try:
            assets = []
            search_text = search_text.strip()
            
            # 1. 直接查询DuckDB数据库（参考左侧面板实现）
            try:
                import duckdb
                from pathlib import Path
                
                logger.info(f"直接查询DuckDB数据库: {asset_type.value}")
                
                # 获取数据库路径
                try:
                    from core.asset_database_manager import get_asset_separated_database_manager
                    asset_db_manager = get_asset_separated_database_manager()
                    db_path = asset_db_manager.get_database_path(asset_type)
                except Exception as e:
                    logger.warning(f"获取资产数据库路径失败: {e}，使用默认路径")
                    # 降级：使用默认路径
                    asset_type_str = asset_type.value.lower()
                    db_path = Path.cwd() / "cache" / "duckdb" / asset_type_str / f"{asset_type_str}_data.duckdb"
                    db_path = str(db_path)
                
                # 检查数据库文件是否存在
                if not Path(db_path).exists():
                    logger.warning(f"DuckDB文件不存在: {db_path}")
                else:
                    # 构建查询条件
                    query_conditions = []
                    query_conditions.append(f"asset_type = '{asset_type.value}'")
                    
                    if search_text:
                        search_condition = f"(symbol LIKE '%{search_text}%' OR name LIKE '%{search_text}%')"
                        query_conditions.append(search_condition)
                    
                    # 构建查询SQL
                    base_query = "SELECT symbol as code, name, market, industry, sector, asset_type, updated_at as update_time FROM asset_metadata"
                    if query_conditions:
                        query = f"{base_query} WHERE {' AND '.join(query_conditions)}"
                    else:
                        query = base_query
                    
                    query += " ORDER BY symbol"
                    
                    # 执行查询
                    with duckdb.connect(db_path) as conn:
                        # 检查表是否存在
                        table_check = "SHOW TABLES"
                        tables_result = conn.execute(table_check).fetchall()
                        table_names = [table[0] for table in tables_result]
                        
                        if 'asset_metadata' in table_names:
                            # 执行股票查询
                            asset_df = conn.execute(query).df()
                            
                            if not asset_df.empty:
                                # 转换为标准格式
                                for _, row in asset_df.iterrows():
                                    code = str(row.get('code', ''))
                                    name = str(row.get('name', ''))
                                    
                                    if code and code != 'nan' and code != 'None':
                                        display_text = f"{code} {name}" if name and name != 'nan' and name != 'None' else code
                                        asset_item = {
                                            'code': code,
                                            'name': name if name != 'nan' and name != 'None' else '',
                                            'market': str(row.get('market', '')),
                                            'industry': str(row.get('industry', '')),
                                            'sector': str(row.get('sector', '')),
                                            'display': display_text
                                        }
                                        assets.append(asset_item)
                                
                                return assets
                            else:
                                logger.info("DuckDB查询返回空结果")
                
            except ImportError:
                logger.debug("duckdb模块不可用，跳过直接查询")
            except Exception as e:
                logger.warning(f"直接查询DuckDB失败: {e}")
            
            # 2. 优先使用AssetService（更稳定的API）
            if self.asset_service:
                try:
                    logger.info(f"使用AssetService搜索资产: {asset_type.value}")
                    asset_list = self.asset_service.get_asset_list(asset_type, market='all')
                    
                    if asset_list and isinstance(asset_list, list) and len(asset_list) > 0:
                        # 应用搜索过滤
                        if search_text:
                            search_lower = search_text.lower()
                            filtered_assets = [
                                asset for asset in asset_list
                                if search_lower in asset.get('code', '').lower() or
                                   search_lower in asset.get('name', '').lower() or
                                   search_lower in str(asset.get('symbol', '')).lower()
                            ]
                        else:
                            filtered_assets = asset_list
                        
                        # 标准化格式
                        standardized_assets = []
                        for asset in filtered_assets:
                            code = str(asset.get('code', '') or asset.get('symbol', ''))
                            name = str(asset.get('name', ''))
                            
                            if code and code != 'nan' and code != 'None':
                                standardized_assets.append({
                                    'code': code,
                                    'name': name if name != 'nan' and name != 'None' else '',
                                    'market': str(asset.get('market', '')),
                                    'industry': str(asset.get('industry', '')),
                                    'sector': str(asset.get('sector', '')),
                                    'display': f"{code} {name}" if name and name != 'nan' and name != 'None' else code
                                })
                        
                        logger.info(f"AssetService搜索成功: {len(standardized_assets)} 个资产")
                        return standardized_assets
                        
                except Exception as e:
                    logger.warning(f"AssetService获取资产列表失败: {e}")
            
            # 3. 降级到UnifiedDataManager（修复参数格式）
            if self.data_manager:
                try:
                    
                    logger.info(f"使用UnifiedDataManager搜索资产: {asset_type}")
                    
                    # 转换资产类型为字符串，确保兼容性
                    asset_type_str = asset_type.value.lower()
                    asset_df = self.data_manager.get_asset_list(
                        asset_type=asset_type_str, 
                        market='all'
                    )
                    
                    if asset_df is not None and not asset_df.empty:
                        # 应用搜索过滤
                        if search_text:
                            search_lower = search_text.lower()
                            # 查找包含搜索文本的列
                            search_columns = ['code', 'symbol', 'name']
                            search_conditions = []
                            
                            for col in search_columns:
                                if col in asset_df.columns:
                                    search_conditions.append(
                                        asset_df[col].astype(str).str.contains(search_lower, case=False, na=False)
                                    )
                            
                            if search_conditions:
                                # 合并所有搜索条件
                                combined_condition = search_conditions[0]
                                for condition in search_conditions[1:]:
                                    combined_condition = combined_condition | condition
                                
                                filtered_df = asset_df[combined_condition]
                            else:
                                filtered_df = asset_df
                        else:
                            filtered_df = asset_df
                        
                        # 转换为标准格式
                        for _, row in filtered_df.iterrows():
                            code = str(row.get('code', '') or row.get('symbol', ''))
                            name = str(row.get('name', ''))
                            
                            if code and code != 'nan' and code != 'None':
                                assets.append({
                                    'code': code,
                                    'name': name if name != 'nan' and name != 'None' else '',
                                    'market': str(row.get('market', '')),
                                    'industry': str(row.get('industry', '')),
                                    'sector': str(row.get('sector', '')),
                                    'display': f"{code} {name}" if name and name != 'nan' and name != 'None' else code
                                })
                        
                        logger.info(f"UnifiedDataManager搜索成功: {len(assets)} 个资产")
                        return assets
                    else:
                        logger.warning("UnifiedDataManager返回空DataFrame")
                        
                except Exception as e:
                    logger.warning(f"UnifiedDataManager获取资产列表失败: {e}")
            
            # 最后降级到默认数据（确保有数据可用）
            logger.info("使用默认资产列表")
            return self._get_default_assets(asset_type)
            
        except Exception as e:
            logger.error(f"执行资产搜索失败: {e}")
            # 即使出错也返回默认数据，确保UI有内容显示
            return self._get_default_assets(asset_type)
    
    
    def _get_default_assets(self, asset_type: AssetType) -> List[Dict[str, Any]]:
        """获取默认资产列表（扩展支持所有资产类型）"""
        defaults = {
            # 股票类
            AssetType.STOCK_A: [
                {'code': '000001', 'name': '平安银行', 'market': 'sz'},
                {'code': '000002', 'name': '万科A', 'market': 'sz'},
                {'code': '600000', 'name': '浦发银行', 'market': 'sh'},
                {'code': '600036', 'name': '招商银行', 'market': 'sh'},
                {'code': '600519', 'name': '贵州茅台', 'market': 'sh'},
                {'code': '000858', 'name': '五粮液', 'market': 'sz'}
            ],
            AssetType.STOCK_US: [
                {'code': 'AAPL', 'name': '苹果公司', 'market': 'us'},
                {'code': 'MSFT', 'name': '微软', 'market': 'us'},
                {'code': 'GOOGL', 'name': '谷歌', 'market': 'us'},
                {'code': 'AMZN', 'name': '亚马逊', 'market': 'us'},
                {'code': 'TSLA', 'name': '特斯拉', 'market': 'us'}
            ],
            AssetType.STOCK_HK: [
                {'code': '0700', 'name': '腾讯控股', 'market': 'hk'},
                {'code': '9988', 'name': '阿里巴巴', 'market': 'hk'},
                {'code': '3690', 'name': '美团', 'market': 'hk'},
                {'code': '0939', 'name': '建设银行', 'market': 'hk'},
                {'code': '939', 'name': '建设银行', 'market': 'hk'}
            ],
            AssetType.STOCK_B: [
                {'code': '900901', 'name': '大秦铁路B', 'market': 'sh'},
                {'code': '900902', 'name': '国药股份B', 'market': 'sh'}
            ],
            AssetType.STOCK_H: [
                {'code': '000001', 'name': '中国平安', 'market': 'hk'},
                {'code': '600036', 'name': '招商银行', 'market': 'hk'}
            ],
            # 衍生品
            AssetType.FUTURES: [
                {'code': 'IF2401', 'name': '沪深300期货2401', 'market': 'cffex'},
                {'code': 'IC2401', 'name': '中证500期货2401', 'market': 'cffex'},
                {'code': 'IH2401', 'name': '上证50期货2401', 'market': 'cffex'},
                {'code': 'CU2401', 'name': '沪铜2401', 'market': 'shfe'},
                {'code': 'AL2401', 'name': '沪铝2401', 'market': 'shfe'}
            ],
            AssetType.OPTION: [
                {'code': 'IO2401C5500', 'name': '中证500看涨期权', 'market': 'cffex'},
                {'code': 'IO2401P4500', 'name': '中证500看跌期权', 'market': 'cffex'}
            ],
            AssetType.WARRANT: [
                {'code': '580030', 'name': '华宝油气认购', 'market': 'sh'},
                {'code': '500011', 'name': '深证成指认购', 'market': 'sz'}
            ],
            # 基金债券
            AssetType.FUND: [
                {'code': '161039', 'name': '富国中证500ETF联接', 'market': 'sz'},
                {'code': '161032', 'name': '富国中证煤炭指数', 'market': 'sz'},
                {'code': '000001', 'name': '华夏上证50ETF', 'market': 'sh'}
            ],
            AssetType.BOND: [
                {'code': '204001', 'name': '国债逆回购1天', 'market': 'sh'},
                {'code': '019002', 'name': '国债1902', 'market': 'sh'},
                {'code': '113011', 'name': '石化转债', 'market': 'sh'}
            ],
            # 指数
            AssetType.INDEX: [
                {'code': '000001', 'name': '上证指数', 'market': 'sh'},
                {'code': '000300', 'name': '沪深300', 'market': 'sh'},
                {'code': '000016', 'name': '上证50', 'market': 'sh'},
                {'code': '399001', 'name': '深证成指', 'market': 'sz'},
                {'code': '399006', 'name': '创业板指', 'market': 'sz'}
            ],
            # 板块
            AssetType.INDUSTRY_SECTOR: [
                {'code': 'BK0451', 'name': '证券板块', 'market': 'concept'},
                {'code': 'BK0437', 'name': '银行板块', 'market': 'concept'}
            ],
            AssetType.CONCEPT_SECTOR: [
                {'code': 'BK0501', 'name': '新能源概念', 'market': 'concept'},
                {'code': 'BK0801', 'name': '人工智能概念', 'market': 'concept'}
            ],
            # 其他
            AssetType.CRYPTO: [
                {'code': 'BTCUSDT', 'name': '比特币/泰达币', 'market': 'binance'},
                {'code': 'ETHUSDT', 'name': '以太坊/泰达币', 'market': 'binance'},
                {'code': 'BNBUSDT', 'name': '币安币/泰达币', 'market': 'binance'},
                {'code': 'XRPUSDT', 'name': '瑞波币/泰达币', 'market': 'binance'},
                {'code': 'SOLUSDT', 'name': '索拉纳/泰达币', 'market': 'binance'}
            ],
            AssetType.FOREX: [
                {'code': 'USDCNY', 'name': '美元/人民币', 'market': 'oanda'},
                {'code': 'EURUSD', 'name': '欧元/美元', 'market': 'oanda'},
                {'code': 'GBPUSD', 'name': '英镑/美元', 'market': 'oanda'}
            ],
            AssetType.COMMODITY: [
                {'code': 'C2401', 'name': '玉米2401', 'market': 'cbot'},
                {'code': 'CL2401', 'name': '原油2401', 'market': 'nymex'},
                {'code': 'GC2402', 'name': '黄金2402', 'market': 'comex'}
            ],
            AssetType.MACRO: [
                {'code': 'GDP_CN', 'name': '中国GDP', 'market': 'macro'},
                {'code': 'CPI_CN', 'name': '中国CPI', 'market': 'macro'},
                {'code': 'M2_CN', 'name': '中国M2', 'market': 'macro'}
            ]
        }

        default_list = defaults.get(asset_type, [])
        for asset in default_list:
            asset['display'] = f"{asset['code']} {asset['name']}"

        return default_list


class EnhancedAssetSelector(QWidget):
    """增强型资产选择器（只支持股票A股）"""
    
    # 信号定义
    asset_selected = pyqtSignal(dict)  # 资产选择信号
    
    def __init__(self, 
                 data_manager: Optional[UnifiedDataManager] = None,
                 asset_service: Optional[AssetService] = None,
                 default_asset_type: AssetType = AssetType.STOCK_A,
                 parent=None):
        """
        初始化增强型资产选择器
        
        Args:
            data_manager: 统一数据管理器
            asset_service: 资产服务
            default_asset_type: 默认资产类型
            parent: 父组件
        """
        super().__init__(parent)
        self.data_manager = data_manager
        self.asset_service = asset_service
        
        # 当前状态（支持多资产类型，默认股票A股）
        self.current_asset_type = default_asset_type
        self.current_search_text = ""
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
        
        # 搜索工作线程
        self.search_worker = AssetSearchWorker(data_manager, asset_service)
        self.search_worker.search_completed.connect(self._on_search_completed)
        self.search_worker.error_occurred.connect(self._on_search_error)
        
        # 缓存
        self.asset_cache = {}  # 资产类型 -> 资产列表的缓存
        self.search_results = []  # 当前搜索结果
        
        # 初始化UI
        self._setup_ui()
        self._setup_connections()
        
        # 加载初始数据
        self._load_initial_assets()
    
    def _setup_ui(self) -> None:
        """设置用户界面（简化版：只支持股票A股）"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 设置大小策略，确保在QFormLayout中能正确显示
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(250)  # 设置最小高度
        
        # 标题区域（使用UIAssetTypeUtils动态获取显示名称）
        display_name = UIAssetTypeUtils.get_display_name(self.current_asset_type)
        title_label = QLabel(f"{display_name}选择")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px 0px;
            }
        """)
        layout.addWidget(title_label)
        self.title_label = title_label  # 保存引用以便后续更新
        
        # 搜索区域
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        search_label = QLabel("搜索:")
        search_label.setFixedWidth(40)
        
        self.search_input = QLineEdit()
        asset_display_name = UIAssetTypeUtils.get_display_name(self.current_asset_type)
        self.search_input.setPlaceholderText(f"输入{asset_display_name}代码或名称（支持模糊匹配）...")
        self.search_input.setClearButtonEnabled(True)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        
        layout.addWidget(search_frame)
        
        # 搜索结果区域
        results_frame = QFrame()
        results_layout = QVBoxLayout(results_frame)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        # 搜索结果列表
        self.results_list = QListWidget()
        self.results_list.setMinimumHeight(150)  # 设置最小高度
        self.results_list.setMaximumHeight(300)  # 设置最大高度
        self.results_list.setAlternatingRowColors(True)
        self.results_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results_list.itemClicked.connect(self._on_result_clicked)
        self.results_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 设置边框和样式，使其更明显
        self.results_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 3px;
                background-color: white;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
        """)
        
        results_layout.addWidget(QLabel(f"搜索结果 ({asset_display_name}):"))
        results_layout.addWidget(self.results_list, 1)  # 添加伸缩因子，确保列表框能自适应大小
        
        layout.addWidget(results_frame)
        
        # 已选择资产显示区域
        selected_frame = QFrame()
        selected_layout = QVBoxLayout(selected_frame)
        selected_layout.setContentsMargins(0, 0, 0, 0)
        
        selected_layout.addWidget(QLabel(f"已选择{asset_display_name}:"))
        
        self.selected_label = QLabel("未选择")
        self.selected_label.setStyleSheet("""
            QLabel {
                background-color: #24f0f0;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                font-weight: bold;
                color: #34495e;
            }
        """)
        
        selected_layout.addWidget(self.selected_label)
        
        layout.addWidget(selected_frame)
    
    def _setup_connections(self) -> None:
        """设置信号连接"""
        # 搜索文本变化
        self.search_input.textChanged.connect(self._on_search_text_changed)
        
        # 回车键搜索
        self.search_input.returnPressed.connect(self._perform_search)
    
    def _load_initial_assets(self) -> None:
        """加载初始资产数据"""
        # 直接加载股票数据（不需要资产类型选择）
        self._load_assets_for_type(self.current_asset_type)
    

    
    def _load_assets_for_type(self, asset_type: AssetType) -> None:
        """为指定资产类型加载资产列表"""
        try:
            # 检查缓存
            cache_key = f"{asset_type.value}_all"
            if cache_key in self.asset_cache:
                self._display_search_results(self.asset_cache[cache_key])
                return
            
            # 异步加载资产列表
            self.search_worker.search_assets("", asset_type)
            
        except Exception as e:
            logger.error(f"加载资产类型 {asset_type.value} 失败: {e}")
    
    @pyqtSlot(str)
    def _on_search_text_changed(self, text: str) -> None:
        """处理搜索文本变化"""
        # 清除之前的定时器
        self.search_timer.stop()
        
        # 设置新的定时器（防抖）
        self.search_timer.start(300)  # 300ms延迟
    
    def _perform_search(self) -> None:
        """执行搜索"""
        try:
            search_text = self.search_input.text().strip()
            self.current_search_text = search_text
            
            # 如果搜索文本为空，显示所有资产
            if not search_text:
                self._load_assets_for_type(self.current_asset_type)
                return
            
            # 执行异步搜索
            self.search_worker.search_assets(search_text, self.current_asset_type)
            
        except Exception as e:
            logger.error(f"执行搜索失败: {e}")
    
    @pyqtSlot(list)
    def _on_search_completed(self, assets: List[Dict[str, Any]]) -> None:
        """处理搜索完成"""
        try:
            logger.info(f"收到搜索完成信号，资产数量: {len(assets)}")
            self.search_results = assets
            
            # 缓存搜索结果
            cache_key = f"{self.current_asset_type.value}_{self.current_search_text}"
            self.asset_cache[cache_key] = assets
            
            # 显示搜索结果
            logger.info(f"准备显示搜索结果，资产数量: {len(assets)}")
            self._display_search_results(assets)
            
            logger.info(f"搜索完成，找到 {len(assets)} 个资产")
            
        except Exception as e:
            logger.error(f"处理搜索结果失败: {e}")
            import traceback
            traceback.print_exc()
    
    @pyqtSlot(str)
    def _on_search_error(self, error_message: str) -> None:
        """处理搜索错误"""
        logger.error(f"搜索失败: {error_message}")
        QMessageBox.warning(self, "搜索错误", f"搜索资产失败: {error_message}")
    
    def _display_search_results(self, assets: List[Dict[str, Any]]) -> None:
        """显示搜索结果"""
        try:            
            # 清空列表
            self.results_list.clear()
            
            # 添加搜索结果
            for i, asset in enumerate(assets):
                item = QListWidgetItem(asset['display'])
                item.setData(Qt.UserRole, asset)  # 存储完整的资产数据
                self.results_list.addItem(item)
            
            # 如果没有结果，显示提示信息
            if not assets:
                logger.info("没有找到匹配的资产，显示提示信息")
                item = QListWidgetItem("没有找到匹配的资产")
                item.setFlags(Qt.NoItemFlags)
                item.setTextAlignment(Qt.AlignCenter)
                self.results_list.addItem(item)
            
            # 强制更新UI
            self.results_list.update()
            self.results_list.repaint()
            
            logger.info(f"显示搜索结果完成，当前列表项数量: {self.results_list.count()}")
            
        except Exception as e:
            logger.error(f"显示搜索结果失败: {e}")
            import traceback
            traceback.print_exc()
    
    @pyqtSlot(QListWidgetItem)
    def _on_result_clicked(self, item: QListWidgetItem) -> None:
        """处理搜索结果点击"""
        try:
            # 获取资产数据
            asset_data = item.data(Qt.UserRole)
            if not asset_data:
                return
            
            # 更新选择显示
            self.selected_label.setText(asset_data['display'])
            self.selected_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e8;
                    border: 2px solid #4CAF50;
                    border-radius: 3px;
                    padding: 5px;
                    font-weight: bold;
                    color: #2E7D32;
                }
            """)
            
            # 发射选择信号
            self.asset_selected.emit(asset_data)
            
            logger.info(f"已选择资产: {asset_data['display']}")
            
        except Exception as e:
            logger.error(f"处理资产选择失败: {e}")
    
    def get_selected_asset(self) -> Optional[Dict[str, Any]]:
        """获取当前选择的资产"""
        try:
            # 首先尝试从当前搜索结果中获取
            for asset in self.search_results:
                if asset['display'] == self.selected_label.text():
                    return asset
            
            # 如果搜索结果中没有，尝试从缓存中获取
            cache_key = f"{self.current_asset_type.value}_all"
            if cache_key in self.asset_cache:
                for asset in self.asset_cache[cache_key]:
                    if asset['display'] == self.selected_label.text():
                        return asset
            
            # 如果仍然没有找到，检查是否是默认的"未选择"状态
            if self.selected_label.text() == "未选择":
                return None
                
            return None
            
        except Exception as e:
            logger.error(f"获取选择资产失败: {e}")
            return None
    
    def set_selected_asset(self, asset_code: str) -> bool:
        """设置选中的资产"""
        try:
            # 在当前搜索结果中查找
            for asset in self.search_results:
                if asset['code'] == asset_code:
                    self.selected_label.setText(asset['display'])
                    self.asset_selected.emit(asset)
                    return True
            
            # 如果当前搜索结果中没有，尝试从缓存中加载
            cache_key = f"{self.current_asset_type.value}_all"
            if cache_key in self.asset_cache:
                for asset in self.asset_cache[cache_key]:
                    if asset['code'] == asset_code:
                        self.selected_label.setText(asset['display'])
                        self.asset_selected.emit(asset)
                        return True
            
            logger.warning(f"未找到资产代码: {asset_code}")
            return False
            
        except Exception as e:
            logger.error(f"设置选中资产失败: {e}")
            return False
    
    def clear_selection(self) -> None:
        """清空选择"""
        self.selected_label.setText("未选择")
        self.selected_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                font-weight: bold;
            }
        """)
    
    def get_current_asset_type(self) -> AssetType:
        """获取当前资产类型"""
        return self.current_asset_type
    
    def sizeHint(self) -> QSize:
        """返回组件的建议大小"""
        # 确保在QFormLayout中能正确显示，设置合适的高度
        return QSize(400, 350)  # 宽度400，高度350，确保有足够空间显示搜索结果
    
    def minimumSizeHint(self) -> QSize:
        """返回组件的最小建议大小"""
        return QSize(300, 250)  # 最小宽度300，最小高度250