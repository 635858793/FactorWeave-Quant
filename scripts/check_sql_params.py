#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查SQL占位符和参数数量
"""

import sqlite3
import os
from datetime import datetime

# 数据库路径
db_path = os.path.join(os.getcwd(), 'data', 'hikyuu.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表结构
cursor.execute("PRAGMA table_info(accounts)")
columns = cursor.fetchall()
print(f"账户表列数: {len(columns)}")

# 检查SQL语句
insert_sql = """
INSERT INTO accounts (
    account_id, account_name, account_type, status,
    balance, available_balance, frozen_balance, market_value, total_assets,
    profit_loss, profit_loss_ratio, create_time, update_time,
    user_id, trading_day, risk_level, margin_ratio, maintenance_margin, metadata,
    ctp_broker_id, ctp_investor_id, ctp_password, ctp_trade_front, ctp_quote_front,
    ctp_app_id, ctp_auth_code, ctp_product_info,
    xtp_account_id, xtp_password, xtp_server_address
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

placeholder_count = insert_sql.count('?')
print(f"SQL占位符数量: {placeholder_count}")

# 检查参数数量
account_id = "TEST_ACCOUNT_001"
account_name = "测试账户"
account_type = "期货账户"
status = "active"
balance = 100000.0
available_balance = 100000.0
frozen_balance = 0.0
market_value = 0.0
total_assets = 100000.0
profit_loss = 0.0
profit_loss_ratio = 0.0
create_time = datetime.now().isoformat()
update_time = datetime.now().isoformat()

ctp_broker_id = "9999"
ctp_investor_id = "test_investor"
ctp_password = "test_password"
ctp_trade_front = "tcp://180.168.146.187:10130"
ctp_quote_front = "tcp://180.168.146.187:10131"
ctp_app_id = "simnow_client_test"
ctp_auth_code = "0000000000000000"
ctp_product_info = "simnow_client_test"

params = (
    account_id, account_name, account_type, status,
    balance, available_balance, frozen_balance, market_value, total_assets,
    profit_loss, profit_loss_ratio, create_time, update_time,
    'system', '', 'normal', 0.0, 0.0, '{}',
    ctp_broker_id, ctp_investor_id, ctp_password, ctp_trade_front, ctp_quote_front,
    ctp_app_id, ctp_auth_code, ctp_product_info,
    '', '', ''
)

print(f"参数数量: {len(params)}")

# 检查是否匹配
if placeholder_count == len(params):
    print("占位符和参数数量匹配")
else:
    print(f"❌ 占位符和参数数量不匹配: {placeholder_count} vs {len(params)}")

conn.close()
