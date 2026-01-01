# 策略管理器UI全面分析与优化增强方案

## 文档信息
- **创建日期**: 2025-12-31
- **分析版本**: EnhancedStrategyManagerDialog v1.0
- **分析范围**: UI界面 + 后端业务逻辑 + 调用链 + 业务框架

---

## 一、系统架构概览

### 1.1 整体架构层次

```
┌─────────────────────────────────────────────────────────────┐
│                     UI Presentation Layer                     │
│  EnhancedStrategyManagerDialog (4935 lines)                 │
│  ├─ EnhancedStrategyTable (策略表格)                         │
│  ├─ StrategyCreationWizard (策略创建向导)                    │
│  └─ ServiceContainer (服务容器/依赖注入)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer (服务层)                     │
│  ├─ StrategyService (策略管理服务)                            │
│  ├─ TradingService (交易服务)                                │
│  └─ DatabaseService (数据库服务)                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                       │
│  ├─ StrategyEngine (策略执行引擎)                            │
│  ├─ StrategyFactory (策略工厂)                               │
│  ├─ StrategyRegistry (策略注册器)                            │
│  └─ StrategyDatabase (策略数据库)                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Core Framework Layer                      │
│  ├─ BaseStrategy (策略基类)                                  │
│  ├─ StrategyExtensions (策略扩展)                            │
│  ├─ EventBus (事件总线)                                      │
│  └─ ThemeManager (主题管理器)                                │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件关系图

```
EnhancedStrategyManagerDialog
    │
    ├─→ StrategyService (策略服务)
    │       ├─→ StrategyFactory (创建策略实例)
    │       ├─→ StrategyRegistry (策略注册)
    │       ├─→ StrategyDatabase (持久化)
    │       └─→ PluginFactories (插件工厂)
    │
    ├─→ TradingService (交易服务)
    │       ├─→ OrderManager (订单管理)
    │       ├─→ PositionManager (持仓管理)
    │       └─→ PortfolioManager (组合管理)
    │
    ├─→ EventBus (事件总线)
    │       ├─→ StrategyStartedEvent
    │       ├─→ StrategyStoppedEvent
    │       ├─→ SignalGeneratedEvent
    │       └─→ PerformanceUpdatedEvent
    │
    └─→ ThemeManager (主题管理)
            ├─→ Light Theme
            ├─→ Dark Theme
            └─→ Gradient Theme
```

---

## 二、UI代码结构与功能分析

### 2.1 主要UI组件

#### 2.1.1 EnhancedStrategyManagerDialog (主对话框)
**文件位置**: `gui/dialogs/enhanced_strategy_manager_dialog.py`

**核心功能**:
- 策略列表展示和管理
- 策略创建向导
- 策略参数配置
- 策略状态监控
- 策略性能展示
- 回测和优化功能

**UI布局结构**:
```
EnhancedStrategyManagerDialog
├─ Left Panel (左侧面板)
│   ├─ 策略列表工具栏
│   │   ├─ 创建/刷新/导入/导出按钮
│   │   ├─ 搜索框
│   │   ├─ 状态筛选下拉框
│   │   └─ 批量操作按钮
│   └─ EnhancedStrategyTable (策略表格)
│       ├─ 选择列
│       ├─ 策略ID
│       ├─ 框架类型
│       ├─ 状态
│       ├─ 性能
│       └─ 操作按钮
│
└─ Right Panel (右侧面板)
    ├─ TabWidget (选项卡)
    │   ├─ 参数配置选项卡
    │   ├─ 回测选项卡
    │   ├─ 优化选项卡
    │   ├─ 快速执行选项卡
    │   ├─ 监控选项卡
    │   ├─ 模板管理选项卡
    │   └─ 分组管理选项卡
    └─ 策略详情展示区
```

#### 2.1.2 EnhancedStrategyTable (增强型策略表格)
**特性**:
- 支持多选和批量操作
- 右键菜单上下文操作
- 搜索和筛选功能
- 状态过滤
- 拖拽排序（待实现）

**信号定义**:
```python
strategy_selected = pyqtSignal(str)  # 策略ID
batch_operation_requested = pyqtSignal(str)  # 批量操作类型
```

#### 2.1.3 StrategyCreationWizard (策略创建向导)
**功能**:
- 分步创建策略
- 策略类型选择
- 参数配置向导
- 策略预览和确认

### 2.2 UI功能模块详解

#### 2.2.1 策略列表管理
**实现位置**: `_create_left_panel()`, `EnhancedStrategyTable`

**功能点**:
- ✅ 策略列表展示
- ✅ 策略搜索
- ✅ 状态筛选
- ✅ 批量操作（启动/停止/删除）
- ✅ 策略复制
- ✅ 策略导出
- ❌ 策略分组显示（部分实现）
- ❌ 策略排序
- ❌ 策略标签过滤

**代码片段**:
```python
# 创建策略表格
self.strategy_table = EnhancedStrategyTable()
self.strategy_table.strategy_selected.connect(self._on_strategy_selected)
self.strategy_table.batch_operation_requested.connect(self._on_batch_operation)

# 搜索功能
self.search_edit = QLineEdit()
self.search_edit.setPlaceholderText("搜索策略...")
self.search_edit.textChanged.connect(self._on_search_text_changed)

# 状态筛选
self.status_filter = QComboBox()
self.status_filter.addItems(["全部状态", "已配置", "运行中", "错误"])
self.status_filter.currentTextChanged.connect(self._on_status_filter_changed)
```

#### 2.2.2 参数配置选项卡
**实现位置**: `_create_config_tab()`

**功能点**:
- ✅ 动态参数表单生成
- ✅ 参数类型适配（SpinBox, DoubleSpinBox, ComboBox等）
- ✅ 参数验证
- ✅ 配置保存
- ❌ 参数预设模板
- ❌ 参数历史记录
- ❌ 参数依赖关系显示

**代码片段**:
```python
def _create_config_tab(self):
    """创建参数配置选项卡"""
    tab = QWidget()
    layout = QVBoxLayout(tab)
    
    # 参数配置表单
    self.config_form = QScrollArea()
    self.config_widget = QWidget()
    self.config_layout = QFormLayout(self.config_widget)
    self.config_form.setWidget(self.config_widget)
    self.config_form.setWidgetResizable(True)
    
    layout.addWidget(self.config_form)
    
    # 保存按钮
    save_button = QPushButton("保存配置")
    save_button.clicked.connect(self._save_config)
    layout.addWidget(save_button)
    
    return tab
```

#### 2.2.3 回测功能选项卡
**实现位置**: `_create_backtest_tab()`

**功能点**:
- ✅ 回测参数配置
- ✅ 回测任务提交
- ✅ 回测进度显示
- ✅ 回测结果展示（文本）
- ❌ 回测结果图表化
- ❌ 回测历史记录
- ❌ 回测结果对比

**代码片段**:
```python
def _create_backtest_tab(self):
    """创建回测选项卡"""
    tab = QWidget()
    layout = QVBoxLayout(tab)
    
    # 回测配置
    config_group = QGroupBox("回测配置")
    config_layout = QFormLayout(config_group)
    
    # 股票代码
    self.backtest_symbols_edit = QLineEdit()
    config_layout.addRow("股票代码:", self.backtest_symbols_edit)
    
    # 日期范围
    self.backtest_start_date = QDateEdit()
    self.backtest_end_date = QDateEdit()
    config_layout.addRow("日期范围:", self.backtest_start_date)
    
    # 运行回测按钮
    self.run_backtest_button = QPushButton("运行回测")
    self.run_backtest_button.clicked.connect(self._run_backtest)
    
    # 回测结果
    self.backtest_result_text = QTextEdit()
    self.backtest_result_text.setReadOnly(True)
    
    return tab
```

#### 2.2.4 优化功能选项卡
**实现位置**: `_create_optimization_tab()`

**功能点**:
- ✅ 优化参数配置
- ✅ 优化算法选择
- ✅ 优化任务提交
- ✅ 优化进度显示
- ❌ 优化过程可视化
- ❌ 参数重要性分析
- ❌ 优化历史对比

#### 2.2.5 快速执行选项卡
**实现位置**: `_create_quick_execution_tab()`

**功能点**:
- ✅ 快速策略选择
- ✅ 简化参数配置
- ✅ 一键执行
- ✅ 结果展示
- ❌ 执行历史
- ❌ 执行结果对比

#### 2.2.6 监控选项卡
**实现位置**: `_create_monitoring_tab()`

**功能点**:
- ✅ 实时状态显示
- ✅ 信号历史表格
- ✅ 交易历史表格
- ❌ 实时图表
- ❌ 告警设置
- ❌ 性能指标图表

#### 2.2.7 模板管理选项卡
**实现位置**: `_create_templates_tab()`

**功能点**:
- ✅ 模板列表展示
- ✅ 创建新模板
- ✅ 模板刷新
- ❌ 模板编辑
- ❌ 模板删除
- ❌ 模板导入/导出

#### 2.2.8 分组管理选项卡
**实现位置**: `_create_groups_tab()`

**功能点**:
- ✅ 分组列表展示
- ✅ 创建新分组
- ✅ 分组颜色选择
- ✅ 策略数量统计
- ❌ 分组编辑
- ❌ 分组删除
- ❌ 策略拖拽到分组

### 2.3 UI交互流程

#### 2.3.1 策略创建流程
```
用户点击"创建策略"
    ↓
