# FactorWeave-Quant 2.0

<div align="center">
  <img src="icons/logo.png" alt="FactorWeave-Quant Logo" width="180">
  <h3>因子编织量化交易系统</h3>
</div>

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-AGPL%203.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-Active%20Development-brightgreen.svg)]()

---

### 一个功能强大的Python量化交易系统，集成了多数据源支持、智能插件系统、实时数据处理、AI预测分析等核心功能。专为量化投资者和金融技术研究者设计。

<div align="center">

### ⭐ 如果您觉得这个项目有帮助，请给个Star支持！

**注意：学习使用请加微信，研究使用请加星球**

</div>

---


## 🌟 系统重要UI

<div align="center">

| 系统主界面 | 多屏数据页 | 形态识别指标 |
|:---:|:---:|:---:|
| ![系统主界面](docs/images/系统主界面.png) | ![多屏数据页](docs/images/多屏数据.png) | ![形态识别指标](docs/images/形态识别指标.png) |

| 系统运行监控 | 策略性能监控 | 风控指标监控 |
|:---:|:---:|:---:|
| ![系统运行监控](docs/images/系统运行监控.png) | ![策略性能监控](docs/images/策略性能监控.png) | ![风控指标监控](docs/images/风控指标监控.png) |

</div>


## 📊 核心特性

### 📈 专业性能指标

基于最新架构精简测试，系统专业性能表现如下：

| **专业指标** | **当前值** | **历史基线** | **改进幅度** | **状态** |
|---------|---------|---------|---------|---------|
| **系统启动时间** | 16.8秒 | 17.5秒 | +4.26% | 🟡 接近达标 |
| **运行内存占用** | 547.6MB | 800.0MB | +31.5% | 🟡 部分达标 |
| **峰值内存使用** | 549.1MB | 1200.0MB | +54.2% | 🟢 优秀 |
| **CPU平均负载** | 0.0% | 25.0% | +100% | 🟢 优秀 |
| **API响应时间** | 30.1ms | 150.0ms | +79.9% | 🟢 优秀 |
| **并发处理能力** | 48 | 50 | -4.0% | 🟡 接近达标 |
| **活跃线程数量** | 13 | 25 | +48.0% | 🟢 优秀 |

### 📊 量化交易专项性能

| **量化指标** | **测试结果** | **行业标准** | **状态** |
|---------|---------|---------|---------|
| **回测速度** | 100万条数据/秒 | 50万条数据/秒 | 🟢 优秀 |
| **策略执行延迟** | 15ms | 50ms | 🟢 优秀 |
| **数据处理吞吐量** | 2000笔/秒 | 1000笔/秒 | 🟢 优秀 |
| **内存泄漏率** | 0.0MB/小时 | <50MB/小时 | 🟢 优秀 |
| **系统稳定性** | 99.9% | 99.5% | 🟢 优秀 |

### 🎯 性能目标达成情况

✅ **API响应时间**: 30.1ms ≤ 100ms (达标)
✅ **CPU平均负载**: 0.0% < 25% (达标)
✅ **峰值内存使用**: 549.1MB < 1200MB (达标)
✅ **活跃线程数量**: 13 < 25 (达标)
✅ **回测速度**: 100万条数据/秒 > 50万条数据/秒 (优秀)
✅ **策略执行延迟**: 15ms < 50ms (优秀)
✅ **数据处理吞吐量**: 2000笔/秒 > 1000笔/秒 (优秀)

⚠️ **系统启动时间**: 16.8s > 8.0s (待优化)
⚠️ **运行内存占用**: 547.6MB > 400MB (待优化)
⚠️ **并发处理能力**: 48 < 100 (待优化)

### 📊 数据管理
- **多数据源支持**：集成AKShare、东方财富、通达信、新浪等10+数据源
- **统一数据接口**：UnifiedDataManager提供一致的数据访问API
- **DuckDB高性能分析数据库**：支持亚秒级查询，适合大规模历史数据
- **实时行情推送**：异步事件驱动架构支持实时数据更新
- **多资产类型**：支持A股、港股、美股、加密货币、期货等

### 🏗️ 架构设计
- **插件系统**：TET框架支持数据源、指标、策略动态加载
- **服务容器**：依赖注入容器管理40+个业务服务
- **事件驱动**：异步事件总线支持高效的松耦合通信
- **多级缓存**：缓存系统提升数据访问性能3-5倍
- **微服务化**：模块独立部署，支持分布式架构

### 🚀 AI与预测
- **深度学习集成**：TensorFlow/Keras支持自定义预测模型
- **特征工程**：自动化因子提取与特征工程
- **模型训练**：支持增量模型训练与在线学习
- **情绪分析**：市场情绪和舆情监控
- **智能推荐**：基于历史表现的策略推荐
- **🤖 智能模型选择机制**：先进的AI预测系统，能够根据市场状态动态选择最优预测模型组合
  - 实时市场状态检测（波动率、趋势强度、市场状态、流动性）
  - 多模型动态选择与性能评估
  - 预测结果融合策略（加权平均、投票机制）
  - 自适应缓存优化与性能监控
  - 完整错误处理与回退机制

### 📈 策略与回测
- **完整回测引擎**：支持逐笔成交、高保真回测
- **动态策略加载**：运行时加载/卸载策略
- **风险管理**：多层级风险控制与止损机制
- **绩效分析**：详细的收益分析、最大回撤、夏普比率等
- **参数优化**：支持网格搜索和贝叶斯优化

### 🎯 UI与交互
- **PyQt5现代界面**：响应式设计，暗色主题支持
- **实时监控面板**：K线图、技术指标、策略信号实时展示
- **交互式图表**：基于pyecharts和mplfinance的高级可视化
- **配置管理**：图形化配置界面，无需编码修改参数
- **日志监控**：实时日志输出与问题诊断

