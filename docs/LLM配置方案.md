# LLM配置方案文档

## 概述

本系统提供统一的LLM（大语言模型）配置管理，支持多个大模型提供商，方便用户根据需求选择合适的模型。

## 支持的LLM提供商

### 国际大模型

1. **OpenAI** (GPT系列)
   - 模型：gpt-4, gpt-4-turbo, gpt-3.5-turbo, gpt-3.5-turbo-16k
   - 默认模型：gpt-3.5-turbo
   - 文档：https://platform.openai.com/docs
   - 定价：https://openai.com/pricing

2. **Anthropic** (Claude系列)
   - 模型：claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
   - 默认模型：claude-3-sonnet-20240229
   - 文档：https://docs.anthropic.com
   - 定价：https://www.anthropic.com/pricing

3. **Google** (Gemini系列)
   - 模型：gemini-pro, gemini-pro-vision
   - 默认模型：gemini-pro
   - 文档：https://ai.google.dev/docs
   - 定价：https://ai.google.dev/pricing

4. **Azure OpenAI**
   - 模型：gpt-4, gpt-35-turbo
   - 默认模型：gpt-35-turbo
   - 文档：https://learn.microsoft.com/azure/ai-services/openai
   - 定价：https://azure.microsoft.com/pricing/details/cognitive-services/openai-service
   - 特点：需要API密钥和API Secret

### 国内大模型

5. **通义千问** (阿里云)
   - 模型：qwen-turbo, qwen-plus, qwen-max
   - 默认模型：qwen-plus
   - 文档：https://help.aliyun.com/zh/dashscope/
   - 定价：https://help.aliyun.com/zh/dashscope/developer-reference/price

6. **文心一言** (百度)
   - 模型：ernie-bot-4, ernie-bot-turbo
   - 默认模型：ernie-bot-turbo
   - 文档：https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html
   - 定价：https://cloud.baidu.com/product/wenxinworkshop

7. **智谱AI** (清华)
   - 模型：glm-4, glm-3-turbo
   - 默认模型：glm-3-turbo
   - 文档：https://open.bigmodel.cn/dev/api
   - 定价：https://open.bigmodel.cn/pricing

8. **DeepSeek**
   - 模型：deepseek-chat, deepseek-coder
   - 默认模型：deepseek-chat
   - 文档：https://platform.deepseek.com/docs
   - 定价：https://platform.deepseek.com/pricing

9. **百川智能**
   - 模型：Baichuan2-Turbo, Baichuan2-53B
   - 默认模型：Baichuan2-Turbo
   - 文档：https://platform.baichuan-ai.com/docs
   - 定价：https://platform.baichuan-ai.com/price

10. **月之暗面** (Moonshot AI)
    - 模型：moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k
    - 默认模型：moonshot-v1-8k
    - 文档：https://platform.moonshot.cn/docs
    - 定价：https://platform.moonshot.cn/pricing

## 架构设计

### 核心组件

1. **LLMConfigService** (`core/services/llm_config_service.py`)
   - 统一的LLM配置管理服务
   - 支持多个提供商的配置
   - 提供加密存储API密钥
   - 支持连接测试

2. **LLMConfigDialog** (`gui/dialogs/llm_config_dialog.py`)
   - LLM配置UI对话框
   - 提供友好的配置界面
   - 支持连接测试

3. **AISelectionIntegrationService** 集成
   - 自动使用LLMConfigService获取配置
   - 支持多个提供商的LLM解析

### 配置存储

- **位置**：`config/llm_config.json`
- **加密**：使用Fernet加密API密钥
- **密钥文件**：`config/.llm_key`

## 使用方式

### 1. 通过UI配置

1. 打开AI选股面板
2. 点击"LLM配置"按钮
3. 在弹出的对话框中选择提供商
4. 填写API密钥和配置
5. 点击"测试连接"验证配置
6. 点击"保存配置"保存设置

### 2. 通过代码配置

```python
from core.services.llm_config_service import LLMConfigService, LLMProvider, LLMConfig

# 获取LLM配置服务
service_container = get_service_container()
llm_config_service = service_container.resolve(LLMConfigService)

# 创建配置
config = LLMConfig(
    provider=LLMProvider.OPENAI,
    api_key="your-api-key",
    model="gpt-3.5-turbo",
    temperature=0.7,
    max_tokens=2000,
    timeout=30,
    enabled=True
)

# 保存配置
llm_config_service.set_config(config)

# 设置为当前提供商
llm_config_service.set_current_provider(LLMProvider.OPENAI)

# 测试连接
result = llm_config_service.test_connection(LLMProvider.OPENAI)
if result['success']:
    print("连接成功！")
else:
    print(f"连接失败: {result['error']}")
```

