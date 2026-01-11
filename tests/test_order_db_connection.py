"""
简单测试订单数据库连接（忽略QTimer错误）
"""

import sys
from pathlib import Path
import warnings

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 忽略QObject警告
warnings.filterwarnings("ignore", category=RuntimeWarning)

from core.services.database_service import DatabaseService

def main():
    """主函数"""
    print("测试订单数据库连接...")
    
    try:
        # 初始化数据库服务
        db_service = DatabaseService.get_instance()
        
        # 检查订单数据库连接池是否创建
        print("\n检查订单数据库连接池...")
        order_pools = [pool_name for pool_name in db_service._connection_pools.keys() if "_orders" in pool_name]
        
        if order_pools:
            print(f"找到 {len(order_pools)} 个订单数据库连接池:")
            for pool_name in order_pools:
                print(f"  - {pool_name}: OK")
        else:
            print("未找到订单数据库连接池")
        
        print("\n测试完成！")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
