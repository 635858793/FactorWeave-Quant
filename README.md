# Hikyuu UI Web Interface

基于FastAPI + Vue.js 3 + DuckDB的现代化交易系统Web界面。

## 项目特性

- 🚀 **高性能**: 使用FastAPI和DuckDB实现高性能数据处理
- 🔐 **安全可靠**: JWT认证 + 双因素认证 + RBAC权限控制
- 📊 **数据可视化**: 集成Plotly交互式图表
- 📱 **响应式设计**: 基于Element Plus的现代化UI
- 🐳 **容器化部署**: Docker Compose一键部署
- 🔒 **全面安全**: SQL注入、XSS、CSRF等多重防护

## 技术栈

### 后端
- **Web框架**: FastAPI 0.104.0
- **数据库**: DuckDB 0.9.2, PostgreSQL 15, Redis 7
- **认证**: JWT, 双因素认证(2FA)
- **数据可视化**: Matplotlib, Plotly
- **文档生成**: ReportLab

### 前端
- **框架**: Vue.js 3.3.0
- **路由**: Vue Router 4.2.0
- **状态管理**: Pinia 2.1.0
- **UI组件**: Element Plus 2.3.0
- **图表**: Plotly.js 2.24.0
- **构建工具**: Vite 4.3.0

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Docker 20.10+ (可选)
- Docker Compose 2.0+ (可选)

### 本地开发

#### 1. 克隆项目

```bash
git clone https://github.com/yourusername/hikyuu-ui.git
cd hikyuu-ui
```

#### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑.env文件，设置相关配置
```

#### 3. 后端开发

```bash
# 创建虚拟环境
conda create -n hikyuu python=3.11
conda activate hikyuu

# 安装依赖
pip install -r requirements.txt

# 启动后端服务
python -m web.backend.main
```

后端服务将在 http://localhost:8000 启动

API文档: http://localhost:8000/docs

#### 4. 前端开发

```bash
# 进入前端目录
cd web/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 http://localhost:3000 启动

### Docker部署

#### 1. 构建镜像

```bash
docker-compose build
```

#### 2. 启动服务

```bash
docker-compose up -d
```

#### 3. 查看日志

```bash
docker-compose logs -f
```

#### 4. 停止服务

```bash
docker-compose down
```

## 项目结构

```
hikyuu-ui/
├── web/                      # Web应用
│   ├── backend/              # 后端代码
│   │   ├── api/            # API路由
│   │   ├── config/         # 配置文件
│   │   ├── middleware/     # 中间件
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # Pydantic模式
│   │   ├── services/       # 业务逻辑
│   │   └── security/       # 安全工具
│   └── frontend/           # 前端代码
│       └── src/
│           ├── api/        # API调用
│           ├── assets/     # 静态资源
│           ├── components/ # 组件
│           ├── layouts/    # 布局
│           ├── router/     # 路由
│           ├── stores/     # 状态管理
│           ├── utils/      # 工具函数
│           └── views/      # 页面
├── nginx/                  # Nginx配置
├── data/                   # 数据目录
├── docker-compose.yml       # Docker Compose配置
├── requirements.txt         # Python依赖
└── README.md             # 项目文档
```

## 核心功能

### 1. 认证授权
- 用户注册/登录
- JWT Token认证
- 双因素认证(2FA)
- 密码修改/重置
- RBAC权限控制

### 2. 订单管理
- 订单查询/创建/修改/取消
- 批量操作
- 订单模板
- 订单分组
- 成交记录查询

### 3. 账户管理
- 账户CRUD
- 连接测试
- 持仓查询
- 余额查询

### 4. 分析报告
- 综合分析报告
- 订单执行分析
- 滑点分析
- 成交量分析
- 订单效率分析
- 可视化图表
- 报告导出(PDF/HTML/CSV)

### 5. 用户管理
- 用户CRUD
- 角色管理
- 权限管理
- 角色分配

### 6. 系统管理
- 系统信息
- 健康检查
- 配置管理
- 备份恢复
- 日志管理

### 7. 安全管理
- 安全配置
- IP黑白名单
- 审计日志
- 安全扫描

## API文档

启动后端服务后，访问以下地址查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发指南

### 代码规范

- **Python**: 遵循PEP 8规范
- **JavaScript**: 遵循ESLint规范
- **Vue**: 使用Composition API

### Git规范

- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

## 测试

### 后端测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_auth.py

# 查看覆盖率
pytest --cov=web.backend
```

### 前端测试

```bash
# 运行单元测试
npm run test:unit

# 运行E2E测试
npm run test:e2e
```

## 部署

### 生产环境部署

1. **配置环境变量**

```bash
# 编辑.env文件
DEBUG=False
JWT_SECRET_KEY=your-production-secret-key
DATABASE_URL=postgresql://user:password@db:5432/hikyuu
REDIS_ENABLED=True
```

2. **配置SSL证书**

```bash
# 将SSL证书放在nginx/ssl/目录
cp cert.pem nginx/ssl/
cp key.pem nginx/ssl/
```

3. **启动服务**

```bash
docker-compose up -d
```

4. **配置域名**

编辑`nginx/nginx.conf`，修改`server_name`为你的域名

## 性能优化

- 数据库查询优化
- Redis缓存
- 前端代码分割
- 图片优化
- Gzip压缩
- CDN加速

## 安全特性

- JWT认证
- 双因素认证
- RBAC权限控制
- SQL注入防护
- XSS防护
- CSRF防护
- 命令注入防护
- 路径遍历防护
- IP黑白名单
- 审计日志

## 监控告警

- 系统监控(CPU、内存、磁盘)
- 应用监控(响应时间、错误率)
- 业务监控(订单量、成交量)

## 故障排查

### 后端无法启动

- 检查端口是否被占用
- 检查数据库连接
- 查看日志文件

### 前端无法访问后端

- 检查CORS配置
- 检查API代理配置
- 检查网络连接

### 数据库连接失败

- 检查数据库服务状态
- 检查连接字符串
- 检查防火墙设置

## 贡献指南

1. Fork项目
2. 创建功能分支(`git checkout -b feature/AmazingFeature`)
3. 提交代码(`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支(`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

MIT License

## 联系方式

- 项目地址: https://github.com/yourusername/hikyuu-ui
- 问题反馈: https://github.com/yourusername/hikyuu-ui/issues
- 邮箱: your.email@example.com

## 更新日志

### v1.0.0 (2024-01-09)

- 初始版本发布
- 实现核心功能模块
- 完成安全认证系统
- 集成数据可视化
- 支持Docker部署

## 致谢

感谢所有为这个项目做出贡献的开发者！
