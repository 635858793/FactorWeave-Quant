"""
简单测试matplotlib是否可用
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_matplotlib_basic():
    """测试matplotlib基本功能"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        print("✅ matplotlib导入成功")

        fig, ax = plt.subplots(figsize=(10, 6))
        categories = ['A', 'B', 'C', 'D']
        values = [10, 20, 30, 40]
        colors = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12']

        bars = ax.bar(categories, values, color=colors)
        ax.set_title('测试图表', fontsize=14, fontweight='bold')
        ax.set_ylabel('数值', fontsize=12)

        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=10)

        charts_dir = 'charts'
        if not os.path.exists(charts_dir):
            os.makedirs(charts_dir)

        file_path = os.path.join(charts_dir, "test_chart.png")
        plt.savefig(file_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"✅ 测试图表生成成功: {file_path}")
        print(f"✅ 文件存在: {os.path.exists(file_path)}")

        assert os.path.exists(file_path), "图表文件未生成"

        file_size = os.path.getsize(file_path)
        print(f"✅ 文件大小: {file_size} bytes")

        assert file_size > 0, "图表文件大小为0"

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise