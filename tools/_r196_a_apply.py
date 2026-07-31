"""
R196-A 实施核心: 批量在 core/events/types.py 末尾追加 52 个 EventType 枚举

强制度:
- R8 §8.1 #1 双轨注册铁律
- R192-C-3 dotted 风格
- R193-C-D-001 注释模板
- R85 假修复鉴别 4 步法 (Read 确认 EventType 末尾位置)
"""
import sys
sys.path.insert(0, "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

from pathlib import Path
from tools._r196_a_event_defs import NEW_EVENTS

TYPES_FILE = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/events/types.py")

# 读取原文件
content = TYPES_FILE.read_text(encoding="utf-8")

# 检查是否已补全 (幂等性)
if "R196-A 批量补全" in content:
    print("⚠️  R196-A 补全已存在, 跳过 (幂等保护)")
    sys.exit(0)

# 找 ALL_ACTIVE_ORDERS_CANCELLED 末尾位置
all_active_marker = 'ALL_ACTIVE_ORDERS_CANCELLED = "all_active_orders_cancelled"'
idx = content.find(all_active_marker)
if idx == -1:
    print(f"❌ 未找到锚点 {all_active_marker}")
    sys.exit(1)

# 找该行末尾
line_end = content.find("\n", idx) + 1
print(f"✅ 锚点位置: L{content[:idx].count(chr(10)) + 1}")

# 构造补全内容 (R193-C-D-001 注释模板, R196 标识)
appended = "\n    # R196-A 批量补全 (2026-07-25, 子智能体 A 报告, HVD-195-C-2 实施):\n"
appended += "    # Why: R195-C 事件总线治理发现 49 字符串事件缺 EventType 枚举, R196-A 扩大扫描\n"
appended += "    #      范围至全项目 170 publish 调用, 识别 64 业务关键缺失 (R196-A 4 源验证\n"
appended += "    #      100% 命中), 排除 12 GUI 内部事件 + 测试代码, 52 项业务核心需补全.\n"
appended += "    # Fix: 52 个 EventType 枚举 + 字符串值 (与 R193-C-D-001/R192-C-3 dotted 风格一致)\n"
appended += "    # 业务链 (R196-A 已 4 源验证):\n"

# 按类别分组
categories = {
    "订单": [],
    "账户": [],
    "任务": [],
    "风险": [],
    "插件": [],
    "数据源": [],
    "健康检查": [],
    "指标": [],
    "多账户": [],
    "AI 解释": [],
    "性能": [],
    "数据": [],
    "环境": [],
    "训练": [],
    "系统优化": [],
    "数据导入": [],
}
name_to_cat = {
    "ORDER_": "订单", "TRADING_INTERFACE_": "订单", "CANCEL_": "订单", "ORDERS_": "订单",
    "ACCOUNTS_": "账户", "ALL_DATA_": "账户", "ACCOUNT_": "账户", "POSITION_": "账户", "FUND_": "账户",
    "TASK_": "任务",
    "RISK_": "风险",
    "PLUGIN_": "插件",
    "DATA_SOURCES_": "数据源",
    "HEALTH_CHECK": "健康检查",
    "METRICS_": "指标", "RESOURCE_": "指标", "APPLICATION_": "指标",
    "MULTI_ACCOUNT_": "多账户",
    "AI_EXPLANATION_": "AI 解释",
    "PERFORMANCE_": "性能",
    "DATA_MASKED": "数据",
    "ENVIRONMENT_": "环境",
    "TRAINING_": "训练",
    "SYSTEM_OPTIMIZATION_": "系统优化",
    "DATA_IMPORT_": "数据导入",
}

for enum_name, value, desc in NEW_EVENTS:
    cat = None
    for prefix, c in name_to_cat.items():
        if enum_name.startswith(prefix):
            cat = c
            break
    if cat is None:
        cat = "其他"
    if cat not in categories:
        categories[cat] = []
    categories[cat].append((enum_name, value, desc))

for cat, items in categories.items():
    if not items:
        continue
    appended += f"    # {cat} ({len(items)} 项):\n"
    for enum_name, value, desc in items:
        appended += f"    {enum_name} = \"{value}\"\n"
    appended += "\n"

appended = appended.rstrip() + "\n"  # 去掉末尾多余空行

# 写回
new_content = content[:line_end] + appended + content[line_end:]
TYPES_FILE.write_text(new_content, encoding="utf-8")

# 验证: 重新读 + 解析
import ast
tree = ast.parse(new_content)
print(f"✅ EventType 补全成功, 写入 {len(NEW_EVENTS)} 个枚举")
print(f"   文件: {TYPES_FILE}")
print(f"   新文件大小: {len(new_content)} 字节 (原 {len(content)} 字节, +{len(new_content) - len(content)})")

# 验证: 检查 EventType 枚举数量
eventtype_node = None
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "EventType":
        eventtype_node = node
        break

if eventtype_node:
    enum_count = sum(1 for n in eventtype_node.body if isinstance(n, ast.Assign))
    print(f"   EventType 枚举成员数: {enum_count}")
