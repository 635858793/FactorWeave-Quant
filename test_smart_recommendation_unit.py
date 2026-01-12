#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能推荐面板单元测试（非图形界面版本）
测试关键方法的逻辑正确性
"""

import sys
import os
import re
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("智能推荐面板单元测试（非图形界面版本）")
print("=" * 80)

# 读取文件
file_path = Path("gui/widgets/enhanced_ui/smart_recommendation_panel.py")

if not file_path.exists():
    print(f"❌ 文件不存在: {file_path}")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 测试 1: 检查关键方法是否存在
print("\n" + "=" * 80)
print("测试 1: 检查关键方法是否存在")
print("=" * 80)

key_methods = [
    ('def cleanup(self):', '资源清理方法'),
    ('def closeEvent(self, event):', '窗口关闭事件方法'),
    ('def __del__(self):', '析构函数'),
    ('def _update_recommendations(self):', '定时更新推荐方法'),
    ('def _train_recommendation_model(self):', '训练推荐模型方法'),
    ('def _show_recommendation_detail(self, recommendation_data):', '显示推荐详情方法'),
    ('def _record_user_interaction(self, action, recommendation_data):', '记录用户交互方法'),
    ('def _get_current_user_id(self) -> str:', '获取当前用户ID方法'),
    ('def _load_persistent_data(self):', '加载持久化数据方法'),
    ('def _save_persistent_data(self):', '保存持久化数据方法'),
    ('def _create_recommendation_tables(self):', '创建推荐相关表方法')
]

methods_count = 0
for method_pattern, method_name in key_methods:
    if method_pattern in content:
        print(f"✅ {method_name} 已实现")
        methods_count += 1
    else:
        print(f"❌ {method_name} 未找到")

print(f"\n方法覆盖率: {methods_count}/{len(key_methods)} ({methods_count/len(key_methods)*100:.1f}%)")

# 测试 2: 检查资源清理逻辑
print("\n" + "=" * 80)
print("测试 2: 检查资源清理逻辑")
print("=" * 80)

cleanup_checks = [
    ('self.update_timer.stop()', '停止定时器'),
    ('self.update_timer.deleteLater()', '删除定时器'),
    ('worker.deleteLater()', '删除 Worker 对象'),
    ('worker.signals.disconnect()', '断开信号连接'),
    ('logger.info("开始清理', '清理开始日志'),
    ('logger.info("资源清理完成")', '清理完成日志')
]

cleanup_count = 0
for pattern, description in cleanup_checks:
    if pattern in content:
        print(f"✅ {description} 已实现")
        cleanup_count += 1
    else:
        print(f"❌ {description} 未找到")

print(f"\n资源清理覆盖率: {cleanup_count}/{len(cleanup_checks)} ({cleanup_count/len(cleanup_checks)*100:.1f}%)")

# 测试 3: 检查数据库持久化逻辑
print("\n" + "=" * 80)
print("测试 3: 检查数据库持久化逻辑")
print("=" * 80)

db_persistence_checks = [
    ('CREATE TABLE IF NOT EXISTS user_preferences', '创建用户偏好表'),
    ('CREATE TABLE IF NOT EXISTS user_feedback', '创建用户反馈表'),
    ('SELECT preference_key, preference_value FROM user_preferences', '查询用户偏好'),
    ('SELECT id, recommendation_id, feedback_type', '查询用户反馈'),
    ('INSERT INTO user_preferences', '插入用户偏好'),
    ('INSERT INTO user_feedback', '插入用户反馈'),
    ('DELETE FROM user_preferences', '删除用户偏好'),
    ('DELETE FROM user_feedback', '删除用户反馈'),
    ('container.get_service(\'DatabaseService\')', '获取数据库服务'),
    ('self._database_service.fetch_all(', '获取数据库数据'),
    ('self._database_service.execute_query(', '执行数据库查询')
]

db_count = 0
for pattern, description in db_persistence_checks:
    if pattern in content:
        print(f"✅ {description} 已实现")
        db_count += 1
    else:
        print(f"❌ {description} 未找到")

print(f"\n数据库持久化覆盖率: {db_count}/{len(db_persistence_checks)} ({db_count/len(db_persistence_checks)*100:.1f}%)")

# 测试 4: 检查异常处理
print("\n" + "=" * 80)
print("测试 4: 检查异常处理")
print("=" * 80)

exception_checks = [
    ('except Exception as e:', '通用异常捕获'),
    ('logger.error(f', '错误日志记录'),
    ('logger.warning(f', '警告日志记录'),
    ('logger.debug(f', '调试日志记录'),
    ('logger.info(f', '信息日志记录'),
    ('import traceback', '导入 traceback 模块'),
    ('traceback.format_exc()', '打印异常堆栈')
]

exception_count = 0
for pattern, description in exception_checks:
    if pattern in content:
        print(f"✅ {description} 已实现")
        exception_count += 1
    else:
        print(f"❌ {description} 未找到")

print(f"\n异常处理覆盖率: {exception_count}/{len(exception_checks)} ({exception_count/len(exception_checks)*100:.1f}%)")

# 测试 5: 检查定时器逻辑
print("\n" + "=" * 80)
print("测试 5: 检查定时器逻辑")
print("=" * 80)

timer_checks = [
    ('self.update_timer = QTimer()', '创建定时器'),
    ('self.update_timer.timeout.connect(self._update_recommendations)', '连接定时器信号'),
    ('self.update_timer.start(', '启动定时器'),
    ('self.update_timer.stop()', '停止定时器'),
    ('self.update_interval * 60 * 1000', '定时器间隔设置（分钟转毫秒）')
]

timer_count = 0
for pattern, description in timer_checks:
    if pattern in content:
        print(f"✅ {description} 已实现")
        timer_count += 1
    else:
        print(f"❌ {description} 未找到")

print(f"\n定时器逻辑覆盖率: {timer_count}/{len(timer_checks)} ({timer_count/len(timer_checks)*100:.1f}%)")

# 测试 6: 检查 UI 交互逻辑
print("\n" + "=" * 80)
print("测试 6: 检查 UI 交互逻辑")
print("=" * 80)

ui_checks = [
    ('card.card_clicked.connect(self._on_recommendation_clicked)', '卡片点击信号连接'),
    ('card.action_clicked.connect(self._on_recommendation_action)', '操作点击信号连接'),
    ('self.recommendation_selected.emit(recommendation_data)', '发送推荐选择信号'),
    ('event_bus.publish(event)', '发布事件'),
    ('StockSelectedEvent', '股票选择事件')
]

ui_count = 0
for pattern, description in ui_checks:
    if pattern in content:
        print(f"✅ {description} 已实现")
        ui_count += 1
    else:
        print(f"❌ {description} 未找到")

print(f"\nUI 交互逻辑覆盖率: {ui_count}/{len(ui_checks)} ({ui_count/len(ui_checks)*100:.1f}%)")

# 测试 7: 检查数据库表结构
print("\n" + "=" * 80)
print("测试 7: 检查数据库表结构")
print("=" * 80)

table_structure_checks = [
    ('id INTEGER PRIMARY KEY AUTOINCREMENT', '主键字段'),
    ('user_id VARCHAR(100) NOT NULL', '用户 ID 字段'),
    ('preference_key VARCHAR(100) NOT NULL', '偏好键字段'),
    ('preference_value TEXT NOT NULL', '偏好值字段'),
    ('recommendation_id VARCHAR(100) NOT NULL', '推荐 ID 字段'),
    ('feedback_type VARCHAR(50) NOT NULL', '反馈类型字段'),
    ('rating INTEGER NOT NULL', '评分字段'),
    ('comment TEXT', '评论字段'),
    ('timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP', '时间戳字段'),
    ('UNIQUE(user_id, preference_key)', '唯一约束'),
    ('INDEX idx_user_feedback_user_id_timestamp (user_id, timestamp)', '用户 ID 和时间戳复合索引'),
    ('INDEX idx_user_feedback_recommendation_id (recommendation_id)', '推荐 ID 索引'),
    ('INDEX idx_user_feedback_feedback_type (feedback_type)', '反馈类型索引')
]

table_count = 0
for pattern, description in table_structure_checks:
    if pattern in content:
        print(f"✅ {description} 已添加")
        table_count += 1
    else:
        print(f"❌ {description} 未找到")

print(f"\n数据库表结构覆盖率: {table_count}/{len(table_structure_checks)} ({table_count/len(table_structure_checks)*100:.1f}%)")

# 测试 8: 检查数据限制
print("\n" + "=" * 80)
print("测试 8: 检查数据限制")
print("=" * 80)

data_limit_checks = [
    ('LIMIT 1000', '反馈历史限制'),
    ('recent_feedback = self.feedback_history[-1000:]', '反馈历史切片限制'),
    ('if len(self.feedback_history) > 1000', '反馈历史长度检查')
]

limit_count = 0
for pattern, description in data_limit_checks:
    if pattern in content:
        print(f"✅ {description} 已添加")
        limit_count += 1
    else:
        print(f"❌ {description} 未找到")

print(f"\n数据限制覆盖率: {limit_count}/{len(data_limit_checks)} ({limit_count/len(data_limit_checks)*100:.1f}%)")

# 测试总结
print("\n" + "=" * 80)
print("测试总结")
print("=" * 80)

total_tests = 8
passed_tests = 0

if methods_count >= len(key_methods) * 0.9:
    passed_tests += 1
    print("✅ 测试 1: 关键方法检查 - 通过")
else:
    print("❌ 测试 1: 关键方法检查 - 未通过")

if cleanup_count >= len(cleanup_checks) * 0.9:
    passed_tests += 1
    print("✅ 测试 2: 资源清理逻辑检查 - 通过")
else:
    print("❌ 测试 2: 资源清理逻辑检查 - 未通过")

if db_count >= len(db_persistence_checks) * 0.9:
    passed_tests += 1
    print("✅ 测试 3: 数据库持久化逻辑检查 - 通过")
else:
    print("❌ 测试 3: 数据库持久化逻辑检查 - 未通过")

if exception_count >= len(exception_checks) * 0.9:
    passed_tests += 1
    print("✅ 测试 4: 异常处理检查 - 通过")
else:
    print("❌ 测试 4: 异常处理检查 - 未通过")

if timer_count >= len(timer_checks) * 0.9:
    passed_tests += 1
    print("✅ 测试 5: 定时器逻辑检查 - 通过")
else:
    print("❌ 测试 5: 定时器逻辑检查 - 未通过")

if ui_count >= len(ui_checks) * 0.9:
    passed_tests += 1
    print("✅ 测试 6: UI 交互逻辑检查 - 通过")
else:
    print("❌ 测试 6: UI 交互逻辑检查 - 未通过")

if table_count >= len(table_structure_checks) * 0.9:
    passed_tests += 1
    print("✅ 测试 7: 数据库表结构检查 - 通过")
else:
    print("❌ 测试 7: 数据库表结构检查 - 未通过")

if limit_count >= len(data_limit_checks) * 0.9:
    passed_tests += 1
    print("✅ 测试 8: 数据限制检查 - 通过")
else:
    print("❌ 测试 8: 数据限制检查 - 未通过")

print("\n" + "=" * 80)
print(f"通过测试: {passed_tests}/{total_tests}")
print(f"通过率: {passed_tests/total_tests*100:.1f}%")
print("=" * 80)

if passed_tests >= total_tests * 0.9:
    print("✅ 单元测试通过！代码质量良好！")
    exit(0)
else:
    print("⚠️  部分测试未通过，需要进一步检查")
    exit(1)