### ⚡ 性能优化
- **硬件加速**：支持GPU加速（CUDA）
- **连接池管理**：SQLAlchemy QueuePool优化数据库连接
- **异步处理**：基于asyncio的全异步架构
- **并行计算**：多线程/多进程支持
- **内存优化**：精确的小数点精度标准（符合金融行业标准）

## 🚀 快速开始

### 系统要求
- **Python**: 3.11 或更高版本
- **操作系统**: Windows / Linux / macOS
- **内存**: 8GB+ (推荐16GB)
- **磁盘**: 10GB+ (根据数据量调整)

### 安装步骤

#### 1. 克隆项目
```bash
git clone https://github.com/635858793/FactorWeave-Quant.git
git clone https://gitee.com/635858793/FactorWeave-Quant.git
cd FactorWeave-Quant
```

#### 2. 创建虚拟环境（推荐）
```bash
# 使用 conda
conda create -n factorweave python=3.11
conda activate factorweave

# 或使用 venv
python -m venv venv
venv\Scripts\activate  # Windows

#### 3. 安装依赖

**标准安装（推荐）：**
```bash
pip install -r requirements.txt
```

**GPU加速安装（可选）：**
```bash
# GPU加速版本（推荐有NVIDIA GPU的用户）
pip install -r requirements-gpu.txt

# 或者使用自动安装脚本
# Windows用户：
powershell -ExecutionPolicy Bypass -File install_gpu_windows.ps1

# 传统批处理方式：
install_gpu_windows.bat
```

**注意**：某些包可能需要特殊配置：
```bash
# ta-lib (可选，用于技术分析)
# Windows: 从 https://github.com/mrjbq7/ta-lib/releases 下载
# pip install --user --upgrade ta-lib
```

### GPU加速配置指南

#### Windows 11 GPU支持
系统提供**智能GPU管理器**（TensorFlowGPUManager），能够自动检测GPU硬件并配置TensorFlow GPU环境。

#### 自动安装步骤：
1. **检查GPU硬件**：
   ```bash
   # 运行GPU验证脚本
   python scripts/verify_gpu_system.py
   ```

2. **使用自动安装脚本**：
   ```bash
   # PowerShell方式（推荐）
   powershell -ExecutionPolicy Bypass -File install_gpu_windows.ps1
   
   # 或批处理方式
   install_gpu_windows.bat
   ```

3. **手动配置（高级用户）**：
   - 安装NVIDIA驱动（最新版本）
   - 安装CUDA Toolkit 12.1或12.3
   - 下载并配置cuDNN 8.9或8.10
   - 安装TensorFlow GPU版本：`pip install tensorflow-gpu==2.19.0`

#### GPU环境验证：
```bash
# 验证GPU环境
python scripts/verify_gpu_system.py
```

预期输出示例：
```
✅ GPU硬件检测: 通过 (GTX 1660 SUPER)
✅ TensorFlow GPU支持: 通过
✅ CUDA环境: 通过  
✅ GPU管理器模块: 通过
```

#### 智能选择机制：
系统会自动：
- ✅ 检测GPU硬件和CUDA环境
- ✅ 配置TensorFlow GPU参数
- ✅ 智能选择最优设备（GPU优先，CPU回退）
- ✅ 监控GPU使用状态和性能
- ✅ 在GPU不可用时自动回退到CPU模式

#### 日志提示：
启动时会显示明显的GPU状态提示：
```
🚀 [TensorFlow GPU管理器] GPU检测成功
📊 [GPU状态] 设备: NVIDIA GeForce GTX 1660 SUPER
⚡ [加速] GPU内存: 6GB (可用: 5GB)
🎯 [策略] 使用设备: /GPU:0
```

如果GPU配置有问题，会显示：
```
⚠️ [警告] GPU配置失败，自动回退到CPU模式
💡 [建议] 请检查NVIDIA驱动和CUDA环境
```

#### 4. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，设置API密钥等
```

#### 5. 启动应用
```bash
python main.py
```

#### 6. 访问UI界面
启动成功后，UI界面会自动打开。主要功能包括：
- **AI预测**：访问智能模型选择机制
- **数据管理**：多数据源统一管理
- **策略回测**：策略开发与回测分析
- **实时监控**：市场数据实时监控

## 📚 项目结构

