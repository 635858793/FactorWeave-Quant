@echo off
REM ============================================
REM 测试运行脚本 (Windows)
REM ============================================
REM 用法: scripts\run_tests.bat [选项]
REM 选项:
REM   --coverage    运行并生成覆盖率报告
REM   --verbose     详细输出
REM   --specific    运行特定测试文件
REM ============================================

echo ============================================
echo HIkyuu-UI 核心业务逻辑单元测试
echo ============================================
echo.

REM 设置项目根目录
set PROJECT_ROOT=%~dp0..
cd /d %PROJECT_ROOT%

REM 激活 conda 环境
echo [1/3] 激活 conda 环境...
call conda activate hikyuu
if errorlevel 1 (
    echo [错误] 无法激活 conda 环境 hikyuu
    exit /b 1
)
echo [成功] conda 环境已激活
echo.

REM 检查 pytest 是否安装
echo [2/3] 检查测试依赖...
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo [提示] pytest 未安装，正在安装...
    pip install pytest pytest-cpytest-mock
    if errorlevel 1 (
        echo [错误] 无法安装 pytest
        exit /b 1
    )
)
echo [成功] 测试依赖已就绪
echo.

REM 运行测试
echo [3/3] 运行测试...
echo.

set TESTS_DIR=tests
set TEST_FILES=test_unified_sqlite_access.py test_order_executor.py test_coordinators.py test_event_bus.py

if "%1"=="--coverage" (
    echo [模式] 覆盖率测试
    echo --------------------------------------------
    python -m pytest %TESTS_DIR%\test_unified_sqlite_access.py ^
                     %TESTS_DIR%\test_order_executor.py ^
                     %TESTS_DIR%\test_coordinators.py ^
                     %TESTS_DIR%\test_event_bus.py ^
                     -v --tb=short ^
                     --cov=core/database/unified_sqlite_access ^
                     --cov=core/trading/order_executor ^
                     --cov=core/coordinators/base_coordinator ^
                     --cov=core/events/event_bus ^
                     --cov-report=term-missing ^
                     --cov-report=html:coverage_html ^
                     --cov-report=xml:coverage.xml
) else if "%1"=="--verbose" (
    echo [模式] 详细输出
    echo --------------------------------------------
    python -m pytest %TESTS_DIR%\test_unified_sqlite_access.py ^
                     %TESTS_DIR%\test_order_executor.py ^
                     %TESTS_DIR%\test_coordinators.py ^
                     %TESTS_DIR%\test_event_bus.py ^
                     -vvv --tb=long
) else if "%1"=="--specific" (
    if "%2"=="" (
        echo [错误] 请指定要运行的测试文件
        echo 用法: run_tests.bat --specific test_unified_sqlite_access.py
        exit /b 1
    )
    echo [模式] 运行特定测试: %2
    echo --------------------------------------------
    python -m pytest %TESTS_DIR%\%2 -v --tb=short
) else (
    echo [模式] 标准测试
    echo --------------------------------------------
    python -m pytest %TESTS_DIR%\test_unified_sqlite_access.py ^
                     %TESTS_DIR%\test_order_executor.py ^
                     %TESTS_DIR%\test_coordinators.py ^
                     %TESTS_DIR%\test_event_bus.py ^
                     -v --tb=short
)

set EXIT_CODE=%errorlevel%

echo.
echo ============================================
if %EXIT_CODE% equ 0 (
    echo 测试运行完成 - 全部通过
) else (
    echo 测试运行完成 - 存在失败
)
echo ============================================

if "%1"=="--coverage" (
    echo.
    echo [提示] 覆盖率报告已生成:
    echo   - HTML: coverage_html\index.html
    echo   - XML: coverage.xml
)

exit /b %EXIT_CODE%
