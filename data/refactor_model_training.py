import re

file_path = r"D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\model_training_service.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

if 'from ..database.unified_sqlite_access import' not in content and 'get_unified_db_connection' not in content:
    insert_pos = content.find('from .base_service import BaseService')
    if insert_pos > 0:
        new_import = 'from ..database.unified_sqlite_access import UnifiedSQLiteAccess\n'
        content = content[:insert_pos] + new_import + content[insert_pos:]
        print("Added import")

content = content.replace(
    'conn = sqlite3.connect(str(db_path))',
    'conn = UnifiedSQLiteAccess.get_instance(str(db_path)).get_connection().__enter__()'
)

content = content.replace(
    'conn.close()',
    'conn.close()  # UnifiedSQLiteAccess handles WAL mode'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Refactoring completed")
