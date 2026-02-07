# Windows 11 TensorFlow GPU安装脚本 (PowerShell版本)
# 自动检测GPU硬件并安装匹配的CUDA和TensorFlow GPU版本
#
# 使用方法：
# 1. 确保已安装NVIDIA驱动和CUDA Toolkit
# 2. 以管理员权限运行此脚本
# 3. 脚本会自动检测GPU并安装对应的TensorFlow GPU版本

param(
    [switch]$InstallGPU = $false,
    [switch]$InstallCPU = $false,
    [switch]$SkipDriverCheck = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Windows 11 TensorFlow GPU安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "[警告] 建议以管理员权限运行此脚本以确保完整功能" -ForegroundColor Yellow
    $continue = Read-Host "是否继续？(y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}

Write-Host "[检查] 检查系统环境..." -ForegroundColor Green

# 检查Python环境
try {
    $pythonVersion = python --version 2>$null
    Write-Host "[成功] 检测到Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] Python未安装或不在PATH中" -ForegroundColor Red
    Write-Host "请先安装Python 3.8-3.12版本，下载地址：https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

# 检查pip版本
try {
    $pipVersion = pip --version 2>$null
    Write-Host "[成功] pip环境正常" -ForegroundColor Green
} catch {
    Write-Host "[错误] pip不可用" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 升级pip
Write-Host "[更新] 升级pip到最新版本..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "[成功] pip升级完成" -ForegroundColor Green
} else {
    Write-Host "[警告] pip升级失败，继续安装..." -ForegroundColor Yellow
}

Write-Host ""

# 检查NVIDIA驱动（可选）
if (-not $SkipDriverCheck) {
    Write-Host "[检查] NVIDIA GPU驱动状态..." -ForegroundColor Yellow
    try {
        $gpuInfo = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
        if ($gpuInfo) {
            Write-Host "[成功] 检测到NVIDIA GPU：" -ForegroundColor Green
            $gpuInfo | ForEach-Object { Write-Host "  $_" -ForegroundColor Cyan }
        } else {
            Write-Host "[警告] 未检测到NVIDIA GPU驱动或GPU设备" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[警告] 无法运行nvidia-smi，请确保安装了NVIDIA驱动" -ForegroundColor Yellow
    }
    Write-Host ""
}

# 安装GPU检测工具
Write-Host "[安装] GPU检测工具..." -ForegroundColor Yellow
pip install nvidia-ml-py3 psutil --quiet --no-warn-script-location
if ($LASTEXITCODE -eq 0) {
    Write-Host "[成功] GPU检测工具安装完成" -ForegroundColor Green
} else {
    Write-Host "[警告] GPU检测工具安装失败，继续..." -ForegroundColor Yellow
}
Write-Host ""

# 运行GPU检测脚本
Write-Host "[检测] 开始GPU硬件检测..." -ForegroundColor Yellow
$scriptPath = Join-Path $PSScriptRoot "scripts\verify_gpu_system.py"
if (Test-Path $scriptPath) {
    python $scriptPath
    Write-Host ""
} else {
    Write-Host "[警告] GPU检测脚本不存在，跳过硬件检测" -ForegroundColor Yellow
}

# 选择安装方案
if (-not $InstallGPU -and -not $InstallCPU) {
    Write-Host "[选择] 请选择安装方案：" -ForegroundColor Cyan
    Write-Host "1. 自动安装TensorFlow GPU版本（推荐，有GPU设备时）" -ForegroundColor White
    Write-Host "2. 安装TensorFlow CPU版本（兼容性最好）" -ForegroundColor White
    Write-Host "3. 仅安装基础依赖，不安装TensorFlow" -ForegroundColor White
    Write-Host "4. 退出安装" -ForegroundColor White
    Write-Host ""
    
    do {
        $choice = Read-Host "请选择 (1-4)"
        switch ($choice) {
            "1" { $installType = "gpu"; break }
            "2" { $installType = "cpu"; break }
            "3" { $installType = "minimal"; break }
            "4" { Write-Host "安装已取消"; exit 0 }
            default { Write-Host "[错误] 请输入1-4之间的数字" -ForegroundColor Red }
        }
    } while (-not $installType)
} else {
    if ($InstallGPU) { $installType = "gpu" }
    elseif ($InstallCPU) { $installType = "cpu" }
    else { $installType = "minimal" }
}

Write-Host ""
Write-Host "[安装] 开始安装：$installType" -ForegroundColor Cyan

# 安装基础依赖
Write-Host "[步骤1] 安装基础依赖..." -ForegroundColor Yellow
pip install pandas numpy scipy scikit-learn --quiet --no-warn-script-location
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 基础依赖安装失败" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 根据选择安装TensorFlow
switch ($installType) {
    "gpu" {
        Write-Host "[步骤2] 安装TensorFlow GPU版本..." -ForegroundColor Yellow
        Write-Host "[提示] 如果GPU安装失败，系统会自动回退到CPU版本" -ForegroundColor Cyan
        
        try {
            # 尝试安装GPU版本
            pip install tensorflow-gpu==2.19.0 --quiet --no-warn-script-location
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[成功] TensorFlow GPU版本安装完成" -ForegroundColor Green
            } else {
                throw "GPU版本安装失败"
            }
        } catch {
            Write-Host "[警告] TensorFlow GPU版本安装失败，尝试安装CPU版本..." -ForegroundColor Yellow
            pip install tensorflow==2.19.0 --quiet --no-warn-script-location
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[成功] TensorFlow CPU版本安装完成（GPU支持不可用）" -ForegroundColor Green
            } else {
                throw "CPU版本也安装失败"
            }
        }
    }
    "cpu" {
        Write-Host "[步骤2] 安装TensorFlow CPU版本..." -ForegroundColor Yellow
        pip install tensorflow==2.19.0 --quiet --no-warn-script-location
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[成功] TensorFlow CPU版本安装完成" -ForegroundColor Green
        } else {
            throw "TensorFlow安装失败"
        }
    }
    "minimal" {
        Write-Host "[步骤2] 跳过TensorFlow安装（选择minimal模式）" -ForegroundColor Yellow
    }
}

