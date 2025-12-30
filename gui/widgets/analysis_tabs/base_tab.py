import csv
import json
from loguru import logger
"""
分析标签页基类 - 增强版
"""
from typing import Dict, Any, List, Optional, Callable, Union
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QKeySequence
import pandas as pd
import time
import traceback
from datetime import datetime
from utils.config_manager import ConfigManager
from utils.cache import Cache
from utils.trace_context import get_trace_id, set_trace_id
from core.performance import measure_performance

class BaseAnalysisTab(QWidget):
    """分析标签页基类 - 增强版"""

    # 定义信号
    analysis_completed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    data_updated = pyqtSignal(dict)  # 新增：数据更新信号
    progress_updated = pyqtSignal(int, str)  # 新增：进度更新信号

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """初始化基类

        Args:
            config_manager: 配置管理器
        """
        super().__init__()

        # 使用统一的管理器工厂
        from utils.manager_factory import get_config_manager
        self.config_manager = config_manager or get_config_manager()
        # 纯Loguru架构，移除log_manager依赖

        self.data_cache = Cache(cache_dir=".cache/data", default_ttl=30*60)

        # 数据状态
        self.current_kdata = None
        self.last_update_time = None
        self.data_hash = None  # 用于检测数据变化

        # 运行状态
        self.is_loading = False
        self.is_initialized = False

        # 初始化安全错误处理（但不自动连接）
        # 子类可以调用 self._init_safe_error_handling() 来启用
        self.analysis_count = 0  # 分析次数统计

        # 性能监控
        self.performance_stats = {
            'total_analysis_time': 0.0,
            'avg_analysis_time': 0.0,
            'last_analysis_time': 0.0,
            'error_count': 0
        }

        # 安全初始化UI
        try:
            self.create_ui()
            self.is_initialized = True
            logger.debug(f"{self.__class__.__name__} 初始化成功")
        except Exception as e:
            logger.error(f"{self.__class__.__name__} 初始化失败: {e}")
            self.error_occurred.emit(f"初始化失败: {str(e)}")

    def create_ui(self):
        """创建用户界面 - 子类需要重写"""
        raise NotImplementedError("子类必须实现create_ui方法")

    def set_kdata(self, kdata):
        """设置K线数据 - 增强版（异步优化）

        Args:
            kdata: K线数据
        """
        try:
            # 数据验证
            if not self._validate_kdata(kdata):
                logger.warning(f"{self.__class__.__name__}: 无效的K线数据")
                return

            # 检测数据是否变化
            new_hash = self._calculate_data_hash(kdata)
            if new_hash == self.data_hash:
                logger.debug(
                    f"{self.__class__.__name__}: 数据未变化，跳过更新")
                return

            # 更新数据
            self.current_kdata = kdata
            self.kdata = kdata  # 为兼容性设置kdata属性
            self.data_hash = new_hash
            self.last_update_time = datetime.now()

            # 发射数据更新信号
            self.data_updated.emit({
                'timestamp': self.last_update_time.isoformat(),
                'data_length': len(kdata) if hasattr(kdata, '__len__') else 0,
                'data_type': type(kdata).__name__
            })

            # 异步刷新数据，避免阻塞UI线程
            self._schedule_async_refresh()

        except Exception as e:
            logger.error(f"{self.__class__.__name__} 设置K线数据失败: {e}")
            self.error_occurred.emit(f"设置K线数据失败: {str(e)}")

    def append_kdata(self, new_data) -> None:
        """
        渐进式追加K线数据（用于渐进式加载）

        参数:
            new_data: 新的数据块
        """
        try:
            if not self._validate_kdata(new_data):
                logger.warning(f"{self.__class__.__name__}: 追加数据验证失败")
                return

            if self.current_kdata is None:
                # 如果没有现有数据，直接设置
                self.set_kdata(new_data)
                return

            # 合并数据
            if isinstance(self.current_kdata, pd.DataFrame) and isinstance(new_data, pd.DataFrame):
                # 对于pandas DataFrame，使用concat
                self.current_kdata = pd.concat([self.current_kdata, new_data], ignore_index=True)
                self.kdata = self.current_kdata  # 保持兼容性
            elif hasattr(self.current_kdata, 'extend') and hasattr(new_data, '__iter__'):
                # 对于列表等可迭代对象
                self.current_kdata.extend(new_data)
                self.kdata = self.current_kdata
            else:
                # 其他情况，尝试转换为列表处理
                if not isinstance(self.current_kdata, list):
                    self.current_kdata = [self.current_kdata]
                if isinstance(new_data, list):
                    self.current_kdata.extend(new_data)
                else:
                    self.current_kdata.append(new_data)
                self.kdata = self.current_kdata

            # 更新元数据
            self.last_update_time = datetime.now()
            self.data_hash = self._calculate_data_hash(self.current_kdata)

            # 发射追加数据信号
            self.data_updated.emit({
                'timestamp': self.last_update_time.isoformat(),
                'data_length': len(self.current_kdata) if hasattr(self.current_kdata, '__len__') else 0,
                'data_type': type(self.current_kdata).__name__,
                'operation': 'append'
            })

            # 轻量级刷新（仅更新新增部分）
            self._schedule_incremental_refresh(new_data)

        except Exception as e:
            logger.error(f"{self.__class__.__name__} 追加K线数据失败: {e}")
            self.error_occurred.emit(f"追加K线数据失败: {str(e)}")

    def _schedule_incremental_refresh(self, new_data):
        """调度增量刷新（仅刷新新增数据部分）"""
        try:
            # 如果子类实现了增量刷新方法，使用它
            if hasattr(self, 'refresh_incremental'):
                QTimer.singleShot(50, lambda: self.refresh_incremental(new_data))
            else:
                # 否则使用完整刷新
                self._schedule_async_refresh()

        except Exception as e:
            logger.error(f"调度增量刷新失败: {e}")
            # 回退到完整刷新
            self._schedule_async_refresh()

    def _schedule_async_refresh(self):
        """异步调度数据刷新，避免阻塞UI线程"""
        try:
            # 取消之前的刷新任务
            if hasattr(self, '_refresh_timer'):
                self._refresh_timer.stop()

            # 创建单次定时器，延迟执行刷新
            from PyQt5.QtCore import QTimer
            self._refresh_timer = QTimer()
            self._refresh_timer.setSingleShot(True)
            self._refresh_timer.timeout.connect(self._async_refresh_data)

            # 延迟100ms执行，让UI有机会响应
            self._refresh_timer.start(100)

            logger.debug(f"{self.__class__.__name__}: 已调度异步刷新")

        except Exception as e:
            logger.error(f"调度异步刷新失败: {e}")
            # 如果异步调度失败，回退到同步刷新
            self.refresh_data()

    def _async_refresh_data(self):
        """异步刷新数据的实际执行方法"""
        try:
            logger.debug(f"{self.__class__.__name__}: 开始异步刷新数据")
            self.refresh_data()
        except Exception as e:
            logger.error(f"异步刷新数据失败: {e}")
            self.error_occurred.emit(f"异步刷新数据失败: {str(e)}")

    def _validate_kdata(self, kdata) -> bool:
        """验证K线数据有效性 - 使用统一验证模块"""
        try:
            # 使用统一的数据验证模块
            from utils.data_preprocessing import validate_kdata
            return validate_kdata(kdata, context=f"{self.__class__.__name__}验证")
        except ImportError:
            # 如果统一模块不可用，使用简化验证
            return self._validate_kdata_fallback(kdata)
        except Exception as e:
            # 安全的日志记录，避免LogManager被删除的问题
            try:
                logger.error(f"数据验证失败: {e}")
            except:
                logger.info(f"[{self.__class__.__name__}] 数据验证失败: {e}")
            return False

    def _validate_kdata_fallback(self, kdata) -> bool:
        """简化的数据验证 - 作为后备方案"""
        if kdata is None:
            return False

        # 检查pandas DataFrame
        if isinstance(kdata, pd.DataFrame):
            if kdata.empty:
                return False
            # 检查必要的列
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [
                col for col in required_columns if col not in kdata.columns]
            if missing_columns:
                logger.warning(f"缺少必要列: {missing_columns}")
                return False
            return True

        # 检查其他数据类型
        if hasattr(kdata, '__len__') and len(kdata) == 0:
            return False

        return True

    def _calculate_data_hash(self, kdata) -> str:
        """计算数据哈希值用于变化检测"""
        try:
            if isinstance(kdata, pd.DataFrame):
                # 使用数据长度和最后几行的哈希
                if len(kdata) > 0:
                    last_rows = kdata.tail(5).to_string()
                    return f"{len(kdata)}_{hash(last_rows)}"
            return str(hash(str(kdata)))
        except Exception:
            return str(time.time())  # fallback

    def refresh_data(self):
        """刷新数据 - 增强版（性能优化）"""
        if not self.is_initialized:
            return

        # 防止重复刷新
        if hasattr(self, '_is_refreshing') and self._is_refreshing:
            logger.debug(f"{self.__class__.__name__}: 正在刷新中，跳过重复请求")
            return

        self._is_refreshing = True
        start_time = time.time()

        try:
            self._do_refresh_data()

            # 更新性能统计
            analysis_time = time.time() - start_time
            self._update_performance_stats(analysis_time)

        except Exception as e:
            self.performance_stats['error_count'] += 1
            logger.error(f"{self.__class__.__name__} 刷新数据失败: {e}")
            self.error_occurred.emit(f"刷新数据失败: {str(e)}")
        finally:
            self._is_refreshing = False

    def _do_refresh_data(self):
        """实际的数据刷新逻辑 - 子类可重写"""
        pass

    def _update_performance_stats(self, analysis_time: float):
        """更新性能统计"""
        self.analysis_count += 1
        self.performance_stats['last_analysis_time'] = analysis_time
        self.performance_stats['total_analysis_time'] += analysis_time
        self.performance_stats['avg_analysis_time'] = (
            self.performance_stats['total_analysis_time'] / self.analysis_count
        )

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return {
            **self.performance_stats,
            'analysis_count': self.analysis_count,
            'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None,
            'is_loading': self.is_loading,
            'data_length': len(self.current_kdata) if self.current_kdata is not None and hasattr(self.current_kdata, '__len__') else 0
        }

    def clear_data(self):
        """清除数据 - 增强版"""
        try:
            self.current_kdata = None
            self.data_hash = None
            self.last_update_time = None
            self._do_clear_data()
            logger.debug(f"{self.__class__.__name__} 数据已清除")
        except Exception as e:
            logger.error(f"{self.__class__.__name__} 清除数据失败: {e}")
            self.error_occurred.emit(f"清除数据失败: {str(e)}")

    def _do_clear_data(self):
        """实际的数据清除逻辑 - 子类可重写"""
        pass

    def show_loading(self, message="正在分析..."):
        """显示加载状态 - 增强版"""
        self.is_loading = True
        if hasattr(self, 'parent_widget') and self.parent_widget:
            self.parent_widget.show_loading(message)
        logger.debug(f"{self.__class__.__name__}: {message}")

    def hide_loading(self):
        """隐藏加载状态 - 增强版"""
        self.is_loading = False
        if hasattr(self, 'parent_widget') and self.parent_widget:
            self.parent_widget.hide_loading()

    def update_loading_progress(self, value: int, message: Optional[str] = None):
        """更新加载进度 - 增强版"""
        if hasattr(self, 'parent_widget') and self.parent_widget:
            self.parent_widget.update_loading_progress(value, message)

        # 发射进度信号
        self.progress_updated.emit(value, message or "")

    def run_analysis_async(self, analysis_func: Callable, *args, **kwargs):
        """异步运行分析函数 - 增强版"""
        if not self.is_initialized:
            self.error_occurred.emit("组件未初始化")
            return None

        if hasattr(self, 'parent_widget') and self.parent_widget:
            return self.parent_widget.run_button_analysis_async(
                None, analysis_func, *args, **kwargs
            )
        else:
            # 如果没有父组件，直接同步执行
            try:
                result = analysis_func(*args, **kwargs)
                self.analysis_completed.emit(result if isinstance(
                    result, dict) else {"result": result})
                return result
            except Exception as e:
                self.error_occurred.emit(f"分析执行失败: {str(e)}")
                return None

    def _kdata_preprocess(self, kdata, context="分析"):
        """K线数据预处理 - 增强版"""
        try:
            # 导入统一的预处理函数
            from utils.data_preprocessing import kdata_preprocess
            return kdata_preprocess(kdata, context)
        except ImportError:
            # 如果导入失败，使用基本的验证
            if not self._validate_kdata(kdata):
                return None
            return kdata
        except Exception as e:
            logger.error(f"数据预处理失败: {e}")
            return None

    def export_data(self, format_type: str = "json") -> Optional[Dict[str, Any]]:
        """导出数据 - 增强版通用方法"""
        try:
            export_data = {
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'tab_type': self.__class__.__name__,
                    'export_format': format_type,
                    'version': '1.0'
                },
                'performance_stats': self.get_performance_stats(),
                'data_info': {
                    'has_data': self.current_kdata is not None,
                    'data_length': len(self.current_kdata) if self.current_kdata is not None and hasattr(self.current_kdata, '__len__') else 0,
                    'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
                    'data_hash': self.data_hash
                },
                'status_info': self.get_status_info()
            }

            # 子类可以重写此方法添加特定数据
            specific_data = self._get_export_specific_data()
            if specific_data:
                export_data['specific_data'] = specific_data

            # 如果有K线数据，添加基本统计信息
            if self.current_kdata is not None and hasattr(self.current_kdata, 'describe'):
                try:
                    export_data['data_statistics'] = self.current_kdata.describe(
                    ).to_dict()
                except Exception:
                    pass

            return export_data

        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            return None

    def _get_export_specific_data(self):
        """获取导出数据 - 子类需要重写此方法"""
        return {}

    def export_to_file(self, filename: str, format_type: str = "json") -> bool:
        """导出数据到文件 - 新增便捷方法"""
        try:
            export_data = self.export_data(format_type)
            if not export_data:
                return False

            if format_type.lower() == "json":
                with open(filename, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
            elif format_type.lower() == "csv":
                # 将嵌套数据展平为CSV格式
                flattened_data = self._flatten_export_data(export_data)
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    if flattened_data:
                        writer = csv.DictWriter(
                            f, fieldnames=flattened_data[0].keys())
                        writer.writeheader()
                        writer.writerows(flattened_data)
            else:
                logger.warning(f"不支持的导出格式: {format_type}")
                return False

            logger.info(f"数据已导出到: {filename}")
            return True

        except Exception as e:
            logger.error(f"导出到文件失败: {e}")
            return False

    def _flatten_export_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将嵌套的导出数据展平为CSV格式"""
        try:
            flattened = []

            def flatten_dict(d, parent_key='', sep='_'):
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    elif isinstance(v, list):
                        # 对于列表，只取前几个元素或转为字符串
                        if len(v) > 0 and isinstance(v[0], dict):
                            # 如果是字典列表，只取第一个
                            items.extend(flatten_dict(
                                v[0], new_key, sep=sep).items())
                        else:
                            items.append((new_key, str(v)))
                    else:
                        items.append((new_key, v))
                return dict(items)

            flat_data = flatten_dict(data)
            flattened.append(flat_data)

            return flattened

        except Exception as e:
            logger.error(f"数据展平失败: {e}")
            return []

    def reset_performance_stats(self):
        """重置性能统计"""
        self.performance_stats = {
            'total_analysis_time': 0.0,
            'avg_analysis_time': 0.0,
            'last_analysis_time': 0.0,
            'error_count': 0
        }
        self.analysis_count = 0
        logger.info(f"{self.__class__.__name__} 性能统计已重置")

    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            'class_name': self.__class__.__name__,
            'is_initialized': self.is_initialized,
            'is_loading': self.is_loading,
            'has_data': self.current_kdata is not None,
            'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
            'analysis_count': self.analysis_count,
            'performance': self.get_performance_stats()
        }

    # 统一的警告消息处理方法
    def show_warning(self, message: str, title: str = "警告"):
        """显示统一的警告消息框

        Args:
            message: 警告消息内容
            title: 警告标题，默认为"警告"
        """
        try:
            QMessageBox.warning(self, title, message)
            logger.warning(f"{self.__class__.__name__}: {message}")
        except Exception as e:
            logger.error(f"显示警告消息失败: {e}")

    def show_kdata_warning(self):
        """显示K线数据无效的标准警告"""
        self.show_warning("请先加载有效的K线数据")

    def show_no_data_warning(self, data_type: str = "数据"):
        """显示无数据可导出的标准警告

        Args:
            data_type: 数据类型描述，如"技术分析数据"、"形态数据"等
        """
        self.show_warning(f"没有可导出的{data_type}")

    def show_library_warning(self, library_name: str, feature_name: str = "功能"):
        """显示缺少依赖库的标准警告

        Args:
            library_name: 库名称
            feature_name: 功能名称
        """
        self.show_warning(f"需要安装{library_name}库才能使用{feature_name}")

    def show_selection_warning(self, item_type: str = "项目"):
        """显示未选择项目的标准警告

        Args:
            item_type: 项目类型，如"形态"、"指标"等
        """
        self.show_warning(f"请先选择要操作的{item_type}")

    def validate_kdata_with_warning(self) -> bool:
        """验证K线数据并在无效时显示警告

        Returns:
            bool: 数据是否有效
        """
        if not self._validate_kdata(self.current_kdata):
            self.show_kdata_warning()
            return False
        return True

    # 统一表格操作方法
    def create_standard_table(self, columns: list, parent=None) -> QTableWidget:
        """创建标准表格"""
        table = QTableWidget(0, len(columns), parent)
        table.setHorizontalHeaderLabels(columns)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSortingEnabled(True)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def update_table_data(self, table: QTableWidget, data: list, column_keys: list = None):
        """统一更新表格数据 - 增强版（过滤空值）

        Args:
            table: 要更新的表格
            data: 数据列表，每个元素为字典或列表
            column_keys: 如果data元素为字典，指定要显示的键的顺序
        """
        if not data:
            table.setRowCount(0)
            return

        # 过滤掉完全为空的数据行
        valid_data = []
        for item in data:
            if isinstance(item, dict):
                # 检查字典是否有有效值
                has_valid_data = False
                for key, value in item.items():
                    if value is not None and str(value).strip() != '' and str(value) != 'N/A':
                        has_valid_data = True
                        break
                if has_valid_data:
                    valid_data.append(item)
            elif isinstance(item, (list, tuple)):
                # 检查列表是否有有效值
                has_valid_data = any(
                    value is not None and str(value).strip() != '' and str(value) != 'N/A'
                    for value in item
                )
                if has_valid_data:
                    valid_data.append(item)

        if not valid_data:
            table.setRowCount(0)
            return

        table.setRowCount(len(valid_data))

        for row, item in enumerate(valid_data):
            if isinstance(item, dict):
                # 字典数据
                if column_keys:
                    for col, key in enumerate(column_keys):
                        value = item.get(key, '')

                        # 处理空值和None值
                        if value is None or str(value).strip() == '':
                            text = "--"
                        elif isinstance(value, (int, float)):
                            if isinstance(value, float):
                                text = f"{value:.2f}" if abs(
                                    value) < 1000 else f"{value:.0f}"
                            else:
                                text = str(value)
                        else:
                            text = str(value) if str(value) != 'N/A' else "--"

                        table.setItem(row, col, QTableWidgetItem(text))
                else:
                    # 使用字典的值顺序
                    for col, value in enumerate(item.values()):
                        if col >= table.columnCount():
                            break

                        # 处理空值
                        if value is None or str(value).strip() == '':
                            text = "--"
                        elif isinstance(value, (int, float)):
                            text = f"{value:.2f}" if isinstance(value, float) else str(value)
                        else:
                            text = str(value) if str(value) != 'N/A' else "--"

                        table.setItem(row, col, QTableWidgetItem(text))
            elif isinstance(item, (list, tuple)):
                # 列表数据
                for col, value in enumerate(item):
                    if col >= table.columnCount():
                        break

                    # 处理空值
                    if value is None or str(value).strip() == '':
                        text = "--"
                    elif isinstance(value, (int, float)):
                        text = f"{value:.2f}" if isinstance(value, float) else str(value)
                    else:
                        text = str(value) if str(value) != 'N/A' else "--"

                    table.setItem(row, col, QTableWidgetItem(text))
                else:
                    # 使用字典的值顺序
                    for col, value in enumerate(item.values()):
                        if col >= table.columnCount():
                            break
                        text = str(value) if not isinstance(
                            value, (int, float)) else f"{value:.2f}"
                        table.setItem(row, col, QTableWidgetItem(text))
            elif isinstance(item, (list, tuple)):
                # 列表数据
                for col, value in enumerate(item):
                    if col >= table.columnCount():
                        break
                    text = str(value) if not isinstance(
                        value, (int, float)) else f"{value:.2f}"
                    table.setItem(row, col, QTableWidgetItem(text))

    def clear_table(self, table: QTableWidget):
        """清空表格"""
        table.setRowCount(0)

    def clear_multiple_tables(self, *tables: QTableWidget):
        """清空多个表格"""
        for table in tables:
            if table:
                self.clear_table(table)

    def get_table_data_for_export(self, table: QTableWidget) -> list:
        """获取表格数据用于导出"""
        data = []

        # 获取表头
        headers = []
        for col in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col)
            headers.append(header_item.text()
                           if header_item else f"Column {col}")
        data.append(headers)

        # 获取数据行
        for row in range(table.rowCount()):
            row_data = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                row_data.append(item.text() if item else "")
            data.append(row_data)

        return data

    def export_table_to_csv(self, table: QTableWidget, filename: str):
        """导出表格到CSV文件"""

        data = self.get_table_data_for_export(table)

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(data)

    def set_table_column_widths(self, table: QTableWidget, widths: list):
        """设置表格列宽"""
        for col, width in enumerate(widths):
            if col < table.columnCount():
                table.setColumnWidth(col, width)

    # 统一状态栏操作方法
    def create_standard_status_bar(self, parent_layout=None) -> QFrame:
        """创建标准状态栏

        Args:
            parent_layout: 如果提供，会自动添加到布局中

        Returns:
            QFrame: 状态栏框架
        """
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.StyledPanel)
        status_layout = QHBoxLayout(status_frame)

        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)

        if parent_layout:
            parent_layout.addWidget(status_frame)

        return status_frame

    def update_status(self, message: str):
        """更新状态信息"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)

    def show_progress(self, visible: bool = True):
        """显示/隐藏进度条"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(visible)

    def set_progress_value(self, value: int):
        """设置进度条值"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(value)

    def set_progress_range(self, minimum: int, maximum: int):
        """设置进度条范围"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setRange(minimum, maximum)

    # 统一样式管理方法
    def get_button_style(self, color: str, hover_factor: float = 0.1, pressed_factor: float = 0.2) -> str:
        """获取统一的按钮样式

        Args:
            color: 按钮主色调
            hover_factor: 悬停时颜色加深因子
            pressed_factor: 按下时颜色加深因子

        Returns:
            str: CSS样式字符串
        """
        hover_color = self.darken_color(color, hover_factor)
        pressed_color = self.darken_color(color, pressed_factor)

        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {color}, stop:1 {hover_color});
                color: white; font-weight: bold; padding: 8px 16px;
                border-radius: 6px; border: none; min-width: 120px;
            }}
            QPushButton:hover {{ background: {hover_color}; }}
            QPushButton:pressed {{ background: {pressed_color}; }}
        """

    def darken_color(self, color: str, factor: float = 0.1) -> str:
        """颜色加深处理

        Args:
            color: 原始颜色（支持#RRGGBB格式）
            factor: 加深因子（0-1之间）

        Returns:
            str: 加深后的颜色
        """
        if not color.startswith('#') or len(color) != 7:
            return color  # 如果不是标准格式，直接返回

        try:
            # 提取RGB值
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)

            # 加深处理
            r = max(0, int(r * (1 - factor)))
            g = max(0, int(g * (1 - factor)))
            b = max(0, int(b * (1 - factor)))

            return f"#{r:02x}{g:02x}{b:02x}"
        except ValueError:
            return color  # 如果解析失败，返回原色

    def create_styled_button(self, text: str, color: str, callback=None) -> QPushButton:
        """创建带样式的按钮

        Args:
            text: 按钮文本
            color: 按钮颜色
            callback: 点击回调函数

        Returns:
            QPushButton: 样式化的按钮
        """
        button = QPushButton(text)
        button.setStyleSheet(self.get_button_style(color))

        if callback:
            button.clicked.connect(callback)

        return button

    def create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """创建统计卡片

        Args:
            title: 卡片标题
            value: 显示值
            color: 主题色

        Returns:
            QFrame: 统计卡片
        """
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel)

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 12px; color: #6c757d;")

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {color};")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        # 保存值标签引用，便于后续更新
        card.value_label = value_label

        return card

    def get_standard_colors(self) -> dict:
        """获取标准颜色方案"""
        return {
            'primary': '#1976D2',
            'secondary': '#424242',
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#F44336',
            'info': '#2196F3',
            'light': '#F5F5F5',
            'dark': '#212121'
        }

    # ==================== 第九轮优化：布局创建统一化 ====================

    def create_standard_layout(self, layout_type: str = "vbox", spacing: int = 10, margins: tuple = None) -> QLayout:
        """创建标准布局

        Args:
            layout_type: 布局类型 ('vbox', 'hbox', 'grid')
            spacing: 间距
            margins: 边距 (left, top, right, bottom)

        Returns:
            QLayout: 创建的布局对象
        """
        if layout_type.lower() == 'vbox':
            layout = QVBoxLayout()
        elif layout_type.lower() == 'hbox':
            layout = QHBoxLayout()
        elif layout_type.lower() == 'grid':
            layout = QGridLayout()
        else:
            raise ValueError(f"不支持的布局类型: {layout_type}")

        layout.setSpacing(spacing)
        if margins:
            layout.setContentsMargins(*margins)

        return layout

    def create_button_layout(self, buttons: list, spacing: int = 10, alignment: str = "left") -> QHBoxLayout:
        """创建按钮布局

        Args:
            buttons: 按钮列表 [(text, callback, style_color), ...]
            spacing: 按钮间距
            alignment: 对齐方式 ('left', 'center', 'right')

        Returns:
            QHBoxLayout: 按钮布局
        """
        button_layout = QHBoxLayout()
        button_layout.setSpacing(spacing)

        if alignment == "center":
            button_layout.addStretch()

        for button_info in buttons:
            if len(button_info) >= 2:
                text, callback = button_info[:2]
                color = button_info[2] if len(button_info) > 2 else '#1976D2'

                button = self.create_styled_button(text, color, callback)
                button_layout.addWidget(button)

        if alignment in ["center", "right"]:
            button_layout.addStretch()

        return button_layout

    def create_cards_layout(self, cards_data: list, columns: int = 3) -> QGridLayout:
        """创建卡片网格布局

        Args:
            cards_data: 卡片数据 [(title, value, color, trend), ...]
            columns: 每行卡片数量

        Returns:
            QGridLayout: 卡片布局
        """
        cards_layout = QGridLayout()
        cards_layout.setSpacing(15)

        for i, card_data in enumerate(cards_data):
            if len(card_data) >= 3:
                title, value, color = card_data[:3]
                trend = card_data[3] if len(card_data) > 3 else None

                card = self.create_stat_card(title, value, color)

                # 如果有趋势信息，添加趋势标签
                if trend:
                    card_layout = card.layout()
                    if card_layout:
                        trend_label = QLabel(trend)
                        trend_label.setStyleSheet(
                            f"color: {color}; font-size: 16px; font-weight: bold;")
                        card_layout.addWidget(trend_label)

                row = i // columns
                col = i % columns
                cards_layout.addWidget(card, row, col)

        return cards_layout

    def create_control_buttons_layout(self, include_export: bool = True, include_alert: bool = True,
                                      custom_buttons: list = None) -> QHBoxLayout:
        """创建标准控制按钮布局

        Args:
            include_export: 是否包含导出按钮
            include_alert: 是否包含预警按钮
            custom_buttons: 自定义按钮 [(text, callback, color), ...]

        Returns:
            QHBoxLayout: 控制按钮布局
        """
        buttons = []

        if include_export:
            buttons.append(("导出数据", self.export_results, '#4CAF50'))

        if include_alert:
            buttons.append(("设置预警", self.show_alert_dialog, '#FF9800'))

        if custom_buttons:
            buttons.extend(custom_buttons)

        return self.create_button_layout(buttons)

    def show_alert_dialog(self):
        """显示预警设置对话框 - 默认实现"""
        self.show_info_message("预警功能", "预警功能正在开发中，敬请期待！")

    # ==================== 第九轮优化：对话框管理统一化 ====================

    def show_info_message(self, title: str, message: str, parent=None) -> int:
        """显示信息消息框

        Args:
            title: 对话框标题
            message: 消息内容
            parent: 父窗口

        Returns:
            int: 用户选择结果
        """
        if parent is None:
            parent = self

        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Ok)

        # 应用样式
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: white;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #1565C0;
            }
        """)

        return msg_box.exec_()

    def show_warning_message(self, title: str, message: str, parent=None) -> int:
        """显示警告消息框"""
        if parent is None:
            parent = self

        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: white;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #F57C00;
            }
        """)

        return msg_box.exec_()

    def show_error_message(self, title: str, message: str, parent=None) -> int:
        """显示错误消息框"""
        if parent is None:
            parent = self

        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: white;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #D32F2F;
            }
        """)

        return msg_box.exec_()

    def show_question_message(self, title: str, message: str, parent=None) -> int:
        """显示询问消息框

        Returns:
            int: QMessageBox.Yes 或 QMessageBox.No
        """
        if parent is None:
            parent = self

        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: white;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QMessageBox QPushButton[text="Yes"] {
                background-color: #4CAF50;
            }
            QMessageBox QPushButton[text="Yes"]:hover {
                background-color: #45A049;
            }
            QMessageBox QPushButton[text="No"] {
                background-color: #F44336;
            }
            QMessageBox QPushButton[text="No"]:hover {
                background-color: #D32F2F;
            }
        """)

        return msg_box.exec_()

    def create_standard_dialog(self, title: str, width: int = 600, height: int = 400, parent=None) -> QDialog:
        """创建标准对话框

        Args:
            title: 对话框标题
            width: 对话框宽度
            height: 对话框高度
            parent: 父窗口

        Returns:
            QDialog: 创建的对话框
        """
        if parent is None:
            parent = self

        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(width, height)
        dialog.setModal(True)

        # 应用样式
        dialog.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 8px;
            }
            QDialog QLabel {
                color: #333333;
                font-size: 12px;
            }
            QDialog QLineEdit, QDialog QTextEdit, QDialog QComboBox {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }
            QDialog QLineEdit:focus, QDialog QTextEdit:focus, QDialog QComboBox:focus {
                border-color: #1976D2;
            }
        """)

        return dialog

    def create_dialog_button_box(self, buttons: str = "ok_cancel") -> QDialogButtonBox:
        """创建对话框按钮框

        Args:
            buttons: 按钮类型 ('ok', 'ok_cancel', 'yes_no', 'save_cancel')

        Returns:
            QDialogButtonBox: 按钮框
        """
        if buttons == "ok":
            button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        elif buttons == "ok_cancel":
            button_box = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        elif buttons == "yes_no":
            button_box = QDialogButtonBox(
                QDialogButtonBox.Yes | QDialogButtonBox.No)
        elif buttons == "save_cancel":
            button_box = QDialogButtonBox(
                QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        else:
            button_box = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        # 应用样式
        button_box.setStyleSheet("""
            QDialogButtonBox QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
                font-size: 12px;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #1565C0;
            }
            QDialogButtonBox QPushButton[text="Cancel"], 
            QDialogButtonBox QPushButton[text="No"] {
                background-color: #757575;
            }
            QDialogButtonBox QPushButton[text="Cancel"]:hover,
            QDialogButtonBox QPushButton[text="No"]:hover {
                background-color: #616161;
            }
        """)

        return button_box

    def center_dialog(self, dialog: QDialog, parent=None, offset_y: int = 50):
        """居中显示对话框

        Args:
            dialog: 要居中的对话框
            parent: 父窗口
            offset_y: Y轴偏移量
        """
        if parent is None:
            parent = self

        # 获取父窗口的几何信息
        if hasattr(parent, 'geometry'):
            parent_rect = parent.geometry()
        else:
            # 如果没有父窗口，使用屏幕中心
            screen = QApplication.primaryScreen()
            parent_rect = screen.availableGeometry()

        # 计算对话框位置
        dialog_rect = dialog.geometry()
        x = parent_rect.x() + (parent_rect.width() - dialog_rect.width()) // 2
        y = parent_rect.y() + (parent_rect.height() - dialog_rect.height()) // 2 - offset_y

        dialog.move(x, y)

    # ==================== 第九轮优化：文件操作统一化 ====================

    def show_save_file_dialog(self, title: str = "保存文件",
                              default_name: str = "",
                              file_filter: str = "所有文件 (*.*)") -> str:
        """显示保存文件对话框

        Args:
            title: 对话框标题
            default_name: 默认文件名
            file_filter: 文件过滤器

        Returns:
            str: 选择的文件路径，如果取消则返回空字符串
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self, title, default_name, file_filter
        )
        return file_path

    def show_open_file_dialog(self, title: str = "打开文件",
                              file_filter: str = "所有文件 (*.*)") -> str:
        """显示打开文件对话框

        Args:
            title: 对话框标题
            file_filter: 文件过滤器

        Returns:
            str: 选择的文件路径，如果取消则返回空字符串
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, title, "", file_filter
        )
        return file_path

    def export_data_to_file(self, data, file_path: str) -> bool:
        """导出数据到文件

        Args:
            data: 要导出的数据
            file_path: 文件路径

        Returns:
            bool: 是否导出成功
        """
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            elif file_path.endswith('.csv'):
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    df.to_csv(file_path, index=False, encoding='utf-8-sig')
                else:
                    # 如果数据不是列表格式，尝试转换
                    df = pd.DataFrame(
                        [data] if isinstance(data, dict) else data)
                    df.to_csv(file_path, index=False, encoding='utf-8-sig')

            elif file_path.endswith('.xlsx'):
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    df.to_excel(file_path, index=False)
                else:
                    df = pd.DataFrame(
                        [data] if isinstance(data, dict) else data)
                    df.to_excel(file_path, index=False)

            else:
                # 默认保存为文本文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(data))

            logger.info(f"数据已导出到: {file_path}")
            return True

        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            return False

    # ==================== 第十轮优化：线程管理统一化 ====================

    def create_data_update_thread(self, data_fetcher: Callable, update_interval: int = 60,
                                  max_retries: int = 3, retry_interval: int = 5) -> 'BaseDataUpdateThread':
        """创建统一的数据更新线程

        Args:
            data_fetcher: 数据获取函数
            update_interval: 更新间隔（秒）
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）

        Returns:
            BaseDataUpdateThread: 数据更新线程实例
        """
        thread = BaseDataUpdateThread(
            data_fetcher=data_fetcher,
            update_interval=update_interval,
            max_retries=max_retries,
            retry_interval=retry_interval
        )

        # 连接信号
        thread.data_updated.connect(self._on_data_updated)
        thread.error_occurred.connect(self._on_thread_error)
        thread.status_changed.connect(self._on_thread_status_changed)

        return thread

    def create_analysis_thread(self, analysis_func: Callable, *args, **kwargs) -> 'BaseAnalysisThread':
        """创建统一的分析线程

        Args:
            analysis_func: 分析函数
            *args: 分析函数参数
            **kwargs: 分析函数关键字参数

        Returns:
            BaseAnalysisThread: 分析线程实例
        """
        thread = BaseAnalysisThread(
            analysis_func=analysis_func,
            args=args,
            kwargs=kwargs
        )

        # 连接信号
        thread.analysis_completed.connect(self._on_analysis_completed)
        thread.error_occurred.connect(self._on_thread_error)
        thread.progress_updated.connect(self._on_thread_progress_updated)

        return thread

    def create_export_thread(self, export_func: Callable, file_path: str, data) -> 'BaseExportThread':
        """创建统一的导出线程

        Args:
            export_func: 导出函数
            file_path: 文件路径
            data: 要导出的数据

        Returns:
            BaseExportThread: 导出线程实例
        """
        thread = BaseExportThread(
            export_func=export_func,
            file_path=file_path,
            data=data
        )

        # 连接信号
        thread.export_completed.connect(self._on_export_completed)
        thread.error_occurred.connect(self._on_thread_error)
        thread.progress_updated.connect(self._on_thread_progress_updated)

        return thread

    def _on_data_updated(self, data: dict):
        """数据更新完成处理"""
        try:
            self.data_updated.emit(data)
            logger.info("数据更新完成")
        except Exception as e:
            logger.error(f"处理数据更新失败: {e}")

    def _on_analysis_completed(self, results: dict):
        """分析完成处理"""
        try:
            self.analysis_completed.emit(results)
            self.hide_loading()
            logger.info("分析完成")
        except Exception as e:
            logger.error(f"处理分析完成失败: {e}")

    def _on_export_completed(self, file_path: str):
        """导出完成处理"""
        try:
            self.show_info_message("导出成功", f"数据已导出到: {file_path}")
            logger.info(f"导出完成: {file_path}")
        except Exception as e:
            logger.error(f"处理导出完成失败: {e}")

    def _on_thread_error(self, error_msg: str):
        """线程错误处理"""
        try:
            self.error_occurred.emit(error_msg)
            self.hide_loading()
            logger.error(f"线程错误: {error_msg}")
        except Exception as e:
            logger.error(f"处理线程错误失败: {e}")

    def _on_thread_status_changed(self, status: str):
        """线程状态变化处理"""
        try:
            if hasattr(self, 'status_label'):
                self.status_label.setText(status)
            logger.debug(f"线程状态: {status}")
        except Exception as e:
            logger.error(f"处理线程状态变化失败: {e}")

    def _on_thread_progress_updated(self, progress: int, message: str = ""):
        """线程进度更新处理"""
        try:
            self.progress_updated.emit(progress, message)
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setValue(progress)
            if message and hasattr(self, 'status_label'):
                self.status_label.setText(message)
        except Exception as e:
            logger.error(f"处理线程进度更新失败: {e}")

# ==================== 统一线程基类 ====================

class BaseDataUpdateThread(QThread):
    """统一的数据更新线程基类"""

    data_updated = pyqtSignal(dict)  # 数据更新信号
    error_occurred = pyqtSignal(str)  # 错误信号
    status_changed = pyqtSignal(str)  # 状态信号

    def __init__(self, data_fetcher: Callable, update_interval: int = 60,
                 max_retries: int = 3, retry_interval: int = 5):
        super().__init__()
        self.data_fetcher = data_fetcher
        self.update_interval = update_interval
        self.max_retries = max_retries
        self.retry_interval = retry_interval

        self._stop_requested = False

    @measure_performance("BaseDataUpdateThread.run")
    def run(self):
        """运行数据更新线程"""
        set_trace_id(get_trace_id())
        self.running = True
        retry_count = 0

        while self.running:
            try:
                logger.debug("正在更新数据...")
                self.status_changed.emit("正在更新数据...")

                # 调用数据获取函数
                data = self.data_fetcher()

                if data:
                    self.data_updated.emit(data)
                    logger.debug("数据更新成功")
                    self.status_changed.emit("数据更新成功")
                    retry_count = 0  # 重置重试计数
                else:
                    raise ValueError("获取数据为空")

            except Exception as e:
                retry_count += 1
                error_msg = f"数据更新失败 ({retry_count}/{self.max_retries}): {str(e)}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                self.status_changed.emit("更新失败，准备重试...")

                if retry_count >= self.max_retries:
                    logger.warning("达到最大重试次数，等待下一轮更新")
                    self.status_changed.emit("达到最大重试次数，等待下一轮更新")
                    retry_count = 0
                    self._sleep_interruptible(self.update_interval)
                else:
                    self._sleep_interruptible(self.retry_interval)
                continue

            # 正常更新后的等待
            self._sleep_interruptible(self.update_interval)

        logger.info("数据更新线程已停止")
        self.status_changed.emit("已停止更新")

    def _sleep_interruptible(self, seconds: int):
        """可中断的睡眠"""
        for _ in range(seconds):
            if not self.running:
                break
            self.msleep(1000)

    def stop(self):
        """停止线程"""
        self.running = False
        self.status_changed.emit("正在停止...")

class BaseAnalysisThread(QThread):
    """统一的分析线程基类"""

    analysis_completed = pyqtSignal(dict)  # 分析完成信号
    error_occurred = pyqtSignal(str)  # 错误信号
    progress_updated = pyqtSignal(int, str)  # 进度更新信号

    def __init__(self, analysis_func: Callable, args: tuple = (), kwargs: dict = None):
        super().__init__()
        self.analysis_func = analysis_func
        self.args = args
        self.kwargs = kwargs or {}

        # 使用统一的管理器工厂
        # log_manager已迁移到Loguru

    @measure_performance("BaseAnalysisThread.run")
    def run(self):
        """运行分析线程"""
        set_trace_id(self.kwargs.get('trace_id', get_trace_id()))
        try:
            logger.info(f"开始分析... trace_id={get_trace_id()}")
            self.progress_updated.emit(0, "开始分析...")

            # 执行分析函数
            results = self.analysis_func(*self.args, **self.kwargs)

            self.progress_updated.emit(100, "分析完成")
            self.analysis_completed.emit(results)
            logger.info(f"分析完成 trace_id={get_trace_id()}")

        except Exception as e:
            error_msg = f"分析失败: {str(e)} trace_id={get_trace_id()}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

class BaseExportThread(QThread):
    """统一的导出线程基类"""

    export_completed = pyqtSignal(str)  # 导出完成信号
    error_occurred = pyqtSignal(str)  # 错误信号
    progress_updated = pyqtSignal(int, str)  # 进度更新信号

    def __init__(self, export_func: Callable, file_path: str, data):
        super().__init__()
        self.export_func = export_func
        self.file_path = file_path
        self.data = data

    @measure_performance("BaseExportThread.run")
    def run(self):
        """运行导出线程"""
        set_trace_id(self.kwargs.get('trace_id', get_trace_id())
                     if hasattr(self, 'kwargs') else get_trace_id())
        try:
            logger.info(
                f"开始导出到: {self.file_path} trace_id={get_trace_id()}")
            self.progress_updated.emit(0, "开始导出...")

            # 执行导出函数
            success = self.export_func(self.data, self.file_path)

            if success:
                self.progress_updated.emit(100, "导出完成")
                self.export_completed.emit(self.file_path)
                logger.info(
                    f"导出完成: {self.file_path} trace_id={get_trace_id()}")
            else:
                raise Exception("导出函数返回失败")

        except Exception as e:
            error_msg = f"导出失败: {str(e)} trace_id={get_trace_id()}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def _init_safe_error_handling(self):
        """初始化安全的错误处理机制"""
        # 注意：只在子类需要时调用
        # 避免与现有的信号连接冲突
        pass

    def _handle_error_safely(self, error_msg: str):
        """安全地处理错误，避免阻塞UI"""
        try:
            # 记录到日志
            logger.error(f"错误处理: {error_msg}")

            # 使用QTimer延迟显示错误，避免阻塞当前线程
            QTimer.singleShot(0, lambda: self._show_error_safely(error_msg))

        except Exception as e:
            # 如果错误处理本身出错，至少记录到日志
            logger.info(f"错误处理失败: {e}")

    def _show_error_safely(self, error_msg: str):
        """安全地显示错误信息"""
        try:
            # 查找顶级窗口
            parent = self
            while parent.parent():
                parent = parent.parent()

            # 创建非模态消息框
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("操作提示")
            msg_box.setText("操作过程中出现问题")
            msg_box.setDetailedText(error_msg)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.setModal(False)  # 设置为非模态

            # 非阻塞显示
            msg_box.show()

            # 5秒后自动关闭
            QTimer.singleShot(5000, msg_box.close)

        except Exception as e:
            # 如果GUI显示失败，至少打印到控制台
            logger.info(f"GUI错误显示失败: {e}")
            logger.info(f"原始错误: {error_msg}")
