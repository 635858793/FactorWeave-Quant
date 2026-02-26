from loguru import logger
"""
图表渲染功能Mixin - 处理K线渲染、指标渲染、样式配置等功能
"""
import time
import numpy as np
import pandas as pd
import re
from typing import Dict, Any, Tuple, Optional, List
from PyQt5.QtCore import Qt
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 替换旧的指标系统导入
from core.indicator_adapter import get_indicator_english_name


class IndicatorPerformanceOptimizer:
    """指标性能优化器 - 缓存和批量计算"""
    
    def __init__(self):
        self._precomputed_indicators = {}
        self._style_cache = {}
        self._cache_version = 0
        self._talib_module = None
        self._pattern_cache = {}
    
    def clear_cache(self):
        """清除所有缓存"""
        self._precomputed_indicators.clear()
        self._style_cache.clear()
        self._cache_version += 1
        self._pattern_cache.clear()
    
    def get_precomputed_indicators(self, kdata_hash, required_indicators):
        """获取预计算的指标"""
        cache_key = f"{kdata_hash}_{hash(str(required_indicators))}"
        return self._precomputed_indicators.get(cache_key, {})
    
    def cache_indicators(self, kdata_hash, required_indicators, results):
        """缓存指标计算结果"""
        cache_key = f"{kdata_hash}_{hash(str(required_indicators))}"
        self._precomputed_indicators[cache_key] = results
    
    def get_cached_style(self, name, index, theme_version):
        """获取缓存的样式"""
        cache_key = f"{name}_{index}_{theme_version}"
        return self._style_cache.get(cache_key)
    
    def cache_style(self, name, index, theme_version, style):
        """缓存样式"""
        cache_key = f"{name}_{index}_{theme_version}"
        self._style_cache[cache_key] = style
    
    @property
    def talib(self):
        """惰性加载talib模块"""
        if self._talib_module is None:
            try:
                import talib
                self._talib_module = talib
            except ImportError:
                self._talib_module = False
        return self._talib_module
    
    def get_cached_pattern(self, pattern_name):
        """获取缓存的正则表达式"""
        if pattern_name not in self._pattern_cache:
            if pattern_name == 'ma':
                self._pattern_cache[pattern_name] = re.compile(r'^MA(\d+)?$')
            elif pattern_name == 'builtin':
                self._pattern_cache[pattern_name] = {'MA', 'MACD', 'RSI', 'BOLL'}
        return self._pattern_cache[pattern_name]


