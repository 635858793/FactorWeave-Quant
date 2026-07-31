"""R231 死代码审计 + 价值评估 - 直接调用工具 + 输出报告"""
import json
import sys
import os

# 切换到项目根目录
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入工具
sys.path.insert(0, "tools")
from service_dispose_audit import audit_service_dispose

# 运行审计
report = audit_service_dispose()

# 写入文件
with open("dispose_audit_r231.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False, default=str)

print(f"已写入 dispose_audit_r231.json, total={report['total_classes']}, "
      f"with={report['with_dispose']}, without={report['without_dispose']}, "
      f"coverage={report['coverage_percent']}%")
print(f"by_category:")
for cat, stats in sorted(report["by_category"].items(), key=lambda x: -x[1]["without_dispose"]):
    cov = (stats["with_dispose"] / stats["total"] * 100.0) if stats["total"] > 0 else 0.0
    print(f"  {cat:12s}: total={stats['total']:3d} with={stats['with_dispose']:3d} "
          f"without={stats['without_dispose']:3d} with_do_dispose={stats['with_do_dispose']:3d} "
          f"coverage={cov:.1f}%")