打开StrategyCreationWizard
    ↓
选择策略类型（factorweave/backtrader/custom）
    ↓
配置策略参数
    ↓
预览策略信息
    ↓
确认创建
    ↓
调用StrategyService.create_strategy_config()
    ↓
发布StrategyConfigCreatedEvent
    ↓
刷新策略列表
```

#### 2.3.2 策略回测流程
```
用户选择策略
    ↓
切换到回测选项卡
    ↓
配置回测参数（股票代码、日期范围等）
    ↓
点击"运行回测"
    ↓
调用StrategyService.run_backtest()
    ↓
创建BacktestTask
    ↓
异步执行回测
    ↓
更新进度条
    ↓
回测完成，显示结果
    ↓
发布BacktestCompletedEvent
```

#### 2.3.3 策略优化流程
```
用户选择策略
    ↓
切换到优化选项卡
    ↓
配置优化参数（优化算法、参数范围等）
    ↓
点击"运行优化"
    ↓
调用StrategyService.run_optimization()
    ↓
创建OptimizationTask
    ↓
异步执行优化
    ↓
更新进度条
    ↓
优化完成，显示最优参数
    ↓
发布OptimizationCompletedEvent
```

---

## 三、后端业务逻辑分析

### 3.1 StrategyService (策略服务)

**文件位置**: `core/services/strategy_service.py`

**核心职责**:
1. 策略插件管理和注册
2. 策略配置管理
3. 策略回测服务
4. 策略优化服务
5. 策略评估和性能分析
6. 策略模板管理

#### 3.1.1 策略插件管理
**实现位置**: `_load_strategy_plugins()`, `_register_builtin_plugin_factories()`

**支持的插件类型**:
- `factorweave`: FactorWeave量化策略
- `backtrader`: Backtrader回测框架
- `adj_momentum`: 复权价格动量策略
- `vwap_reversion`: VWAP均值回归策略
- `custom`: 自定义策略

**插件工厂注册**:
```python
def _register_builtin_plugin_factories(self) -> None:
    """注册内置策略插件工厂"""
    try:
        from plugins.strategies.adaptive_strategy import create_adaptive_pandas_strategy
        self._plugin_factories['factorweave'] = lambda: create_adaptive_pandas_strategy()
    except ImportError:
        logger.warning("FactorWeave策略插件不可用")
    
    try:
        from plugins.strategies.backtrader_strategy_plugin import BacktraderStrategyPlugin
        self._plugin_factories['backtrader'] = lambda: BacktraderStrategyPlugin()
    except ImportError:
        logger.warning("Backtrader策略插件不可用")
    
    # ... 其他插件
```

#### 3.1.2 策略配置管理
**数据结构**:
```python
@dataclass
class StrategyConfig:
    """策略配置"""
    strategy_id: str
    plugin_type: str  # 'factorweave', 'backtrader', 'custom'
    parameters: Dict[str, Any]
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**核心方法**:
- `create_strategy_config()`: 创建策略配置
- `update_strategy_config()`: 更新策略配置
- `delete_strategy_config()`: 删除策略配置
- `get_strategy_config()`: 获取策略配置
- `get_all_strategy_configs()`: 获取所有策略配置

**数据库存储**:
```python
# 保存到数据库
sql = """
INSERT INTO strategy_configs (
    strategy_id, plugin_type, parameters, enabled, created_at, updated_at, metadata
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""
with database_service.get_connection("strategy_sqlite") as conn:
    conn.execute(sql, (
        strategy_id,
        plugin_type,
        json.dumps(parameters),
        config.enabled,
        config.created_at.isoformat(),
        config.updated_at.isoformat(),
        json.dumps(config.metadata)
    ))
```

#### 3.1.3 策略回测服务
**数据结构**:
```python
@dataclass
class BacktestTask:
    """回测任务"""
    task_id: str
    strategy_config: StrategyConfig
    market_data: StandardMarketData
    context: StrategyContext
    status: BacktestStatus = BacktestStatus.PENDING
    progress: float = 0.0
    result: Optional[PerformanceMetrics] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

**回测流程**:
```python
async def run_backtest(self, strategy_id: str, market_data: Any, context: Any) -> str:
    """运行回测"""
    # 1. 获取策略配置
    config = self.get_strategy_config(strategy_id)
    
    # 2. 创建回测任务
    task_id = str(uuid.uuid4())
    task = BacktestTask(
        task_id=task_id,
        strategy_config=config,
        market_data=market_data,
        context=context
    )
    self._backtest_tasks[task_id] = task
    
    # 3. 异步执行回测
    async def _execute_backtest():
        try:
            task.status = BacktestStatus.RUNNING
            task.started_at = datetime.now()
            
            # 创建策略插件实例
            plugin = self.create_strategy_plugin(config.plugin_type)
            plugin.initialize_strategy(context, config.parameters)
            
            # 生成信号
            signals = plugin.generate_signals(market_data, context)
            
            # 计算性能指标
            performance = self._calculate_performance(signals, market_data)
            
            task.result = performance
            task.status = BacktestStatus.COMPLETED
            task.completed_at = datetime.now()
            
        except Exception as e:
            task.status = BacktestStatus.FAILED
            task.error_message = str(e)
    
    # 4. 启动异步任务
    self._running_backtests[task_id] = asyncio.create_task(_execute_backtest())
    
    return task_id
```

#### 3.1.4 策略优化服务
**数据结构**:
```python
@dataclass
class OptimizationTask:
    """优化任务"""
    task_id: str
    strategy_config: StrategyConfig
    optimization_params: Dict[str, Any]
    market_data: StandardMarketData
    context: StrategyContext
    status: OptimizationStatus = OptimizationStatus.PENDING
    progress: float = 0.0
    best_parameters: Optional[Dict[str, Any]] = None
    best_performance: Optional[PerformanceMetrics] = None
    optimization_history: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

**优化流程**:
```python
async def run_optimization(self, strategy_id: str, optimization_params: Dict, market_data: Any, context: Any) -> str:
    """运行优化"""
    # 1. 获取策略配置
    config = self.get_strategy_config(strategy_id)
    
    # 2. 创建优化任务
    task_id = str(uuid.uuid4())
    task = OptimizationTask(
        task_id=task_id,
        strategy_config=config,
        optimization_params=optimization_params,
        market_data=market_data,
        context=context
    )
    self._optimization_tasks[task_id] = task
    
    # 3. 异步执行优化
    async def _execute_optimization():
        try:
            task.status = OptimizationStatus.RUNNING
            task.started_at = datetime.now()
            
            # 获取优化算法
            algorithm = optimization_params.get('algorithm', 'grid_search')
            
            # 执行优化
            if algorithm == 'grid_search':
                best_params = await self._grid_search(task)
            elif algorithm == 'random_search':
                best_params = await self._random_search(task)
            elif algorithm == 'bayesian':
                best_params = await self._bayesian_optimization(task)
            
            task.best_parameters = best_params
            task.status = OptimizationStatus.COMPLETED
            task.completed_at = datetime.now()
            
        except Exception as e:
            task.status = OptimizationStatus.FAILED
            task.error_message = str(e)
    
    # 4. 启动异步任务
    self._running_optimizations[task_id] = asyncio.create_task(_execute_optimization())
    
    return task_id
```

#### 3.1.5 动态并发控制
**实现位置**: `_update_concurrent_limits()`

**特性**:
- 基于系统资源动态调整并发数
- CPU核心数、内存使用率、CPU使用率综合考量
- 高负载时自动降低并发
- 低负载时提高并发

```python
def _update_concurrent_limits(self):
    """根据系统资源动态调整并发限制"""
    try:
        # 获取CPU核心数
        cpu_count = os.cpu_count() or 4
        # 获取可用内存（GB）
        available_mem_gb = psutil.virtual_memory().available / (1024 ** 3)
        # 获取CPU使用率
        cpu_usage = psutil.cpu_percent(interval=0.1)
        # 获取内存使用率
        mem_usage = psutil.virtual_memory().percent
        
        # 基于资源使用情况动态调整并发数
        base_backtests = max(1, cpu_count // 2)
        base_optimizations = max(1, cpu_count // 4)
        
        # 根据系统负载调整
        load_factor = 1.0
        if cpu_usage > 70 or mem_usage > 80:
            load_factor = 0.5  # 高负载
        elif cpu_usage > 50 or mem_usage > 60:
            load_factor = 0.8  # 中等负载
        elif cpu_usage < 30 and mem_usage < 40:
            load_factor = 1.5  # 低负载
        
        # 计算最终并发限制
        self._max_concurrent_backtests = max(1, int(base_backtests * load_factor))
        self._max_concurrent_optimizations = max(1, int(base_optimizations * load_factor))
        
    except Exception as e:
        logger.error(f"更新并发限制失败: {e}")
        self._max_concurrent_backtests = 3
        self._max_concurrent_optimizations = 1
```