class RenderingMixin:
    """图表渲染功能Mixin"""
    
    def __init__(self):
        """初始化渲染混入类"""
        super().__init__()
        # 初始化性能优化器
        self._performance_optimizer = IndicatorPerformanceOptimizer()
        # 预编译的正则表达式
        self._ma_pattern = re.compile(r'^MA(\d+)?$')
        # 内置指标集合（用于快速匹配）
        self._builtin_indicators = {'MA', 'MACD', 'RSI', 'BOLL'}

    def _get_kdata_hash(self, kdata: pd.DataFrame) -> str:
        """获取kdata的唯一标识符，用于缓存"""
        try:
            # 使用数据的基本统计信息作为哈希
            stats = {
                'length': len(kdata),
                'columns': list(kdata.columns),
                'dtypes': dict(kdata.dtypes),
                'first_close': float(kdata['close'].iloc[0]) if not kdata.empty else 0,
                'last_close': float(kdata['close'].iloc[-1]) if not kdata.empty else 0
            }
            return str(hash(str(stats)))
        except Exception as e:
            logger.warning(f"生成kdata哈希失败: {e}")
            return "default_hash"
    
    def _batch_precompute_indicators(self, kdata: pd.DataFrame, indicators: List[Dict]) -> Dict:
        """批量预计算所有需要的指标（包含custom指标优化）"""
        precomputed = {}
        
        # 收集需要计算的指标类型
        required_macd = False
        required_rsi_periods = set()
        required_boll_params = set()
        required_ma_periods = set()
        
        # 收集custom指标信息
        required_custom_indicators = []
        
        for indicator in indicators:
            # 空值检查
            if indicator is None:
                logger.warning(f"跳过空指标")
                continue
                
            name = indicator.get('name', '')
            if not name:
                logger.warning(f"跳过缺少名称的指标")
                continue
                
            group = indicator.get('group', '')
            params = indicator.get('params', {})
            
            # 验证参数是否为字典
            if not isinstance(params, dict):
                logger.warning(f"指标 {name} 参数格式错误，应为字典")
                params = {}
            
            if group == 'builtin':
                if name == 'MACD':
                    required_macd = True
                elif name == 'RSI':
                    period = int(params.get('n', 14))
                    required_rsi_periods.add(period)
                elif name == 'BOLL':
                    n = int(params.get('n', 20))
                    p = float(params.get('p', 2))
                    required_boll_params.add((n, p))
                elif self._ma_pattern.match(name):
                    ma_match = self._ma_pattern.match(name)
                    if ma_match and ma_match.group(1):
                        period = int(ma_match.group(1))
                    else:
                        period = int(params.get('n', 20))
                    required_ma_periods.add(period)
            elif group == 'custom':
                formula = indicator.get('formula', '')
                if formula:
                    required_custom_indicators.append({
                        'name': name,
                        'formula': formula,
                        'params': params
                    })
        
        # 批量计算MACD
        if required_macd:
            macd, sig, hist = self._calculate_macd(kdata)
            precomputed['MACD'] = {
                'macd': macd.dropna(),
                'signal': sig.dropna(),
                'hist': hist.dropna()
            }
        
        # 批量计算RSI
        for period in required_rsi_periods:
            rsi = self._calculate_rsi(kdata, period)
            precomputed[f'RSI_{period}'] = rsi.dropna()
        
        # 批量计算BOLL
        for n, p in required_boll_params:
            mid, upper, lower = self._calculate_boll(kdata, n, p)
            precomputed[f'BOLL_{n}_{p}'] = {
                'mid': mid.dropna(),
                'upper': upper.dropna(),
                'lower': lower.dropna()
            }
        
        # 批量计算MA
        for period in required_ma_periods:
            ma = kdata['close'].rolling(period).mean()
            precomputed[f'MA_{period}'] = ma.dropna()
        
        # 智能并行计算custom指标（重要优化）
        if required_custom_indicators:
            # 🧠 智能判断是否使用并行计算
            data_size = len(kdata)
            indicator_count = len(required_custom_indicators)
            
            # 📏 自适应并行策略：基于数据量和指标数量
            use_parallel = self._should_use_parallel_computation(data_size, indicator_count)
            
            if use_parallel:
                # 并行计算路径
                logger.debug(f"使用并行计算: {data_size}条数据, {indicator_count}个指标")
                precomputed.update(self._parallel_compute_custom_indicators(kdata, required_custom_indicators))
            else:
                # 📋 顺序计算路径（避免不必要的开销）
                logger.debug(f"使用顺序计算: {data_size}条数据, {indicator_count}个指标")
                precomputed.update(self._sequential_compute_custom_indicators(kdata, required_custom_indicators))
        else:
            logger.debug("没有需要计算的custom指标")
        
        return precomputed
    
    def _should_use_parallel_computation(self, data_size: int, indicator_count: int) -> bool:
        """🧠 智能判断是否使用并行计算 - 基于实测结果优化的保守策略
        
        根据测试结果：
        - 大多数情况下并行计算并没有显著性能提升
        - 并行计算的开销（线程创建、上下文切换、GIL限制）超过了收益
        - 只在极端情况下才考虑并行计算
        
        优化策略：极保守的并行策略，只在非常极端的情况下才使用并行
        """
        # 极保守策略：只有在大数据集且指标数量极多的情况下才使用并行
        if data_size >= 5000 and indicator_count >= 15:  # 超大数据集 + 极多指标
            return True
        else:
            return False  # 默认使用顺序计算
    
    def _sequential_compute_custom_indicators(self, kdata: pd.DataFrame, required_custom_indicators: List[Dict]) -> Dict:
        """📋 顺序计算custom指标（避免并行开销）"""
        precomputed = {}
        
        for custom_indicator in required_custom_indicators:
            name = custom_indicator['name']
            formula = custom_indicator['formula']
            try:
                # 使用pandas.eval批量计算custom指标
                local_vars = {col: kdata[col] for col in kdata.columns}
                arr = pd.eval(formula, local_dict=local_vars)
                arr = arr.dropna()
                precomputed[f'CUSTOM_{name}'] = arr
                logger.debug(f"📋 顺序预计算custom指标 {name} 完成")
            except Exception as e:
                logger.warning(f"📋 顺序预计算custom指标 {name} 失败: {str(e)}")
                # 即使失败也记录，避免重复计算
                precomputed[f'CUSTOM_{name}'] = pd.Series(dtype=float)
        
        return precomputed
    
    def _parallel_compute_custom_indicators(self, kdata: pd.DataFrame, required_custom_indicators: List[Dict]) -> Dict:
        """并行计算custom指标（适用于大数据量、多指标情况）- 优化版本"""
        precomputed = {}
        
        def calculate_single_custom_indicator(kdata_copy, custom_indicator):
            """线程安全的单个自定义指标计算 - 使用独立数据副本"""
            name = custom_indicator['name']
            formula = custom_indicator['formula']
            try:
                # 优化：使用共享的pandas.eval调用，避免重复创建变量字典
                arr = pd.eval(formula, local_dict=kdata_copy)
                arr = arr.dropna()
                return (name, arr, None)
            except Exception as e:
                logger.warning(f"并行预计算custom指标 {name} 失败: {str(e)}")
                return (name, pd.Series(dtype=float), str(e))
        
        # 核心优化：预构建变量字典，避免在线程中重复创建
        local_vars = {col: kdata[col] for col in kdata.columns}
        
        # 核心优化：使用ThreadPoolExecutor并行计算所有custom指标
        max_workers = min(4, len(required_custom_indicators))  # 限制线程数，避免过载
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有计算任务，传递共享变量字典
            future_to_indicator = {
                executor.submit(calculate_single_custom_indicator, local_vars, indicator): indicator 
                for indicator in required_custom_indicators
            }
            
            # 收集所有结果
            for future in as_completed(future_to_indicator):
                name, arr, error = future.result()
                precomputed[f'CUSTOM_{name}'] = arr
                if error:
                    logger.warning(f"并行预计算custom指标 {name} 失败: {error}")
                else:
                    logger.debug(f"并行预计算custom指标 {name} 完成")
        
        logger.info(f"并行计算 {len(required_custom_indicators)} 个custom指标完成")
        return precomputed
    
    def _get_optimized_indicator_style(self, name: str, index: int = 0) -> Dict[str, Any]:
        """优化的指标样式获取方法，使用缓存"""
        # 使用主题版本作为缓存键的一部分
        try:
            theme_version = hash(str(getattr(self, 'theme_manager', {}).get_theme_colors() if hasattr(self.theme_manager, 'get_theme_colors') else {}))
        except:
            theme_version = 0
        
        # 尝试从缓存获取
        cached_style = self._performance_optimizer.get_cached_style(name, index, theme_version)
        if cached_style:
            return cached_style
        
        # 计算样式
        colors = self.theme_manager.get_theme_colors() if hasattr(self, 'theme_manager') else {}
        indicator_colors = colors.get('indicator_colors', [
            '#fbc02d', '#ab47bc', '#1976d2', '#43a047', '#e53935', '#00bcd4', '#ff9800'])
        
        style = {
            'color': indicator_colors[index % len(indicator_colors)],
            'linewidth': 0.7,
            'alpha': 0.85,
            'label': name
        }
        
        # 缓存结果
        self._performance_optimizer.cache_style(name, index, theme_version, style)
        return style
    
    def _fast_indicator_match(self, name: str, group: str) -> Optional[Tuple[str, Any]]:
        """快速指标类型匹配"""
        if group != 'builtin':
            return None
        
        # 使用集合进行快速匹配
        if name == 'MACD':
            return ('MACD', None)
        elif name == 'RSI':
            return ('RSI', None)
        elif name == 'BOLL' or name == 'BBANDS':
                return ('BOLL', None)
        elif self._ma_pattern.match(name):
            ma_match = self._ma_pattern.match(name)
            if ma_match and ma_match.group(1):
                period = int(ma_match.group(1))
                return ('MA', {'period': period})
            else:
                return ('MA', {'period': 20})
        
        return None
    
    def update_chart(self, data: dict = None):
        """唯一K线渲染实现，X轴为等距序号，彻底消除节假日断层。"""
        try:
            if not data:
                return
            start_time = time.time()
            # 🔴 性能优化P1.4：降低日志级别，避免list()调用和DataFrame.head()打印
            logger.debug(f"RenderingMixin.update_chart接收到数据类型: {type(data)}")

            # 处理不同的数据字段格式，兼容kdata和kline_data
            kdata = None
            if 'kdata' in data:
                kdata = data['kdata']
                logger.debug(f"从'kdata'键获取数据，类型: {type(kdata)}")
            elif 'kline_data' in data:
                kdata = data['kline_data']
                logger.debug(f"从'kline_data'键获取数据，类型: {type(kdata)}")
            else:
                # 没有找到有效的K线数据
                logger.error("未找到有效的K线数据键")
                self.show_no_data("无K线数据")
                return

            # 处理嵌套的数据结构
            if isinstance(kdata, dict) and 'kline_data' in kdata:
                # 这是一个嵌套的数据结构，真正的K线数据在kline_data键中
                logger.debug(f"检测到嵌套的数据结构，从kline_data键中提取真正的K线数据")
                nested_kdata = kdata.get('kline_data')
                logger.debug(f"嵌套的K线数据类型: {type(nested_kdata)}")
                kdata = nested_kdata

            # 处理kdata是字典的情况
            if isinstance(kdata, dict):
                # 如果kdata是字典，尝试从中提取DataFrame
                logger.info(f"kdata是字典")

                if 'data' in kdata:
                    # 如果字典中有data键，使用它
                    df_data = kdata.get('data')
                    logger.debug(f"从字典的'data'键获取数据，类型: {type(df_data)}")

                    if isinstance(df_data, pd.DataFrame):
                        kdata = df_data
                        logger.debug(f"成功从字典的'data'键获取DataFrame，形状: {kdata.shape}")
                    elif isinstance(df_data, list) and df_data:
                        kdata = pd.DataFrame(df_data)
                        logger.debug(f"将列表转换为DataFrame，形状: {kdata.shape}")
                    else:
                        logger.error(f"字典中的'data'键内容无效: {type(df_data)}")
                        self.show_no_data(f"K线数据格式错误: {type(df_data)}")
                        return
                else:
                    # 尝试将整个字典转换为DataFrame
                    try:
                        kdata = pd.DataFrame([kdata])
                        logger.debug(f"将整个字典转换为DataFrame，形状: {kdata.shape}")
                    except Exception as e:
                        logger.error(f"无法将字典转换为DataFrame: {e}")
                        self.show_no_data("K线数据格式错误")
                        return

            # 记录处理后的kdata信息
            logger.debug(f"处理后的kdata类型: {type(kdata)}")
            if hasattr(kdata, 'shape'):
                logger.debug(f"处理后的kdata形状: {kdata.shape}")

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"K线类型转化完成，耗时: {render_time:.2f}ms")

            start_time = time.time()
            # 检查kdata是否包含必要的列
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if isinstance(kdata, pd.DataFrame):
                missing_columns = [col for col in required_columns if col not in kdata.columns]
                if missing_columns:
                    logger.error(f"K线数据缺少必要列: {missing_columns}")
                    self.show_no_data(f"K线数据缺少必要列: {', '.join(missing_columns)}")
                    return

            kdata = self._downsample_kdata(kdata)
            kdata = kdata.dropna(how='any')
            kdata = kdata.loc[~kdata.index.duplicated(keep='first')]

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"K线数据校验，耗时: {render_time:.2f}ms")

            start_time = time.time()
            self.current_kdata = kdata

            # 记录清理后的kdata信息
            logger.debug(f"清理后的kdata形状: {kdata.shape}")

            if not kdata.empty:
                self._ymin = float(kdata['low'].min())
                self._ymax = float(kdata['high'].max())
                logger.debug(f"Y轴范围: {self._ymin} - {self._ymax}")
            else:
                self._ymin = 0
                self._ymax = 1
                logger.warning("kdata为空，设置默认Y轴范围")

            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                ax.cla()

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"K线price_ax，耗时: {render_time:.2f}ms")

            start_time = time.time()

            style = self._get_chart_style()
            x = np.arange(len(kdata))  # 用等距序号做X轴

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"K线style设置，耗时: {render_time:.2f}ms")

            start_time = time.time()

            # 记录渲染参数
            logger.debug(f"准备调用renderer.render_candlesticks，x轴长度: {len(x)}")

            # 性能优化：延迟绘制 - 先完成所有渲染，最后统一绘制
            # 调用渲染器
            try:
                self.renderer.render_candlesticks(self.price_ax, kdata, style, x=x)
                logger.debug("K线渲染成功")
            except Exception as e:
                logger.error(f"K线渲染失败: {e}", exc_info=True)
                raise
            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"render_candlesticks，耗时: {render_time:.2f}ms")

            start_time = time.time()
            try:
                self.renderer.render_volume(self.volume_ax, kdata, style, x=x)
                logger.debug("成交量渲染成功")
            except Exception as e:
                logger.error(f"成交量渲染失败: {e}", exc_info=True)

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"render_volume，耗时: {render_time:.2f}ms")

            start_time = time.time()

            # 性能优化P2.1：合并autoscale_view()调用 - 在所有渲染完成后统一调用
            # 统一设置所有轴（价格、成交量、指标）的自动缩放范围
            try:
                self.price_ax.autoscale_view()
                self.volume_ax.autoscale_view()
                if hasattr(self, 'indicator_ax') and self.indicator_ax:
                    self.indicator_ax.autoscale_view()
                logger.debug("统一调用autoscale_view()完成（3轴合并）")
            except Exception as e:
                logger.warning(f"autoscale_view()调用失败: {e}")

            # 处理indicators_data（如果存在）
            indicators_data = data.get('indicators_data', {})
            if indicators_data:
                # 将indicators_data传递给渲染函数
                logger.info(f"检测到indicators_data，指标数量: {len(indicators_data)}, 指标名称: {list(indicators_data.keys())}")
                self._render_indicator_data(indicators_data, kdata, x)
                logger.info(f"_render_indicator_data调用完成")
            else:
                logger.debug(f"💡 indicators_data为空，builtin指标将在_render_indicators中计算")

            start_time = time.time()
            # 🔧 修复：只在active_indicators为None时使用默认指标，保护用户的选择
            if self.active_indicators is None:  # 仅当完全未设置时才使用默认
                # 调用_get_active_indicators获取默认指标
                if hasattr(self, '_get_active_indicators'):
                    self.active_indicators = self._get_active_indicators()
                    logger.info(f"active_indicators为None，使用默认指标: {len(self.active_indicators) if self.active_indicators else 0}个")
                else:
                    # 硬编码默认指标作为最后的fallback
                    self.active_indicators = [
                        {"name": "MA20", "params": {"period": 20}, "group": "builtin"},
                        {"name": "MA60", "params": {"period": 60}, "group": "builtin"}
                    ]
                    logger.info(f"active_indicators为None，使用硬编码默认指标: MA20, MA60")
            else:
                # 验证active_indicators是否为列表
                if not isinstance(self.active_indicators, list):
                    logger.warning(f"active_indicators格式错误，应为列表，实际为: {type(self.active_indicators)}")
                    # 重置为默认指标
                    self.active_indicators = [
                        {"name": "MA20", "params": {"period": 20}, "group": "builtin"},
                        {"name": "MA60", "params": {"period": 60}, "group": "builtin"}
                    ]
                    logger.info(f"active_indicators格式错误，已重置为默认指标: MA20, MA60")
                else:
                    # 记录active_indicators状态
                    indicator_names = []
                    for ind in self.active_indicators:
                        if ind is not None and isinstance(ind, dict):
                            indicator_names.append(ind.get('name', 'unknown'))
                        else:
                            indicator_names.append('invalid')
                    logger.info(f"active_indicators已被设置，保持现有值不变: {indicator_names}")

            # 记录active_indicators状态
            active_inds = getattr(self, 'active_indicators', None)
            # 如果active_indicators为None，使用空列表
            if active_inds is None:
                active_inds = []
            else:
                # 验证active_indicators中的每个指标
                validated_inds = []
                for i, ind in enumerate(active_inds):
                    if ind is not None and isinstance(ind, dict) and ind.get('name'):
                        validated_inds.append(ind)
                    else:
                        logger.warning(f"移除无效指标 #{i}: {ind}")
                active_inds = validated_inds
                self.active_indicators = active_inds  # 更新为验证后的列表
            
            logger.info(f"准备调用_render_indicators，active_indicators状态: {len(active_inds) if active_inds else 0}个指标")
            # if active_inds:
            #     logger.info(f"active_indicators内容: {[ind.get('name', 'unknown') for ind in active_inds]}")

            self._render_indicators(kdata, x=x)

            # --- 新增：形态信号可视化 ---
            pattern_signals = data.get('pattern_signals', None)
            if pattern_signals:
                self.plot_patterns(pattern_signals)
            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"_render_indicators，耗时: {render_time:.2f}ms")

            # 性能优化P1: 统一调用_optimize_display()设置所有轴的完整样式
            # 替代chart_renderer中的_optimize_display()调用，避免重复设置样式
            # _optimize_display()会设置所有轴（price_ax、volume_ax、indicator_ax）的样式
            self._optimize_display()

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"形态信号可视化，耗时: {render_time:.2f}ms")

            if not kdata.empty:
                for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                    ax.set_xlim(0, len(kdata)-1)
                self.price_ax.set_ylim(self._ymin, self._ymax)
                # 设置X轴刻度和标签（间隔显示，防止过密）
                step = max(1, len(kdata)//8)
                xticks = np.arange(0, len(kdata), step)
                xticklabels = [self._safe_format_date(
                    kdata.iloc[i], i, kdata) for i in xticks]
                self.indicator_ax.set_xticks(xticks)
                # 修复：确保tick数量和label数量一致
                if len(xticks) == len(xticklabels):
                    self.indicator_ax.set_xticklabels(
                        xticklabels, rotation=30, fontsize=8)
                else:
                    # 自动补齐或截断
                    min_len = min(len(xticks), len(xticklabels))
                    self.indicator_ax.set_xticks(xticks[:min_len])
                    self.indicator_ax.set_xticklabels(
                        xticklabels[:min_len], rotation=30, fontsize=8)
            self.close_loading_dialog()
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                ax.yaxis.set_tick_params(direction='in', pad=0)
                ax.yaxis.set_label_position('left')
                ax.tick_params(axis='y', direction='in', pad=0)

            # 性能优化：延迟十字光标初始化到渲染完成后
            # 不在渲染过程中初始化，避免影响渲染性能
            self.crosshair_enabled = True
            # self.enable_crosshair(force_rebind=True)  # 已移除，延迟到绘制完成后

            # 性能优化：延迟绘制 - 所有渲染和范围设置完成后，只调用一次draw_idle()
            # 这样可以避免K线、成交量、指标分别触发绘制，大幅提升性能
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.draw_idle()
                logger.debug("统一绘制完成（延迟绘制优化）")

            # 性能优化P3：进一步延迟十字光标初始化到用户交互时
            # 不在渲染完成后立即初始化，而是在用户首次鼠标移动时再初始化
            # 这样可以避免在渲染过程中初始化十字光标，进一步提升渲染性能
            if hasattr(self, 'crosshair_enabled') and self.crosshair_enabled:
                # 标记需要初始化，但不立即执行
                self._crosshair_needs_init = True
                logger.debug("十字光标初始化已延迟到用户交互时")

                # 如果已经初始化，只需要清除旧元素（不重新绑定事件）
                if hasattr(self, '_crosshair_initialized') and self._crosshair_initialized:
                    try:
                        if hasattr(self, '_clear_crosshair_elements'):
                            self._clear_crosshair_elements()
                            logger.debug("十字光标元素已清除（已初始化，不重新绑定）")
                    except Exception as e:
                        logger.warning(f"清除十字光标元素失败: {e}")
            # 左上角显示股票名称和代码
            if hasattr(self, '_stock_info_text') and self._stock_info_text:
                try:
                    if self._stock_info_text in self.price_ax.texts:
                        self._stock_info_text.remove()
                except Exception as e:
                    if True:  # 使用Loguru日志
                        logger.warning(f"移除股票信息文本失败: {str(e)}")
                self._stock_info_text = None
            stock_name = data.get('title') or getattr(
                self, 'current_stock', '')
            stock_code = data.get('stock_code') or getattr(
                self, 'current_stock', '')
            if stock_name and stock_code and stock_code not in stock_name:
                info_str = f"{stock_name} ({stock_code})"
            elif stock_name:
                info_str = stock_name
            elif stock_code:
                info_str = stock_code
            else:
                info_str = ''
            colors = self.theme_manager.get_theme_colors()
            text_color = colors.get('chart_text', '#222b45')
            bg_color = colors.get('chart_background', '#ffffff')
            self._stock_info_text = self.price_ax.text(
                0.01, 0.99, info_str,  # y坐标0.98
                transform=self.price_ax.transAxes,
                va='top', ha='left',
                fontsize=8,
                color=text_color,
                bbox=dict(facecolor=bg_color, alpha=0.7,
                          edgecolor='none', boxstyle='round,pad=0.2'),
                zorder=200
            )
            # 性能优化P0: 移除draw_idle()调用，由最后统一绘制处理
            # 不再在这里触发绘制，避免在渲染过程中触发额外绘制
            # self.canvas.draw_idle()  # 已移除，在最后统一绘制
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                for label in (ax.get_xticklabels() + ax.get_yticklabels()):
                    label.set_fontsize(8)
                ax.title.set_fontsize(8)
                ax.xaxis.label.set_fontsize(8)
                ax.yaxis.label.set_fontsize(8)

            # # 右下角显示数据时间
            # if hasattr(self, '_data_time_text') and self._data_time_text:
            #     try:
            #         if self._data_time_text in self.price_ax.texts:
            #             self._data_time_text.remove()
            #     except Exception as e:
            #         if True:  # 使用Loguru日志
            #             logger.warning(f"移除数据时间文本失败: {str(e)}")
            #     self._data_time_text = None

            # # 获取数据时间
            # import datetime
            # now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # data_time_str = f"当前时间: {now}"

            # # 右下角显示数据时间
            # self._data_time_text = self.price_ax.text(
            #     0.99, 0.01, data_time_str,
            #     transform=self.price_ax.transAxes,
            #     va='bottom', ha='right',
            #     fontsize=8,
            #     color=text_color,
            #     bbox=dict(facecolor=bg_color, alpha=0.7,
            #               edgecolor='none', boxstyle='round,pad=0.2'),
            #     zorder=200
            # )

            self._optimize_display()
        except Exception as e:
            logger.error(f"更新图表失败: {str(e)}")
            logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
            self.show_no_data("渲染失败")

    def _render_indicator_data(self, indicators_data, kdata, x=None):
        """渲染从indicators_data传递的指标数据"""
        try:
            logger.info(f"_render_indicator_data开始执行")
            if not indicators_data:
                logger.warning(f"❌ indicators_data为空，直接返回")
                return

            if x is None:
                x = np.arange(len(kdata))

            logger.info(f"准备遍历indicators_data，指标数量: {len(indicators_data)}")
            # 遍历所有指标
            for i, (indicator_name, indicator_data) in enumerate(indicators_data.items()):
                logger.info(f"处理指标 {i+1}/{len(indicators_data)}: {indicator_name}, 数据类型: {type(indicator_data)}")
                # 处理MA指标
                if indicator_name == 'MA':
                    for j, (period, values) in enumerate(indicator_data.items()):
                        # 确保values是列表
                        values_list = values
                        if hasattr(values, 'tolist'):
                            values_list = values.tolist()

                        # 处理值为None的情况
                        valid_values = []
                        valid_x = []
                        for idx, val in enumerate(values_list):
                            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                                valid_values.append(val)
                                valid_x.append(x[idx] if idx < len(x) else idx)

                        if valid_values:
                            style = self._get_indicator_style(f'MA{period}', j)
                            self.price_ax.plot(
                                valid_x,
                                valid_values,
                                color=style['color'],
                                linewidth=style['linewidth'],
                                alpha=style['alpha'],
                                label=f'MA{period}'
                            )

                # 处理MACD指标
                elif indicator_name == 'MACD':
                    # MACD通常有DIF、DEA和MACD三个数据序列
                    dif_values = indicator_data.get('DIF', [])
                    dea_values = indicator_data.get('DEA', [])
                    hist_values = indicator_data.get('MACD', [])

                    # 确保是列表
                    if hasattr(dif_values, 'tolist'):
                        dif_values = dif_values.tolist()
                    if hasattr(dea_values, 'tolist'):
                        dea_values = dea_values.tolist()
                    if hasattr(hist_values, 'tolist'):
                        hist_values = hist_values.tolist()

                    # 绘制DIF和DEA线
                    valid_dif = [(idx, val) for idx, val in enumerate(dif_values)
                                 if val is not None and not (isinstance(val, float) and np.isnan(val))]
                    valid_dea = [(idx, val) for idx, val in enumerate(dea_values)
                                 if val is not None and not (isinstance(val, float) and np.isnan(val))]

                    if valid_dif:
                        valid_x_dif, valid_y_dif = zip(*valid_dif)
                        self.indicator_ax.plot(
                            [x[i] for i in valid_x_dif if i < len(x)],
                            valid_y_dif,
                            color='#1976d2',  # 蓝色
                            linewidth=0.7,
                            alpha=0.85,
                            label='DIF'
                        )

                    if valid_dea:
                        valid_x_dea, valid_y_dea = zip(*valid_dea)
                        self.indicator_ax.plot(
                            [x[i] for i in valid_x_dea if i < len(x)],
                            valid_y_dea,
                            color='#ff9800',  # 橙色
                            linewidth=0.7,
                            alpha=0.85,
                            label='DEA'
                        )

                    # 绘制MACD柱状图
                    valid_hist = [(idx, val) for idx, val in enumerate(hist_values)
                                  if val is not None and not (isinstance(val, float) and np.isnan(val))]

                    if valid_hist:
                        valid_x_hist, valid_y_hist = zip(*valid_hist)
                        valid_x_hist = [x[i]
                                        for i in valid_x_hist if i < len(x)]
                        colors = ['#e53935' if h >=
                                  0 else '#43a047' for h in valid_y_hist]  # 红色和绿色
                        self.indicator_ax.bar(
                            valid_x_hist,
                            valid_y_hist,
                            color=colors,
                            alpha=0.5,
                            width=0.6
                        )

                # 其他指标类型...可以根据需要添加更多指标的处理逻辑

        except Exception as e:
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(f"渲染指标数据失败: {str(e)}")
            logger.error(f"渲染指标数据失败: {str(e)}")

    def _render_indicators(self, kdata: pd.DataFrame, x=None):
        """优化的技术指标渲染 - 使用缓存和批量计算"""
        try:
            start_time = time.time()
            indicators = getattr(self, 'active_indicators', [])
            if not indicators:
                logger.debug("指标列表为空，跳过渲染")
                return
            
            if x is None:
                x = np.arange(len(kdata))
            
            logger.info(f"开始优化渲染 {len(indicators)} 个指标")
            
            # 🔥 关键优化1: 批量预计算所有指标
            kdata_hash = self._get_kdata_hash(kdata)
            precomputed = self._batch_precompute_indicators(kdata, indicators)
            
            # 验证precomputed是否为字典
            if not isinstance(precomputed, dict):
                precomputed = {}
            
            render_time = (time.time() - start_time) * 1000
            logger.info(f"批量预计算完成，耗时: {render_time:.2f}ms")
            
            start_time = time.time()
            
            # 🔥 关键优化2: 使用优化的渲染循环
            plot_commands = []  # 收集绘图命令，减少matplotlib调用次数
            
            for i, indicator in enumerate(indicators):
                # 全面空值检查
                if indicator is None:
                    logger.warning(f"指标 #{i} 为空，跳过渲染")
                    continue
                
                name = indicator.get('name', '')
                if not name:
                    logger.warning(f"指标 #{i} 缺少名称，跳过渲染")
                    continue
                
                group = indicator.get('group', '')
                params = indicator.get('params', {})
                formula = indicator.get('formula', None)
                
                # 验证参数是否为字典
                if not isinstance(params, dict):
                    params = {}
                
                # 🔥 关键优化3: 使用缓存的样式
                style = self._get_optimized_indicator_style(name, i)
                
                # 🔥 关键优化4: 使用快速匹配builtin指标
                indicator_type = self._fast_indicator_match(name, group)
                
                if indicator_type and group == 'builtin':
                    # 验证indicator_type是否为元组
                    if not isinstance(indicator_type, tuple) or len(indicator_type) != 2:
                        logger.warning(f"indicator_type格式错误，应为(ind_type, ind_params)元组，实际为: {indicator_type}")
                        continue
                    
                    ind_type, ind_params = indicator_type
                    
                    # 验证ind_params是否为字典
                    if not isinstance(ind_params, dict):
                        ind_params = {}
                    
                    if ind_type == 'MA':
                        # 优化的MA指标渲染
                        period = ind_params.get('period', 20)
                        cache_key = f'MA_{period}'
                        if cache_key in precomputed:
                            ma = precomputed[cache_key]
                            if ma is not None and hasattr(ma, 'empty') and not ma.empty:
                                plot_commands.append(('plot', self.price_ax, x[-len(ma):], ma.values, 
                                                     style['color'], style['linewidth'], style['alpha'], name))                    
                    elif ind_type == 'MACD':
                        # 优化的MACD指标渲染
                        cache_key = 'MACD'
                        if cache_key in precomputed:
                            macd_data = precomputed[cache_key]
                            if macd_data is not None and isinstance(macd_data, dict):
                                macd = macd_data.get('macd')
                                sig = macd_data.get('signal')
                                hist = macd_data.get('hist')
                                
                                if macd is not None and hasattr(macd, 'empty') and not macd.empty:
                                    macd_style = self._get_optimized_indicator_style('MACD', i)
                                    signal_style = self._get_optimized_indicator_style('MACD-Signal', i+1)
                                    
                                    # 验证sig和hist
                                    if sig is not None and hasattr(sig, 'empty') and not sig.empty:
                                        plot_commands.append(('plot', self.indicator_ax, x[-len(macd):], macd.values,
                                                             macd_style['color'], 0.7, 0.85, 'MACD'))
                                        plot_commands.append(('plot', self.indicator_ax, x[-len(sig):], sig.values,
                                                             signal_style['color'], 0.7, 0.85, 'Signal'))
                                        
                                        if hist is not None and hasattr(hist, 'empty') and not hist.empty:
                                            hist_colors = ['red' if h >= 0 else 'green' for h in hist.values]
                                            plot_commands.append(('bar', self.indicator_ax, x[-len(hist):], hist.values,
                                                                 hist_colors, 0.5, None, None))
                    
                    elif ind_type == 'RSI':
                        # 优化的RSI指标渲染
                        period = ind_params.get('period', 14)
                        cache_key = f'RSI_{period}'
                        if cache_key in precomputed:
                            rsi = precomputed[cache_key]
                            if rsi is not None and hasattr(rsi, 'empty') and not rsi.empty:
                                plot_commands.append(('plot', self.indicator_ax, x[-len(rsi):], rsi.values,
                                                     style['color'], style['linewidth'], style['alpha'], 'RSI'))
                    
                    elif ind_type == 'BOLL':
                        # 优化的BOLL指标渲染
                        # 修复1: 确保参数类型一致，使用整数和浮点数
                        n = int(params.get('n', 20))
                        p = float(params.get('p', 2))
                        cache_key = f'BOLL_{n}_{p}'
                        # 移除不必要的BBANDS缓存键检查
                        if cache_key in precomputed:
                            boll_data = precomputed[cache_key]
                            if boll_data is not None and isinstance(boll_data, dict):
                                mid = boll_data.get('mid')
                                upper = boll_data.get('upper')
                                lower = boll_data.get('lower')
                                
                                mid_style = self._get_optimized_indicator_style('BOLL-Mid', i)
                                upper_style = self._get_optimized_indicator_style('BOLL-Upper', i+1)
                                lower_style = self._get_optimized_indicator_style('BOLL-Lower', i+2)
                                
                                # 修复3: 优化数据验证条件，允许部分数据缺失时的渲染
                                if mid is not None and hasattr(mid, 'empty') and not mid.empty:
                                    # 渲染中轨（始终显示，因为它是BOLL的核心）
                                    plot_commands.append(('plot', self.price_ax, x[-len(mid):], mid.values,
                                                         mid_style['color'], 0.5, 0.85, 'BOLL-Mid'))
                                    
                                    # 条件性渲染上轨（如果有数据）
                                    if upper is not None and hasattr(upper, 'empty') and not upper.empty:
                                        plot_commands.append(('plot', self.price_ax, x[-len(upper):], upper.values,
                                                             upper_style['color'], 0.7, 0.85, 'BOLL-Upper'))
                                    
                                    # 条件性渲染下轨（如果有数据）
                                    if lower is not None and hasattr(lower, 'empty') and not lower.empty:
                                        plot_commands.append(('plot', self.price_ax, x[-len(lower):], lower.values,
                                                             lower_style['color'], 0.5, 0.85, 'BOLL-Lower'))
                
                elif group == 'talib':
                    try:
                        # 使用优化的talib处理
                        if self._performance_optimizer.talib:
                            # 如果name是中文名称，需要转换为英文名称
                            english_name = get_indicator_english_name(name)

                            func = getattr(self._performance_optimizer.talib, english_name)
                            # 只传递非空参数
                            func_params = {k: v for k,
                                           v in params.items() if v != ''}

                            # 获取该指标需要的输入列
                            from core.indicator_adapter import get_indicator_inputs
                            required_inputs = get_indicator_inputs(english_name)

                            # 构建函数参数 - 确保所有输入数据都转换为float64类型
                            func_args = []
                            for input_name in required_inputs:
                                if input_name in kdata.columns:
                                    # 关键修复：将数据转换为float64（double）类型
                                    input_data = kdata[input_name].values.astype(np.float64)
                                    func_args.append(input_data)
                                    logger.debug(f"指标 {english_name} 输入列 {input_name}: dtype={input_data.dtype}, shape={input_data.shape}")
                                else:
                                    logger.warning(f"指标 {english_name} 缺少必要列: {input_name}")
                                    raise ValueError(f"缺少列: {input_name}")

                            # 传递计算参数（转换为浮点数）
                            kwargs = {k: float(v) if v else None for k, v in func_params.items()}
                            logger.debug(f"指标 {english_name} 参数: {kwargs}")

                            # 调用talib函数
                            result = func(*func_args, **kwargs)

                            if isinstance(result, tuple):
                                for j, arr in enumerate(result):
                                    arr = np.asarray(arr)
                                    arr = arr[~np.isnan(arr)]
                                    # 使用中文名称作为标签显示
                                    display_name = name
                                    result_style = self._get_optimized_indicator_style(display_name, i+j)
                                    plot_commands.append(('plot', self.indicator_ax, x[-len(arr):], arr,
                                                         result_style['color'], 0.7, 0.85, f'{display_name}-{j}'))
                            else:
                                arr = np.asarray(result)
                                arr = arr[~np.isnan(arr)]
                                display_name = name
                                plot_commands.append(('plot', self.indicator_ax, x[-len(arr):], arr,
                                                     style['color'], 0.7, 0.85, display_name))
                        else:
                            logger.warning("talib模块未正确加载，回退到原始实现")
                            # 回退到原始实现
                            import talib
                            english_name = get_indicator_english_name(name)
                            func = getattr(talib, english_name)
                            func_params = {k: v for k, v in params.items() if v != ''}
                            required_inputs = get_indicator_inputs(english_name)
                            func_args = []
                            for input_name in required_inputs:
                                if input_name in kdata.columns:
                                    input_data = kdata[input_name].values.astype(np.float64)
                                    func_args.append(input_data)
                                else:
                                    raise ValueError(f"缺少列: {input_name}")
                            kwargs = {k: float(v) if v else None for k, v in func_params.items()}
                            result = func(*func_args, **kwargs)
                            if isinstance(result, tuple):
                                for j, arr in enumerate(result):
                                    arr = np.asarray(arr)
                                    arr = arr[~np.isnan(arr)]
                                    display_name = name
                                    self.indicator_ax.plot(x[-len(arr):], arr, color=self._get_optimized_indicator_style(display_name, i+j)['color'],
                                                           linewidth=0.7, alpha=0.85, label=f'{display_name}-{j}')
                            else:
                                arr = np.asarray(result)
                                arr = arr[~np.isnan(arr)]
                                display_name = name
                                self.indicator_ax.plot(x[-len(arr):], arr, color=style['color'],
                                                       linewidth=0.7, alpha=0.85, label=display_name)
                    except Exception as e:
                        logger.error(f"ta-lib指标 {name} 渲染失败: {str(e)}")
                        self.error_occurred.emit(f"ta-lib指标渲染失败: {str(e)}")
                
                elif group == 'custom' and formula:
                    try:
                        # 使用预计算结果，避免重复计算
                        cache_key = f'CUSTOM_{name}'
                        if cache_key in precomputed:
                            arr = precomputed[cache_key]
                            if arr is not None and hasattr(arr, 'empty') and not arr.empty:
                                plot_commands.append(('plot', self.price_ax, x[-len(arr):], arr.values,
                                                     style['color'], style['linewidth'], style['alpha'], name))
                        else:
                            # 兜底：没有预计算结果时才执行计算
                            logger.warning(f"Custom指标 {name} 缺少预计算结果，执行兜底计算")
                            local_vars = {col: kdata[col] for col in kdata.columns}
                            arr = pd.eval(formula, local_dict=local_vars)
                            arr = arr.dropna()
                            plot_commands.append(('plot', self.price_ax, x[-len(arr):], arr.values,
                                                 style['color'], style['linewidth'], style['alpha'], name))
                    except Exception as e:
                        logger.error(f"自定义公式渲染失败: {str(e)}")
                        self.error_occurred.emit(f"自定义公式渲染失败: {str(e)}")
            
            # 🔥 关键优化5: 批量执行所有绘图命令
            if plot_commands:
                # 验证所有绘图命令
                validated_commands = []
                for cmd in plot_commands:
                    if cmd and isinstance(cmd, (list, tuple)) and len(cmd) >= 2:
                        validated_commands.append(cmd)
                    else:
                        logger.warning(f"无效绘图命令: {cmd}")
                
                if validated_commands:
                    self._execute_batch_plots(validated_commands)
                else:
                    logger.warning("没有有效的绘图命令可以执行")
            else:
                logger.debug("没有绘图命令需要执行")
                
            render_time = (time.time() - start_time) * 1000
            logger.info(f"指标渲染完成，总耗时: {render_time:.2f}ms")
            
        except Exception as e:
            error_msg = f"渲染指标失败: {str(e)}"
            self.error_occurred.emit(error_msg)
            logger.error(f"{error_msg}")
            # 记录详细错误信息
            import traceback
            logger.error(f"指标渲染失败详细信息: {traceback.format_exc()}")
    
    def _execute_batch_plots(self, plot_commands: List[Tuple]):
        """批量执行绘图命令，减少matplotlib调用次数"""
        try:
            for cmd in plot_commands:
                # 验证命令格式
                if not cmd or not isinstance(cmd, (list, tuple)) or len(cmd) < 2:
                    logger.warning(f"无效绘图命令格式: {cmd}")
                    continue
                    
                plot_type = cmd[0]
                if plot_type == 'plot':
                    # 验证plot命令参数
                    if len(cmd) < 8:
                        logger.warning(f"plot命令参数不足，需要8个，实际: {len(cmd)}")
                        continue
                    
                    try:
                        ax, x, y, color, linewidth, alpha, label = cmd[1:]
                        # 验证数据有效性
                        if x is not None and y is not None and len(x) == len(y):
                            ax.plot(x, y, color=color, linewidth=linewidth, alpha=alpha, label=label)
                        else:
                            logger.warning(f"plot命令数据无效: x={x}, y={y}")
                    except Exception as e:
                        logger.error(f"解析plot命令失败: {e}")
                        
                elif plot_type == 'bar':
                    # 验证bar命令参数
                    if len(cmd) < 7:
                        logger.warning(f"bar命令参数不足，需要7个，实际: {len(cmd)}")
                        continue
                    
                    try:
                        ax, x, y, colors, alpha, _, _ = cmd[1:]
                        # 验证数据有效性
                        if x is not None and y is not None and len(x) == len(y):
                            ax.bar(x, y, color=colors, alpha=alpha)
                        else:
                            logger.warning(f"bar命令数据无效: x={x}, y={y}")
                    except Exception as e:
                        logger.error(f"解析bar命令失败: {e}")
                        
                else:
                    logger.warning(f"未知绘图命令类型: {plot_type}")
                    
            logger.debug(f"批量执行了 {len(plot_commands)} 个绘图命令")
        except Exception as e:
            logger.error(f"批量绘图执行失败: {e}")
            # 回退到逐个执行
            for cmd in plot_commands:
                try:
                    # 验证命令格式
                    if not cmd or not isinstance(cmd, (list, tuple)) or len(cmd) < 2:
                        logger.warning(f"无效绘图命令格式: {cmd}")
                        continue
                        
                    plot_type = cmd[0]
                    if plot_type == 'plot':
                        if len(cmd) >= 8:
                            ax, x, y, color, linewidth, alpha, label = cmd[1:]
                            if x is not None and y is not None and len(x) == len(y):
                                ax.plot(x, y, color=color, linewidth=linewidth, alpha=alpha, label=label)
                    elif plot_type == 'bar':
                        if len(cmd) >= 7:
                            ax, x, y, colors, alpha, _, _ = cmd[1:]
                            if x is not None and y is not None and len(x) == len(y):
                                ax.bar(x, y, color=colors, alpha=alpha)
                except Exception as e2:
                    logger.error(f"单个绘图命令失败: {e2}")
    
    def clear_performance_cache(self):
        """清除性能优化缓存"""
        self._performance_optimizer.clear_cache()
        logger.info("性能优化缓存已清除")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return {
            'precomputed_count': len(self._performance_optimizer._precomputed_indicators),
            'style_cache_count': len(self._performance_optimizer._style_cache),
            'cache_version': self._performance_optimizer._cache_version,
            'talib_available': self._performance_optimizer.talib is not None and self._performance_optimizer.talib is not False
        }

    def _get_chart_style(self) -> Dict[str, Any]:
        """获取图表样式，所有颜色从theme_manager.get_theme_colors获取"""
        try:
            colors = self.theme_manager.get_theme_colors()
            
            # 处理颜色格式，确保rgba格式被正确解析
            processed_colors = {}
            for key, value in colors.items():
                if isinstance(value, str) and value.startswith('rgba('):
                    # 解析rgba格式
                    try:
                        rgba_content = value[5:-1]  # 去掉 "rgba(" 和 ")"
                        parts = [part.strip() for part in rgba_content.split(',')]
                        if len(parts) >= 4:
                            r, g, b = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
                            processed_colors[key] = (r, g, b)
                        else:
                            processed_colors[key] = value
                    except (ValueError, IndexError):
                        processed_colors[key] = value
                else:
                    processed_colors[key] = value
                    
            return {
                'up_color': processed_colors.get('k_up', '#e74c3c'),
                'down_color': processed_colors.get('k_down', '#27ae60'),
                'edge_color': processed_colors.get('k_edge', '#2c3140'),
                'volume_up_color': processed_colors.get('volume_up', '#e74c3c'),
                'volume_down_color': processed_colors.get('volume_down', '#27ae60'),
                'volume_alpha': processed_colors.get('volume_alpha', 0.5),
                'grid_color': processed_colors.get('chart_grid', '#e0e0e0'),
                'background_color': processed_colors.get('chart_background', '#ffffff'),
                'text_color': processed_colors.get('chart_text', '#222b45'),
                'axis_color': processed_colors.get('chart_grid', '#e0e0e0'),
                'label_color': processed_colors.get('chart_text', '#222b45'),
                'border_color': processed_colors.get('chart_grid', '#e0e0e0'),
            }
        except Exception as e:
            logger.error(f"获取图表样式失败: {str(e)}")
            return {}

    def _get_indicator_style(self, name: str, index: int = 0) -> Dict[str, Any]:
        """获取指标样式，颜色从theme_manager.get_theme_colors获取"""
        colors = self.theme_manager.get_theme_colors()
        indicator_colors = colors.get('indicator_colors', [
            '#fbc02d', '#ab47bc', '#1976d2', '#43a047', '#e53935', '#00bcd4', '#ff9800'])
        return {
            'color': indicator_colors[index % len(indicator_colors)],
            'linewidth': 0.7,
            'alpha': 0.85,
            'label': name
        }

    def _optimize_rendering(self):
        """优化渲染性能"""
        try:
            # 启用双缓冲
            self.setAttribute(Qt.WA_OpaquePaintEvent)
            self.setAttribute(Qt.WA_NoSystemBackground)
            self.setAutoFillBackground(True)

            # 优化matplotlib设置
            plt.style.use('fast')
            self.figure.set_dpi(100)

            # 禁用不必要的特性
            plt.rcParams['path.simplify'] = True
            plt.rcParams['path.simplify_threshold'] = 1.0
            plt.rcParams['agg.path.chunksize'] = 20000

            # 优化布局（只保留subplots_adjust，去除set_tight_layout和set_constrained_layout）
            # self.figure.set_tight_layout(False)
            # self.figure.set_constrained_layout(True)

            # 设置固定边距
            self.figure.subplots_adjust(
                left=0.02, right=0.98,
                top=0.98, bottom=0.02,
                hspace=0.1
            )

        except Exception as e:
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(f"优化渲染失败: {str(e)}")

    def _on_render_progress(self, progress: int, message: str):
        """处理渲染进度"""
        self.update_loading_progress(progress, message)

    def _on_render_complete(self):
        """处理渲染完成"""
        self.close_loading_dialog()

    def _on_render_error(self, error: str):
        """处理渲染错误"""
        if hasattr(self, 'error_occurred'):
            self.error_occurred.emit(error)
        self.close_loading_dialog()

    def clear_chart(self):
        """清空图表"""
        try:
            # 清空所有子图
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                ax.cla()

            # 重置数据
            self.current_kdata = None
            self._ymin = 0
            self._ymax = 1

            # 清空十字光标
            if hasattr(self, '_crosshair_lines'):
                # 确保_crosshair_lines是字典类型
                if isinstance(self._crosshair_lines, dict):
                    for line in self._crosshair_lines.values():
                        try:
                            line.remove()
                        except:
                            pass
                else:
                    # 兼容处理列表类型
                    for line in self._crosshair_lines:
                        try:
                            line.remove()
                        except:
                            pass
                # 重置为空字典，与CrosshairMixin保持一致
                self._crosshair_lines = {}

            if hasattr(self, '_crosshair_text') and self._crosshair_text:
                try:
                    self._crosshair_text.remove()
                except:
                    pass
                self._crosshair_text = None

            # 清空股票信息文本
            if hasattr(self, '_stock_info_text') and self._stock_info_text:
                try:
                    self._stock_info_text.remove()
                except:
                    pass
                self._stock_info_text = None

            # 重新绘制
            self.canvas.draw()

        except Exception as e:
            logger.error(f"清空图表失败: {str(e)}")

    def apply_theme(self):
        """应用主题"""
        try:
            if not hasattr(self, 'theme_manager') or not self.theme_manager:
                return

            colors = self.theme_manager.get_theme_colors()
            
            # 处理颜色格式，确保rgba格式被正确解析
            processed_colors = {}
            for key, value in colors.items():
                if isinstance(value, str) and value.startswith('rgba('):
                    # 解析rgba格式
                    try:
                        rgba_content = value[5:-1]  # 去掉 "rgba(" 和 ")"
                        parts = [part.strip() for part in rgba_content.split(',')]
                        if len(parts) >= 4:
                            r, g, b = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
                            processed_colors[key] = (r, g, b)
                        else:
                            processed_colors[key] = value
                    except (ValueError, IndexError):
                        processed_colors[key] = value
                else:
                    processed_colors[key] = value
            
            bg_color = processed_colors.get('chart_background', '#ffffff')
            
            # 处理背景色格式
            if isinstance(bg_color, tuple) and len(bg_color) >= 3:
                bg_color = bg_color[:3]  # 使用RGB部分

            # 设置图表背景色
            self.figure.patch.set_facecolor(bg_color)

            # 设置各子图背景色
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                ax.set_facecolor(bg_color)

                # 设置网格样式
                grid_color = processed_colors.get('chart_grid', '#e0e0e0')
                ax.grid(True, color=grid_color, alpha=0.3, linewidth=0.5)

                # 设置刻度和标签颜色
                text_color = processed_colors.get('chart_text', '#222b45')
                ax.tick_params(colors=text_color)
                ax.xaxis.label.set_color(text_color)
                ax.yaxis.label.set_color(text_color)

            # 重新绘制
            self.canvas.draw()

        except Exception as e:
            logger.error(f"应用主题失败: {str(e)}")
            logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")

    def _init_figure_layout(self):
        """初始化图表布局"""
        try:
            # 创建子图
            self.price_ax = self.figure.add_subplot(211)  # 价格图
            self.volume_ax = self.figure.add_subplot(212)  # 成交量图
            self.indicator_ax = self.volume_ax  # 指标图与成交量图共用

            # 设置子图间距
            self.figure.subplots_adjust(
                left=0.02, right=0.98,
                top=0.98, bottom=0.02,
                hspace=0.1
            )

            # 应用主题
            self.apply_theme()

        except Exception as e:
            logger.error(f"初始化图表布局失败: {str(e)}")

    def draw_overview(self, ax, kdata):
        """绘制概览图"""
        try:
            if kdata is None or kdata.empty:
                return

            # 简化的K线图
            x = np.arange(len(kdata))
            ax.plot(x, kdata['close'], color='blue', linewidth=1, alpha=0.7)

            # 设置样式
            ax.set_xlim(0, len(kdata)-1)
            ax.set_ylim(kdata['low'].min(), kdata['high'].max())
            ax.grid(True, alpha=0.3)

        except Exception as e:
            logger.error(f"绘制概览图失败: {str(e)}")

    def show_no_data(self, message: str = "无数据"):
        """无数据时清空图表并显示提示信息，所有字体统一为8号，健壮处理异常，始终显示网格和XY轴刻度"""
        try:
            if hasattr(self, 'figure'):
                self.figure.clear()
                # 重新创建子图，防止后续渲染异常
                self.price_ax = self.figure.add_subplot(211)
                self.volume_ax = self.figure.add_subplot(212)
                self.indicator_ax = self.volume_ax
                # 清空其他内容
                self.price_ax.cla()
                self.volume_ax.cla()
                # 在主图中央显示提示文本
                self.price_ax.text(0.5, 0.5, message,
                                   transform=self.price_ax.transAxes,
                                   fontsize=16, color='#888',
                                   ha='center', va='center', alpha=0.85)
                # 设置默认XY轴刻度和网格
                self.price_ax.set_xlim(0, 1)
                self.price_ax.set_ylim(0, 1)
                self.volume_ax.set_xlim(0, 1)
                self.volume_ax.set_ylim(0, 1)
                self._optimize_display()  # 保证无数据时也显示网格和刻度

                # 使用安全的布局调整方式
                from utils.matplotlib_utils import safe_figure_layout
                safe_figure_layout(self.figure)

                self.canvas.draw()

                # 统一字体大小（全部设为8号）
                for ax in [self.price_ax, self.volume_ax]:
                    for label in (ax.get_xticklabels() + ax.get_yticklabels()):
                        label.set_fontsize(8)
                    ax.title.set_fontsize(8)
                    ax.xaxis.label.set_fontsize(8)
                    ax.yaxis.label.set_fontsize(8)
        except Exception as e:
            if True:  # 使用Loguru日志
                logger.error(f"显示无数据提示失败: {str(e)}")

    def _get_style(self) -> Dict[str, Any]:
        """获取样式配置"""
        return self._get_chart_style()

    def on_period_changed(self, period: str):
        """处理周期变更"""
        try:
            # 这里可以根据周期调整显示样式
            if hasattr(self, 'current_period'):
                self.current_period = period

            # 发射周期变更信号
            if hasattr(self, 'period_changed'):
                self.period_changed.emit(period)

            # 刷新图表
            if hasattr(self, 'current_kdata') and self.current_kdata is not None:
                self.update_chart({'kdata': self.current_kdata})

        except Exception as e:
            logger.error(f"处理周期变更失败: {str(e)}")

    def on_indicator_changed(self, indicator: str):
        """处理指标变更"""
        try:
            # 发射指标变更信号
            if hasattr(self, 'indicator_changed'):
                self.indicator_changed.emit(indicator)

            # 刷新图表
            if hasattr(self, 'current_kdata') and self.current_kdata is not None:
                self.update_chart({'kdata': self.current_kdata})

        except Exception as e:
            logger.error(f"处理指标变更失败: {str(e)}")

    def _optimize_display(self):
        """优化显示效果，所有坐标轴字体统一为8号，始终显示网格和XY轴刻度（任何操作都不隐藏）"""
        try:

            start_time = time.time()

            # 确保所有子图都有网格和刻度
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                if not ax:
                    continue

                # 获取主题颜色
                colors = self.theme_manager.get_theme_colors()
                grid_color = colors.get('chart_grid', '#e0e0e0')
                text_color = colors.get('chart_text', '#222b45')

                # 设置网格
                ax.grid(True, linestyle='--', alpha=0.3, color=grid_color)

                # 设置刻度样式
                ax.tick_params(axis='both', which='major',
                               labelsize=8, colors=text_color)
                ax.tick_params(axis='y', which='major', labelleft=True)

                # 设置所有文本字体大小
                for label in (ax.get_yticklabels()):
                    label.set_fontsize(8)
                    label.set_color(text_color)

                # 设置标题和标签字体
                if ax.get_title():
                    ax.title.set_fontsize(8)
                    ax.title.set_color(text_color)
                ax.xaxis.label.set_fontsize(8)
                ax.xaxis.label.set_color(text_color)
                ax.yaxis.label.set_fontsize(8)
                ax.yaxis.label.set_color(text_color)

            # 只设置indicator_ax的X轴刻度样式，其他子图隐藏X轴
            if self.price_ax:
                self.price_ax.set_xticklabels([])
                self.price_ax.tick_params(
                    axis='x', which='both', bottom=False, top=False, labelbottom=False)

            if self.volume_ax and self.volume_ax != self.indicator_ax:
                self.volume_ax.set_xticklabels([])
                self.volume_ax.tick_params(
                    axis='x', which='both', bottom=False, top=False, labelbottom=False)

            if self.indicator_ax:
                self.indicator_ax.tick_params(
                    axis='x', which='major', labelsize=8, labelbottom=True, colors=text_color)
                for label in self.indicator_ax.get_xticklabels():
                    label.set_fontsize(8)
                    label.set_color(text_color)
                    label.set_rotation(30)

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"_optimize_display，耗时: {render_time:.2f}ms")

        except Exception as e:
            logger.error(f"优化显示失败: {str(e)}")