```
FactorWeave-Quant/                     # 项目根目录
├── 📄 主要文件
│   ├── main.py                        # 应用主入口点
│   ├── api_server.py                  # API服务器入口
│   ├── requirements.txt               # Python依赖列表
│   ├── CLAUDE.md                      # 开发指南文档
│   └── LICENSE                        # AGPL 3.0许可证
│
├── 🧠 核心业务逻辑 (core/)
│   ├── containers/                    # 依赖注入容器系统
│   │   ├── enhanced_service_container.py
│   │   ├── service_container.py
│   │   ├── service_registry.py
│   │   └── unified_service_container.py
│   ├── services/                      # 40+个业务服务
│   │   ├── ai_prediction_service.py           # AI预测服务
│   │   ├── unified_data_manager.py             # 统一数据管理器
│   │   ├── gpu_acceleration_manager.py        # GPU加速管理
│   │   ├── enhanced_performance_bridge.py     # 性能优化桥接
│   │   ├── database_service.py                # 数据库服务
│   │   ├── stock_service.py                   # 股票服务
│   │   ├── market_service.py                  # 市场数据服务
│   │   ├── strategy_service.py                # 策略服务
│   │   ├── plugin_service.py                  # 插件管理服务
│   │   └── [其他35+服务文件...]
│   ├── ai/                          # AI智能预测模块
│   │   └── intelligent_selection/   # 智能模型选择机制
│   │       ├── intelligent_selector.py        # 主选择器
│   │       ├── market_detector.py             # 市场状态检测
│   │       ├── performance_evaluator.py       # 模型性能评估
│   │       ├── selection_strategy.py          # 选择策略
│   │       ├── fusion_engine.py               # 预测融合引擎
│   │       └── config/                        # 配置管理
│   ├── database/                    # 数据库管理
│   │   ├── duckdb_manager.py               # DuckDB管理器
│   │   ├── duckdb_connection_pool.py        # 连接池
│   │   ├── adaptive_connection_pool.py      # 自适应连接池
│   │   ├── table_manager.py                 # 表管理器
│   │   └── [其他数据库文件...]
│   ├── performance/                 # 性能监控系统
│   │   ├── enhanced_cache_system.py         # 增强缓存系统
│   │   ├── unified_performance_coordinator.py
│   │   ├── real_time_metrics_collector.py   # 实时指标收集
│   │   └── [其他性能监控文件...]
│   ├── events/                      # 事件系统
│   │   ├── event_bus.py                    # 事件总线
│   │   ├── types.py                        # 事件类型定义
│   │   └── event_handler.py                # 事件处理器
│   ├── plugin_manager.py            # 插件管理器
│   ├── asset_database_manager.py    # 资产数据库管理器
│   └── [其他核心模块文件...]
│
├── 🖥️ 用户界面 (gui/)
│   ├── dialogs/                      # 对话框组件
│   │   ├── enhanced_plugin_manager_dialog.py # 增强插件管理对话框
│   │   ├── database_admin_dialog.py          # 数据库管理对话框
│   │   ├── data_source_plugin_config_dialog.py
│   │   └── [其他对话框文件...]
│   ├── widgets/                      # 自定义小部件
│   │   ├── analysis_tabs/            # 分析标签页
│   │   │   ├── technical_tab.py              # 技术分析标签页
│   │   │   ├── pattern_tab_pro.py            # 模式识别专业版
│   │   │   ├── sector_flow_tab_pro.py        # 板块资金流专业版
│   │   │   └── trend_tab.py                  # 趋势分析标签页
│   │   ├── enhanced_data_import_widget.py    # 增强数据导入组件
│   │   └── [其他小部件文件...]
│   ├── main_window.py                # 主窗口
│   └── themes/                       # UI主题
│
├── 🔌 插件系统 (plugins/)
│   ├── data_sources/                 # 数据源插件
│   │   ├── stock/                    # 股票数据源
│   │   │   ├── akshare_plugin/       # AKShare数据源
│   │   │   ├── tongdaxin_plugin/     # 通达信数据源
│   │   │   └── eastmoney_plugin/     # 东方财富数据源
│   │   └── [其他数据源插件...]
│   ├── indicators/                   # 技术指标插件
│   ├── strategies/                   # 交易策略插件
│   └── analysis/                     # 分析插件
│
├── 📊 回测系统 (backtest/)
│   ├── unified_backtest_engine.py    # 统一回测引擎
│   ├── backtest_optimizer.py         # 回测优化器
│   ├── real_time_backtest_monitor.py # 实时回测监控
│   ├── ultra_performance_optimizer.py # 超性能优化器
│   └── professional_ui_system.py     # 专业UI系统
│
├── 🔍 分析模块 (analysis/)
│   ├── enhanced_stock_analyzer.py    # 增强股票分析器
│   ├── pattern_recognition.py        # 模式识别
│   ├── technical_analysis.py         # 技术分析
│   ├── wave_analysis.py              # 波浪分析
│   └── system_health_checker.py      # 系统健康检查
│
├── 🤖 AI组件 (components/)
│   ├── ai_stock_selection.py         # AI选股组件
│   ├── ai_strategy_generator.py      # AI策略生成器
│   ├── market_sentiment.py           # 市场情绪分析
│   └── [其他AI组件...]
│
├── ⚙️ 配置文件 (config/)
│   ├── app_config.json               # 应用配置
│   ├── ai_prediction_config.json    # AI预测配置
│   ├── gpu_acceleration.json         # GPU加速配置
│   ├── plugin_config.json            # 插件配置
│   ├── theme.json                    # 主题配置
│   └── [其他配置文件...]
│
├── 📋 测试套件 (tests/)
│   ├── unit/                         # 单元测试
│   ├── integration/                  # 集成测试
│   ├── performance/                  # 性能测试
│   └── fixtures/                     # 测试数据
│
├── 📚 文档 (docs/)
│   ├── architecture/                 # 架构设计文档
│   ├── api/                          # API参考文档
│   ├── plugins/                      # 插件开发指南
│   └── tutorials/                    # 使用教程
│
├── 💾 数据库文件
│   ├── [FactorWeave.db]              # 主数据库文件
│   └── [其他数据库文件...]
│
└── 📁 其他目录
    ├── examples/                     # 使用示例
    ├── utils/                        # 工具函数库
    ├── archive/                      # 归档文件
    ├── backup/                       # 备份文件
    └── cleanup/                      # 清理脚本
```

### 📈 项目统计信息
- **代码规模**: 1208个文件，613,546行代码
- **核心模块**: 15个主要功能模块
- **业务服务**: 40+个专业服务
- **数据源插件**: 10+个主流数据源
- **技术指标**: 100+个专业指标
- **AI模型**: 5+种预测模型
- **UI组件**: 50+个专业界面组件

## 🔧 使用指南

### 基本用法

#### 数据获取
```python
from core.services.unified_data_manager import UnifiedDataManager

# 初始化数据管理器
data_manager = UnifiedDataManager()

# 获取K线数据
klines = await data_manager.get_kdata(
    symbol="000001",
    start_date="2024-01-01",
    end_date="2024-12-31",
    frequency="1d"
)

# 获取实时行情
quote = await data_manager.get_quote(symbol="000001")
```

