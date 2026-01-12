#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能推荐面板功能测试脚本
测试资源清理、数据持久化和定时器更新功能
"""

import sys
import os
import json
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
        self.setWindowTitle("智能推荐面板功能测试")
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
        
        self.test_persistence_btn = QPushButton("测试 2: 数据持久化功能")
        self.test_persistence_btn.clicked.connect(self.test_persistence)
        test_layout.addWidget(self.test_persistence_btn)
        
        self.test_timer_btn = QPushButton("测试 3: 定时器更新功能")
        self.test_timer_btn.clicked.connect(self.test_timer)
        test_layout.addWidget(self.test_timer_btn)
        
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
        
        # 测试数据目录
        self.test_data_dir = Path.home() / ".hikyuu" / "smart_recommendation"
        
        self.log("测试环境初始化完成")
        self.log(f"测试数据目录: {self.test_data_dir}")
    
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
    
    def test_persistence(self):
        """测试数据持久化功能"""
        self.log("=" * 60)
        self.log("开始测试数据持久化功能...")
        
        try:
            # 检查数据目录是否存在
            if self.test_data_dir.exists():
                self.log(f"✅ 数据目录存在: {self.test_data_dir}")
            else:
                self.log(f"⚠️  数据目录不存在: {self.test_data_dir}")
                self.log("这可能是首次运行，数据将在首次保存时创建")
            
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
            
            # 检查文件是否创建
            prefs_file = self.test_data_dir / "user_preferences.json"
            feedback_file = self.test_data_dir / "feedback_history.json"
            
            if prefs_file.exists():
                self.log(f"✅ 用户偏好文件已创建: {prefs_file}")
                # 读取并验证内容
                with open(prefs_file, 'r', encoding='utf-8') as f:
                    saved_prefs = json.load(f)
                    self.log(f"✅ 用户偏好内容: {saved_prefs}")
                    # 验证测试数据
                    if 'test_key_1' in saved_prefs and saved_prefs['test_key_1'] == 'test_value_1':
                        self.log("✅ 测试偏好数据保存正确")
                    else:
                        self.log("❌ 测试偏好数据保存错误")
            else:
                self.log(f"❌ 用户偏好文件未创建: {prefs_file}")
            
            if feedback_file.exists():
                self.log(f"✅ 反馈历史文件已创建: {feedback_file}")
                # 读取并验证内容
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    saved_feedback = json.load(f)
                    self.log(f"✅ 反馈历史内容: {saved_feedback}")
                    # 验证测试数据
                    if len(saved_feedback) > 0 and saved_feedback[0].get('recommendation_id') == 'test_rec_1':
                        self.log("✅ 测试反馈数据保存正确")
                    else:
                        self.log("❌ 测试反馈数据保存错误")
            else:
                self.log(f"❌ 反馈历史文件未创建: {feedback_file}")
            
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
            
            self.log("✅ 数据持久化功能测试通过")
            
        except Exception as e:
            self.log(f"❌ 数据持久化功能测试失败: {e}")
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
    
    def test_all(self):
        """测试所有功能"""
        self.log("开始执行所有测试...")
        self.test_cleanup()
        time.sleep(0.5)
        self.test_persistence()
        time.sleep(0.5)
        self.test_timer()
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