### 3.2 TradingService (交易服务)

**文件位置**: `core/services/trading_service.py`

**核心职责**:
1. 订单管理
2. 持仓管理
3. 投资组合管理
4. 风险控制
5. 交易执行

#### 3.2.1 订单管理
**数据结构**:
```python
@dataclass
class TradingOrder:
    """交易订单"""
    order_id: str
    symbol: str
    symbol_name: str
    order_type: OrderType
    side: OrderSide
    quantity: int
    price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    created_time: datetime = field(default_factory=datetime.now)
    filled_time: Optional[datetime] = None
    filled_quantity: int = 0
    filled_price: Optional[Decimal] = None
    commission: Decimal = Decimal('0')
```

#### 3.2.2 持仓管理
**数据结构**:
```python
@dataclass
class Position:
    """持仓信息"""
    symbol: str
    symbol_name: str
    quantity: int
    cost_price: Decimal
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    profit_loss: Optional[Decimal] = None
    profit_loss_ratio: Optional[float] = None
    last_update: datetime = field(default_factory=datetime.now)
```

#### 3.2.3 投资组合管理
**数据结构**:
```python
@dataclass
class Portfolio:
    """投资组合"""
    portfolio_id: str
    name: str
    positions: Dict[str, Position] = field(default_factory=dict)
    cash: Decimal = Decimal('0')
    total_cost: Decimal = Decimal('0')
    total_market_value: Decimal = Decimal('0')
    total_profit_loss: Decimal = Decimal('0')
```

### 3.3 StrategyEngine (策略执行引擎)

**文件位置**: `core/strategy/strategy_engine.py`

**核心职责**:
1. 策略实例管理
2. 策略执行调度
3. 缓存管理
4. 性能监控

#### 3.3.1 策略缓存
**实现位置**: `StrategyCache`

**特性**:
- LRU缓存策略
- 细粒度缓存控制
- 策略分组管理
- 缓存统计
- 优先级支持

```python
class StrategyCache:
    """策略缓存管理器 - 支持细粒度缓存控制"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.default_ttl = ttl_seconds
        
        # 缓存存储 - 支持按策略分组
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._strategy_groups: Dict[str, List[str]] = {}
        
        # 统计信息
        self._hits = 0
        self._misses = 0
        self._evictions = 0
```

### 3.4 StrategyFactory (策略工厂)

**文件位置**: `core/strategy/strategy_factory.py`

**核心职责**:
1. 策略实例创建
2. 策略参数管理
3. 策略验证
4. 数据库集成

```python
class StrategyFactory:
    """策略工厂 - 统一的策略创建和管理"""
    
    def create_strategy(self, strategy_name: str, instance_name: str = None, **kwargs) -> Optional[BaseStrategy]:
        """创建策略实例"""
        # 1. 获取策略类
        strategy_class = self.registry.get_strategy_class(strategy_name)
        
        # 2. 创建实例
        strategy = strategy_class(name=instance_name)
        
        # 3. 设置参数
        for param_name, param_value in kwargs.items():
            strategy.set_parameter(param_name, param_value)
        
        # 4. 验证参数
        valid, errors = strategy.validate_parameters()
        if not valid:
            return None
        
        # 5. 缓存实例
        self._instances[instance_name] = strategy
        
        return strategy
```

### 3.5 StrategyRegistry (策略注册器)

**文件位置**: `core/strategy/strategy_registry.py`

**核心职责**:
1. 策略注册
2. 策略发现
3. 策略查询
4. 数据库集成

```python
class StrategyRegistry:
    """策略注册器"""
    
    def register(self, strategy_name: str, strategy_class: Type[BaseStrategy], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """注册策略"""
        # 1. 验证策略类
        if not issubclass(strategy_class, BaseStrategy):
            return False
        
        # 2. 提取元数据
        if metadata is None:
            metadata = self._extract_metadata(strategy_class)
        
        # 3. 注册到内存
        self._strategies[strategy_name] = strategy_class
        self._metadata[strategy_name] = metadata
        
        # 4. 注册到数据库
        strategy_id = self.db_manager.register_strategy(strategy_class, metadata)
        
        return True
```

### 3.6 StrategyDatabase (策略数据库)

**文件位置**: `core/strategy/strategy_database.py`

**核心职责**:
1. 策略持久化
2. 策略查询
3. 策略更新
4. 策略删除

**数据库表结构**:
```sql
-- 策略基本信息表
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    strategy_type TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0.0',
    author TEXT DEFAULT '',
    description TEXT DEFAULT '',
    category TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    class_path TEXT NOT NULL
)

-- 策略参数表
CREATE TABLE strategy_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    param_name TEXT NOT NULL,
    param_value TEXT NOT NULL,
    param_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    min_value TEXT DEFAULT NULL,
    max_value TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE,
    UNIQUE(strategy_id, param_name)
)

-- 策略执行历史表
CREATE TABLE strategy_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_hash TEXT NOT NULL,
    signals_count INTEGER DEFAULT 0,
    execution_duration REAL DEFAULT 0.0,
    success BOOLEAN DEFAULT 1,
    error_message TEXT DEFAULT NULL,
    performance_metrics TEXT DEFAULT '{}',
    FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE
)

-- 策略信号表
CREATE TABLE strategy_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    signal_type TEXT NOT NULL,
    price REAL NOT NULL,
    confidence REAL NOT NULL,
    reason TEXT DEFAULT '',
    stop_loss REAL DEFAULT NULL,
    take_profit REAL DEFAULT NULL,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (execution_id) REFERENCES strategy_executions (id) ON DELETE CASCADE
)
```

---

## 四、调用链分析

### 4.1 策略创建调用链

```
UI: EnhancedStrategyManagerDialog._create_strategy()
    ↓
UI: StrategyCreationWizard.exec_()
    ↓
UI: StrategyCreationWizard._create_strategy()
    ↓
Service: StrategyService.create_strategy_config()
    ↓
Service: StrategyService._strategy_configs[strategy_id] = config
    ↓
Service: DatabaseService.execute(INSERT INTO strategy_configs...)
    ↓
EventBus: publish(StrategyConfigCreatedEvent)
    ↓
UI: EnhancedStrategyManagerDialog._load_strategies()
    ↓
UI: EnhancedStrategyTable.refresh()
```

### 4.2 策略回测调用链

```
UI: EnhancedStrategyManagerDialog._run_backtest()
    ↓
Service: StrategyService.run_backtest()
    ↓
Service: StrategyService._backtest_tasks[task_id] = BacktestTask
    ↓
Service: asyncio.create_task(_execute_backtest())
    ↓
Service: StrategyService.create_strategy_plugin()
    ↓
Plugin: IStrategyPlugin.initialize_strategy()
    ↓
Plugin: IStrategyPlugin.generate_signals()
    ↓
Service: StrategyService._calculate_performance()
    ↓
Service: BacktestTask.result = PerformanceMetrics
    ↓
EventBus: publish(BacktestCompletedEvent)
    ↓
UI: EnhancedStrategyManagerDialog._on_backtest_completed()
    ↓
UI: EnhancedStrategyManagerDialog._display_backtest_result()
```

### 4.3 策略优化调用链

```
UI: EnhancedStrategyManagerDialog._run_optimization()
    ↓
Service: StrategyService.run_optimization()
    ↓
Service: StrategyService._optimization_tasks[task_id] = OptimizationTask
    ↓
Service: asyncio.create_task(_execute_optimization())
    ↓
Service: StrategyService._grid_search() / _random_search() / _bayesian_optimization()
    ↓
Service: StrategyService.run_backtest() (多次)
    ↓
Service: OptimizationTask.best_parameters = best_params
    ↓
EventBus: publish(OptimizationCompletedEvent)
    ↓
UI: EnhancedStrategyManagerDialog._on_optimization_completed()
    ↓
UI: EnhancedStrategyManagerDialog._display_optimization_result()
```

### 4.4 策略执行调用链

