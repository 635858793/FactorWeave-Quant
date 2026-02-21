# 分布式计算节点

## 简介

这是FactorWeave-Quant系统的分布式计算节点实现，支持：

- 独立运行的计算节点
- 自动任务分发和负载均衡
- 💪 真实的数据导入和分析任务
- 实时健康监控
- 🛡️ API密钥认证
- 容错和自动恢复

## 快速开始

### 1. 安装依赖

```bash
pip install -r distributed_node/requirements.txt
```

### 2. 启动节点

**方式一：交互式启动**
```bash
python distributed_node/start_node.py
```

**方式二：命令行启动**
```bash
python distributed_node/node_server.py --port 8900 --node-name "Worker-1"
```

**方式三：使用配置文件**
```bash
python distributed_node/node_server.py --config distributed_node/node_config.json
```

### 3. 验证节点

访问健康检查接口：
```bash
curl http://localhost:8900/api/v1/health
```

## 配置说明

配置文件 `node_config.json`:

```json
{
  "node_id": "node_001",
  "node_name": "Worker Node 1",
  "host": "0.0.0.0",
  "port": 8900,
  "api_key": null,
  "master_host": "localhost",
  "master_port": 8888,
  "auto_register": true,
  "max_workers": 4,
  "task_timeout": 300,
  "heartbeat_interval": 10,
  "max_memory_mb": 4096,
  "max_cpu_percent": 80.0,
  "log_level": "INFO",
  "log_file": "logs/node.log",
  "data_dir": "data/node_data",
  "cache_dir": "cache/node_cache"
}
```

### 环境变量

也可以通过环境变量配置：

```bash
export NODE_PORT=8900
export NODE_NAME="Worker Node 1"
export MAX_WORKERS=8
export NODE_API_KEY="your-secret-key"
```

## API接口

### 健康检查
```
GET /api/v1/health
```

### 执行任务
```
POST /api/v1/task/execute
Content-Type: application/json

{
  "task_id": "task_123",
  "task_type": "data_import",
  "task_data": {
    "symbols": ["000001.SZ"],
    "data_source": "tongdaxin"
  },
  "priority": 5,
  "timeout": 300
}
```

### 查询任务状态
```
GET /api/v1/task/{task_id}/status
```

### 获取统计信息
```
GET /api/v1/node/stats
```

## 任务类型

支持的任务类型：

- `data_import`: 数据导入
- `analysis`: 技术分析
- `backtest`: 策略回测
- `optimization`: 参数优化
- `custom`: 自定义任务

## 架构说明

```
distributed_node/
├── node_server.py      # 服务器主程序
├── node_config.py      # 配置管理
├── task_executor.py    # 任务执行器
├── api/
│   ├── routes.py       # API路由
│   └── models.py       # 数据模型
├── ui/
│   ├── node_dashboard.py    # 监控UI
│   └── node_config_ui.py    # 配置UI
└── start_node.py       # 启动脚本
```

## 性能优化

- 异步IO处理避免阻塞
- 任务队列管理并发
- 资源监控防止过载
- 连接池复用HTTP连接

## 安全建议

1. 生产环境启用API密钥
2. 使用HTTPS加密传输
3. 限制允许的IP地址
4. 定期更新依赖包

## 故障排除

### 端口被占用
```bash
# 更改端口
python distributed_node/node_server.py --port 8901
```

### 内存不足
```bash
# 减少最大工作线程
python distributed_node/node_server.py --max-workers 2
```

### 日志查看
```bash
tail -f logs/node.log
```

## 许可证

MIT License