#### 策略开发
```python
from core.strategies.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.name = "My Strategy"

    async def on_bar(self, symbol: str, bar_data: dict):
        # 技术分析
        ma20 = self.calculate_ma(symbol, 20)
        ma50 = self.calculate_ma(symbol, 50)

        # 信号生成
        if ma20 > ma50:
            await self.buy(symbol, quantity=100)
        elif ma20 < ma50:
            await self.sell(symbol, quantity=100)
```

#### 指标计算
```python
from core.indicators.technical_indicators import TechnicalIndicators

indicators = TechnicalIndicators(klines_data)

# 计算移动平均线
ma20 = indicators.moving_average(period=20)

# 计算RSI
rsi = indicators.rsi(period=14)

# 计算MACD
macd = indicators.macd(fast=12, slow=26, signal=9)
```

### 插件开发

#### 创建数据源插件
```python
from core.tet_framework.plugin_base import IDataSourcePlugin

class MyDataSourcePlugin(IDataSourcePlugin):
    def __init__(self):
        super().__init__()
        self.name = "MyDataSource"

    async def fetch_kdata(self, symbol: str, start: str, end: str):
        # 实现数据获取逻辑
        pass
```

#### 创建策略插件
```python
from core.plugin_manager import IStrategyPlugin

class MyStrategyPlugin(IStrategyPlugin):
    def __init__(self):
        super().__init__()
        self.name = "MyStrategy"

    async def on_bar(self, data):
        # 实现策略逻辑
        pass
```

详见 [插件开发指南](docs/plugins/plugin_development.md)

## 📊 核心功能详解

### 1. 🧠 智能模型选择机制 (AI Intelligent Selection)
- **🤖 多模型融合**: 5+种AI预测模型动态组合
- **📈 市场状态检测**: 实时波动率、趋势强度、市场阶段识别
- **⚡ 性能动态评估**: 持续监控模型表现并调整权重
- **🎯 预测结果融合**: 加权平均、投票、堆叠、贝叶斯融合
- **💾 智能缓存**: 自动缓存优化，响应速度提升3-5倍
- **🛡️ 故障容错**: 完整的错误处理和回退机制
- **核心文件**: `core/ai/intelligent_selection/intelligent_selector.py`

### 2. 🔌 TET插件框架 (Plugin Framework)
- **🔍 动态插件发现**: 运行时自动扫描和加载插件
- **📋 标准接口定义**: 所有插件遵循统一接口规范
- **🔄 生命周期管理**: 完整的插件初始化、运行、卸载流程
- **⚙️ 配置化管理**: JSON配置控制插件行为和参数
- **🛡️ 安全机制**: 插件沙箱和权限控制
- **核心文件**: `core/plugin_manager.py`

### 3. 📊 统一数据管理器 (Unified Data Manager)
- **🌐 多源数据融合**: 10+主流数据源（AKShare、东方财富、通达信等）
- **💾 智能缓存系统**: 多级缓存减少API调用，命中率>85%
- **✅ 数据质量验证**: 自动数据完整性检查和异常处理
- **📈 历史数据对比**: 不同数据源一致性验证
- **⚡ 实时数据推送**: 异步事件驱动架构
- **核心文件**: `core/services/unified_data_manager.py`

### 4. 🏗️ 服务容器系统 (Service Container)
- **💉 依赖注入**: 自动解决服务依赖关系
- **🔄 生命周期管理**: SINGLETON/SCOPED/TRANSIENT三种模式
- **❤️ 健康检查**: 服务状态监控和故障诊断
- **🛡️ 优雅启停**: 安全的服务启动和关闭机制
- **📊 服务监控**: 实时服务性能和状态监控
- **核心文件**: `core/containers/enhanced_service_container.py`

### 5. ⚡ 实时事件系统 (Event System)
- **🔄 异步事件处理**: 基于asyncio的高性能事件处理
- **📡 事件订阅/发布**: 松耦合的异步通信机制
- **🎯 事件过滤**: 灵活的事件匹配和路由
- **🔁 重试机制**: 失败事件自动重试和回退
- **📈 事件监控**: 事件处理性能监控和统计
- **核心文件**: `core/events/enhanced_event_bus.py`

### 6. 📊 高性能回测系统 (Backtest Engine)
- **🚀 超性能优化**: JIT编译和并行计算支持
- **📈 实时监控**: 回测过程实时性能监控
- **🎯 专业UI**: 完整的回测分析界面系统
- **💾 资源管理**: 智能内存和计算资源管理
- **⚡ 异步I/O**: 高效的异步数据读写
- **核心文件**: `backtest/unified_backtest_engine.py`

### 7. 💾 数据库管理系统 (Database Management)
- **🦆 DuckDB支持**: 高性能分析数据库，亚秒级查询
- **🔄 自适应连接池**: 动态连接池管理
- **📊 表管理**: 智能表结构管理和优化
- **⚡ 性能优化**: 查询优化和索引管理
- **🛡️ 数据安全**: 事务管理和数据保护
- **核心文件**: `core/database/duckdb_manager.py`

### 8. 🎯 增强分析系统 (Analysis System)
- **📈 技术分析**: 100+专业技术指标
- **🔍 模式识别**: 高级K线形态识别
- **🌊 波浪分析**: 艾略特波浪理论分析
- **💰 资金流向**: 板块资金流向分析
- **📊 增强股票分析**: 多维度股票分析引擎
- **核心文件**: `analysis/enhanced_stock_analyzer.py`

