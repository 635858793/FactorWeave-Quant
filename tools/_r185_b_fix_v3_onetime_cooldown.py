"""
R185-B HVD-182-3 第三轮修复 (1 项)
修复 test_reset_after_trigger_recovers:
  cool-down 改为一次性 (第 4 次 True 后立即清空, 允许业务方后续正常计数)
  R8 设计"业务方可恢复"原则, 5s 持续 break 会永久屏蔽
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def fix_self_loop_detector_onetime_cooldown():
    path = PROJECT_ROOT / "core/events/self_loop_detector.py"
    src = path.read_text(encoding="utf-8")

    # 改 is_self_loop 的 cool-down 检查: 一次性 (立即清空)
    old = '''            # R185-B 修复 (2026-07-25) Step 1: cool-down 检查
            # 触发后 5s 内, 任何相同 key 直接返回 True (不计数, 不重新进入 _window)
            if event_key in self._cool_down:
                trigger_time = self._cool_down[event_key]
                if trigger_time > cutoff:
                    # cool-down 期内, 仍记为 detected (累计计数便于观察)
                    self._stats["self_loops_detected"] += 1
                    return True
                else:
                    # cool-down 过期, 清空
                    del self._cool_down[event_key]'''

    new = '''            # R185-B 修复 (2026-07-25) Step 1: 一次性 cool-down (R8 设计原则)
            # Why: 业务方期望"触发后可恢复" (test_reset_after_trigger_recovers 验证),
            #      5s 持续 break 会永久屏蔽业务方, 违反 R8 防御性原则.
            # Fix: cool-down 仅 1 次调用窗口: 第 4 次返回 True, 立即清空 cool-down,
            #      第 5 次起进入正常 _window 计数 (从 1 开始, hit<3 时 False).
            if event_key in self._cool_down:
                trigger_time = self._cool_down[event_key]
                # 一次性: 无论是否过期都清空 (避免永久屏蔽)
                del self._cool_down[event_key]
                if trigger_time > cutoff:
                    # 在 5s 窗口内: 仍返回 True (防自环风暴) + 累计 detected
                    self._stats["self_loops_detected"] += 1
                    self._stats["cool_down_active"] = len(self._cool_down)
                    return True
                # 过期 cool-down: 不算 detected, 走正常 _window 计数'''

    if old not in src:
        print(f"FAIL: 找不到 cool-down 检查原文 in {path}")
        return False
    src = src.replace(old, new)
    print(f"OK: 修复 - {path} cool-down 改为一次性 (R8 业务方可恢复)")
    path.write_text(src, encoding="utf-8")
    return True


if __name__ == "__main__":
    if fix_self_loop_detector_onetime_cooldown():
        print("\n第三轮修复完成, 请重新跑 pytest 验证")
        sys.exit(0)
    else:
        sys.exit(1)