## 可商用性分析

### 优势

1. **统一接口**
   - 所有提供商使用统一的配置接口
   - 便于扩展新的提供商
   - 降低维护成本

2. **安全性**
   - API密钥加密存储
   - 避免明文存储敏感信息
   - 支持密钥轮换

3. **灵活性**
   - 支持多个提供商同时配置
   - 可以快速切换提供商
   - 支持自定义API地址和代理

4. **可扩展性**
   - 易于添加新的LLM提供商
   - 支持自定义参数
   - 支持自定义API地址

5. **用户友好**
   - 提供图形化配置界面
   - 支持连接测试
   - 提供详细的错误提示

### 商用建议

1. **API密钥管理**
   - 建议使用环境变量存储API密钥
   - 定期轮换API密钥
   - 使用密钥管理服务（如AWS Secrets Manager）

2. **成本控制**
   - 合理设置max_tokens参数
   - 根据需求选择合适的模型
   - 监控API使用量和费用

3. **高可用性**
   - 配置多个提供商作为备选
   - 实现自动故障转移
   - 设置合理的超时时间

4. **性能优化**
   - 使用缓存减少API调用
   - 批量处理请求
   - 异步处理提高响应速度

## 开源项目参考

以下开源项目可以复用或参考：

### 1. LangChain
- **地址**：https://github.com/langchain-ai/langchain
- **特点**：
  - 支持多个LLM提供商
  - 提供统一的接口
  - 丰富的生态系统

### 2. LlamaIndex
- **地址**：https://github.com/run-llama/llama_index
- **特点**：
  - 专注于RAG（检索增强生成）
  - 支持多种向量数据库
  - 与LangChain兼容

### 3. OpenAI Python SDK
- **地址**：https://github.com/openai/openai-python
- **特点**：
  - 官方SDK
  - 完整的API支持
  - 良好的文档

### 4. Anthropic Python SDK
- **地址**：https://github.com/anthropics/anthropic-sdk-python
- **特点**：
  - 官方SDK
  - 支持Claude系列模型
  - 流式响应支持

## 依赖安装

```bash
# OpenAI
pip install openai

# Anthropic
pip install anthropic

# Google
pip install google-generativeai

# 通义千问
pip install dashscope

# 加密库
pip install cryptography
```

## 配置示例

### OpenAI配置

```json
{
  "current_provider": "openai",
  "providers": {
    "openai": {
      "provider": "openai",
      "api_key": "sk-...",
      "api_secret": null,
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-3.5-turbo",
      "temperature": 0.7,
      "max_tokens": 2000,
      "timeout": 30,
      "enabled": true,
      "proxy": null,
      "extra_params": {}
    }
  }
}
```

### 通义千问配置

```json
{
  "current_provider": "qianwen",
  "providers": {
    "qianwen": {
      "provider": "qianwen",
      "api_key": "sk-...",
      "api_secret": null,
      "base_url": "https://dashscope.aliyuncs.com/api/v1",
      "model": "qwen-plus",
      "temperature": 0.7,
      "max_tokens": 2000,
      "timeout": 30,
      "enabled": true,
      "proxy": null,
      "extra_params": {}
    }
  }
}
```

## 故障排查

### 常见问题

1. **连接测试失败**
   - 检查API密钥是否正确
   - 检查网络连接
   - 检查代理设置
   - 检查API地址是否正确

2. **导入错误**
   - 确保已安装对应的SDK
   - 检查Python版本兼容性
   - 查看错误日志获取详细信息

3. **配置保存失败**
   - 检查config目录权限
   - 检查磁盘空间
   - 查看日志获取详细信息

## 未来扩展

### 计划功能

1. **更多提供商**
   - 支持更多国内大模型
   - 支持自部署模型（如Llama）
   - 支持API网关

2. **高级功能**
   - 支持流式响应
   - 支持函数调用
   - 支持多模态输入

3. **监控和统计**
   - API使用量统计
   - 费用统计
   - 性能监控

## 联系和支持

如有问题或建议，请通过以下方式联系：
- GitHub Issues
- 文档反馈
- 社区讨论

## 许可证

本LLM配置方案遵循项目整体许可证。