```
UI: EnhancedStrategyManagerDialog._quick_execute_strategy()
    ↓
Service: StrategyService.create_strategy_plugin()
    ↓
Plugin: IStrategyPlugin.initialize_strategy()
    ↓
Plugin: IStrategyPlugin.generate_signals()
    ↓
Service: TradingService.execute_orders()
    ↓
Service: TradingService._update_positions()
    ↓
Service: TradingService._update_portfolio()
    ↓
EventBus: publish(TradeExecutedEvent)
    ↓
EventBus: publish(PositionUpdatedEvent)
    ↓
UI: EnhancedStrategyManagerDialog._on_trade_executed()
    ↓
UI: EnhancedStrategyManagerDialog._on_position_updated()
```

### 4.5 事件驱动调用链

```
EventBus: publish(StrategyConfigCreatedEvent)
    ↓
Subscriber 1: EnhancedStrategyManagerDialog._on_strategy_config_created()
    ↓
Subscriber 2: TradingService._on_strategy_config_created()
    ↓
Subscriber 3: MonitoringService._on_strategy_config_created()
    ↓
...
```

---

## 五、业务框架与架构设计

### 5.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  Presentation Layer (表现层)                                 │
│  - EnhancedStrategyManagerDialog                             │
│  - EnhancedStrategyTable                                      │
│  - StrategyCreationWizard                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Service Layer (服务层)                                      │
│  - StrategyService (策略管理)                                 │
│  - TradingService (交易管理)                                 │
│  - DatabaseService (数据管理)                                │
│  - EventBus (事件总线)                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Business Logic Layer (业务逻辑层)                           │
│  - StrategyEngine (策略引擎)                                  │
│  - StrategyFactory (策略工厂)                                 │
│  - StrategyRegistry (策略注册器)                              │
│  - StrategyDatabase (策略数据库)                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Core Framework Layer (核心框架层)                           │
│  - BaseStrategy (策略基类)                                    │
│  - StrategyExtensions (策略扩展)                              │
│  - IStrategyPlugin (策略插件接口)                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Infrastructure Layer (基础设施层)                            │
│  - Database (SQLite)                                         │
│  - Logging (loguru)                                          │
│  - Configuration (config_manager)                           │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 设计模式

#### 5.2.1 工厂模式
**实现**: `StrategyFactory`
**用途**: 统一创建策略实例
**优势**: 
- 解耦策略创建和使用
- 支持多种策略类型
- 易于扩展新策略

#### 5.2.2 注册表模式
**实现**: `StrategyRegistry`
**用途**: 策略注册和发现
**优势**:
- 集中管理策略
- 支持动态注册
- 便于查询和检索

#### 5.2.3 插件模式
**实现**: `IStrategyPlugin` 接口
**用途**: 支持多种策略框架
**优势**:
- 高度可扩展
- 模块化设计
- 易于维护

#### 5.2.4 观察者模式
**实现**: `EventBus`
**用途**: 事件驱动架构
**优势**:
- 松耦合
- 异步通信
- 易于扩展

#### 5.2.5 依赖注入
**实现**: `ServiceContainer`
**用途**: 服务管理
**优势**:
- 降低耦合
- 易于测试
- 便于替换实现

#### 5.2.6 缓存模式
**实现**: `StrategyCache`
**用途**: 性能优化
**优势**:
- 减少重复计算
- 提高响应速度
- 降低资源消耗

### 5.3 核心接口

#### 5.3.1 IStrategyPlugin
```python
class IStrategyPlugin(ABC):
    """策略插件接口"""
    
    @abstractmethod
    def get_strategy_info(self) -> StrategyInfo:
        """获取策略信息"""
        pass
    
    @abstractmethod
    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]):
        """初始化策略"""
        pass
    
    @abstractmethod
    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """生成交易信号"""
        pass
    
    @abstractmethod
    def destroy(self):
        """销毁策略"""
        pass
```

#### 5.3.2 IStrategyService
```python
class IStrategyService(ABC):
    """策略服务接口"""
    
    @abstractmethod
    def get_all_strategy_configs(self) -> List[StrategyConfig]:
        """获取所有策略配置"""
        pass
    
    @abstractmethod
    def create_strategy_config(self, config: StrategyConfig) -> bool:
        """创建策略配置"""
        pass
    
    @abstractmethod
    async def run_backtest(self, strategy_id: str, market_data: Any, context: Any) -> str:
        """运行回测"""
        pass
    
    @abstractmethod
    async def run_optimization(self, strategy_id: str, optimization_params: Dict, market_data: Any, context: Any) -> str:
        """运行优化"""
        pass
```

### 5.4 数据流

#### 5.4.1 策略配置数据流
```
用户输入 → UI表单 → StrategyConfig → StrategyService → Database
```

#### 5.4.2 市场数据流
```
数据源 → StandardMarketData → IStrategyPlugin → Signals → TradingService
```

#### 5.4.3 回测结果数据流
```
Signals → PerformanceMetrics → BacktestTask → UI展示
```

---

## 六、代码层面优化方案

### 6.1 高优先级优化

#### 6.1.1 线程生命周期管理优化
**问题**: 定时器和线程没有在对话框关闭时正确清理，可能导致内存泄漏

**优化方案**:
```python
def closeEvent(self, event):
    """关闭事件 - 完善资源清理"""
    try:
        # 停止所有定时器
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
            self.status_timer.deleteLater()
        if hasattr(self, 'monitor_timer'):
            self.monitor_timer.stop()
            self.monitor_timer.deleteLater()
        
        # 取消所有待执行的线程任务
        if hasattr(self, 'strategy_loader_thread'):
            self.strategy_loader_thread.quit()
            self.strategy_loader_thread.wait()
        if hasattr(self, 'strategy_details_loader_thread'):
            self.strategy_details_loader_thread.quit()
            self.strategy_details_loader_thread.wait()
        
        # 清理所有子控件
        self._cleanup_widgets()
        
        # 断开信号连接
        self._disconnect_signals()
        
        logger.info("策略管理器对话框资源清理完成")
        event.accept()
    except Exception as e:
        logger.error(f"关闭对话框时出错: {e}")
        event.accept()

def _cleanup_widgets(self):
    """清理所有子控件"""
    for child in self.findChildren(QWidget):
        try:
            child.deleteLater()
        except Exception as e:
            logger.warning(f"清理控件失败: {e}")

def _disconnect_signals(self):
    """断开所有信号连接"""
    try:
        self.strategy_table.strategy_selected.disconnect()
        self.strategy_table.batch_operation_requested.disconnect()
        # ... 其他信号
    except Exception as e:
        logger.warning(f"断开信号连接失败: {e}")
```

#### 6.1.2 统一使用QRunnable工作线程模式
**问题**: 直接使用QThread而非更现代的QRunnable+QThreadPool模式

**优化方案**:
```python
class StrategyLoaderRunnable(QRunnable):
    """策略加载任务"""
    
    def __init__(self, strategy_service, callback):
        super().__init__()
        self.strategy_service = strategy_service
        self.callback = callback
        self.setAutoDelete(True)
    
    def run(self):
        try:
            configs = self.strategy_service.get_all_strategy_configs()
            QMetaObject.invokeMethod(
                self.callback,
                "load_strategies",
                Qt.QueuedConnection,
                Q_ARG(list, configs)
            )
        except Exception as e:
            QMetaObject.invokeMethod(
                self.callback,
                "load_error",
                Qt.QueuedConnection,
                Q_ARG(str, str(e))
            )

# 使用方式
def _load_strategies(self):
    """加载策略列表"""
    runnable = StrategyLoaderRunnable(self.strategy_service, self)
    QThreadPool.globalInstance().start(runnable)
```

#### 6.1.3 异常处理增强
**问题**: 部分异步操作缺乏完整的异常处理和用户反馈

**优化方案**:
```python
class ErrorHandler:
    """统一错误处理器"""
    
    @staticmethod
    def handle_error(error: Exception, context: str = "", show_dialog: bool = True):
        """处理错误"""
        logger.error(f"{context}: {error}", exc_info=True)
        
        if show_dialog:
            QMessageBox.critical(
                None,
                "错误",
                f"{context}\n\n{str(error)}"
            )

# 使用方式
try:
    await self.strategy_service.run_backtest(strategy_id, market_data, context)
except Exception as e:
    ErrorHandler.handle_error(e, "回测执行失败")
```

#### 6.1.4 性能优化
**问题**: 大数据量场景性能未知，频繁调用可能影响性能

**优化方案**:
```python
# 1. 添加虚拟滚动支持
class VirtualScrollingTable(QTableWidget):
    """支持虚拟滚动的表格"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible_range = (0, 100)  # 可见行范围
        self._data_cache = {}
        
    def set_data(self, data: List[Dict]):
        """设置数据"""
        self._data = data
        self._update_visible_items()
    
    def _update_visible_items(self):
        """只更新可见项"""
        start, end = self._visible_range
        for i in range(start, min(end, len(self._data))):
            self._update_row(i, self._data[i])

# 2. 添加分页支持
class PaginatedStrategyTable(QTableWidget):
    """支持分页的策略表格"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_size = 50
        self._current_page = 0
        self._all_data = []
    
    def set_data(self, data: List[Dict]):
        """设置数据"""
        self._all_data = data
        self._current_page = 0
        self._update_page()
    
    def _update_page(self):
        """更新当前页"""
        start = self._current_page * self._page_size
        end = start + self._page_size
        page_data = self._all_data[start:end]
        self._display_data(page_data)
```

