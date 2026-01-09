# XTP Pro交易接口配置指南

## 概述

XTP Pro是中泰证券提供的专业交易接口，支持A股、港股、美股等市场。本系统已经集成了XTP Pro交易接口的完整实现，支持真实的交易功能。

## 前置要求

### 1. 获取XTP账户

- 联系中泰证券开通XTP交易账户
- 获取以下信息：
  - 账户ID（account_id）
  - 交易密码（password）
  - 客户端ID（client_id，默认为1）
  - 软件密钥（software_key）
  - 交易服务器地址（trade_server）
  - 行情服务器地址（quote_server）

### 2. 安装XTP SDK

#### 方法1：从中泰证券官网下载

1. 访问中泰证券官网：https://www.zts.com.cn/
2. 注册并登录开发者账户
3. 下载XTP Python SDK（通常为.whl文件）
4. 解压并安装：
```bash
pip install xtp_api-*.whl
```

#### 方法2：使用pip安装（如果可用）

```bash
pip install xtp_api
```

### 3. 验证安装

```python
import xtp_api
print("XTP SDK版本:", xtp_api.__version__)
```

## 配置步骤

### 1. 在账户管理中配置XTP账户

通过系统的账户管理界面，添加XTP账户：

```python
from core.trading.account_models import TradingAccount
from core.trading.trading_types import TradingInterfaceType

account = TradingAccount(
    account_id="your_account_id",
    account_name="XTP实盘账户",
    trading_interface_type=TradingInterfaceType.XTP_PRO,
    xtp_account_id="your_xtp_account_id",
    xtp_password="your_xtp_password",
    xtp_client_id=1,
    xtp_software_key="your_software_key",
    xtp_td_ip="trade_server_ip",
    xtp_td_port=6000,
    xtp_md_ip="quote_server_ip",
    xtp_md_port=6002,
    xtp_protocol="tcp",
    xtp_buffer_size=1024
)
```

### 2. 配置参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| account_id | 系统内部账户ID | "xtp_account_001" |
| account_name | 账户名称 | "XTP实盘账户" |
| trading_interface_type | 交易接口类型 | TradingInterfaceType.XTP_PRO |
| xtp_account_id | XTP账户ID | "12345678" |
| xtp_password | XTP账户密码 | "your_password" |
| xtp_client_id | 客户端ID | 1 |
| xtp_software_key | 软件密钥 | "your_software_key" |
| xtp_td_ip | 交易服务器IP | "192.168.1.100" |
| xtp_td_port | 交易服务器端口 | 6000 |
| xtp_md_ip | 行情服务器IP | "192.168.1.101" |
| xtp_md_port | 行情服务器端口 | 6002 |
| xtp_protocol | 协议类型 | "tcp" |
| xtp_buffer_size | 缓冲区大小 | 1024 |

## 使用示例

### 1. 初始化XTP Pro接口

```python
from core.trading.interfaces.xtp_pro_trading_interface import XTPProTradingInterface
from core.events.event_bus import EventBus

# 创建事件总线
event_bus = EventBus()

# 初始化XTP Pro接口
xtp_interface = XTPProTradingInterface(
    account_id="your_xtp_account_id",
    password="your_xtp_password",
    client_id=1,
    trade_server="192.168.1.100:6000",
    quote_server="192.168.1.101:6002",
    event_bus=event_bus
)
```

### 2. 连接和登录

```python
# 连接服务器
if xtp_interface.connect():
    print("XTP服务器连接成功")
    
    # 登录账户
    if xtp_interface.login():
        print("XTP账户登录成功")
    else:
        print("XTP账户登录失败")
else:
    print("XTP服务器连接失败")
```

### 3. 提交订单

```python
from core.trading.order_models import Order, OrderType, OrderCategory
from core.trading.trading_types import TradingInterface

# 创建订单
order = Order(
    order_id="order_001",
    stock_code="000001",
    stock_name="平安银行",
    order_type=OrderType.BUY,
    order_category=OrderCategory.LIMIT,
    order_price=10.50,
    order_quantity=1000,
    account_id="your_xtp_account_id"
)

# 提交订单
result = xtp_interface.submit_order(order)
if result.status == ExecutionStatus.SUCCESS:
    print(f"订单提交成功，交易所订单ID: {result.exchange_order_id}")
else:
    print(f"订单提交失败: {result.message}")
```

### 4. 查询订单状态

```python
# 查询订单状态
result = xtp_interface.query_order_status("order_001")
if result.status == ExecutionStatus.SUCCESS:
    print(f"订单状态: {result.details['order_status']}")
    print(f"成交数量: {result.details['filled_quantity']}")
    print(f"剩余数量: {result.details['remaining_quantity']}")
```

