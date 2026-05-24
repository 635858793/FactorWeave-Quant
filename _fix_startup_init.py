import re

path = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\app_initialization.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '# 这个函数应该在应用的main.py或__init__.py中调用\ndef startup_initialization():\n    """启动时的初始化"""\n    logger.info("开始应用启动初始化...")\n    \n    try:\n        results = initialize_application()\n        \n        if results.get(\'error\'):\n            logger.error(f"应用初始化包含错误: {results[\'error\']}")\n        else:\n            logger.info("应用启动初始化成功完成")\n        \n        return results\n        \n    except Exception as e:\n        logger.error(f"应用启动初始化失败: {e}")\n        return {\'error\': str(e)}'

new = '''def startup_initialization():
    """
    启动时的初始化

    .. deprecated::
        此函数未被项目任何代码调用，属于死代码。
        如需应用启动初始化，请直接调用 initialize_application()。
        计划在后续版本中移除此函数。
    """
    import warnings
    warnings.warn(
        "startup_initialization() is deprecated. Use initialize_application() instead.",
        DeprecationWarning,
        stacklevel=2
    )

    logger.info("开始应用启动初始化...")

    try:
        results = initialize_application()

        if results.get('error'):
            logger.error(f"应用初始化包含错误: {results['error']}")
        else:
            logger.info("应用启动初始化成功完成")

        return results

    except Exception as e:
        logger.error(f"应用启动初始化失败: {e}")
        return {'error': str(e)}'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: startup_initialization deprecated')
else:
    print('ERROR: old text not found')
    idx = content.find('def startup_initialization')
    if idx >= 0:
        print(f'Found at index {idx}')
        print(repr(content[idx:idx+200]))