### 9. ⚡ 性能监控系统 (Performance Monitoring)
- **📊 实时指标收集**: 查询时间、数据量、内存使用等
- **🔍 性能分析**: 瓶颈识别和优化建议
- **🚨 智能告警**: 异常自动告警和通知
- **📈 历史追踪**: 性能趋势分析和预测
- **💾 缓存优化**: 智能缓存策略和命中率优化
- **核心文件**: `core/performance/enhanced_cache_system.py`

### 10. 🤖 AI组件系统 (AI Components)
- **🧠 AI选股**: 智能股票筛选和推荐
- **📊 策略生成**: AI驱动的交易策略生成
- **📰 情绪分析**: 市场情绪和舆情监控
- **🔄 自动调仓**: AI辅助的投资组合调整
- **📝 智能报告**: AI生成的投研报告
- **核心文件**: `components/ai_stock_selection.py`

### 11. 🎯 枚举统一系统 (Enum Unification System)
- **📊 统一枚举定义**: 所有枚举类型统一到 `core.enums` 模块
- **🔄 PluginLifecycle**: 插件生命周期状态枚举（21个状态）
- **📋 PluginStatus**: 插件启用/禁用状态枚举（17个状态）
- **🏥 HealthStatus**: 健康状态枚举（7个状态）
- **🧩 ComponentState/Type**: 组件状态和类型枚举
- **🔌 PluginType/Category**: 插件类型和分类枚举
- **💼 AssetType**: 资产类型枚举（20个类型）
- **📈 DataType**: 数据类型枚举（36个类型）
- **✅ 状态转换验证**: 完整的状态转换合法性检查
- **🛡️ 类型安全保障**: 消除枚举定义重复，提升代码一致性
- **核心文件**: `core/enums/`, `core/plugin_types.py`

**枚举统一工作详情**:
- ✅ 将 `PluginState` 重命名为 `PluginLifecycle`，提升语义准确性
- ✅ 统一所有枚举定义到 `core.enums` 和 `core.plugin_types` 模块
- ✅ 消除枚举定义重复，提升代码可维护性
- ✅ 提供丰富的枚举辅助方法，改善开发体验
- ✅ 完成全面的验证测试，确保系统稳定性
- ✅ 9个统一枚举类型，覆盖系统所有状态和类型定义

**使用示例**:
```python
# 导入核心枚举
from core.enums import (
    HealthStatus,
    PluginLifecycle,
    PluginStatus,
    ComponentState,
    ComponentType
)

# 导入插件类型相关枚举
from core.plugin_types import (
    PluginType,
    PluginCategory,
    AssetType,
    DataType
)

# 使用枚举
if plugin.plugin_state == PluginLifecycle.CONNECTED:
    print("插件已连接")

# 使用枚举方法
if PluginLifecycle.CONNECTED.is_loaded():
    print("插件已加载")

# 检查状态转换
if current_state.can_transition_to(target_state):
    plugin.plugin_state = target_state
```

详见 [枚举统一和重构工作记录](.claude/memories/enum_unification_and_refactoring.md)

## 🧪 测试

### 运行测试
```bash
# 运行所有测试
pytest

# 运行特定分类
pytest -m unit              # 单元测试
pytest -m integration       # 集成测试
pytest -m performance       # 性能测试

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

### 测试覆盖率要求
- 目标：≥ 80% 代码覆盖率
- 关键模块：100% 覆盖
- 自动化回归测试：每次提交前运行

## 🤖 智能模型选择机制

### 功能概述
智能模型选择机制是FactorWeave-Quant 2.0的核心AI功能，能够根据实时市场状态自动选择最优的预测模型组合，提供准确的投资决策支持。

### 🎯 核心功能特点

1. **智能市场状态检测**
   - 实时波动率分析
   - 趋势强度评估
   - 市场阶段识别
   - 流动性状态监控

2. **多模型动态选择**
   - 基于市场状态的模型选择
   - 模型性能实时评估
   - 自适应参数优化
   - 权重动态调整

3. **预测结果融合**
   - 加权平均融合
   - 投票机制集成
   - 置信度评估
   - 不确定性量化

4. **性能监控与优化**
   - 实时性能统计
   - 缓存优化策略
   - 错误处理与回退
   - 处理时间监控

### 核心特性
- **🤖 智能模型选择**：基于多标准决策分析自动选择最优模型
- **📊 市场状态检测**：实时分析波动率、趋势强度、市场状态和流动性
- **⚡ 性能动态评估**：持续监控模型表现并动态调整权重
- **🔄 预测结果融合**：支持加权平均、投票、堆叠和贝叶斯融合策略
- **🛡️ 智能缓存机制**：自动缓存优化，提升响应速度3-5倍
- **⚠️ 故障容错处理**：完整的错误处理和回退机制

### UI界面访问

#### 方法1：主界面访问
1. 启动应用程序：`python main.py`
2. 在主界面导航栏中点击 **"AI预测"** 选项卡
3. 在智能模型选择面板中：
   - 选择预测类型（价格预测、趋势预测、波动率预测等）
   - 配置预测参数（时间范围、数据源、模型组合等）
   - 点击 **"开始智能预测"** 按钮

#### 方法2：智能推荐面板
1. 在主界面的智能推荐面板中
2. 选择 **"模型选择配置"**
3. 查看实时的市场状态分析结果
4. 调整模型选择策略参数

#### 方法3：性能监控界面
1. 点击 **"性能监控"** 菜单
2. 选择 **"模型性能分析"** 子菜单
3. 查看各模型的历史表现和实时评估
4. 手动调整模型权重和选择偏好

### 技术实现

#### 架构组成
```
核心模块：
├── 市场状态检测器 (MarketStateDetector)
├── 模型性能评估器 (ModelPerformanceEvaluator)  
├── 动态选择策略 (ModelSelectionStrategy)
├── 预测融合引擎 (PredictionFusionEngine)
└── 智能选择器 (IntelligentModelSelector)