### 5. 取消订单

```python
# 取消订单
result = xtp_interface.cancel_order("order_001")
if result.status == ExecutionStatus.SUCCESS:
    print("订单取消成功")
else:
    print(f"订单取消失败: {result.message}")
```

### 6. 查询资金信息

```python
# 查询资金信息
fund_info = xtp_interface.query_fund_info("your_xtp_account_id")
if fund_info:
    print(f"总资产: {fund_info.total_assets}")
    print(f"可用资金: {fund_info.available_cash}")
    print(f"持仓市值: {fund_info.market_value}")
    print(f"今日盈亏: {fund_info.today_profit_loss}")
```

### 7. 查询持仓信息

```python
# 查询持仓信息
positions = xtp_interface.query_positions("your_xtp_account_id")
for position in positions:
    print(f"股票代码: {position.stock_code}")
    print(f"股票名称: {position.stock_name}")
    print(f"持仓数量: {position.quantity}")
    print(f"可用数量: {position.available_quantity}")
    print(f"持仓成本: {position.cost_price}")
    print(f"当前价格: {position.current_price}")
    print(f"持仓盈亏: {position.profit_loss}")
    print(f"盈亏比例: {position.profit_loss_ratio}")
```

## 回调机制

XTP Pro接口支持以下回调：

### 1. 订单状态回调

当订单状态发生变化时，会触发订单状态回调：

```python
def _on_order_event(self, order_info):
    """
    订单状态回调
    
    Args:
        order_info: XTP订单信息
    """
    # 处理订单状态变化
    # 会自动更新本地订单状态
    # 如果配置了事件总线，会发布order_status_changed事件
```

### 2. 成交回报回调

当订单成交时，会触发成交回报回调：

```python
def _on_trade_event(self, trade_info):
    """
    成交回报回调
    
    Args:
        trade_info: XTP成交信息
    """
    # 处理成交信息
    # 会自动更新订单的成交数量和成交价格
    # 如果配置了事件总线，会发布trade_event事件
```

### 3. 错误回调

当发生错误时，会触发错误回调：

```python
def _on_error_event(self, error_info):
    """
    错误回调
    
    Args:
        error_info: XTP错误信息
    """
    # 处理错误信息
    # 会记录错误日志
    # 如果配置了事件总线，会发布error_event事件
```

## 模拟模式

如果XTP SDK未安装或配置不完整，XTP Pro接口会自动降级到模拟模式：

```python
# 模拟模式下，所有操作都会成功，但不会真实交易
# 适合用于测试和开发
```

## 注意事项

1. **安全性**
   - 不要在代码中硬编码账户密码
   - 使用加密存储敏感信息
   - 定期更换密码

2. **风险控制**
   - 在实盘交易前，先在模拟环境充分测试
   - 设置合理的风险控制参数
   - 监控订单执行情况

3. **网络连接**
   - 确保网络连接稳定
   - 处理网络中断情况
   - 实现断线重连机制

4. **错误处理**
   - 捕获并处理所有异常
   - 记录详细的错误日志
   - 实现错误恢复机制

5. **性能优化**
   - 合理使用缓存
   - 避免频繁查询
   - 使用异步操作

## 故障排除

### 1. XTP SDK未安装

**错误信息**：`XTP SDK未安装，使用模拟模式`

**解决方法**：
- 按照上述步骤安装XTP SDK
- 验证安装：`import xtp_api`

### 2. 连接失败

**错误信息**：`连接XTP Pro交易服务器失败`

**解决方法**：
- 检查服务器地址和端口是否正确
- 检查网络连接
- 检查防火墙设置
- 联系中泰证券确认服务器状态

### 3. 登录失败

**错误信息**：`登录XTP Pro账户失败`

**解决方法**：
- 检查账户ID和密码是否正确
- 检查客户端ID是否正确
- 检查软件密钥是否正确
- 联系中泰证券确认账户状态

### 4. 订单提交失败

**错误信息**：`提交订单到XTP Pro失败`

**解决方法**：
- 检查账户是否已登录
- 检查账户资金是否充足
- 检查订单参数是否正确
- 检查交易时间是否在交易时段内

## 技术支持

- 中泰证券官网：https://www.zts.com.cn/
- XTP API文档：https://github.com/ztsec/xtp_api_python
- 技术支持邮箱：support@zts.com.cn

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本
- 支持基本的交易功能
- 支持订单管理
- 支持资金查询
- 支持持仓查询
- 支持回调机制
- 支持模拟模式