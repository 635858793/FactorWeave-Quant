"""
LLM配置服务测试

测试LLM配置服务的各项功能（使用数据库存储）
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from loguru import logger

try:
    from core.services.llm_config_service import (
        LLMConfigService, LLMProvider, LLMConfig, LLMProviderInfo
    )
    from core.containers import ServiceContainer
    from core.events import EventBus
    from db.models.llm_config_models import LLMConfigManager
except ImportError as e:
    logger.error(f"LLM配置服务导入失败: {e}")
    pytest.skip("LLM配置服务不可用")


class TestLLMConfigService:
    """LLM配置服务测试"""

    @pytest.fixture
    def llm_config_service(self, tmp_path):
        """创建LLM配置服务实例"""
        # 使用唯一的数据库文件名和密钥文件名避免冲突
        import uuid
        db_path = tmp_path / f"test_llm_config_{uuid.uuid4().hex}.sqlite"
        key_path = tmp_path / f"test_llm_key_{uuid.uuid4().hex}.key"
        
        # 创建服务容器和事件总线
        event_bus = EventBus()
        service_container = ServiceContainer()
        
        # 创建配置服务
        service = LLMConfigService(config={}, event_bus=event_bus)
        
        # 替换配置管理器，使用独立的密钥文件
        config_manager = LLMConfigManager(db_path=str(db_path), key_path=str(key_path))
        service._config_manager = config_manager
        
        # 初始化服务
        service.initialize()
        
        yield service
        
        # 清理 - 先关闭服务，再删除文件
        try:
            # 删除文件
            if db_path.exists():
                import os
                import time
                max_retries = 5
                for i in range(max_retries):
                    try:
                        db_path.unlink()
                        break
                    except PermissionError:
                        if i < max_retries - 1:
                            time.sleep(0.5)  # 增加等待时间
                        else:
                            logger.warning(f"无法删除测试数据库文件: {db_path}")
            
            # 删除密钥文件
            if key_path.exists():
                try:
                    key_path.unlink()
                except Exception as e:
                    logger.warning(f"无法删除测试密钥文件: {key_path}")
        except Exception as e:
            logger.warning(f"清理测试数据库文件失败: {e}")

    def test_service_initialization(self, llm_config_service):
        """测试服务初始化"""
        assert llm_config_service is not None
        assert llm_config_service.initialized
        assert hasattr(llm_config_service, 'PROVIDER_INFO')

    def test_get_all_providers(self, llm_config_service):
        """测试获取所有提供商"""
        providers = llm_config_service.get_all_providers()
        
        assert len(providers) > 0
        assert all(isinstance(p, LLMProviderInfo) for p in providers)
        
        # 检查关键提供商
        provider_names = [p.provider for p in providers]
        assert LLMProvider.OPENAI in provider_names
        assert LLMProvider.ANTHROPIC in provider_names
        assert LLMProvider.GOOGLE in provider_names
        assert LLMProvider.QIANWEN in provider_names

    def test_get_provider_info(self, llm_config_service):
        """测试获取提供商信息"""
        # 测试OpenAI
        openai_info = llm_config_service.get_provider_info(LLMProvider.OPENAI)
        assert openai_info is not None
        assert openai_info.provider == LLMProvider.OPENAI
        assert openai_info.name == "OpenAI"
        assert "gpt-3.5-turbo" in openai_info.models
        
        # 测试不存在的提供商
        invalid_info = llm_config_service.get_provider_info(LLMProvider.DEEPSEEK)
        assert invalid_info is not None

    def test_set_and_get_config(self, llm_config_service):
        """测试设置和获取配置"""
        # 创建配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=2000,
            timeout=30,
            enabled=True
        )
        
        # 设置配置
        llm_config_service.set_config(config)
        
        # 获取配置
        retrieved_config = llm_config_service.get_config(LLMProvider.OPENAI)
        
        assert retrieved_config is not None
        assert retrieved_config.provider == LLMProvider.OPENAI
        assert retrieved_config.api_key == "test-api-key"
        assert retrieved_config.model == "gpt-3.5-turbo"
        assert retrieved_config.temperature == 0.7
        assert retrieved_config.max_tokens == 2000

    def test_set_current_provider(self, llm_config_service):
        """测试设置当前提供商"""
        # 先设置配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        
        # 设置当前提供商
        llm_config_service.set_current_provider(LLMProvider.OPENAI)
        
        # 获取当前提供商
        current = llm_config_service.get_current_provider()
        assert current == LLMProvider.OPENAI

    def test_get_current_config(self, llm_config_service):
        """测试获取当前配置"""
        # 设置配置和当前提供商
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        llm_config_service.set_current_provider(LLMProvider.OPENAI)
        
        # 获取当前配置
        current_config = llm_config_service.get_current_config()
        
        assert current_config is not None
        assert current_config.provider == LLMProvider.OPENAI
        assert current_config.api_key == "test-api-key"

    def test_remove_config(self, llm_config_service):
        """测试删除配置"""
        # 设置配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        
        # 删除配置
        llm_config_service.remove_config(LLMProvider.OPENAI)
        
        # 验证删除
        retrieved_config = llm_config_service.get_config(LLMProvider.OPENAI)
        assert retrieved_config is None

    def test_is_configured(self, llm_config_service):
        """测试检查是否已配置"""
        # 未配置时
        assert not llm_config_service.is_configured(LLMProvider.OPENAI)
        
        # 配置后
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        
        # 验证已配置
        assert llm_config_service.is_configured(LLMProvider.OPENAI)

    def test_get_available_providers(self, llm_config_service):
        """测试获取已配置的提供商"""
        # 配置多个提供商
        for provider in [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GOOGLE]:
            config = LLMConfig(
                provider=provider,
                api_key=f"test-{provider.value}-key",
                model="test-model"
            )
            llm_config_service.set_config(config)
        
        # 获取已配置的提供商
        available = llm_config_service.get_available_providers()
        
        assert len(available) == 3
        assert LLMProvider.OPENAI in available
        assert LLMProvider.ANTHROPIC in available
        assert LLMProvider.GOOGLE in available

    def test_health_check(self, llm_config_service):
        """测试健康检查"""
        # 配置一个提供商
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        llm_config_service.set_current_provider(LLMProvider.OPENAI)
        
        # 执行健康检查
        health = llm_config_service.health_check()
        
        assert health['service'] == 'LLMConfigService'
        assert health['status'] == 'healthy'
        assert health['current_provider'] == 'openai'
        assert health['configured_providers'] == 1
        assert 'openai' in health['providers']

    def test_encryption_decryption(self, llm_config_service):
        """测试加密和解密"""
        # 设置配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="sensitive-api-key-123",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        
        # 获取配置
        retrieved_config = llm_config_service.get_config(LLMProvider.OPENAI)
        
        # 验证API密钥被正确加密和解密
        assert retrieved_config is not None
        assert retrieved_config.api_key == "sensitive-api-key-123"

    def test_get_api_key_for_provider(self, llm_config_service):
        """测试获取提供商的API密钥"""
        # 设置配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        
        # 获取API密钥
        api_key = llm_config_service.get_api_key_for_provider(LLMProvider.OPENAI)
        
        assert api_key == "test-api-key"
        
        # 获取不存在的提供商的API密钥
        invalid_key = llm_config_service.get_api_key_for_provider(LLMProvider.DEEPSEEK)
        assert invalid_key is None

    def test_get_api_key_for_current_provider(self, llm_config_service):
        """测试获取当前提供商的API密钥"""
        # 未设置当前提供商时
        assert llm_config_service.get_api_key_for_current_provider() is None
        
        # 设置当前提供商
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        llm_config_service.set_current_provider(LLMProvider.OPENAI)
        
        # 获取当前提供商的API密钥
        api_key = llm_config_service.get_api_key_for_current_provider()
        
        assert api_key == "test-api-key"

    def test_test_connection_mock(self, llm_config_service):
        """测试连接测试（使用Mock）"""
        pytest.importorskip('openai', reason='openai module not installed')
        
        # 设置配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config)
        
        # Mock OpenAI客户端 - 需要在导入时mock
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            # 测试连接
            result = llm_config_service.test_connection(LLMProvider.OPENAI)
            
            # 验证结果
            assert result['success'] == True
            assert result['model'] == 'gpt-3.5-turbo'
            assert 'Test response' in result['response']

    def test_test_connection_unconfigured(self, llm_config_service):
        """测试未配置的提供商连接测试"""
        # 测试未配置的提供商
        result = llm_config_service.test_connection(LLMProvider.OPENAI)
        
        assert result['success'] == False
        assert '配置不存在' in result['error']

    def test_multiple_providers(self, llm_config_service):
        """测试多个提供商配置"""
        # 配置多个提供商
        providers = [
            (LLMProvider.OPENAI, "openai-key", "gpt-3.5-turbo"),
            (LLMProvider.ANTHROPIC, "anthropic-key", "claude-3-sonnet-20240229"),
            (LLMProvider.GOOGLE, "google-key", "gemini-pro"),
            (LLMProvider.QIANWEN, "qianwen-key", "qwen-plus")
        ]
        
        for provider, api_key, model in providers:
            config = LLMConfig(
                provider=provider,
                api_key=api_key,
                model=model
            )
            llm_config_service.set_config(config)
        
        # 验证所有提供商都已配置
        for provider, _, _ in providers:
            assert llm_config_service.is_configured(provider)
        
        # 验证已配置的提供商数量
        available = llm_config_service.get_available_providers()
        assert len(available) == 4

    def test_provider_switching(self, llm_config_service):
        """测试提供商切换"""
        # 配置两个提供商
        config1 = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="openai-key",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config1)
        
        config2 = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            api_key="anthropic-key",
            model="claude-3-sonnet-20240229"
        )
        llm_config_service.set_config(config2)
        
        # 切换到OpenAI
        llm_config_service.set_current_provider(LLMProvider.OPENAI)
        assert llm_config_service.get_current_provider() == LLMProvider.OPENAI
        assert llm_config_service.get_current_config().provider == LLMProvider.OPENAI
        
        # 切换到Anthropic
        llm_config_service.set_current_provider(LLMProvider.ANTHROPIC)
        assert llm_config_service.get_current_provider() == LLMProvider.ANTHROPIC
        assert llm_config_service.get_current_config().provider == LLMProvider.ANTHROPIC

    def test_config_with_extra_params(self, llm_config_service):
        """测试带额外参数的配置"""
        # 创建带额外参数的配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo",
            extra_params={
                "top_p": 0.9,
                "frequency_penalty": 0.5
            }
        )
        
        # 设置配置
        llm_config_service.set_config(config)
        
        # 获取配置
        retrieved_config = llm_config_service.get_config(LLMProvider.OPENAI)
        
        # 验证额外参数
        assert retrieved_config is not None
        assert retrieved_config.extra_params == {
            "top_p": 0.9,
            "frequency_penalty": 0.5
        }

    def test_config_with_proxy(self, llm_config_service):
        """测试带代理的配置"""
        # 创建带代理的配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo",
            proxy="http://127.0.0.1:7890"
        )
        
        # 设置配置
        llm_config_service.set_config(config)
        
        # 获取配置
        retrieved_config = llm_config_service.get_config(LLMProvider.OPENAI)
        
        # 验证代理设置
        assert retrieved_config is not None
        assert retrieved_config.proxy == "http://127.0.0.1:7890"

    def test_config_with_api_secret(self, llm_config_service):
        """测试带API密钥的配置（Azure）"""
        # 创建带API密钥的配置
        config = LLMConfig(
            provider=LLMProvider.AZURE_OPENAI,
            api_key="test-api-key",
            api_secret="test-api-secret",
            model="gpt-35-turbo"
        )
        
        # 设置配置
        llm_config_service.set_config(config)
        
        # 获取配置
        retrieved_config = llm_config_service.get_config(LLMProvider.AZURE_OPENAI)
        
        # 验证API密钥
        assert retrieved_config is not None
        assert retrieved_config.api_key == "test-api-key"
        assert retrieved_config.api_secret == "test-api-secret"

    def test_disabled_provider(self, llm_config_service):
        """测试禁用的提供商"""
        # 创建禁用的配置
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo",
            enabled=False
        )
        
        # 设置配置
        llm_config_service.set_config(config)
        
        # 获取配置
        retrieved_config = llm_config_service.get_config(LLMProvider.OPENAI)
        
        # 验证禁用状态
        assert retrieved_config is not None
        assert retrieved_config.enabled == False

    def test_config_history(self, llm_config_service):
        """测试配置历史"""
        # 创建配置
        config1 = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key-1",
            model="gpt-3.5-turbo"
        )
        llm_config_service.set_config(config1)
        
        # 更新配置
        config2 = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key-2",
            model="gpt-4"
        )
        llm_config_service.set_config(config2)
        
        # 获取历史
        history = llm_config_service.get_config_history(LLMProvider.OPENAI)
        
        # 验证历史记录
        assert len(history) >= 2
        assert history[0]['operation'] == 'update'
        assert history[1]['operation'] == 'create'

    def test_export_import_config(self, llm_config_service, tmp_path):
        """测试导出和导入配置"""
        # 配置多个提供商
        for provider in [LLMProvider.OPENAI, LLMProvider.ANTHROPIC]:
            config = LLMConfig(
                provider=provider,
                api_key=f"test-{provider.value}-key",
                model="test-model"
            )
            llm_config_service.set_config(config)
        
        # 设置当前提供商
        llm_config_service.set_current_provider(LLMProvider.OPENAI)
        
        # 导出配置
        export_file = tmp_path / "llm_config_export.json"
        assert llm_config_service.export_config(str(export_file))
        
        # 验证导出文件存在
        assert export_file.exists()
        
        # 清空配置
        llm_config_service.remove_config(LLMProvider.OPENAI)
        llm_config_service.remove_config(LLMProvider.ANTHROPIC)
        
        # 导入配置
        assert llm_config_service.import_config(str(export_file))
        
        # 验证导入成功
        assert llm_config_service.is_configured(LLMProvider.OPENAI)
        assert llm_config_service.is_configured(LLMProvider.ANTHROPIC)
        assert llm_config_service.get_current_provider() == LLMProvider.OPENAI

    def test_llm_config_to_dict(self):
        """测试LLMConfig转换为字典"""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-api-key",
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=2000
        )
        
        config_dict = config.to_dict()
        
        assert config_dict['provider'] == 'openai'
        assert config_dict['api_key'] == 'test-api-key'
        assert config_dict['model'] == 'gpt-3.5-turbo'
        assert config_dict['temperature'] == 0.7
        assert config_dict['max_tokens'] == 2000

    def test_llm_config_from_dict(self):
        """测试从字典创建LLMConfig"""
        config_dict = {
            'provider': 'openai',
            'api_key': 'test-api-key',
            'model': 'gpt-3.5-turbo',
            'temperature': 0.7,
            'max_tokens': 2000,
            'enabled': True
        }
        
        config = LLMConfig.from_dict(config_dict)
        
        assert config.provider == LLMProvider.OPENAI
        assert config.api_key == 'test-api-key'
        assert config.model == 'gpt-3.5-turbo'
        assert config.temperature == 0.7
        assert config.max_tokens == 2000
        assert config.enabled == True