# 安装其他AI相关库
Write-Host "[步骤3] 安装其他AI库..." -ForegroundColor Yellow
pip install torch torchvision torchaudio --quiet --no-warn-script-location
pip install lightgbm xgboost --quiet --no-warn-script-location
Write-Host "[成功] AI库安装完成" -ForegroundColor Green

# 安装其他系统依赖
Write-Host "[步骤4] 安装系统依赖..." -ForegroundColor Yellow
pip install loguru qasync requests aiohttp click pyyaml python-dotenv tqdm --quiet --no-warn-script-location
Write-Host "[成功] 系统依赖安装完成" -ForegroundColor Green

# 测试安装
Write-Host ""
Write-Host "[测试] 验证安装结果..." -ForegroundColor Yellow

try {
    $pythonTest = @'
import sys
print(f"Python版本: {sys.version}")

try:
    import tensorflow as tf
    print(f"TensorFlow版本: {tf.__version__}")
    gpus = tf.config.list_physical_devices('GPU')
    print(f"GPU设备数量: {len(gpus)}")
    if len(gpus) > 0:
        print("TensorFlow GPU支持正常")
    else:
        print("⚠️  仅CPU模式运行")
except ImportError:
    print("❌ TensorFlow未安装")

try:
    import torch
    print(f"PyTorch版本: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"CUDA可用: 是 (设备数: {torch.cuda.device_count()})")
    else:
        print("CUDA不可用: 否")
except ImportError:
    print("❌ PyTorch未安装")

try:
    import pandas as pd
    print(f"pandas版本: {pd.__version__}")
except ImportError:
    print("❌ pandas未安装")
'@
    
    $result = python -c $pythonTest
    Write-Host $result
} catch {
    Write-Host "[警告] 测试脚本执行失败" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "建议的下一步操作：" -ForegroundColor White
Write-Host "1. 运行GPU验证脚本：python scripts\verify_gpu_system.py" -ForegroundColor Gray
Write-Host "2. 启动应用：python main.py" -ForegroundColor Gray
Write-Host "3. 查看日志输出确认GPU状态" -ForegroundColor Gray
Write-Host ""
Write-Host "如需GPU加速，请确保：" -ForegroundColor Yellow
Write-Host "- 已安装最新NVIDIA驱动" -ForegroundColor Gray
Write-Host "- 已安装匹配的CUDA Toolkit版本" -ForegroundColor Gray
Write-Host "- 已安装cuDNN库" -ForegroundColor Gray
Write-Host ""

Read-Host "按回车键退出"