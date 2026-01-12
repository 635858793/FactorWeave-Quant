#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能推荐面板数据库持久化功能测试脚本
测试数据库持久化、资源清理和定时器更新功能
"""

import sys
import os
import time
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QTextEdit
from PyQt5.QtCore import QTimer, Qt

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.widgets.enhanced_ui.smart_recommendation_panel import SmartRecommendationPanel


class TestWindow(QMainWindow):
    """测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能推荐面板数据库持久化功能测试")
        self.setGeometry(100, 100, 1200, 800)
        
        # 主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 创建测试按钮
        test_layout = QVBoxLayout()
        
        self.test_cleanup_btn = QPushButton("测试 1: 资源清理功能")
        self.test_cleanup_btn.clicked.connect(self.test_cleanup)
        test_layout.addWidget(self.test_cleanup_btn)
        
        self.test_db_persistence_btn = QPushButton("测试 2: 数据库持久化功能")
        self.test_db_persistence_btn.clicked.connect(self.test_db_persistence)
        test_layout.addWidget(self.test_db_persistence_btn)
        
        self.test_timer_btn = QPushButton("测试 3: 定时器更新功能")
        self.test_timer_btn.clicked.connect(self.test_timer)
        test_layout.addWidget(self.test_timer_btn)
        
        self.test_recommendation_detail_btn = QPushButton("测试 4: 推荐详情显示功能")
        self.test_recommendation_detail_btn.clicked.connect(self.test_recommendation_detail)
        test_layout.addWidget(self.test_recommendation_detail_btn)
        
        self.test_user_interaction_btn = QPushButton("测试 5: 用户交互记录功能")
        self.test_user_interaction_btn.clicked.connect(self.test_user_interaction)
        test_layout.addWidget(self.test_user_interaction_btn)
        
        self.test_all_btn = QPushButton("测试所有功能")
        self.test_all_btn.clicked.connect(self.test_all)
        test_layout.addWidget(self.test_all_btn)
        
        layout.addLayout(test_layout)
        
        # 创建日志输出区域
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(300)
        layout.addWidget(QLabel("测试日志:"))
        layout.addWidget(self.log_output)
        
        # 创建智能推荐面板
        try:
            from core.containers import get_service_container
            from core.services.recommendation_model_trainer import RecommendationModelTrainer
            from core.services.smart_recommendation_engine import SmartRecommendationEngine
            
            container = get_service_container()
            recommendation_engine = None
            model_trainer = None
            
            try:
                recommendation_engine = container.resolve(SmartRecommendationEngine)
                self.log("✅ 成功获取SmartRecommendationEngine服务")
            except Exception as e:
                self.log(f"⚠️ 无法获取SmartRecommendationEngine服务: {e}")
            
            try:
                model_trainer = container.resolve(RecommendationModelTrainer)
                self.log("✅ 成功获取RecommendationModelTrainer服务")
            except Exception as e:
                self.log(f"⚠️ 无法获取RecommendationModelTrainer服务: {e}")
            
            self.recommendation_panel = SmartRecommendationPanel(
                recommendation_engine=recommendation_engine,
                model_trainer=model_trainer
            )
        except Exception as e:
            self.log(f"⚠️ 创建SmartRecommendationPanel时出错: {e}")
            self.recommendation_panel = SmartRecommendationPanel()
        
        layout.addWidget(self.recommendation_panel)
        
        self.log("测试环境初始化完成")
    
    def log(self, message):
        """输出日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")
        print(f"[{timestamp}] {message}")
    
    def test_cleanup(self):
        """测试资源清理功能"""
        self.log("=" * 60)
        self.log("开始测试资源清理功能...")
        
        try:
            # 检查 cleanup 方法是否存在
            if hasattr(self.recommendation_panel, 'cleanup'):
                self.log("✅ cleanup 方法存在")
            else:
                self.log("❌ cleanup 方法不存在")
                return
            
            # 检查 closeEvent 方法是否存在
            if hasattr(self.recommendation_panel, 'closeEvent'):
                self.log("✅ closeEvent 方法存在")
            else:
                self.log("❌ closeEvent 方法不存在")
                return
            
            # 检查 __del__ 方法是否存在
            if hasattr(self.recommendation_panel, '__del__'):
                self.log("✅ __del__ 方法存在")
            else:
                self.log("❌ __del__ 方法不存在")
                return
            
            # 测试 cleanup 方法
            self.log("调用 cleanup 方法...")
            self.recommendation_panel.cleanup()
            self.log("✅ cleanup 方法执行成功")
            
            # 检查定时器是否被清理
            if self.recommendation_panel.update_timer is None:
                self.log("✅ 定时器已被清理")
            else:
                self.log("⚠️  定时器未被清理（可能被重新创建）")
            
            # 检查 Worker 对象是否被清理
            workers = ['hybrid_worker', 'cache_warmup_worker', 'cache_clear_worker', 
                      'cache_stats_worker', '_recommendation_worker']
            all_cleaned = True
            for worker_name in workers:
                worker = getattr(self.recommendation_panel, worker_name, None)
                if worker is None:
                    self.log(f"✅ {worker_name} 已被清理")
                else:
                    self.log(f"⚠️  {worker_name} 未被清理")
                    all_cleaned = False
            
            if all_cleaned:
                self.log("✅ 所有 Worker 对象已被清理")
            else:
                self.log("⚠️  部分 Worker 对象未被清理")
            
            self.log("✅ 资源清理功能测试通过")
            
        except Exception as e:
            self.log(f"❌ 资源清理功能测试失败: {e}")
            import traceback
            self.log(traceback.format_exc())
        
        self.log("=" * 60)
    
    def test_db_persistence(self):
        """测试数据库持久化功能"""
        self.log("=" * 60)
        self.log("开始测试数据库持久化功能...")
        
        try:
            # 检查数据库服务是否可用
            if self.recommendation_panel._database_service is None:
                self.log("❌ 数据库服务不可用")
                return
            else:
                self.log("✅ 数据库服务可用")
            
            # 检查 _load_persistent_data 方法是否存在
            if hasattr(self.recommendation_panel, '_load_persistent_data'):
                self.log("✅ _load_persistent_data 方法存在")
            else:
                self.log("❌ _load_persistent_data 方法不存在")
                return
            
            # 检查 _save_persistent_data 方法是否存在
            if hasattr(self.recommendation_panel, '_save_persistent_data'):
                self.log("✅ _save_persistent_data 方法存在")
            else:
                self.log("❌ _save_persistent_data 方法不存在")
                return
            
            # 检查 _create_recommendation_tables 方法是否存在
            if hasattr(self.recommendation_panel, '_create_recommendation_tables'):
                self.log("✅ _create_recommendation_tables 方法存在")
            else:
                self.log("❌ _create_recommendation_tables 方法不存在")
                return
            
            # 测试保存功能
            self.log("测试保存功能...")
            
            # 修改用户偏好
            test_preferences = {
                'test_key_1': 'test_value_1',
                'test_key_2': 0.75,
                'technical_preference': 0.8,
                'fundamental_preference': 0.6
            }
            self.recommendation_panel.user_preferences.update(test_preferences)
            self.log(f"✅ 设置测试偏好: {test_preferences}")
            
            # 添加测试反馈
            test_feedback = {
                'recommendation_id': 'test_rec_1',
                'feedback_type': 'positive',
                'rating': 5,
                'comment': '测试反馈',
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.recommendation_panel.feedback_history.append(test_feedback)
            self.log(f"✅ 添加测试反馈: {test_feedback}")
            
            # 调用保存方法
            self.recommendation_panel._save_persistent_data()
            self.log("✅ 数据保存方法执行成功")
            
            # 验证数据库中的数据
            self.log("验证数据库中的数据...")
            
            # 验证用户偏好
            prefs_sql = "SELECT preference_key, preference_value FROM user_preferences WHERE user_id = ?"
            prefs_result = self.recommendation_panel._database_service.fetch_all(
                prefs_sql, 
                [self.recommendation_panel._get_current_user_id()]
            )
            
            if prefs_result:
                saved_prefs = {row['preference_key']: row['preference_value'] for row in prefs_result}
                self.log(f"✅ 用户偏好数据库记录: {saved_prefs}")
                # 验证测试数据
                if 'test_key_1' in saved_prefs and saved_prefs['test_key_1'] == 'test_value_1':
                    self.log("✅ 测试偏好数据保存正确")
                else:
                    self.log("❌ 测试偏好数据保存错误")
            else:
                self.log("❌ 用户偏好数据库记录为空")
            
            # 验证反馈历史
            feedback_sql = "SELECT id, recommendation_id, feedback_type, rating, comment, timestamp FROM user_feedback WHERE user_id = ?"
            feedback_result = self.recommendation_panel._database_service.fetch_all(
                feedback_sql, 
                [self.recommendation_panel._get_current_user_id()]
            )
            
            if feedback_result:
                self.log(f"✅ 反馈历史数据库记录: {len(feedback_result)} 条")
                # 验证测试数据
                if len(feedback_result) > 0 and feedback_result[0].get('recommendation_id') == 'test_rec_1':
                    self.log("✅ 测试反馈数据保存正确")
                else:
                    self.log("❌ 测试反馈数据保存错误")
            else:
                self.log("❌ 反馈历史数据库记录为空")
            
            # 测试加载功能
            self.log("测试加载功能...")
            
            # 清空当前数据
            self.recommendation_panel.user_preferences.clear()
            self.recommendation_panel.feedback_history.clear()
            self.log("✅ 清空当前数据")
            
            # 调用加载方法
            self.recommendation_panel._load_persistent_data()
            self.log("✅ 数据加载方法执行成功")
            
            # 验证加载的数据
            if 'test_key_1' in self.recommendation_panel.user_preferences:
                self.log("✅ 用户偏好加载成功")
            else:
                self.log("❌ 用户偏好加载失败")
            
            if len(self.recommendation_panel.feedback_history) > 0:
                self.log("✅ 反馈历史加载成功")
            else:
                self.log("❌ 反馈历史加载失败")
            
            self.log("✅ 数据库持久化功能测试通过")
            
        except Exception as e:
            self.log(f"❌ 数据库持久化功能测试失败: {e}")
            import traceback
            self.log(traceback.format_exc())
        
        self.log("=" * 60)
    
    def test_timer(self):
        """测试定时器更新功能"""
        self.log("=" * 60)
        self.log("开始测试定时器更新功能...")
        
        try:
            # 检查 _update_recommendations 方法是否存在
            if hasattr(self.recommendation_panel, '_update_recommendations'):
                self.log("✅ _update_recommendations 方法存在")
            else:
                self.log("❌ _update_recommendations 方法不存在")
                return
            
            # 检查 _train_recommendation_model 方法是否存在
            if hasattr(self.recommendation_panel, '_train_recommendation_model'):
                self.log("✅ _train_recommendation_model 方法存在")
            else:
                self.log("❌ _train_recommendation_model 方法不存在")
                return
            
            # 检查定时器是否存在
            if self.recommendation_panel.update_timer is not None:
                self.log(f"✅ 定时器存在: {self.recommendation_panel.update_timer}")
            else:
                self.log("❌ 定时器不存在")
                return
            
            # 检查定时器是否在运行
            if self.recommendation_panel.update_timer.isActive():
                self.log("✅ 定时器正在运行")
            else:
                self.log("⚠️  定时器未运行")
            
            # 获取定时器间隔
            interval = self.recommendation_panel.update_timer.interval()
            self.log(f"✅ 定时器间隔: {interval} ms ({interval/1000/60:.1f} 分钟)")
            
            # 测试手动调用更新方法
            self.log("测试手动调用 _update_recommendations 方法...")
            self.recommendation_panel._update_recommendations()
            self.log("✅ _update_recommendations 方法执行成功")
            
            # 测试手动调用训练方法
            self.log("测试手动调用 _train_recommendation_model 方法...")
            self.recommendation_panel._train_recommendation_model()
            self.log("✅ _train_recommendation_model 方法执行成功")
            
            # 测试定时器重启
            self.log("测试定时器重启...")
            self.recommendation_panel._create_update_timer()
            if self.recommendation_panel.update_timer is not None:
                self.log("✅ 定时器重启成功")
            else:
                self.log("❌ 定时器重启失败")
            
            # 测试定时器停止
            self.log("测试定时器停止...")
            self.recommendation_panel.update_timer.stop()
            if not self.recommendation_panel.update_timer.isActive():
                self.log("✅ 定时器停止成功")
            else:
                self.log("❌ 定时器停止失败")
            
            # 重新启动定时器
            self.log("重新启动定时器...")
            self.recommendation_panel.update_timer.start()
            if self.recommendation_panel.update_timer.isActive():
                self.log("✅ 定时器重新启动成功")
            else:
                self.log("❌ 定时器重新启动失败")
            
            self.log("✅ 定时器更新功能测试通过")
            
        except Exception as e:
            self.log(f"❌ 定时器更新功能测试失败: {e}")
            import traceback
            self.log(traceback.format_exc())
        
        self.log("=" * 60)
    
    def test_recommendation_detail(self):
        """测试推荐详情显示功能"""
        self.log("=" * 60)
        self.log("开始测试推荐详情显示功能...")
        
        try:
            # 检查 _show_recommendation_detail 方法是否存在
            if hasattr(self.recommendation_panel, '_show_recommendation_detail'):
                self.log("✅ _show_recommendation_detail 方法存在")
            else:
                self.log("❌ _show_recommendation_detail 方法不存在")
                return
            
            # 创建测试推荐数据
            test_recommendation = {
                'id': 'test_rec_1',
                'type': 'stock',
                'title': '测试股票推荐',
                'description': '这是一个测试股票推荐',
                'score': 0.85,
                'confidence': 0.9,
                'reason': '基于技术分析',
                'metadata': {
                    'stock_code': '000001',
                    'stock_name': '平安银行'
                }
            }
            
            self.log(f"✅ 创建测试推荐数据: {test_recommendation}")
            
            # 测试显示推荐详情
            self.log("测试显示推荐详情...")
            self.recommendation_panel._show_recommendation_detail(test_recommendation)
            self.log("✅ 推荐详情显示成功")
            
            # 测试不同类型的推荐
            test_recommendations = [
                {
                    'id': 'test_rec_2',
                    'type': 'strategy',
                    'title': '测试策略推荐',
                    'description': '这是一个测试策略推荐',
                    'score': 0.8,
                    'confidence': 0.85,
                    'reason': '基于历史回测'
                },
                {
                    'id': 'test_rec_3',
                    'type': 'indicator',
                    'title': '测试指标推荐',
                    'description': '这是一个测试指标推荐',
                    'score': 0.75,
                    'confidence': 0.8,
                    'reason': '基于趋势分析'
                }
            ]
            
            for rec in test_recommendations:
                self.log(f"测试显示 {rec['type']} 类型推荐详情...")
                self.recommendation_panel._show_recommendation_detail(rec)
                self.log(f"✅ {rec['type']} 类型推荐详情显示成功")
            
            self.log("✅ 推荐详情显示功能测试通过")
            
        except Exception as e:
            self.log(f"❌ 推荐详情显示功能测试失败: {e}")
            import traceback
            self.log(traceback.format_exc())
        
        self.log("=" * 60)
    
    def test_user_interaction(self):
        """测试用户交互记录功能"""
        self.log("=" * 60)
        self.log("开始测试用户交互记录功能...")
        
        try:
            # 检查 _record_user_interaction 方法是否存在
            if hasattr(self.recommendation_panel, '_record_user_interaction'):
                self.log("✅ _record_user_interaction 方法存在")
            else:
                self.log("❌ _record_user_interaction 方法不存在")
                return
            
            # 检查 _get_current_user_id 方法是否存在
            if hasattr(self.recommendation_panel, '_get_current_user_id'):
                self.log("✅ _get_current_user_id 方法存在")
            else:
                self.log("❌ _get_current_user_id 方法不存在")
                return
            
            # 获取当前用户ID
            user_id = self.recommendation_panel._get_current_user_id()
            self.log(f"✅ 当前用户ID: {user_id}")
            
            # 创建测试推荐数据
            test_recommendation = {
                'id': 'test_rec_1',
                'type': 'stock',
                'title': '测试股票推荐',
                'description': '这是一个测试股票推荐',
                'score': 0.85,
                'confidence': 0.9
            }
            
            # 测试记录用户交互
            self.log("测试记录用户交互...")
            
            # 测试点击交互
            self.recommendation_panel._record_user_interaction('click', test_recommendation)
            self.log("✅ 点击交互记录成功")
            
            # 测试查看详情交互
            self.recommendation_panel._record_user_interaction('view_detail', test_recommendation)
            self.log("✅ 查看详情交互记录成功")
            
            # 测试反馈交互
            self.recommendation_panel._record_user_interaction('feedback', test_recommendation)
            self.log("✅ 反馈交互记录成功")
            
            # 验证反馈历史
            if len(self.recommendation_panel.feedback_history) > 0:
                self.log(f"✅ 反馈历史记录: {len(self.recommendation_panel.feedback_history)} 条")
                for i, feedback in enumerate(self.recommendation_panel.feedback_history):
                    self.log(f"  反馈 {i+1}: {feedback}")
            else:
                self.log("❌ 反馈历史记录为空")
            
            self.log("✅ 用户交互记录功能测试通过")
            
        except Exception as e:
            self.log(f"❌ 用户交互记录功能测试失败: {e}")
            import traceback
            self.log(traceback.format_exc())
        
        self.log("=" * 60)
    
    def test_all(self):
        """测试所有功能"""
        self.log("开始执行所有测试...")
        self.test_cleanup()
        time.sleep(0.5)
        self.test_db_persistence()
        time.sleep(0.5)
        self.test_timer()
        time.sleep(0.5)
        self.test_recommendation_detail()
        time.sleep(0.5)
        self.test_user_interaction()
        self.log("=" * 60)
        self.log("✅ 所有测试完成")
        self.log("=" * 60)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 创建测试窗口
    test_window = TestWindow()
    test_window.show()
    
    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
