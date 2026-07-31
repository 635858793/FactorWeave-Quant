"""R196-A 业务关键事件完整列表查看"""
import json

with open("tools/_r196_a_business_events.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print(f"Total: {d['business_missing_count']}")
for i, x in enumerate(d['business_missing'], 1):
    loc = x['locations'][0]
    file_short = loc['file'].replace('d:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui\\', '')
    line = loc['line']
    print(f"{i:2}. {x['event_name']:50s} | {x['publish_count']:2d} pub | {file_short}:L{line}")
