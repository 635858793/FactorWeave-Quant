# 主题切换架构改进方案：容器+Event模式

## 一、现状分析

### 1.1 当前实现方式
当前主题切换使用**PyQt信号槽机制**：

```python
# utils/theme.py
class ThemeManager(QObject):
    theme_changed = pyqtSignal(Theme)  # PyQt信号
    
    def set_theme(self, theme_name: str):
        # ... 切换主题逻辑
        self.theme_changed.emit(self._current_theme)  # 发送信号

# gui/dialogs/enhanced_strategy_manager_dialog.py
class EnhancedStrategyManagerDialog(QDialog):
    def __init__(self, ...):
        self.theme_manager.theme_changed.connect(self._on_theme_changed)  # 监听信号
```

### 1.2 系统框架架构
系统框架使用**服务容器+事件总线**模式：

```python
# core/containers/service_container.py
class ServiceContainer:
    """依赖注入容器，负责服务的创建、管理和生命周期"""
    def register(self, service_type, implementation, scope)
    def resolve(self, service_type) -> service_instance

# core/events/event_bus.py
class EventBus:
    """事件总线，负责事件的发布、订阅和分发"""
    def subscribe(self, event_type, handler)
    def publish(self, event, **kwargs)
    def unsubscribe(self, event_type, handler)
```

### 1.3 问题分析

#### 问题1：架构不一致
- **主题管理器**使用PyQt信号槽机制
- **其他服务**（StrategyService、TradingService等）使用服务容器
- **数据流**（RealtimeDataEvent、TickDataEvent等）使用事件总线

#### 问题2：耦合度高
- 组件需要直接引用`theme_manager`实例
- 无法通过依赖注入获取主题管理器
- 信号连接管理复杂（需要手动connect/disconnect）

#### 问题3：扩展性差
- 无法支持多个主题管理器实例
- 无法轻松切换主题管理器实现
- 难以进行单元测试（需要mock信号）

#### 问题4：生命周期管理不统一
- 主题管理器的生命周期与组件绑定
- 无法通过容器统一管理
- 资源清理分散

## 二、改进方案：容器+Event模式

### 2.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                   ServiceContainer                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  ThemeManager (Singleton Service)          │   │
│  │  - set_theme()                          │   │
│  │  - get_theme_colors()                  │   │
│  │  - apply_theme()                        │   │
│  └──────────────┬───────────────────────────┘   │
│                 │ publish()                      │
└─────────────────┼─────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│                   EventBus                         │
│  ┌──────────────────────────────────────────────┐   │
│  │  ThemeChangedEvent Subscribers           │   │
│  │  - EnhancedStrategyManagerDialog        │   │
│  │  - MainWindow                         │   │
│  │  - Other Components...                │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 2.2 实现步骤

#### 步骤1：使用现有的ThemeChangedEvent