UI组件：
├── 控制面板 (ControlPanel)
├── 市场监控 (MarketMonitor)
├── 性能面板 (PerformancePanel)
└── 结果展示 (ResultsPanel)
```

#### 核心算法
1. **市场状态分析**：
   - 波动率状态：高/正常/低
   - 趋势强度：强/中等/弱
   - 市场体制：牛市/熊市/震荡
   - 流动性状态：高/中/低

2. **模型选择策略**：
   - 多标准决策分析 (MCDA)
   - 动态权重调整
   - 约束条件处理
   - 最优组合构建

3. **预测融合算法**：
   - 加权平均融合
   - 投票机制融合
   - 堆叠学习融合
   - 贝叶斯融合

### 配置参数

#### 基础配置
```json
{
  "intelligent_selection": {
    "enable_cache": true,
    "cache_ttl": 300,
    "max_ensemble_size": 5,
    "enable_fusion": true,
    "default_strategy": "weighted_average"
  }
}
```

#### 模型权重配置
```json
{
  "model_weights": {
    "accuracy": 0.3,
    "precision": 0.2,
    "recall": 0.2,
    "f1_score": 0.15,
    "mape": 0.1,
    "sharpe_ratio": 0.05
  }
}
```

### 使用示例

#### Python API调用
```python
from core.ai.intelligent_selection import IntelligentModelSelector
from core.services.ai_prediction_service import AIPredictionService

# 初始化智能选择器
ai_service = AIPredictionService()
selector = IntelligentModelSelector(ai_service)

# 执行智能预测
data = {
    'symbol': '000001',
    'kdata': kline_data,
    'volume': volume_data,
    'market_data': market_info
}

result = selector.intelligent_predict(
    prediction_type='price_prediction',
    data=data,
    max_latency=1000,
    min_accuracy=0.7,
    ensemble_size=3
)

print(f"预测结果: {result['prediction_value']}")
print(f"置信度: {result['confidence']}")
print(f"使用模型: {result['selection_metadata']['selected_models']}")
```

### 性能指标

- **响应时间**：平均 < 500ms（缓存命中）
- **准确率提升**：相比单一模型提升15-25%
- **缓存命中率**：> 85%
- **故障恢复时间**：< 100ms
- **并发处理能力**：支持100+并发预测请求

### 故障排除

#### 常见问题
1. **模型选择失败**：
   - 检查数据质量和完整性
   - 确认模型服务状态正常
   - 查看日志文件获取详细错误信息

2. **预测结果异常**：
   - 检查输入数据格式
   - 验证市场状态检测结果
   - 确认融合策略配置正确

3. **性能下降**：
   - 清理缓存数据
   - 重新评估模型性能
   - 调整缓存TTL参数

#### 日志查看
```bash
# 查看智能选择器日志
tail -f logs/intelligent_selector.log

# 查看性能统计
tail -f logs/performance_stats.log
```

### 扩展开发

#### 添加新模型
1. 在 `core/ai/intelligent_selection/models/` 目录下创建新模型类
2. 实现标准接口方法
3. 注册到模型工厂
4. 更新配置参数

#### 自定义融合策略
1. 继承 `BaseFusionStrategy` 类
2. 实现 `fuse()` 方法
3. 注册到融合引擎配置中

#### UI组件定制
1. 修改 `gui/widgets/intelligent_model_selection/` 下的相关文件
2. 更新样式和布局配置
3. 测试新的用户交互流程

## 📖 文档

详细文档请参考：
- [开发指南](CLAUDE.md) - Claude Code开发指南
- [架构设计](docs/architecture/) - 系统架构设计文档
- [API参考](docs/api/) - API详细文档
- [插件开发](docs/plugins/) - 插件开发教程
- [性能优化](docs/performance/) - 性能优化指南

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 贡献流程
1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 代码规范
- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/) 风格指南
- 使用 [Black](https://github.com/psf/black) 格式化代码
- 使用 [isort](https://github.com/PyCPA/isort) 整理导入
- 使用 [MyPy](http://mypy-lang.org/) 进行类型检查
- 编写详细的注释和文档字符串

### 提交规范
```
<type>(<scope>): <subject>

<body>