### 6.2 中优先级优化

#### 6.2.1 参数验证增强
**优化方案**:
```python
class ParameterValidator:
    """参数验证器"""
    
    @staticmethod
    def validate(param_def: ParameterDef, value: Any) -> Tuple[bool, Optional[str]]:
        """验证参数值"""
        # 类型检查
        if not isinstance(value, param_def.type):
            return False, f"类型错误: 期望 {param_def.type}, 实际 {type(value)}"
        
        # 范围检查
        if param_def.min_value is not None and value < param_def.min_value:
            return False, f"值小于最小值: {param_def.min_value}"
        
        if param_def.max_value is not None and value > param_def.max_value:
            return False, f"值大于最大值: {param_def.max_value}"
        
        # 选择检查
        if param_def.choices is not None and value not in param_def.choices:
            return False, f"值不在可选列表中: {param_def.choices}"
        
        return True, None

# 使用方式
valid, error = ParameterValidator.validate(param_def, value)
if not valid:
    QMessageBox.warning(self, "参数错误", error)
```

#### 6.2.2 日志记录增强
**优化方案**:
```python
class StrategyLogger:
    """策略日志记录器"""
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.logger = logger.bind(strategy_id=strategy_id)
    
    def log_signal(self, signal: Signal):
        """记录信号"""
        self.logger.info(
            f"生成信号: {signal.signal_type.value} "
            f"价格={signal.price} 强度={signal.strength}"
        )
    
    def log_trade(self, trade: TradeResult):
        """记录交易"""
        self.logger.info(
            f"执行交易: {trade.action.value} "
            f"数量={trade.quantity} 价格={trade.price}"
        )
    
    def log_error(self, error: Exception):
        """记录错误"""
        self.logger.error(f"策略错误: {error}", exc_info=True)
```

#### 6.2.3 配置管理增强
**优化方案**:
```python
class StrategyConfigManager:
    """策略配置管理器"""
    
    def __init__(self):
        self._config_history: Dict[str, List[StrategyConfig]] = {}
        self._max_history = 10
    
    def save_config(self, config: StrategyConfig):
        """保存配置"""
        strategy_id = config.strategy_id
        
        # 保存历史
        if strategy_id not in self._config_history:
            self._config_history[strategy_id] = []
        
        self._config_history[strategy_id].append(config)
        
        # 限制历史数量
        if len(self._config_history[strategy_id]) > self._max_history:
            self._config_history[strategy_id].pop(0)
    
    def get_config_history(self, strategy_id: str) -> List[StrategyConfig]:
        """获取配置历史"""
        return self._config_history.get(strategy_id, [])
    
    def restore_config(self, strategy_id: str, index: int) -> Optional[StrategyConfig]:
        """恢复配置"""
        history = self._config_history.get(strategy_id, [])
        if 0 <= index < len(history):
            return history[index]
        return None
```

### 6.3 低优先级优化

#### 6.3.1 单元测试
**优化方案**:
```python
import pytest
from unittest.mock import Mock, patch

class TestStrategyService:
    """策略服务测试"""
    
    @pytest.fixture
    def strategy_service(self):
        """创建策略服务"""
        return StrategyService()
    
    def test_create_strategy_config(self, strategy_service):
        """测试创建策略配置"""
        config = StrategyConfig(
            strategy_id="test_strategy",
            plugin_type="factorweave",
            parameters={}
        )
        
        result = strategy_service.create_strategy_config(config)
        assert result is True
        
        retrieved = strategy_service.get_strategy_config("test_strategy")
        assert retrieved is not None
        assert retrieved.strategy_id == "test_strategy"
    
    def test_run_backtest(self, strategy_service):
        """测试回测"""
        # Mock数据
        market_data = Mock()
        context = Mock()
        
        # 创建策略配置
        config = StrategyConfig(
            strategy_id="test_strategy",
            plugin_type="factorweave",
            parameters={}
        )
        strategy_service.create_strategy_config(config)
        
        # 运行回测
        task_id = asyncio.run(strategy_service.run_backtest(
            "test_strategy", market_data, context
        ))
        
        assert task_id is not None
```

#### 6.3.2 性能监控
**优化方案**:
```python
class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}
    
    def record(self, name: str, value: float):
        """记录指标"""
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)
    
    def get_stats(self, name: str) -> Dict[str, float]:
        """获取统计信息"""
        values = self._metrics.get(name, [])
        if not values:
            return {}
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'median': sorted(values)[len(values) // 2]
        }

# 使用装饰器
def monitor_performance(name: str):
    """性能监控装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            PerformanceMonitor.record(name, duration)
            return result
        return wrapper
    return decorator

# 使用方式
@monitor_performance("load_strategies")
def _load_strategies(self):
    """加载策略列表"""
    # ...
```

---

## 七、UI优化增强方案

### 7.1 视觉设计优化

#### 7.1.1 现代化主题系统
**当前问题**: 主题切换不够流畅，部分组件不支持主题

**优化方案**:
```python
class ModernThemeManager:
    """现代化主题管理器"""
    
    def __init__(self):
        self.themes = {
            'light': LightTheme(),
            'dark': DarkTheme(),
            'gradient': GradientTheme(),
            'blue': BlueTheme(),
            'green': GreenTheme()
        }
        self.current_theme = 'light'
    
    def apply_theme(self, widget: QWidget, theme_name: str):
        """应用主题"""
        theme = self.themes.get(theme_name)
        if not theme:
            return
        
        # 应用样式表
        widget.setStyleSheet(theme.get_stylesheet())
        
        # 递归应用到子控件
        for child in widget.findChildren(QWidget):
            child.setStyleSheet(theme.get_stylesheet())

class LightTheme:
    """浅色主题"""
    
    def get_stylesheet(self) -> str:
        return """
        QWidget {
            background-color: #ffffff;
            color: #333333;
            font-family: 'Microsoft YaHei UI', sans-serif;
            font-size: 9pt;
        }
        
        QGroupBox {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        
        QPushButton:hover {
            background-color: #106ebe;
        }
        
        QPushButton:pressed {
            background-color: #005a9e;
        }
        
        QTableWidget {
            gridline-color: #e0e0e0;
            selection-background-color: #0078d4;
            selection-color: white;
        }
        
        QTabWidget::pane {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }
        
        QTabBar::tab {
            background-color: #f5f5f5;
            color: #333333;
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: #0078d4;
            color: white;
        }
        """
```

#### 7.1.2 信息层次优化
**当前问题**: 信息展示不够清晰，缺乏视觉层次

**优化方案**:
```python
class InfoHierarchyWidget(QWidget):
    """信息层次化展示控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 主要信息（大字体、醒目颜色）
        primary_label = QLabel("主要信息")
        primary_label.setStyleSheet("""
            font-size: 16pt;
            font-weight: bold;
            color: #0078d4;
        """)
        layout.addWidget(primary_label)
        
        # 次要信息（中等字体）
        secondary_label = QLabel("次要信息")
        secondary_label.setStyleSheet("""
            font-size: 12pt;
            color: #666666;
        """)
        layout.addWidget(secondary_label)
        
        # 辅助信息（小字体、灰色）
        tertiary_label = QLabel("辅助信息")
        tertiary_label.setStyleSheet("""
            font-size: 9pt;
            color: #999999;
        """)
        layout.addWidget(tertiary_label)
```

#### 7.1.3 视觉反馈增强
**当前问题**: 缺乏足够的视觉反馈

