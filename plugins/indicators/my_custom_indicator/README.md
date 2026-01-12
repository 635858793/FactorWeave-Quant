# 自定义指标插件示例

这是一个展示如何通过插件系统为FactorWeave-Quant ‌添加自定义指标的示例插件。

## 包含的指标

### 1. 市场情绪指标 (EMOTION)

市场情绪指标是一个基于价格变化和成交量的综合指标，用于判断市场情绪是否过热或过冷。

**计算公式:**
```
EMOTION = (CLOSE - OPEN) / (HIGH - LOW) * VOLUME / AVG_VOLUME
```

**参数:**
- `timeperiod`: 计算周期，默认为14

**解读:**
- EMOTION > 0.7: 市场情绪过热，可能即将回调
- EMOTION < -0.7: 市场情绪过冷，可能即将反弹
- -0.3 < EMOTION < 0.3: 市场情绪平稳

### 2. 成交量加权平均价 (VWAP)

成交量加权平均价是一种考虑了成交量因素的价格平均值，常用于日内交易。

**计算公式:**
```
VWAP = ∑(PRICE * VOLUME) / ∑(VOLUME)
```

**解读:**
- 价格高于VWAP: 当日走势偏强
- 价格低于VWAP: 当日走势偏弱
- VWAP可作为支撑/阻力位参考

## 使用方法

1. 将此插件目录复制到FactorWeave-Quant ‌的`plugins`目录下
2. 重启FactorWeave-Quant ‌应用
3. 在技术分析面板中，您将看到新增的"市场情绪指标"和"成交量加权平均价"选项

## 开发自定义指标

如果您想开发自己的指标插件，请按照以下步骤操作：

1. 创建一个新的插件目录，例如`plugins/my_plugin`
2. 创建`plugin_info.py`文件，实现`register_indicators`函数
3. 创建指标实现文件，例如`indicator_impl.py`
4. 实现指标的计算函数
5. 编写README.md文件，说明插件的用途和使用方法

### plugin_info.py示例

```python
def register_indicators():
    return [
        {
            "name": "MY_INDICATOR",
            "display_name": "我的指标",
            "category_id": 6,  # 其他类
            "description": "这是我的自定义指标",
            "formula": "MY_INDICATOR = ...",
            "parameters": [
                {
                    "name": "param1",
                    "description": "参数1",
                    "type": "int",
                    "default_value": 14
                }
            ],
            "implementations": [
                {
                    "engine": "custom",
                    "function_name": "calculate_my_indicator",
                    "code": "from plugins.my_plugin.indicator_impl import calculate_my_indicator",
                    "is_default": True
                }
            ],
            "output_names": ["MY_INDICATOR"]
        }
    ]
```

### indicator_impl.py示例

```python
def calculate_my_indicator(df, param1=14):
    result = df.copy()
    # 计算指标...
    result['MY_INDICATOR'] = ...
    return result
``` 