**注意**：系统中已存在`ThemeChangedEvent`（[core/events/events.py:317-332](file:///d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/events/events.py#L317-L332)），无需重复定义。

**现有定义**：
```python
@dataclass
class ThemeChangedEvent(BaseEvent):
    theme_name: str = ""
    theme_config: Dict[str, Any] = field(default_factory=dict)
```

**使用方式**：
```python
from core.events.events import ThemeChangedEvent

# 创建事件实例
event = ThemeChangedEvent(
    theme_name=theme_name,
    theme_config=theme_config
)
```

#### 步骤2：将ThemeManager注册为服务
```python
# main.py 或初始化代码
from core.containers.service_container import get_service_container
from core.containers.service_registry import ServiceScope
from utils.theme import ThemeManager

container = get_service_container()
container.register(
    service_type=ThemeManager,
    implementation=ThemeManager,
    scope=ServiceScope.SINGLETON,
    name='theme_manager'
)
```

#### 步骤3：修改ThemeManager使用EventBus
```python
# utils/theme.py
from core.events.event_bus import get_event_bus
from core.events.events import ThemeChangedEvent

class ThemeManager(QObject):
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        super().__init__()
        # 保留原有的初始化逻辑
        self._config_manager = config_manager or ConfigManager()
        self._event_bus = get_event_bus()
        
        # 初始化数据库
        self._init_database()
        
        # 扫描主题
        self._scan_qss_themes()
        self._scan_json_themes()
        
        # 加载保存的主题
        self._load_saved_theme()
    
    def set_theme(self, theme_name: str):
        # ... 切换主题逻辑
        
        # 发布主题变化事件（替代信号）
        event = ThemeChangedEvent(
            theme_name=theme_name,
            theme_config=self.get_theme_colors()
        )
        self._event_bus.publish(event)
```

#### 步骤4：组件通过EventBus订阅主题变化
```python
# gui/dialogs/enhanced_strategy_manager_dialog.py
from core.events.event_bus import get_event_bus
from core.events.events import ThemeChangedEvent

class EnhancedStrategyManagerDialog(QDialog):
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        
        # 通过依赖注入获取主题管理器（可选）
        # 方式1：直接使用全局函数
        from utils.theme import get_theme_manager
        self.theme_manager = theme_manager or get_theme_manager()
        
        # 方式2：通过服务容器获取
        # from core.containers.service_container import get_service_container
        # container = get_service_container()
        # self.theme_manager = theme_manager or container.resolve(ThemeManager)
        
        # 订阅主题变化事件
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(
            ThemeChangedEvent,
            self._on_theme_changed
        )
        
        # 应用初始主题
        self.theme_manager.apply_theme(self)
    
    def _on_theme_changed(self, event: ThemeChangedEvent):
        """主题变化事件处理"""
        # 根据主题类型处理
        if hasattr(event, 'theme_type') and event.theme_type == 'qss':
            # QSS主题：全局应用，不需要对每个widget调用apply_theme
            pass
        else:
            # JSON主题：对当前widget应用主题
            self.theme_manager.apply_theme(self)
    
    def closeEvent(self, event):
        """清理事件订阅"""
        self._event_bus.unsubscribe(
            ThemeChangedEvent,
            self._on_theme_changed
        )
        
        # 清理PyQt信号连接（如果保留）
        if hasattr(self, '_theme_connection'):
            self.theme_manager.theme_changed.disconnect(self._on_theme_changed)
        
        super().closeEvent(event)
```

### 2.3 兼容性处理

为了保持向后兼容，可以保留PyQt信号作为备用：

```python
class ThemeManager(QObject):
    theme_changed = pyqtSignal(Theme)  # 保留信号（向后兼容）
    
    def set_theme(self, theme_name: str):
        # ... 切换主题逻辑
        
        # 双重通知：EventBus + 信号
        self._event_bus.publish(ThemeChangedEvent(...))
        self.theme_changed.emit(self._current_theme)  # 保留信号
```

### 2.4 EventBus配置说明

EventBus支持多种配置选项，可以根据需求调整：

#### 配置选项1：同步/异步执行模式
```python
# 创建同步EventBus（默认，性能更好）
from core.events.event_bus import get_event_bus
event_bus = get_event_bus()

# 或创建异步EventBus（适合大量事件处理）
from core.events.event_bus import EventBus
event_bus = EventBus(async_execution=True, max_workers=4)
set_event_bus(event_bus)
```

#### 配置选项2：事件去重窗口
```python
# 创建带去重的EventBus（避免重复事件）
from core.events.event_bus import EventBus
event_bus = EventBus(deduplication_window=0.5)  # 0.5秒去重窗口
set_event_bus(event_bus)
```

#### 配置选项3：性能监控
```python
# 获取性能统计
stats = event_bus.get_stats()
logger.info(f"EventBus stats: {stats}")
# 输出示例：{'events_published': 100, 'events_handled': 98, 'events_deduplicated': 2, ...}
```

### 2.5 主题类型处理说明

QSS主题和JSON主题的处理方式不同：

#### QSS主题
- 通过`app.setStyleSheet()`全局应用
- 不需要对每个widget调用`apply_theme()`
- 性能更好，一次全局应用

#### JSON主题
- 需要对每个widget调用`apply_theme()`
- 遍历所有窗口和子组件
- 性能相对较差，需要异步刷新

## 三、方案对比

| 特性 | 当前方案（信号槽） | 改进方案（容器+Event） |
|------|---------------------|------------------------|
| **架构一致性** | ❌ 与系统框架不一致 | ✅ 与系统框架一致 |
| **耦合度** | ❌ 高（需要直接引用） | ✅ 低（通过EventBus解耦） |
| **依赖注入** | ❌ 不支持 | ✅ 完全支持 |
| **生命周期管理** | ❌ 分散 | ✅ 统一管理 |
| **扩展性** | ❌ 差 | ✅ 好 |
| **可测试性** | ❌ 难以mock信号 | ✅ 容易mock EventBus |
| **多实例支持** | ❌ 不支持 | ✅ 支持（通过容器） |
| **性能** | ✅ 直接调用，性能好 | ⚠️ EventBus有轻微开销 |
| **向后兼容** | ✅ 无需修改 | ⚠️ 需要迁移代码 |
| **实现复杂度** | ✅ 简单 | ⚠️ 中等复杂度 |

## 四、实施建议

### 4.1 渐进式迁移
建议采用**渐进式迁移**策略，分阶段实施：

#### 阶段1：基础架构（1-2天）
1. 修改`ThemeManager`支持EventBus（保留原有初始化逻辑）
2. 添加EventBus配置说明（同步/异步、去重、性能监控）
3. 保留PyQt信号作为备用（可选）
4. 编写单元测试验证EventBus发布

#### 阶段2：核心组件迁移（2-3天）
1. 迁移`EnhancedStrategyManagerDialog`
2. 迁移`MainWindow`
3. 迁移其他核心对话框
4. 验证主题切换功能

#### 阶段3：全面迁移（3-5天）
1. 迁移所有子组件
2. 清理不再需要的信号连接代码
3. 更新文档和注释
4. 性能测试和优化

#### 阶段4：清理和优化（1-2天）
1. 移除PyQt信号（如果确认不再需要）
2. 优化EventBus性能
3. 添加监控和日志
4. 代码审查和重构

### 4.2 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **EventBus性能开销** | 主题切换可能变慢 | 1. 使用同步执行模式（默认）<br>2. 事件去重（0.5秒窗口）<br>3. 性能监控（get_stats） |
| **迁移复杂度** | 需要修改大量代码 | 1. 渐进式迁移<br>2. 保留向后兼容<br>3. 充分测试 |
| **向后兼容性** | 旧代码可能不工作 | 1. 保留PyQt信号<br>2. 文档说明<br>3. 版本兼容检查 |
| **调试难度** | EventBus调试不如信号直观 | 1. 添加详细日志<br>2. 事件追踪工具（get_stats）<br>3. 调试模式 |

### 4.3 成功标准
迁移成功的标准：
1. ✅ 所有组件通过EventBus订阅主题变化
2. ✅ ThemeManager注册为Singleton服务
3. ✅ 主题切换功能正常工作
4. ✅ 性能无明显下降（<5%）
5. ✅ 单元测试覆盖率>80%
6. ✅ 向后兼容性保持

## 五、结论

### 5.1 可行性评估
**✅ 可行** - 主题切换改为"容器+Event"模式完全可行，与系统框架保持一致。

### 5.2 推荐方案
**推荐采用渐进式迁移方案**，理由：
1. 降低风险：分阶段实施，每个阶段都可以回滚
2. 保持兼容：保留PyQt信号作为备用，确保不破坏现有功能
3. 易于测试：每个阶段都可以独立测试和验证
4. 灵活调整：根据实际效果调整后续计划

### 5.3 预期收益
迁移完成后，预期获得以下收益：
1. **架构统一**：主题系统与系统框架完全一致
2. **降低耦合**：组件不再需要直接引用theme_manager
3. **提升可维护性**：生命周期管理统一，代码更清晰
4. **增强扩展性**：支持多实例、易于扩展新功能
5. **改善可测试性**：单元测试更容易编写和维护
6. **长期收益**：为未来架构演进奠定基础

### 5.4 时间估算
- **阶段1（基础架构）**：1-2天
- **阶段2（核心组件）**：2-3天
- **阶段3（全面迁移）**：3-5天
- **阶段4（清理优化）**：1-2天
- **总计**：7-12天（约1.5-2.5周）

## 六、下一步行动

1. **评审方案**：与团队讨论此方案的可行性
2. **技术验证**：创建原型验证EventBus性能
3. **制定计划**：确定具体的迁移时间表
4. **开始实施**：按照渐进式迁移策略执行
5. **持续监控**：在迁移过程中监控性能和稳定性