**优化方案**:
```python
class VisualFeedback:
    """视觉反馈工具"""
    
    @staticmethod
    def show_success(widget: QWidget, message: str, duration: int = 2000):
        """显示成功提示"""
        toast = Toast(widget, message, "success")
        toast.show(duration)
    
    @staticmethod
    def show_error(widget: QWidget, message: str, duration: int = 3000):
        """显示错误提示"""
        toast = Toast(widget, message, "error")
        toast.show(duration)
    
    @staticmethod
    def show_loading(widget: QWidget, message: str = "加载中..."):
        """显示加载动画"""
        loading = LoadingOverlay(widget, message)
        loading.show()
        return loading

class Toast(QWidget):
    """轻量级提示"""
    
    def __init__(self, parent: QWidget, message: str, style: str):
        super().__init__(parent)
        self.message = message
        self.style = style
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        
        # 图标
        icon_label = QLabel()
        if self.style == "success":
            icon_label.setText("✓")
            self.setStyleSheet("""
                background-color: #107c10;
                color: white;
                border-radius: 4px;
            """)
        elif self.style == "error":
            icon_label.setText("✕")
            self.setStyleSheet("""
                background-color: #d13438;
                color: white;
                border-radius: 4px;
            """)
        
        icon_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(icon_label)
        
        # 消息
        message_label = QLabel(self.message)
        layout.addWidget(message_label)
    
    def show(self, duration: int):
        """显示"""
        self.adjustSize()
        self.move(
            self.parent().width() - self.width() - 20,
            self.parent().height() - self.height() - 20
        )
        self.show()
        
        # 自动隐藏
        QTimer.singleShot(duration, self.hide)

class LoadingOverlay(QWidget):
    """加载遮罩"""
    
    def __init__(self, parent: QWidget, message: str = "加载中..."):
        super().__init__(parent)
        self.message = message
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setFixedSize(self.parent().size())
        self.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.5);
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # 加载动画
        movie_label = QLabel()
        movie = QMovie(":/icons/loading.gif")
        movie_label.setMovie(movie)
        movie.start()
        layout.addWidget(movie_label, alignment=Qt.AlignCenter)
        
        # 消息
        message_label = QLabel(self.message)
        message_label.setStyleSheet("""
            color: white;
            font-size: 12pt;
            font-weight: bold;
        """)
        layout.addWidget(message_label, alignment=Qt.AlignCenter)
```

### 7.2 功能增强

#### 7.2.1 策略列表增强
**当前问题**: 策略列表功能过于简陋

**优化方案**:
```python
class EnhancedStrategyTable(QTableWidget):
    """增强型策略表格"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_table()
        self._setup_context_menu()
        self._setup_search()
        self._setup_filter()
        self._setup_sort()
    
    def _setup_sort(self):
        """设置排序功能"""
        header = self.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_clicked)
        
        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder
    
    def _on_header_clicked(self, column: int):
        """表头点击事件"""
        if self._sort_column == column:
            # 切换排序顺序
            self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self._sort_column = column
            self._sort_order = Qt.AscendingOrder
        
        self.sortItems(column, self._sort_order)
    
    def _setup_drag_drop(self):
        """设置拖拽功能"""
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTableWidget.InternalMove)
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasFormat("application/x-strategy-item"):
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """拖拽放置事件"""
        # 处理策略拖拽到分组
        source_row = event.source().currentRow()
        target_row = self.rowAt(event.pos().y())
        
        # 发出信号
        self.strategy_moved.emit(source_row, target_row)
        
        event.accept()
```

#### 7.2.2 回测结果图表化
**当前问题**: 回测结果仅提供纯文本格式

**优化方案**:
```python
class BacktestResultChart(QWidget):
    """回测结果图表"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 图表类型选择
        chart_type_combo = QComboBox()
        chart_type_combo.addItems([
            "权益曲线",
            "回撤分析",
            "收益分布",
            "交易点分析"
        ])
        chart_type_combo.currentTextChanged.connect(self._on_chart_type_changed)
        layout.addWidget(chart_type_combo)
        
        # 图表区域
        self.chart_widget = FigureCanvas(Figure(figsize=(10, 6)))
        layout.addWidget(self.chart_widget)
    
    def _on_chart_type_changed(self, chart_type: str):
        """图表类型改变"""
        if chart_type == "权益曲线":
            self._plot_equity_curve()
        elif chart_type == "回撤分析":
            self._plot_drawdown()
        elif chart_type == "收益分布":
            self._plot_return_distribution()
        elif chart_type == "交易点分析":
            self._plot_trade_points()
    
    def _plot_equity_curve(self):
        """绘制权益曲线"""
        fig = self.chart_widget.figure
        ax = fig.add_subplot(111)
        
        # 绘制权益曲线
        ax.plot(self.equity_curve.index, self.equity_curve.values, label='权益曲线')
        
        # 绘制基准
        if self.benchmark is not None:
            ax.plot(self.benchmark.index, self.benchmark.values, label='基准', linestyle='--')
        
        ax.set_xlabel('日期')
        ax.set_ylabel('权益')
        ax.set_title('权益曲线')
        ax.legend()
        ax.grid(True)
        
        self.chart_widget.draw()
    
    def _plot_drawdown(self):
        """绘制回撤分析"""
        fig = self.chart_widget.figure
        ax = fig.add_subplot(111)
        
        # 计算回撤
        drawdown = self._calculate_drawdown(self.equity_curve)
        
        # 绘制回撤
        ax.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
        ax.plot(drawdown.index, drawdown.values, color='red', label='回撤')
        
        ax.set_xlabel('日期')
        ax.set_ylabel('回撤')
        ax.set_title('回撤分析')
        ax.legend()
        ax.grid(True)
        
        self.chart_widget.draw()
    
    def _plot_return_distribution(self):
        """绘制收益分布"""
        fig = self.chart_widget.figure
        ax = fig.add_subplot(111)
        
        # 计算收益率
        returns = self.equity_curve.pct_change().dropna()
        
        # 绘制直方图
        ax.hist(returns, bins=50, alpha=0.7, color='blue')
        
        # 添加均值线
        ax.axvline(returns.mean(), color='red', linestyle='--', label=f'均值: {returns.mean():.2%}')
        
        ax.set_xlabel('收益率')
        ax.set_ylabel('频数')
        ax.set_title('收益分布')
        ax.legend()
        ax.grid(True)
        
        self.chart_widget.draw()
    
    def _plot_trade_points(self):
        """绘制交易点分析"""
        fig = self.chart_widget.figure
        ax = fig.add_subplot(111)
        
        # 绘制价格曲线
        ax.plot(self.price_curve.index, self.price_curve.values, label='价格')
        
        # 绘制买入点
        buy_points = self.trades[self.trades['action'] == 'buy']
        ax.scatter(buy_points.index, buy_points['price'], color='green', marker='^', s=100, label='买入')
        
        # 绘制卖出点
        sell_points = self.trades[self.trades['action'] == 'sell']
        ax.scatter(sell_points.index, sell_points['price'], color='red', marker='v', s=100, label='卖出')
        
        ax.set_xlabel('日期')
        ax.set_ylabel('价格')
        ax.set_title('交易点分析')
        ax.legend()
        ax.grid(True)
        
        self.chart_widget.draw()
```

#### 7.2.3 优化过程可视化
**当前问题**: 优化功能进度反馈不够直观

**优化方案**:
```python
class OptimizationVisualization(QWidget):
    """优化过程可视化"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 优化进度
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # 优化曲线图
        self.chart_widget = FigureCanvas(Figure(figsize=(10, 6)))
        layout.addWidget(self.chart_widget)
        
        # 参数重要性分析
        self.importance_widget = ParameterImportanceWidget()
        layout.addWidget(self.importance_widget)
        
        # 优化历史对比
        self.history_widget = OptimizationHistoryWidget()
        layout.addWidget(self.history_widget)
    
    def update_progress(self, progress: float, current_params: Dict, current_performance: float):
        """更新进度"""
        self.progress_bar.setValue(int(progress * 100))
        
        # 更新优化曲线
        self._update_optimization_curve(current_params, current_performance)
    
    def _update_optimization_curve(self, params: Dict, performance: float):
        """更新优化曲线"""
        fig = self.chart_widget.figure
        ax = fig.add_subplot(111)
        
        # 绘制优化曲线
        ax.plot(self.iterations, self.performances, 'b-', label='优化过程')
        
        # 标记当前点
        ax.scatter([len(self.iterations)], [performance], color='red', s=100, label='当前')
        
        ax.set_xlabel('迭代次数')
        ax.set_ylabel('性能指标')
        ax.set_title('优化过程')
        ax.legend()
        ax.grid(True)
        
        self.chart_widget.draw()

class ParameterImportanceWidget(QWidget):
    """参数重要性分析"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 参数重要性图表
        self.chart_widget = FigureCanvas(Figure(figsize=(10, 4)))
        layout.addWidget(self.chart_widget)
    
    def update_importance(self, importance: Dict[str, float]):
        """更新参数重要性"""
        fig = self.chart_widget.figure
        ax = fig.add_subplot(111)
        
        # 绘制条形图
        params = list(importance.keys())
        values = list(importance.values())
        
        ax.barh(params, values)
        ax.set_xlabel('重要性')
        ax.set_title('参数重要性分析')
        
        self.chart_widget.draw()
```

#### 7.2.4 策略分组管理
**当前问题**: 策略分组管理功能不完善

