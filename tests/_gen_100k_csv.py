import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

np.random.seed(42)
n = 100000
base_date = datetime(2020, 1, 2)
dates = [base_date + timedelta(days=i) for i in range(n)]

data = {
    'date': [d.strftime('%Y-%m-%d') for d in dates],
    'symbol': [f'TEST{np.random.randint(1, 100):03d}' for _ in range(n)],
    'open': np.round(np.random.uniform(10, 500, n), 2),
    'high': np.round(np.random.uniform(10, 500, n), 2),
    'low': np.round(np.random.uniform(10, 500, n), 2),
    'close': np.round(np.random.uniform(10, 500, n), 2),
    'volume': np.random.randint(1000, 100000000, n),
    'amount': np.round(np.random.uniform(1e6, 1e10, n), 2),
    'turnover': np.round(np.random.uniform(0.1, 10, n), 4),
    'pe_ratio': np.round(np.random.uniform(5, 100, n), 2),
}
df = pd.DataFrame(data)

for i in range(n):
    if df.loc[i, 'high'] < df.loc[i, 'low']:
        df.loc[i, 'high'], df.loc[i, 'low'] = df.loc[i, 'low'], df.loc[i, 'high']
    if df.loc[i, 'open'] < df.loc[i, 'low']:
        df.loc[i, 'open'] = df.loc[i, 'low']
    if df.loc[i, 'high'] < df.loc[i, 'open']:
        df.loc[i, 'high'] = df.loc[i, 'open']
    if df.loc[i, 'low'] > df.loc[i, 'close']:
        df.loc[i, 'close'], df.loc[i, 'low'] = df.loc[i, 'low'], df.loc[i, 'close']

path = os.path.join(os.path.dirname(__file__), '_stress_100k.csv')
df.to_csv(path, index=False)
mb = os.path.getsize(path) / 1024 / 1024
print(f'Generated: {path}')
print(f'Rows: {len(df)}, Cols: {len(df.columns)}, Size: {mb:.1f} MB')
print(df.head(3))
print(df.tail(3))