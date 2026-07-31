"""R196-A 业务关键事件筛选器: 过滤中文/消息文本,只保留真正的业务事件名"""
import json
import re
from pathlib import Path

with open("tools/_r196_a_event_type_scan.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 业务事件名特征:
# 1. 全部是 ASCII 字母/数字/下划线/点号
# 2. 至少含一个字母
# 3. 长度 >= 5
# 4. 不含空格
# 5. 不是常见消息文本(warning/error/info 等)
business_pattern = re.compile(r"^[a-z][a-z0-9_.]{4,}$")
non_event_keywords = {
    "warning", "error", "info", "message", "connection", "message_handle",
    "message_processing", "cancellederror", "already", "stop",
}

business_missing = []
for item in data["missing_list"]:
    name = item["event_name"].lower()
    if not business_pattern.match(name):
        continue
    if any(kw in name for kw in non_event_keywords):
        continue
    business_missing.append(item)

print(f"业务关键缺失 (英文/下划线/点号): {len(business_missing)}")
for i, item in enumerate(business_missing, 1):
    print(f"  {i:2}. {item['event_name']:55s} -> {item['publish_count']:2d} 处 publish")

# 写入分类结果
out = {
    "total_publishes": data["total_publishes"],
    "unique_events": data["unique_events"],
    "missing_total": data["missing_event_types"],
    "business_missing_count": len(business_missing),
    "business_missing": business_missing,
}
with open("tools/_r196_a_business_events.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(f"\n业务事件 JSON 写入: tools/_r196_a_business_events.json")
