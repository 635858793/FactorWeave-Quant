import json
import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox, QSlider, QPushButton, QListWidget, QListWidgetItem, QLineEdit, QMessageBox, QFormLayout, QGroupBox, QDialogButtonBox, QFileDialog, QInputDialog, QGridLayout, QListView
from PyQt5.QtCore import Qt

from .base_dialog import BaseDialog

SETTINGS_FILE = os.path.join(os.path.dirname(
    __file__), '../../config/interval_stat_settings.json')

DEFAULT_SETTINGS = {
    'strong_bull': 15,
    'strong_bear': -15,
    'extreme_volatility': 9,
    'max_drawdown': -15,
    'periods': [5, 20, 60, 120],
    'score_weights': {
        'ret': 0.3,
        'up_ratio': 0.15,
        'mdd': 0.15,
        'vol': 0.15,
        'turnover': 0.1,
        'volatility_vol': 0.05,
        'skew': 0.05,
        'sharpe': 0.05
    },
    'font_size': 13
}

FACTOR_LABELS = {
    'ret': '涨跌幅',
    'up_ratio': '阳线比例',
    'mdd': '最大回撤',
    'vol': '波动率',
    'turnover': '换手率',
    'volatility_vol': '成交量波动',
    'skew': '收益率偏度',
    'sharpe': '夏普比率'
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

class IntervalStatSettingsDialog(BaseDialog):
    def __init__(self, parent=None):
        self.settings = load_settings()
        super().__init__(
            parent,
            title="区间统计设置",
            min_size=(500, 500),
            settings_key="IntervalStatSettingsDialog"
        )
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # 字体大小调节控件
        font_size = self.settings.get('font_size', 13)
        font_hbox = QHBoxLayout()
        font_hbox.addWidget(QLabel("字体大小:"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 24)
        self.font_spin.setValue(font_size)
        self.font_spin.valueChanged.connect(self.on_font_size_changed)
        font_hbox.addWidget(self.font_spin)
        font_hbox.addStretch()
        layout.addLayout(font_hbox)
        # 阈值设置
        threshold_group = QGroupBox("建议阈值设置")
        threshold_grid = QGridLayout(threshold_group)
        self.bull_spin = QDoubleSpinBox()
        self.bull_spin.setRange(1, 50)
        self.bull_spin.setValue(self.settings['strong_bull'])
        self.bear_spin = QDoubleSpinBox()
        self.bear_spin.setRange(-50, -1)
        self.bear_spin.setValue(self.settings['strong_bear'])
        self.vol_spin = QDoubleSpinBox()
        self.vol_spin.setRange(1, 30)
        self.vol_spin.setValue(self.settings['extreme_volatility'])
        self.mdd_spin = QDoubleSpinBox()
        self.mdd_spin.setRange(-50, -1)
        self.mdd_spin.setValue(self.settings['max_drawdown'])
        threshold_grid.addWidget(QLabel("强多头阈值(%)"), 0, 0)
        threshold_grid.addWidget(self.bull_spin, 0, 1)
        threshold_grid.addWidget(QLabel("强空头阈值(%)"), 0, 2)
        threshold_grid.addWidget(self.bear_spin, 0, 3)
        threshold_grid.addWidget(QLabel("极端波动阈值(%)"), 1, 0)
        threshold_grid.addWidget(self.vol_spin, 1, 1)
        threshold_grid.addWidget(QLabel("最大回撤阈值(%)"), 1, 2)
        threshold_grid.addWidget(self.mdd_spin, 1, 3)
        layout.addWidget(threshold_group)
        # 周期设置
        period_group = QGroupBox("分析周期设置")
        period_grid = QGridLayout(period_group)
        self.period_list = QListWidget()
        self.period_list.setViewMode(QListView.IconMode)
        self.period_list.setFlow(QListView.LeftToRight)
        self.period_list.setWrapping(True)
        self.period_list.setSpacing(8)
        self.period_list.setResizeMode(QListWidget.Adjust)
        self.period_list.setMinimumHeight(36)
        self.period_list.setMaximumHeight(120)
        [self.period_list.addItem(str(p)) for p in self.settings['periods']]
        period_grid.addWidget(self.period_list, 0, 0, 1, 3)
        self.period_input = QLineEdit()
        self.period_input.setPlaceholderText("输入周期(天)")
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_period)
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self.del_period)
        add_btn.setFixedHeight(20)
        del_btn.setFixedHeight(20)
        period_grid.addWidget(self.period_input, 1, 0)
        period_grid.addWidget(add_btn, 1, 1)
        period_grid.addWidget(del_btn, 1, 2)
        layout.addWidget(period_group)
        # 评分因子权重
        weight_group = QGroupBox("评分因子与权重设置")
        weight_grid = QGridLayout(weight_group)
        self.factor_list = QListWidget()
        self.factor_list.setViewMode(QListView.IconMode)
        self.factor_list.setFlow(QListView.LeftToRight)
        self.factor_list.setWrapping(True)
        self.factor_list.setSpacing(8)
        self.factor_list.setResizeMode(QListWidget.Adjust)
        self.factor_list.setMinimumHeight(36)
        self.factor_list.setMaximumHeight(120)
        self.factor_list.setSelectionMode(QListWidget.SingleSelection)
        for k, label in FACTOR_LABELS.items():
            item = QListWidgetItem(f"{label} ({k})")
            item.setData(Qt.UserRole, k)
            self.factor_list.addItem(item)
        # 按钮区放入可用因子框内
        factor_btn_hbox = QHBoxLayout()
        add_factor_btn = QPushButton("添加因子")
        add_factor_btn.clicked.connect(self.add_factor)
        del_factor_btn = QPushButton("删除选中因子")
        del_factor_btn.clicked.connect(self.del_factor)
        add_factor_btn.setFixedHeight(20)
        del_factor_btn.setFixedHeight(20)
        factor_btn_hbox.addWidget(add_factor_btn)
        factor_btn_hbox.addWidget(del_factor_btn)
        factor_btn_hbox.addStretch()
        factor_box = QVBoxLayout()
        factor_box.addWidget(self.factor_list)
        factor_box.addLayout(factor_btn_hbox)
        weight_grid.addWidget(QLabel("可用因子："), 0, 0)
        weight_grid.addLayout(factor_box, 0, 1, 1, 3)
        self.weight_sliders = {}
        # 因子分组
        factor_groups = [
            ("趋势类", ["ret", "up_ratio"]),
            ("波动类", ["vol", "volatility_vol", "mdd"]),
            ("收益类", ["skew", "sharpe"]),
            ("成交类", ["turnover"])
        ]
        row = 1
        for group_name, keys in factor_groups:
            group_label = QLabel(f"<b>{group_name}</b>")
            group_label.setStyleSheet(
                f"color:#1976d2;font-size:{font_size+1}px;margin-top:8px;")
            weight_grid.addWidget(group_label, row, 0, 1, 4)
            row += 1
            col = 0
            for k in keys:
                if k not in FACTOR_LABELS:
                    continue
                label = FACTOR_LABELS[k]
                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, 100)
                v = int(self.settings['score_weights'].get(k, 0)*100)
                slider.setValue(v)
                slider.valueChanged.connect(self.update_weight_sum)
                self.weight_sliders[k] = slider
                weight_grid.addWidget(QLabel(f"{label}权重"), row, col*2)
                weight_grid.addWidget(slider, row, col*2+1)
                if col == 1:
                    row += 1
                    col = 0
                else:
                    col += 1
            if col != 0:
                row += 1  # 补齐行
        self.weight_sum_label = QLabel()
        weight_grid.addWidget(QLabel("权重总和(应为100)"), row+2, 0)
        weight_grid.addWidget(self.weight_sum_label, row+2, 1)
        self.update_weight_sum()
        layout.addWidget(weight_group)
        # 导入导出按钮
        import_btn = QPushButton("导入规则")
        import_btn.clicked.connect(self.import_settings)
        export_btn = QPushButton("导出规则")
        export_btn.clicked.connect(self.export_settings)
        import_btn.setFixedHeight(20)
        export_btn.setFixedHeight(20)
        import_export_hbox = QHBoxLayout()
        import_export_hbox.addWidget(import_btn)
        import_export_hbox.addWidget(export_btn)
        import_export_hbox.addStretch()
        layout.addLayout(import_export_hbox)
        # 按钮区
        btns = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.RestoreDefaults | QDialogButtonBox.Cancel)
        for btn in btns.buttons():
            btn.setFixedHeight(15)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.RestoreDefaults).clicked.connect(
            self.restore_defaults)
        layout.addWidget(btns)

    def add_period(self):
        try:
            val = int(self.period_input.text())
            if val > 0 and str(val) not in [self.period_list.item(i).text() for i in range(self.period_list.count())]:
                self.period_list.addItem(str(val))
                self.period_input.clear()
        except Exception:
            QMessageBox.warning(self, "输入错误", "请输入正整数周期")

    def del_period(self):
        for item in self.period_list.selectedItems():
            self.period_list.takeItem(self.period_list.row(item))

    def update_weight_sum(self):
        total = sum(slider.value() for slider in self.weight_sliders.values())
        self.weight_sum_label.setText(str(total))
        if total != 100:
            self.weight_sum_label.setStyleSheet("color:red;")
        else:
            self.weight_sum_label.setStyleSheet("color:green;")

    def add_factor(self):
        text, ok = QInputDialog.getText(self, "添加因子", "请输入因子英文名(如myfactor):")
        if ok and text and text not in self.weight_sliders:
            label, ok2 = QInputDialog.getText(self, "因子名称", "请输入因子中文名:")
            if ok2 and label:
                FACTOR_LABELS[text] = label
                item = QListWidgetItem(f"{label} ({text})")
                item.setData(Qt.UserRole, text)
                self.factor_list.addItem(item)
                slider = QSlider(Qt.Horizontal)
                slider.setRange(20, 100)
                slider.setValue(0)
                slider.valueChanged.connect(self.update_weight_sum)
                self.weight_sliders[text] = slider
                # 动态添加到UI
                group = self.findChild(QGroupBox, "评分因子与权重设置")
                if group:
                    group.layout().addRow(f"{label}权重", slider)
                self.update_weight_sum()

    def del_factor(self):
        items = self.factor_list.selectedItems()
        for item in items:
            k = item.data(Qt.UserRole)
            if k in self.weight_sliders:
                slider = self.weight_sliders.pop(k)
                slider.deleteLater()
            FACTOR_LABELS.pop(k, None)
            self.factor_list.takeItem(self.factor_list.row(item))
            self.update_weight_sum()

    def import_settings(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入规则", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    s = json.load(f)
                self.settings = s
                # 重建UI
                self.close()
                dlg = IntervalStatSettingsDialog(self.parent())
                dlg.exec_()
            except Exception as e:
                QMessageBox.warning(self, "导入失败", str(e))

    def export_settings(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出规则", "interval_stat_settings.json", "JSON Files (*.json)")
        if file_path:
            try:
                save_settings(self.settings)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "导出成功", f"规则已导出到: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", str(e))

    def save(self):
        if sum(slider.value() for slider in self.weight_sliders.values()) != 100:
            QMessageBox.warning(self, "权重错误", "权重总和必须为100")
            return
        self.settings['strong_bull'] = self.bull_spin.value()
        self.settings['strong_bear'] = self.bear_spin.value()
        self.settings['extreme_volatility'] = self.vol_spin.value()
        self.settings['max_drawdown'] = self.mdd_spin.value()
        self.settings['periods'] = [int(self.period_list.item(
            i).text()) for i in range(self.period_list.count())]
        self.settings['score_weights'] = {
            k: self.weight_sliders[k].value()/100 for k in self.weight_sliders}
        save_settings(self.settings)
        self.accept()

    def restore_defaults(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.close()
        dlg = IntervalStatSettingsDialog(self.parent())
        dlg.exec_()

    def on_font_size_changed(self, value):
        self.settings['font_size'] = value
        save_settings(self.settings)