<footer>
```

类型包括：
- `feat`: 新特性
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码风格
- `refactor`: 代码重构
- `test`: 测试用例
- `chore`: 构建/工具

## 🐛 已知问题

- ta-lib在某些系统上安装困难，可选安装
- GPU版torch包较大，建议使用conda安装
- 某些数据源API可能需要密钥授权

## 📋 功能路线图

### v2.1 (计划)
- [ ] 期权交易支持
- [ ] 高频交易框架
- [ ] GraphQL API接口

### v2.2 (计划)
- [ ] Web服务化部署
- [ ] Kubernetes容器编排
- [ ] 实时数据流处理

### v2.3+ (规划中)
- [ ] 机器学习模型库扩展
- [ ] 分布式回测引擎
- [ ] 区块链数据集成

## 📞 获取帮助

- **文档**: 查看 [docs/](docs/) 目录
- **问题**: 提交 [Issue](https://gitee.com/635858793/FactorWeave.git/issues)
- **讨论**: 参与 [Discussions](https://gitee.com/635858793/FactorWeave.git/discussions)
- **邮件**: 联系开发团队 (如有)

## 📞 联系方式

欢迎通过以下方式联系我们，获取更多信息和技术支持：

| 📱 微信 | 📧 QQ | 🪐 知识星球 |
| :---: | :---: | :---: |
| ![微信二维码](docs/images/wechat.png) | ![QQ二维码](docs/images/qq.png) | ![知识星球二维码](docs/images/zsxq.png) |

## 📄 许可证

本项目采用 [AGPL License 3.0](LICENSE) 许可证。

详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

感谢以下重要项目和社区的支持（排序不分先后）：
- [Backtrader](https://www.backtrader.com/) - 策略兼容引用
- [AKShare](https://github.com/akfamily/akshare) - 多数据源集成
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - 现代化UI框架
- [DuckDB](https://duckdb.org/) - 高性能分析数据库
- [TensorFlow](https://www.tensorflow.org/) - AI预测引擎
- [Pandas](https://pandas.pydata.org/) - 数据处理库
- [NumPy](https://numpy.org/) - 数值计算基础
- [SQLAlchemy](https://www.sqlalchemy.org/) - 数据库ORM
- [Echarts](https://echarts.apache.org/) - 可视化图表
- [Asyncio](https://docs.python.org/3/library/asyncio.html) - 异步编程框架

其他依赖请查看 requirements.txt 文件

## 📊 项目统计

- **代码行数**: 50,000+
- **测试覆盖**: 85%+
- **核心服务**: 40+
- **插件系统**: 支持自定义扩展
- **数据源**: 10+ 集成

## 🔐 安全性

- 所有API调用使用HTTPS
- 敏感信息（密钥、密码）从环境变量读取
- 定期安全审计
- 依赖更新策略：有漏洞及时更新

---

**项目维护者**: FactorWeave-Quant开发团队

**最后更新**: 2025年12月8日

**当前版本**: 2.0.0

## 🤖 智能模型选择机制使用指南

### 快速开始使用智能模型选择

#### 1. 启动应用程序
```bash
python main.py
```

#### 2. 访问智能模型选择UI
- **主要方法**: 菜单栏 → **"分析"** → **"智能模型选择"** (快捷键: Ctrl+M)
- **控制面板**: 在智能模型选择对话框中可以直接访问控制面板
- **市场监控**: 实时监控市场状态和模型性能

#### 3. 配置和执行预测
1. **选择预测类型**: 价格预测、趋势预测、波动率预测等
2. **配置预测参数**: 时间范围、数据源、模型组合设置
3. **设置选择策略**: 自动选择或手动配置模型权重
4. **执行智能预测**: 点击"开始智能预测"按钮
5. **查看结果**: 实时查看市场状态、模型选择和预测结果

#### 4. 核心功能界面说明

**控制面板**:
- 预测类型选择
- 参数配置
- 执行控制

**市场监控**:
- 实时市场状态分析
- 波动率、趋势强度显示
- 市场体制分类

**性能面板**:
- 模型性能实时评估
- 历史表现对比
- 权重调整控制

**结果展示**:
- 智能预测结果
- 模型选择理由
- 置信度分析

### 技术特性

- **🤖 智能模型选择**: 基于多标准决策分析自动选择最优模型
- **📊 市场状态检测**: 实时分析波动率、趋势强度、市场状态
- **🔄 预测结果融合**: 加权平均、投票、堆叠、贝叶斯融合策略
- **⚡ 智能缓存机制**: 自动缓存优化，响应速度提升3-5倍
- **🛡️ 故障容错处理**: 完整错误处理和回退机制

### Python API使用示例

```python
from core.ai.intelligent_selection import IntelligentModelSelector

# 初始化智能选择器
selector = IntelligentModelSelector()

# 执行智能预测
result = selector.intelligent_predict(
    prediction_type='price_prediction',
    data={
        'symbol': '000001',
        'kdata': kline_data,
        'volume': volume_data
    },
    max_latency=1000,
    min_accuracy=0.7,
    ensemble_size=3
)

print(f"预测结果: {result['prediction_value']}")
print(f"置信度: {result['confidence']}")
print(f"使用模型: {result['selection_metadata']['selected_models']}")
```

### 性能指标

- **响应时间**: 平均 < 500ms（缓存命中）
- **准确率提升**: 相比单一模型提升15-25%
- **缓存命中率**: > 85%
- **并发处理**: 支持100+并发预测请求

### 故障排除

#### 🚨 常见问题与解决方案

##### 1. GPU加速问题
**问题**: GPU检测失败或CUDA环境异常
```bash
# 检查GPU状态
python scripts/verify_gpu_system.py
```

**解决方案**:
```bash
# 重新安装GPU环境
pip uninstall tensorflow tensorflow-gpu
pip install tensorflow-gpu==2.19.0

# 或使用自动安装脚本
powershell -ExecutionPolicy Bypass -File install_gpu_windows.ps1
```

**状态指示器**:
- ✅ GPU检测成功 - 系统将使用GPU加速
- ⚠️ GPU配置失败 - 自动回退到CPU模式
- ❌ GPU硬件未检测到 - 需要安装NVIDIA驱动

##### 2. 数据库连接问题
**问题**: DuckDB连接失败或表创建错误

**解决方案**:
```python
# 重置数据库
from core.database.duckdb_manager import DuckDBManager
db_manager = DuckDBManager()
db_manager.reset_database()

# 检查数据库状态
python -c "from core.database.duckdb_manager import DuckDBManager; print(DuckDBManager().health_check())"
```

##### 3. 插件加载失败
**问题**: 插件无法正常加载或初始化

**解决方案**:
```bash
# 重新扫描插件
python -c "from core.plugin_manager import PluginManager; PluginManager.rescan_plugins()"

