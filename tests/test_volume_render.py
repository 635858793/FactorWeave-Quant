"""测试成交量渲染"""
import sys
sys.path.insert(0, r'D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from core.webgpu.webgpu_renderer import WebGPURenderer, GPURendererConfig, GPUBackend

def test_volume_rendering():
    print("=" * 60)
    print("测试成交量渲染")
    print("=" * 60)

    # 创建测试数据
    n = 50
    kdata = pd.DataFrame({
        'open': np.random.uniform(10, 20, n),
        'high': np.random.uniform(15, 25, n),
        'low': np.random.uniform(5, 15, n),
        'close': np.random.uniform(10, 20, n),
        'volume': np.random.uniform(1000, 10000, n) * 1000
    })

    # 创建渲染器
    config = GPURendererConfig()
    renderer = WebGPURenderer(config)

    # 初始化
    success = renderer.initialize()
    print(f"渲染器初始化: {success}")

    # 创建图表
    fig, (price_ax, volume_ax) = plt.subplots(2, 1, figsize=(12, 8))

    # 先清空
    price_ax.cla()
    volume_ax.cla()

    print(f"\n渲染前 volume_ax limits:")
    print(f"  xlim: {volume_ax.get_xlim()}")
    print(f"  ylim: {volume_ax.get_ylim()}")

    # 渲染K线
    print(f"\n渲染K线到 price_ax...")
    style = {}
    result1 = renderer.render_candlesticks(price_ax, kdata, style)
    print(f"K线渲染结果: {result1}")

    print(f"\n渲染后 price_ax limits:")
    print(f"  xlim: {price_ax.get_xlim()}")
    print(f"  ylim: {price_ax.get_ylim()}")
    print(f"  price_ax artists 数量: {len(price_ax.artists)}")

    # 清空 volume_ax 再次测试
    volume_ax.cla()
    print(f"\n再次清空 volume_ax 后:")
    print(f"  xlim: {volume_ax.get_xlim()}")
    print(f"  ylim: {volume_ax.get_ylim()}")

    # 渲染成交量
    print(f"\n渲染成交量到 volume_ax...")
    result2 = renderer.render_volume(volume_ax, kdata, style)
    print(f"成交量渲染结果: {result2}")

    print(f"\n渲染后 volume_ax limits:")
    print(f"  xlim: {volume_ax.get_xlim()}")
    print(f"  ylim: {volume_ax.get_ylim()}")

    # 检查 volume_ax 上有多少 artists
    print(f"\nvolume_ax artists 数量: {len(volume_ax.artists)}")
    for i, artist in enumerate(volume_ax.artists):
        print(f"  {i}: {type(artist).__name__}")
        if hasattr(artist, 'get_array'):
            print(f"      array: {artist.get_array()}")
        if hasattr(artist, 'get_offsets'):
            print(f"      offsets: {artist.get_offsets()}")

    # 调用 autoscale_view
    volume_ax.autoscale_view()
    print(f"\nautoscale_view 后 volume_ax limits:")
    print(f"  xlim: {volume_ax.get_xlim()}")
    print(f"  ylim: {volume_ax.get_ylim()}")

    # 保存图片
    fig.savefig(r'D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\test_volume_output.png', dpi=100)
    print(f"\n图片已保存到 test_volume_output.png")

    plt.close(fig)

if __name__ == '__main__':
    test_volume_rendering()