**优化方案**:
```python
class StrategyGroupManager(QWidget):
    """策略分组管理器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        
        # 左侧：分组树
        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderLabels(["分组", "策略数"])
        self.group_tree.setDragEnabled(True)
        self.group_tree.setAcceptDrops(True)
        self.group_tree.setDragDropMode(QTreeWidget.InternalMove)
        layout.addWidget(self.group_tree, stretch=1)
        
        # 右侧：分组操作
        group_operations = QWidget()
        group_layout = QVBoxLayout(group_operations)
        
        # 创建分组按钮
        create_group_btn = QPushButton("创建分组")
        create_group_btn.clicked.connect(self._create_group)
        group_layout.addWidget(create_group_btn)
        
        # 编辑分组按钮
        edit_group_btn = QPushButton("编辑分组")
        edit_group_btn.clicked.connect(self._edit_group)
        group_layout.addWidget(edit_group_btn)
        
        # 删除分组按钮
        delete_group_btn = QPushButton("删除分组")
        delete_group_btn.clicked.connect(self._delete_group)
        group_layout.addWidget(delete_group_btn)
        
        group_layout.addStretch()
        layout.addWidget(group_operations, stretch=0)
    
    def _create_group(self):
        """创建分组"""
        dialog = CreateGroupDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            group_name = dialog.get_group_name()
            group_color = dialog.get_group_color()
            
            # 创建分组
            item = QTreeWidgetItem(self.group_tree)
            item.setText(0, group_name)
            item.setText(1, "0")
            item.setBackground(0, QColor(group_color))
    
    def _edit_group(self):
        """编辑分组"""
        current_item = self.group_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择分组")
            return
        
        dialog = EditGroupDialog(self, current_item.text(0), current_item.background(0).color())
        if dialog.exec_() == QDialog.Accepted:
            group_name = dialog.get_group_name()
            group_color = dialog.get_group_color()
            
            # 更新分组
            current_item.setText(0, group_name)
            current_item.setBackground(0, QColor(group_color))
    
    def _delete_group(self):
        """删除分组"""
        current_item = self.group_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择分组")
            return
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除分组 '{current_item.text(0)}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            root = self.group_tree.invisibleRootItem()
            root.removeChild(current_item)
```

#### 7.2.5 策略模板管理
**当前问题**: 策略模板管理功能不完善

**优化方案**:
```python
class StrategyTemplateManager(QWidget):
    """策略模板管理器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        create_btn = QPushButton("创建模板")
        create_btn.clicked.connect(self._create_template)
        toolbar.addWidget(create_btn)
        
        edit_btn = QPushButton("编辑模板")
        edit_btn.clicked.connect(self._edit_template)
        toolbar.addWidget(edit_btn)
        
        delete_btn = QPushButton("删除模板")
        delete_btn.clicked.connect(self._delete_template)
        toolbar.addWidget(delete_btn)
        
        import_btn = QPushButton("导入模板")
        import_btn.clicked.connect(self._import_template)
        toolbar.addWidget(import_btn)
        
        export_btn = QPushButton("导出模板")
        export_btn.clicked.connect(self._export_template)
        toolbar.addWidget(export_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 模板列表
        self.template_table = QTableWidget()
        self.template_table.setColumnCount(5)
        self.template_table.setHorizontalHeaderLabels([
            "模板ID", "模板名称", "描述", "分类", "标签"
        ])
        self.template_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.template_table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.template_table)
    
    def _create_template(self):
        """创建模板"""
        dialog = CreateTemplateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            template = dialog.get_template()
            
            # 保存模板
            self._save_template(template)
            
            # 刷新模板列表
            self._load_templates()
    
    def _edit_template(self):
        """编辑模板"""
        current_row = self.template_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择模板")
            return
        
        template_id = self.template_table.item(current_row, 0).text()
        template = self._get_template(template_id)
        
        dialog = EditTemplateDialog(self, template)
        if dialog.exec_() == QDialog.Accepted:
            updated_template = dialog.get_template()
            
            # 更新模板
            self._update_template(updated_template)
            
            # 刷新模板列表
            self._load_templates()
    
    def _delete_template(self):
        """删除模板"""
        current_row = self.template_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择模板")
            return
        
        template_id = self.template_table.item(current_row, 0).text()
        template_name = self.template_table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除模板 '{template_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 删除模板
            self._delete_template_by_id(template_id)
            
            # 刷新模板列表
            self._load_templates()
    
    def _import_template(self):
        """导入模板"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入模板",
            "",
            "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            # 创建模板
            template = StrategyTemplate(
                template_id=template_data['template_id'],
                name=template_data['name'],
                description=template_data['description'],
                plugin_type=template_data['plugin_type'],
                default_parameters=template_data['default_parameters'],
                parameter_descriptions=template_data.get('parameter_descriptions', {}),
                tags=template_data.get('tags', []),
                category=template_data.get('category', 'general')
            )
            
            # 保存模板
            self._save_template(template)
            
            # 刷新模板列表
            self._load_templates()
            
            QMessageBox.information(self, "成功", "模板导入成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入模板失败: {e}")
    
    def _export_template(self):
        """导出模板"""
        current_row = self.template_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择模板")
            return
        
        template_id = self.template_table.item(current_row, 0).text()
        template = self._get_template(template_id)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出模板",
            f"{template.name}.json",
            "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if not file_path:
            return
        
        try:
            # 准备导出数据
            export_data = {
                'template_id': template.template_id,
                'name': template.name,
                'description': template.description,
                'plugin_type': template.plugin_type,
                'default_parameters': template.default_parameters,
                'parameter_descriptions': template.parameter_descriptions,
                'tags': template.tags,
                'category': template.category,
                'export_time': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            QMessageBox.information(self, "成功", f"模板已导出到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出模板失败: {e}")
```

### 7.3 交互优化

#### 7.3.1 快捷键支持
**优化方案**:
```python
class ShortcutManager:
    """快捷键管理器"""
    
    def __init__(self, parent: QWidget):
        self.parent = parent
        self._setup_shortcuts()
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        # Ctrl+N: 创建新策略
        create_shortcut = QShortcut(QKeySequence("Ctrl+N"), self.parent)
        create_shortcut.activated.connect(self.parent._create_strategy)
        
        # Ctrl+R: 刷新策略列表
        refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self.parent)
        refresh_shortcut.activated.connect(self.parent._load_strategies)
        
        # Ctrl+E: 编辑策略
        edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), self.parent)
        edit_shortcut.activated.connect(self.parent._edit_current_strategy)
        
        # Ctrl+D: 删除策略
        delete_shortcut = QShortcut(QKeySequence("Ctrl+D"), self.parent)
        delete_shortcut.activated.connect(self.parent._delete_current_strategy)
        
        # Ctrl+F: 搜索策略
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self.parent)
        search_shortcut.activated.connect(self.parent._focus_search_box)
        
        # F5: 运行回测
        backtest_shortcut = QShortcut(QKeySequence("F5"), self.parent)
        backtest_shortcut.activated.connect(self.parent._run_backtest)
        
        # F6: 运行优化
        optimization_shortcut = QShortcut(QKeySequence("F6"), self.parent)
        optimization_shortcut.activated.connect(self.parent._run_optimization)
        
        # Ctrl+S: 保存配置
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self.parent)
        save_shortcut.activated.connect(self.parent._save_config)
```

#### 7.3.2 拖拽操作
**优化方案**:
```python
class DragDropStrategyTable(QTableWidget):
    """支持拖拽的策略表格"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTableWidget.InternalMove)
        self.setSelectionMode(QTableWidget.SingleSelection)
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasFormat("application/x-strategy-item"):
            event.accept()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasFormat("application/x-strategy-item"):
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """拖拽放置事件"""
        if event.mimeData().hasFormat("application/x-strategy-item"):
            # 获取源行
            source_row = self.currentRow()
            
            # 计算目标行
            target_row = self.rowAt(event.pos().y())
            if target_row < 0:
                target_row = self.rowCount() - 1
            
            # 移动行
            self._move_row(source_row, target_row)
            
            event.accept()
        else:
            event.ignore()
    
    def _move_row(self, source_row: int, target_row: int):
        """移动行"""
        # 保存源行数据
        items = []
        for col in range(self.columnCount()):
            item = self.item(source_row, col)
            if item:
                items.append((col, item.clone()))
        
        # 删除源行
        self.removeRow(source_row)
        
        # 插入到目标位置
        self.insertRow(target_row)
        for col, item in items:
            self.setItem(target_row, col, item)
        
        # 选中移动后的行
        self.selectRow(target_row)
```

