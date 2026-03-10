import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_wave_analysis():
    print("=" * 60)
    print("波浪分析功能测试")
    print("=" * 60)

    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication([])
        print("[OK] PyQt5 导入成功")
    except Exception as e:
        print(f"[SKIP] 无法创建QApplication: {e}")
        app = None

    try:
        from gui.widgets.analysis_tabs.wave_tab_pro import WaveAnalysisTabPro
        print("[OK] WaveAnalysisTabPro 导入成功")
    except Exception as e:
        print(f"[FAIL] WaveAnalysisTabPro 导入失败: {e}")
        return False

    if app:
        try:
            wave_tab = WaveAnalysisTabPro()
            print("[OK] WaveAnalysisTabPro 实例化成功")

            kdata = create_sample_kdata(200)
            wave_tab.set_kdata(kdata)
            print("[OK] K线数据设置成功")

            waves = wave_tab._detect_elliott_waves()
            print(f"[OK] 艾略特波浪检测完成，发现 {len(waves)} 个波浪")

            if waves:
                print("\n波浪详情:")
                for i, wave in enumerate(waves[:5]):
                    print(f"  波浪{i+1}: {wave.get('wave')} - {wave.get('type')} - 置信度: {wave.get('confidence', 0):.2f} - 状态: {wave.get('status')}")
                
                confidence_values = [w.get('confidence', 0) for w in waves]
                if all(0.5 <= c <= 0.95 for c in confidence_values):
                    print("[OK] 置信度在有效范围内 (0.5-0.95)")
                else:
                    print("[FAIL] 置信度超出有效范围")
                    return False

            gann_levels = wave_tab._calculate_gann_levels()
            print(f"[OK] 江恩分析完成，发现 {len(gann_levels)} 个水平位")

            fib_levels = wave_tab._calculate_fibonacci_levels()
            print(f"[OK] 斐波那契分析完成，发现 {len(fib_levels)} 个水平位")

            print("\n" + "=" * 60)
            print("所有测试通过!")
            print("=" * 60)
            return True

        except Exception as e:
            import traceback
            print(f"[FAIL] 测试执行失败: {e}")
            traceback.print_exc()
            return False
    else:
        print("[INFO] 无GUI环境，跳过实例化测试")
        
        from gui.widgets.analysis_tabs.wave_tab_pro import WaveAnalysisTabPro
        
        kdata = create_sample_kdata(200)
        
        class MockWaveTab:
            def __init__(self):
                self.elliott_config = WaveAnalysisTabPro().elliott_config
                self.gann_config = WaveAnalysisTabPro().gann_config
                self.algorithm_config = WaveAnalysisTabPro().algorithm_config
                self.current_kdata = kdata
                self.confidence_spin = type('obj', (object,), {'value': lambda self: 0.7})()
                self.min_wave_spin = type('obj', (object,), {'value': lambda self: 5.0})()
                self.precision_slider = type('obj', (object,), {'value': lambda self: 5})()
                self.fractal_analysis_cb = type('obj', (object,), {'isChecked': lambda self: True})()
                self.multi_timeframe_cb = type('obj', (object,), {'isChecked': lambda self: True})()
                
                self._detect_elliott_waves = WaveAnalysisTabPro._detect_elliott_waves
                self._calculate_gann_levels = WaveAnalysisTabPro._calculate_gann_levels
                self._calculate_fibonacci_levels = WaveAnalysisTabPro._calculate_fibonacci_levels
                
        mock_tab = MockWaveTab()
        
        waves = mock_tab._detect_elliott_waves(mock_tab)
        print(f"[OK] 艾略特波浪检测完成，发现 {len(waves)} 个波浪")
        
        if waves:
            confidence_values = [w.get('confidence', 0) for w in waves]
            if all(0.5 <= c <= 0.95 for c in confidence_values):
                print("[OK] 置信度在有效范围内 (0.5-0.95)")
            else:
                print("[FAIL] 置信度超出有效范围")
                return False
                
        gann_levels = mock_tab._calculate_gann_levels(mock_tab)
        print(f"[OK] 江恩分析完成，发现 {len(gann_levels)} 个水平位")
        
        fib_levels = mock_tab._calculate_fibonacci_levels(mock_tab)
        print(f"[OK] 斐波那契分析完成，发现 {len(fib_levels)} 个水平位")
        
        print("\n" + "=" * 60)
        print("所有测试通过!")
        print("=" * 60)
        return True

def create_sample_kdata(n=200):
    """创建模拟K线数据"""
    np.random.seed(42)
    
    base_price = 100.0
    dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
    
    prices = [base_price]
    for i in range(n - 1):
        change = np.random.normal(0, 2)
        prices.append(prices[-1] * (1 + change / 100))
    
    prices = np.array(prices)
    
    kdata = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, n)),
        'high': prices * (1 + np.random.uniform(0.005, 0.02, n)),
        'low': prices * (1 - np.random.uniform(0.005, 0.02, n)),
        'close': prices,
        'volume': np.random.uniform(1000000, 10000000, n)
    }, index=dates)
    
    return kdata

if __name__ == '__main__':
    success = test_wave_analysis()
    sys.exit(0 if success else 1)
