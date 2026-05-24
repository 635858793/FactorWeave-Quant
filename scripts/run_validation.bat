@echo off
REM 自动化验证测试运行脚本
REM 用法: scripts\run_validation.bat [选项]
REM 
REM 选项:
REM   all          - 运行所有测试（默认）
REM   imports      - 仅运行导入验证测试
REM   database     - 仅运行数据库连接测试
REM   coordinator  - 仅运行协调器初始化测试
REM   dialog       - 仅运行对话框创建测试
REM   order        - 仅运行订单执行器测试
REM   report       - 生成测试报告
REM   help         - 显示帮助信息

setlocal

REM 设置项目根目录
set PROJECT_ROOT=%~dp0..
cd /d %PROJECT_ROOT%

REM 设置日志目录
set LOG_DIR=%PROJECT_ROOT%\logs\validation
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 设置测试文件路径
set TEST_FILE=%PROJECT_ROOT%\tests\test_validation_suite.py

REM 检查测试文件是否存在
if not exist "%TEST_FILE%" (
    echo [错误] 测试文件不存在: %TEST_FILE%
    pause
    exit /b 1
)

REM 解析命令行参数
set TEST_MARK=
if "%1"=="" (
    set TEST_MARK=all
) else if "%1"=="imports" (
    set TEST_MARK=-m imports
) else if "%1"=="database" (
    set TEST_MARK=-m database
) else if "%1"=="coordinator" (
    set TEST_MARK=-m coordinator
) else if "%1"=="dialog" (
    set TEST_MARK=-m dialog
) else if "%1"=="order" (
    set TEST_MARK=-m order
) else if "%1"=="report" (
    set TEST_MARK=-m report
) else if "%1"=="help" (
    call :show_help
    pause
    exit /b 0
) else (
    echo [错误] 未知选项: %1
    call :show_help
    pause
    exit /b 1
)

REM 生成时间戳
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%

REM 设置报告文件
set REPORT_FILE=%LOG_DIR%\report_%TIMESTAMP%.html
set LOG_FILE=%LOG_DIR%\run_%TIMESTAMP%.log

echo ============================================
echo FactorWeave-Quant 自动化验证测试
echo ============================================
echo 运行时间: %TIMESTAMP%
echo 测试模式: %TEST_MARK%
echo 测试文件: %TEST_FILE%
echo 报告文件: %REPORT_FILE%
echo 日志文件: %LOG_FILE%
echo ============================================
echo.

REM 激活conda环境（如果需要）
REM call conda activate hikyuu

REM 运行pytest测试
if "%TEST_MARK%"=="all" (
    pytest "%TEST_FILE%" ^
        -v ^
        --tb=short ^
        --log-cli-level=INFO ^
        --html="%REPORT_FILE%" ^
        --self-contained-html ^
        2>&1 | tee "%LOG_FILE%"
) else (
    pytest "%TEST_FILE%" ^
        %TEST_MARK% ^
        -v ^
        --tb=short ^
        --log-cli-level=INFO ^
        --html="%REPORT_FILE%" ^
        --self-contained-html ^
        2>&1 | tee "%LOG_FILE%"
)

REM 检查测试结果
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ============================================
if %EXIT_CODE% EQU 0 (
    echo 测试状态: 全部通过
    echo 报告文件: %REPORT_FILE%
    echo 日志文件: %LOG_FILE%
) else (
    echo 测试状态: 部分测试失败 (退出码: %EXIT_CODE%)
    echo 报告文件: %REPORT_FILE%
    echo 日志文件: %LOG_FILE%
)
echo ============================================

pause
exit /b %EXIT_CODE%

:show_help
echo.
echo 用法: scripts\run_validation.bat [选项]
echo.
echo 选项:
echo   all          - 运行所有测试（默认）
echo   imports      - 仅运行导入验证测试
echo   database     - 仅运行数据库连接测试
echo   coordinator  - 仅运行协调器初始化测试
echo   dialog       - 仅运行对话框创建测试
echo   order        - 仅运行订单执行器测试
echo   report       - 生成测试报告
echo   help         - 显示帮助信息
echo.
echo 示例:
echo   scripts\run_validation.bat          REM 运行所有测试
echo   scripts\run_validation.bat imports  REM 仅运行导入测试
echo   scripts\run_validation.bat database REM 仅运行数据库测试
goto :eof
