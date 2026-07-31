import duckdb
import os
import tempfile

tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "test.duckdb")

with duckdb.connect(db) as conn:
    # 试 1: BIGSERIAL PRIMARY KEY
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_metrics (
                id BIGSERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                source VARCHAR NOT NULL DEFAULT 'health_adapter',
                plugin_id VARCHAR NOT NULL,
                overall_score DOUBLE
            )
        """)
        print("Test 1 CREATE TABLE (BIGSERIAL) OK")
    except Exception as e:
        print(f"Test 1 FAIL: {e}")

    # 试 2: JSON 类型
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_json (
                id INTEGER PRIMARY KEY,
                data JSON
            )
        """)
        print("Test 2 CREATE TABLE (JSON) OK")
    except Exception as e:
        print(f"Test 2 FAIL: {e}")

    # 试 3: INSERT JSON
    try:
        conn.execute("INSERT INTO test_json VALUES (1, '{\"pm\": 1.0}')")
        print("Test 3 INSERT JSON OK")
    except Exception as e:
        print(f"Test 3 FAIL: {e}")

    # 试 4: SELECT
    res = conn.execute("SELECT * FROM test_json").fetchall()
    print(f"Test 4 SELECT: {res}")

    # 试 5: TIMESTAMP DESC 索引
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON test_metrics(timestamp DESC, plugin_id)")
        print("Test 5 CREATE INDEX DESC OK")
    except Exception as e:
        print(f"Test 5 FAIL: {e}")