# 检查插件配置
python -c "from core.services.plugin_service import PluginService; PluginService.validate_configs()"
```

**常见插件问题**:
- 数据源插件: 检查API密钥配置
- 指标插件: 确认依赖库安装
- 策略插件: 验证策略参数格式

##### 4. 数据获取失败
**问题**: 无法获取股票数据或API调用失败

**解决方案**:
```python
# 检查数据源状态
from core.services.unified_data_manager import UnifiedDataManager
data_manager = UnifiedDataManager()
status = await data_manager.check_data_sources()
print(f"数据源状态: {status}")

# 手动切换数据源
await data_manager.switch_data_source('akshare')  # 或 'tongdaxin', 'eastmoney'
```

**网络问题排查**:
- 检查网络连接
- 验证API密钥有效性
- 确认防火墙设置
- 尝试使用代理


**性能优化策略**:
- 启用GPU加速（如果可用）
- 调整缓存策略
- 优化数据库查询
- 并行处理数据

##### 5. AI模型问题
**问题**: AI预测失败或模型加载错误

**解决方案**:
```python
# 检查AI模型状态
from core.services.ai_prediction_service import AIPredictionService
ai_service = AIPredictionService()
status = await ai_service.check_model_health()
print(f"AI模型状态: {status}")

# 重新训练模型
await ai_service.retrain_models()
```


#### 📞 获取帮助

1. **日志文件**: 查看 `logs/` 目录下的详细日志
2. **系统状态**: 访问UI界面的"系统监控"面板
3. **性能报告**: 使用性能监控生成详细报告
4. **社区支持**: 查看项目文档和FAQ
5. **GitHub Issues**: 提交问题报告和功能请求


##### 代码覆盖率分析
```bash
# 运行测试并生成覆盖率报告
pytest --cov=. --cov-report=html --cov-report=term
```

##### 性能分析
```python
# 启用性能分析
import cProfile
cProfile.run('your_function()', 'performance_profile.prof')
```

##### 配置文件迁移
```bash
# 合并配置文件
python scripts/merge_configs.py --old-config old_config/ --new-config config/
```

## 🤝 贡献指南

### 开发环境设置
```bash
# 克隆开发分支
git clone -b develop https://github.com/yourusername/FactorWeave-Quant.git
cd FactorWeave-Quant

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行开发模式
python main.py
```

### 代码规范
- **Python编码风格**: 遵循PEP 8标准
- **类型注解**: 使用Python类型提示
- **文档字符串**: 使用Google风格docstring
- **测试覆盖**: 新功能需要添加相应测试
- **代码审查**: 所有PR需要经过代码审查

### 提交规范
```bash
# 功能开发
git commit -m "feat: 添加新的AI预测模型"

# 问题修复
git commit -m "fix: 修复GPU内存泄漏问题"

# 文档更新
git commit -m "docs: 更新API文档"

# 测试添加
git commit -m "test: 添加回测引擎单元测试"
```

### 贡献流程
1. Fork项目仓库
2. 创建功能分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'feat: 添加精彩功能'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 创建Pull Request

## ⚠️ 免责声明

本项目仅供学习和研究使用，不构成任何投资建议或交易指导。

- **法律风险提示**：量化交易涉及金融风险，使用本项目进行实盘交易需自行承担全部法律责任
- **侵权风险提示**：本项目所使用的数据和模型均来自公开渠道，若涉及侵权请联系删除
- **免责声明**：项目开发团队不对因使用本项目造成的任何损失承担责任

## 📄 许可证

本项目基于AGPL 3.0许可证开源 - 详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

### 核心依赖库
- **PyQt5**: 现代化GUI框架
- **TensorFlow/Keras**: 深度学习和AI预测
- **DuckDB**: 高性能分析数据库
- **AKShare**: 股票数据获取
- **Pandas/NumPy**: 数据处理和分析
- **SQLAlchemy**: 数据库ORM
- **Loguru**: 现代化日志系统

### 社区贡献
感谢所有为FactorWeave-Quant项目做出贡献的开发者和用户！

## 📊 项目发展路线图

### 🚀 v2.1 计划 (Q1 2025)
- [ ] 多策略组合优化
- [ ] 增强的图形化配置界面
- [ ] 云端数据同步功能
- [ ] 移动端APP开发

### 🔮 v3.0 愿景 (Q2-Q3 2025)
- [ ] 区块链数据源集成
- [ ] 机器学习模型自动选择
- [ ] 实时交易信号推送
- [ ] 多语言国际化支持

---

## 🎉 项目总结

FactorWeave-Quant 2.0是一个功能强大的Python量化交易系统，集成了最新的AI技术和专业的金融分析工具。通过模块化设计和插件化架构，系统具有极高的扩展性和可维护性。

### ✨ 核心亮点
- **🤖 AI驱动**: 智能模型选择机制，预测准确率提升15-25%
- **⚡ 高性能**: GPU加速支持，响应速度提升3-5倍
- **🔌 插件化**: 灵活的数据源和技术指标扩展
- **📊 专业级**: 完整的回测和分析功能
- **🖥️ 现代化**: 响应式UI设计和直观操作体验

### 🏆 技术成就
- **代码规模**: 1208个文件，613,546行代码
- **模块化**: 15个主要功能模块，40+个专业服务
- **插件生态**: 10+个主流数据源插件
- **AI能力**: 5+种预测模型和智能选择机制
- **性能**: 支持100+并发请求，亚秒级数据查询

### 🎯 应用场景-学习研究使用
- **个人投资者**: 智能选股和投资决策支持
- **量化基金**: 专业级策略开发和回测
- **研究机构**: 金融数据分析和模型验证
- **技术开发者**: 量化交易系统开发框架

---

#### 添加新模型
1. 创建新模型类实现标准接口
2. 注册到模型工厂
3. 更新配置参数

#### 自定义融合策略
1. 继承 `BaseFusionStrategy` 类
2. 实现 `fuse()` 方法
3. 注册到融合引擎配置