#### 7.3.3 上下文菜单
**优化方案**:
```python
class ContextMenuStrategyTable(QTableWidget):
    """支持上下文菜单的策略表格"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def _show_context_menu(self, position):
        """显示上下文菜单"""
        menu = QMenu(self)
        
        # 获取当前选中的策略
        selected_strategies = self._get_selected_strategy_ids()
        
        if selected_strategies:
            # 单个策略操作
            if len(selected_strategies) == 1:
                edit_action = menu.addAction("编辑策略")
                edit_action.triggered.connect(lambda: self._edit_strategy(selected_strategies[0]))
                
                copy_action = menu.addAction("复制策略")
                copy_action.triggered.connect(lambda: self._copy_strategy(selected_strategies[0]))
                
                menu.addSeparator()
            
            # 批量操作
            batch_menu = menu.addMenu("批量操作")
            
            start_action = batch_menu.addAction("批量启动")
            start_action.triggered.connect(lambda: self._batch_operation("start"))
            
            stop_action = batch_menu.addAction("批量停止")
            stop_action.triggered.connect(lambda: self._batch_operation("stop"))
            
            delete_action = batch_menu.addAction("批量删除")
            delete_action.triggered.connect(lambda: self._batch_operation("delete"))
            
            menu.addSeparator()
            
            # 导出操作
            export_action = menu.addAction("导出策略")
            export_action.triggered.connect(lambda: self._export_strategy(selected_strategies[0]))
            
            menu.addSeparator()
            
            # 分组操作
            group_menu = menu.addMenu("移动到分组")
            
            for group in self._get_groups():
                group_action = group_menu.addAction(group.name)
                group_action.triggered.connect(
                    lambda checked, g=group: self._move_to_group(selected_strategies, g.group_id)
                )
        
        # 显示菜单
        menu.exec_(self.mapToGlobal(position))
```

### 7.4 性能优化

#### 7.4.1 虚拟滚动
**优化方案**:
```python
class VirtualScrollingTable(QTableWidget):
    """支持虚拟滚动的表格"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._visible_start = 0
        self._visible_end = 100
        self._page_size = 100
        
        # 连接滚动事件
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
    
    def set_data(self, data: List[Dict]):
        """设置数据"""
        self._data = data
        self._update_visible_items()
    
    def _on_scroll(self, value):
        """滚动事件"""
        # 计算可见范围
        self._visible_start = value
        self._visible_end = min(value + self._page_size, len(self._data))
        
        # 更新可见项
        self._update_visible_items()
    
    def _update_visible_items(self):
        """更新可见项"""
        self.setRowCount(0)
        
        for i in range(self._visible_start, self._visible_end):
            if i >= len(self._data):
                break
            
            row = self.rowCount()
            self.insertRow(row)
            
            item_data = self._data[i]
            for col, value in enumerate(item_data.values()):
                item = QTableWidgetItem(str(value))
                self.setItem(row, col, item)
```

#### 7.4.2 延迟加载
**优化方案**:
```python
class LazyLoadingTable(QTableWidget):
    """支持延迟加载的表格"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_data = []
        self._loaded_data = []
        self._page_size = 50
        self._current_page = 0
        
        # 连接滚动事件
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
    
    def set_data(self, data: List[Dict]):
        """设置数据"""
        self._all_data = data
        self._current_page = 0
        self._load_page(0)
    
    def _on_scroll(self, value):
        """滚动事件"""
        # 计算当前页
        max_value = self.verticalScrollBar().maximum()
        if value >= max_value * 0.9:
            # 滚动到底部，加载下一页
            self._load_page(self._current_page + 1)
    
    def _load_page(self, page: int):
        """加载指定页"""
        if page < 0 or page * self._page_size >= len(self._all_data):
            return
        
        start = page * self._page_size
        end = start + self._page_size
        page_data = self._all_data[start:end]
        
        # 添加数据到表格
        for item_data in page_data:
            row = self.rowCount()
            self.insertRow(row)
            
            for col, value in enumerate(item_data.values()):
                item = QTableWidgetItem(str(value))
                self.setItem(row, col, item)
        
        self._current_page = page
```

---

## 八、实施计划

### 8.1 第一阶段：核心问题修复（1-2周）

**优先级1**:
1. 修复线程生命周期管理问题
2. 统一使用QRunnable工作线程模式
3. 完善异常处理机制
4. 优化主题系统

**优先级2**:
5. 添加性能监控
6. 完善日志记录
7. 添加单元测试

### 8.2 第二阶段：功能增强（2-3周）

**优先级1**:
1. 增强策略列表功能（排序、拖拽、分组）
2. 实现回测结果图表化
3. 实现优化过程可视化
4. 完善策略模板管理

**优先级2**:
5. 添加快捷键支持
6. 优化上下文菜单
7. 实现虚拟滚动
8. 添加延迟加载

### 8.3 第三阶段：视觉优化（1-2周）

**优先级1**:
1. 实现现代化主题系统
2. 优化信息层次
3. 增强视觉反馈
4. 优化控件样式

**优先级2**:
5. 添加动画效果
6. 优化布局
7. 改进配色方案

### 8.4 第四阶段：质量保证（1周）

**测试活动**:
1. 单元测试
2. 集成测试
3. 性能测试
4. 用户体验测试

**文档输出**:
1. 用户使用手册
2. 开发者文档
3. API接口文档

---

## 九、预期效果

### 9.1 代码质量提升
- ✅ 线程管理更加安全，无内存泄漏
- ✅ 异常处理更加完善，用户体验更好
- ✅ 代码结构更加清晰，可维护性提升
- ✅ 性能优化，响应速度提升30%以上

### 9.2 功能完善
- ✅ 策略列表功能完善，支持100+策略管理
- ✅ 回测结果图表化，提供4种图表类型
- ✅ 优化过程可视化，实时展示优化进度
- ✅ 策略分组管理，支持拖拽操作

### 9.3 用户体验提升
- ✅ UI达到专业软件视觉标准
- ✅ 信息层次清晰，用户易用性提升50%
- ✅ 视觉反馈机制完善，操作更加直观
- ✅ 快捷键支持，操作效率提升30%

### 9.4 性能优化
- ✅ 大数据量场景优化，支持1000+策略
- ✅ 虚拟滚动和延迟加载，内存占用降低40%
- ✅ 缓存优化，响应速度提升50%
- ✅ 动态并发控制，系统资源利用率提升30%

---

## 十、风险评估

### 10.1 技术风险
- **风险**: 图表库集成可能遇到兼容性问题
- **缓解**: 提前进行兼容性测试，准备备用方案

- **风险**: 大量异步操作可能增加系统复杂性
- **缓解**: 使用成熟的异步框架，加强测试

- **风险**: 性能优化可能影响功能完整性
- **缓解**: 分阶段优化，每阶段进行充分测试

### 10.2 业务风险
- **风险**: 用户学习成本可能增加
- **缓解**: 提供详细的使用文档和培训

- **风险**: 现有工作流程可能被打断
- **缓解**: 保持向后兼容，提供迁移指南

- **风险**: 开发周期可能超出预期
- **缓解**: 采用敏捷开发方法，及时调整计划

### 10.3 质量风险
- **风险**: 新功能可能引入新的bug
- **缓解**: 完善的测试体系，代码审查

- **风险**: 性能优化可能影响稳定性
- **缓解**: 充分的性能测试和压力测试

---

## 十一、总结

### 11.1 现状评估
HIkyuu-UI的策略管理器在功能完整性方面已经达到了较高的水平，具备：
- ✅ 完整的策略生命周期管理
- ✅ 支持多种策略框架
- ✅ 异步回测和优化
- ✅ 策略创建向导
- ✅ 性能分析和可视化
- ✅ 实盘交易支持
- ✅ 事件驱动架构
- ✅ 服务容器集成

但在用户体验、视觉设计和技术实现细节上仍有显著提升空间。

### 11.2 关键建议
1. **优先解决架构稳定性问题**: 线程管理和内存泄漏问题必须优先解决
2. **渐进式用户体验提升**: 不建议一次性进行大幅改动，应该采用渐进式改进策略
3. **投资图表化展示能力**: 图表是专业交易软件的核心竞争力
4. **建立质量保证体系**: 完善的质量保证体系是确保改进成功的关键

### 11.3 预期收益
通过实施本优化方案，预计可以将策略管理器提升到行业专业软件的平均水平，为用户提供更好的策略管理体验，同时提高系统的稳定性和可维护性。

---

## 附录：关键代码文件索引

### UI层
- [enhanced_strategy_manager_dialog.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\dialogs\enhanced_strategy_manager_dialog.py) - 主对话框（4935行）

### 服务层
- [strategy_service.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\strategy_service.py) - 策略服务
- [trading_service.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\trading_service.py) - 交易服务

### 业务逻辑层
- [strategy_engine.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\strategy\strategy_engine.py) - 策略引擎
- [strategy_factory.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\strategy\strategy_factory.py) - 策略工厂
- [strategy_registry.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\strategy\strategy_registry.py) - 策略注册器
- [strategy_database.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\strategy\strategy_database.py) - 策略数据库

### 核心框架层
- [base_strategy.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\strategy\base_strategy.py) - 策略基类
- [strategy_extensions.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\strategy_extensions.py) - 策略扩展
- [strategy_events.py](file:///d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\strategy_events.py) - 策略事件

---

**文档结束**
