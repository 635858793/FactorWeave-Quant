#!/usr/bin/env python3
"""R173-D Service metrics/health_check/status 完整性分析"""
import ast
import os
from collections import defaultdict

SERVICES_DIR = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services"
BOOTSTRAP_FILE = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\service_bootstrap.py"

# Parse service_bootstrap.py to find all registered services
with open(BOOTSTRAP_FILE, encoding="utf-8") as f:
    bootstrap_src = f.read()

tree = ast.parse(bootstrap_src)
registered_classes = set()
imported_classes = set()

# Find all class references in _safe_register_service calls
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        # Look for service_container.register / self._safe_register_service with class arg
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("register", "_safe_register_service"):
                # First arg is the class
                if node.args and isinstance(node.args[0], ast.Name):
                    imported_classes.add(node.args[0].id)

# Now parse all service files to find classes inheriting BaseService
service_classes = {}  # name -> (file, has_metrics, has_health_check, has_status, has_init, has_dispose)
for fname in sorted(os.listdir(SERVICES_DIR)):
    if not fname.endswith(".py") or fname in ("__init__.py", "service_bootstrap.py", "base_service.py"):
        continue
    fpath = os.path.join(SERVICES_DIR, fname)
    try:
        with open(fpath, encoding="utf-8") as f:
            src = f.read()
        ftree = ast.parse(src)
    except Exception:
        continue

    for node in ast.walk(ftree):
        if isinstance(node, ast.ClassDef):
            base_names = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    base_names.append(b.id)
                elif isinstance(b, ast.Attribute):
                    base_names.append(b.attr)

            # Check if it's a service (inherits BaseService or similar)
            is_service = any(
                bn in ("BaseService", "AsyncBaseService", "ConfigurableService", "CacheableService", "ServiceBase")
                for bn in base_names
            )
            if not is_service:
                continue

            # Find methods
            methods = set()
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(child.name)

            service_classes[node.name] = {
                "file": fname,
                "bases": base_names,
                "has_metrics": "get_metrics" in methods,
                "has_health_check": "health_check" in methods or "_do_health_check" in methods or "perform_health_check" in methods,
                "has_status": "get_status" in methods or "status" in methods,
                "has_initialize": "initialize" in methods or "_do_initialize" in methods,
                "has_dispose": "dispose" in methods or "_do_dispose" in methods,
                "is_registered": node.name in imported_classes,
            }

# Print summary
print(f"Total Service classes found: {len(service_classes)}")
print(f"Registered in service_bootstrap: {sum(1 for v in service_classes.values() if v['is_registered'])}")
print(f"Not registered: {sum(1 for v in service_classes.values() if not v['is_registered'])}")

# Count coverage
metrics_count = sum(1 for v in service_classes.values() if v["has_metrics"])
health_count = sum(1 for v in service_classes.values() if v["has_health_check"])
status_count = sum(1 for v in service_classes.values() if v["has_status"])
init_count = sum(1 for v in service_classes.values() if v["has_initialize"])
dispose_count = sum(1 for v in service_classes.values() if v["has_dispose"])

print(f"\n=== Observability Coverage ===")
print(f"  get_metrics: {metrics_count}/{len(service_classes)} ({metrics_count*100//len(service_classes)}%)")
print(f"  health_check: {health_count}/{len(service_classes)} ({health_count*100//len(service_classes)}%)")
print(f"  get_status: {status_count}/{len(service_classes)} ({status_count*100//len(service_classes)}%)")
print(f"  initialize: {init_count}/{len(service_classes)} ({init_count*100//len(service_classes)}%)")
print(f"  dispose: {dispose_count}/{len(service_classes)} ({dispose_count*100//len(service_classes)}%)")

# Find services with ALL 3: metrics, health_check, status
full_observability = [
    (n, v) for n, v in service_classes.items()
    if v["has_metrics"] and v["has_health_check"] and v["has_status"]
]
print(f"\nFull 3-Dim observability: {len(full_observability)}/{len(service_classes)}")

# Find services missing observability
missing_obs = [
    (n, v) for n, v in service_classes.items()
    if not (v["has_metrics"] and v["has_health_check"] and v["has_status"])
]
print(f"Missing observability: {len(missing_obs)}")
for n, v in missing_obs[:30]:
    missing = []
    if not v["has_metrics"]: missing.append("metrics")
    if not v["has_health_check"]: missing.append("health")
    if not v["has_status"]: missing.append("status")
    print(f"  {n} ({v['file']}): missing {','.join(missing)}")

# Save to JSON for report use
import json
out = {
    "total": len(service_classes),
    "registered": sum(1 for v in service_classes.values() if v["is_registered"]),
    "not_registered": sum(1 for v in service_classes.values() if not v["is_registered"]),
    "coverage": {
        "get_metrics": metrics_count,
        "health_check": health_count,
        "get_status": status_count,
        "initialize": init_count,
        "dispose": dispose_count,
    },
    "full_observability": len(full_observability),
    "missing_observability": [
        {"name": n, "file": v["file"], "missing": [
            x for x, has in [("metrics", v["has_metrics"]), ("health", v["has_health_check"]), ("status", v["has_status"])] if not has
        ]}
        for n, v in missing_obs
    ],
    "all_classes": {n: v for n, v in service_classes.items()},
}
with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\.trae\reports\rounds\audit_r173_d_service_obs.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\nSaved to audit_r173_d_service_obs.json")
