"""
R106 修复脚本 V2 - 精确截断 right_panel.py 到 L3474 (R106 修复注释之后)
- 删除 L3474 之后所有重复的 import 内容
- 同时添加 _do_dispose 方法(P0-8 + P1-1 修复)
"""
import ast
import sys
from pathlib import Path

TARGET = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\ui\panels\right_panel.py')

source = TARGET.read_text(encoding='utf-8')
print(f"[1] 当前文件: {len(source)} 字符, {source.count(chr(10))+1} 行")

# 2. 找到 R106 修复注释的结束位置
# 注释在 L3470-3473 之后
# 用第二次出现(L3473 文件末尾的注释)
fix_marker = "将由 HVD-36 重建."
idx1 = source.find(fix_marker)
print(f"[2] 第一次找到 '{fix_marker}' idx={idx1}")

# 第二次出现(L3473,文件末尾的修复注释)
idx2 = source.find(fix_marker, idx1 + 1) if idx1 > 0 else -1
print(f"    第二次找到 idx={idx2}")

# 用第二次出现(文件末尾的修复注释),跳过 \n
fix_comment_end_idx = source.find('\n', idx2 + len(fix_marker)) + 1 if idx2 > 0 else -1
print(f"    修复注释后第一个 \\n idx={fix_comment_end_idx}")

# 截断到修复注释后
truncate_to = fix_comment_end_idx

# 准备 _do_dispose 方法 (P0-8 + P1-1 完整版)
dispose_method = '''    def _do_dispose(self) -> None:
        """清理资源: 取消所有EventBus订阅 + 停止所有 QTimer + quit QThread + shutdown executor

        R106 P0-8 修复 (审计 2026-07-06): 添加 _perf_refresh_timer.stop() 清理路径
        R106 P1-1 修复 (审计 2026-07-06): 添加 _ai_thread quit/wait 清理
        R76 修复 (审计 2026-07-03 P1): 优化 dispose 顺序 (executor → timer → unsubscribe)
        """
        # 1. 关闭线程池, 避免新任务提交
        try:
            if hasattr(self, '_tab_update_executor') and self._tab_update_executor is not None:
                self._tab_update_executor.shutdown(wait=False, cancel_futures=True)
                logger.debug("RightPanel _tab_update_executor 已关闭")
            if hasattr(self, '_industry_executor') and self._industry_executor is not None:
                self._industry_executor.shutdown(wait=False, cancel_futures=True)
                logger.debug("RightPanel _industry_executor 已关闭")
        except Exception as exec_exc:
            logger.debug(f"RightPanel executor 关闭失败: {exec_exc}")

        # 2. 停止 QTimer (P0-8 新增 _perf_refresh_timer)
        try:
            if hasattr(self, '_tab_update_timer') and self._tab_update_timer is not None:
                self._tab_update_timer.stop()
                logger.debug("RightPanel _tab_update_timer 已停止")
            # R106 P0-8: 停止 _perf_refresh_timer (性能监控标签页的 3s 周期 timer)
            if hasattr(self, '_perf_refresh_timer') and self._perf_refresh_timer is not None:
                try:
                    self._perf_refresh_timer.stop()
                    self._perf_refresh_timer.deleteLater()
                    logger.debug("RightPanel _perf_refresh_timer 已停止")
                except Exception as t_exc:
                    logger.debug(f"停止 _perf_refresh_timer 失败: {t_exc}")
        except Exception as timer_exc:
            logger.debug(f"RightPanel timer 停止失败: {timer_exc}")

        # 3. 取消 EventBus 订阅 (此时不会有新事件产生)
        try:
            if self.event_bus:
                self.event_bus.unsubscribe(AnalysisCompleteEvent, self._on_analysis_complete)
                self.event_bus.unsubscribe(UIDataReadyEvent, self._on_ui_data_ready)
                # R74 修复: 补全 StockSelectedEvent 订阅
                self.event_bus.unsubscribe(StockSelectedEvent, self._on_stock_selected)
                # R106 P0-6 修复: 取消 _on_asset_selected 订阅
                if hasattr(self, '_on_asset_selected'):
                    self.event_bus.unsubscribe(AssetSelectedEvent, self._on_asset_selected)
                logger.info("RightPanel EventBus订阅已取消")
        except Exception as e:
            logger.error(f"RightPanel清理EventBus订阅失败: {e}")

        # 4. R106 P1-1: quit + wait _ai_thread
        try:
            ai_thread = getattr(self, '_ai_thread', None)
            if ai_thread is not None:
                if ai_thread.isRunning():
                    logger.debug("RightPanel _ai_thread.quit() 等待线程结束...")
                    ai_thread.quit()
                    if not ai_thread.wait(3000):  # 最多等 3 秒
                        logger.warning("RightPanel _ai_thread.wait(3000) 超时, 强制 terminate")
                        ai_thread.terminate()
                        ai_thread.wait(1000)
                logger.debug("RightPanel _ai_thread 已停止")
        except Exception as at_exc:
            logger.debug(f"RightPanel _ai_thread 停止失败: {at_exc}")

        # 5. R81 HVD-2: dispose 时清空 _pending_tab_updates / _tab_stock_code
        # 释放持有的大体积 kline_data DataFrame, 避免 dispose 后引用泄漏
        try:
            with self._tab_update_dicts_lock:
                self._pending_tab_updates.clear()
                self._tab_stock_code.clear()
            # 清空 weakref 字典 (R79 P2-9)
            self._tab_weak_refs.clear()
            logger.debug("RightPanel _pending_tab_updates / _tab_stock_code / _tab_weak_refs 已清空")
        except Exception as dict_exc:
            logger.debug(f"RightPanel 字典清理失败: {dict_exc}")

        # 6. 调用父类 dispose
        try:
            super()._do_dispose()
        except Exception as super_exc:
            logger.debug(f"RightPanel 父类 _do_dispose 失败: {super_exc}")
'''

# 拼接: 截断到 fix_comment_end + dispose_method
new_source = source[:truncate_to] + dispose_method

# 4. 验证
print(f"[3] 新文件: {len(new_source)} 字符")
try:
    ast.parse(new_source)
    print("[4] ✅ Python 语法检查通过")
except SyntaxError as e:
    print(f"[4] ❌ 语法错误: {e}")
    sys.exit(1)

# 5. 验证类内容
class_count = new_source.count('class RightPanel(BasePanel):')
print(f"[5] class RightPanel 出现 {class_count} 次 (正常=1)")

# 6. 验证关键内容
checks = [
    ('_do_dispose', 'def _do_dispose'),
    ('_perf_refresh_timer.stop()', '_perf_refresh_timer.stop()'),
    ('_ai_thread', '_ai_thread.quit()'),
    ('_on_asset_selected 物理删除', 'def _on_asset_selected'),
]
for name, key in checks:
    if name.endswith('物理删除'):
        cnt = new_source.count(key)
        status = "✅" if cnt == 0 else f"❌ 仍{cnt}次"
    else:
        cnt = new_source.count(key)
        status = "✅" if cnt > 0 else "❌ 缺失"
    print(f"    {status} {name}: {key} (count={cnt})")

# 7. 写回
TARGET.write_text(new_source, encoding='utf-8')
print(f"[6] ✅ 写回完成, {new_source.count(chr(10))+1} 行")
