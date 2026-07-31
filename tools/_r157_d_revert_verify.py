"""R157-D 5 项 P0/P1 撤销立项二次验证 (R85 假修复鉴别 4 步法)"""
import sys
sys.path.insert(0, '.')

# 5 项 P0/P1 撤销立项验证
# 1. HVD-156-A-1: 删除 AccountStatusChangedEvent dataclass publish
# 2. HVD-155-3-CALL: trading_engine.py:1346/1605 透传
# 3. HVD-156-A-2/3/4: risk_alert.py 透传 + handler 消费 + audit
# 4. R51-1/2: trading_service.py:1714 + money_manager.py:286 exc_info
# 5. FIX-8: 删除 PERFORMANCE_ALERT 死枚举

# 读取关键文件验证
files_to_check = [
    # (file_path, line_range, expected_text, item_name)
    ('core/trading/account_manager.py', (1004, 1015), "publish('account_status_changed'", "HVD-156-A-1 (dataclass publish 删除)"),
    ('core/trading_engine.py', (1340, 1360), "account_id", "HVD-155-3-CALL buy 透传"),
    ('core/trading_engine.py', (1600, 1620), "account_id", "HVD-155-3-CALL sell 透传"),
    ('core/risk_alert.py', (280, 290), "account_id", "HVD-156-A-2 publish 传 account_id"),
    ('core/risk/risk_event_subscribers.py', (515, 530), "account_id", "HVD-156-A-3 handler 消费 account_id"),
    ('core/risk/compliance_audit_logger.py', (515, 540), "account_id", "HVD-156-A-4 audit 接受 account_id"),
    ('core/services/trading_service.py', (1710, 1725), "exc_info", "R51-1 trading_service.py:1714 exc_info"),
    ('core/money_manager.py', (290, 305), "exc_info", "R51-2 money_manager.py:295 exc_info"),
]

print("R157-D 5 项 P0/P1 撤销立项二次验证 (4 源 Read 源)")
print("=" * 80)

for file_path, (start, end), expected_text, item_name in files_to_check:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # 取目标行
        target_lines = lines[start-1:end]
        content = '\n'.join(target_lines)
        has_text = expected_text in content
        status = "✅" if has_text else "❌"
        print(f"\n[{status}] {item_name}")
        print(f"  文件: {file_path}:{start}-{end}")
        print(f"  期望关键字: {expected_text!r}")
        if has_text:
            for line in target_lines[:5]:
                print(f"    | {line.rstrip()}")
        else:
            print(f"  ⚠️ 实际内容:")
            for line in target_lines[:5]:
                print(f"    | {line.rstrip()}")
    except FileNotFoundError:
        print(f"\n[❌] {item_name} - 文件不存在: {file_path}")
    except Exception as e:
        print(f"\n[❌] {item_name} - ERROR: {e}")

# FIX-8: PERFORMANCE_ALERT 真实引用验证
print("\n" + "=" * 80)
print("FIX-8 (撤销立项) 二次验证: PERFORMANCE_ALERT 真实引用")
print("=" * 80)

try:
    with open('core/events/types.py', 'r', encoding='utf-8') as f:
        content = f.read()
    if 'PERFORMANCE_ALERT' in content and 'PerformanceAlertEvent' in content:
        # 找 PerformanceAlertEvent 类定义位置
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'class PerformanceAlertEvent' in line:
                print(f"  ✅ events/types.py:{i} PerformanceAlertEvent 类定义存在")
            if 'PERFORMANCE_ALERT' in line and i < 120:
                print(f"  ✅ events/types.py:{i} PERFORMANCE_ALERT 枚举定义: {line.strip()}")
            if 'event_type: EventType = EventType.PERFORMANCE_ALERT' in line:
                print(f"  ✅ events/types.py:{i} PerformanceAlertEvent.event_type 引用")
except FileNotFoundError:
    print("  ❌ events/types.py 文件不存在")

# FIX-7: SECURITY_EVENT 死枚举 4 源验证
print("\n" + "=" * 80)
print("FIX-7 (待实施) 二次验证: SECURITY_EVENT 死枚举 4 源")
print("=" * 80)

try:
    with open('core/risk/compliance_audit_logger.py', 'r', encoding='utf-8') as f:
        content = f.read()
    sec_count = content.count('SECURITY_EVENT')
    sec_value_count = content.count('security_event')
    print(f"  源 1: compliance_audit_logger.py 内 SECURITY_EVENT 引用 = {sec_count} 次 (仅 1 hit definition)")
    print(f"  源 2: security_event 字符串字面量 = {sec_value_count} 次")
    # 跨子目录搜索
    import subprocess
    result = subprocess.run(
        ['python', '-c', f"""
import os
import re
count = 0
files_found = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('.git', '.pytest_cache', '__pycache__', 'node_modules', 'tools')]
    for f in files:
        if f.endswith('.py'):
            full = os.path.join(root, f)
            with open(full, 'r', encoding='utf-8', errors='ignore') as fp:
                c = fp.read()
            if 'SECURITY_EVENT' in c and 'compliance_audit_logger' not in full:
                count += c.count('SECURITY_EVENT')
                files_found.append(full)
print(f'源 3: 跨子目录 SECURITY_EVENT 引用 = {count} 次, 文件: {len(files_found)}')
for f in files_found[:5]: print(f'  - {f}')
"""],
        capture_output=True,
        text=True,
        cwd='.'
    )
    print("  " + result.stdout.replace('\n', '\n  '))
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# AccountStatusChangedEvent 订阅方验证
print("\n" + "=" * 80)
print("HVD-156-A-1 二次验证: AccountStatusChangedEvent 0 订阅方")
print("=" * 80)
try:
    with open('core/events/types.py', 'r', encoding='utf-8') as f:
        content = f.read()
    if 'class AccountStatusChangedEvent' in content:
        print(f"  ✅ events/types.py 类定义保留 (向后兼容)")
    else:
        print(f"  ⚠️ events/types.py 类定义不存在")
except Exception as e:
    print(f"  ERROR: {e}")

# 跨子目录查 AccountStatusChangedEvent 订阅
import subprocess
result = subprocess.run(
    ['python', '-c', """
import os
import re
publish_count = 0
subscribe_count = 0
import_count = 0
files = []
for root, dirs, fs in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('.git', '.pytest_cache', '__pycache__', 'node_modules', 'tools')]
    for f in fs:
        if f.endswith('.py'):
            full = os.path.join(root, f)
            with open(full, 'r', encoding='utf-8', errors='ignore') as fp:
                lines = fp.readlines()
            for line in lines:
                if 'AccountStatusChangedEvent' in line:
                    if 'publish' in line.lower() or '.publish(' in line:
                        publish_count += 1
                    elif 'subscribe' in line.lower() or 'on_' in line or 'handler' in line:
                        subscribe_count += 1
                    elif 'import' in line:
                        import_count += 1
                    files.append(full)
                    break
print(f'AccountStatusChangedEvent 文件引用 = {len(set(files))}')
print(f'  publish 引用 = {publish_count}')
print(f'  subscribe 引用 = {subscribe_count}')
print(f'  import 引用 = {import_count}')
"""],
    capture_output=True,
    text=True,
    cwd='.'
)
print("  " + result.stdout.replace('\n', '\n  '))
