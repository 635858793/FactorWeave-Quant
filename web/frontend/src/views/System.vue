<template>
  <div class="system">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409eff">
              <el-icon :size="32"><Cpu /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ systemInfo.cpu_usage }}%</div>
              <div class="stat-label">CPU使用率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #67c23a">
              <el-icon :size="32"><MemoryCard /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ systemInfo.memory_usage }}%</div>
              <div class="stat-label">内存使用率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6a23c">
              <el-icon :size="32"><Files /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ systemInfo.disk_usage }}%</div>
              <div class="stat-label">磁盘使用率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f56c6c">
              <el-icon :size="32"><Connection /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ systemInfo.active_connections }}</div>
              <div class="stat-label">活跃连接</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统信息</span>
              <el-button type="primary" link @click="loadSystemInfo">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="系统名称">{{ systemInfo.system_name }}</el-descriptions-item>
            <el-descriptions-item label="系统版本">{{ systemInfo.system_version }}</el-descriptions-item>
            <el-descriptions-item label="Python版本">{{ systemInfo.python_version }}</el-descriptions-item>
            <el-descriptions-item label="启动时间">{{ systemInfo.start_time }}</el-descriptions-item>
            <el-descriptions-item label="运行时间">{{ systemInfo.uptime }}</el-descriptions-item>
            <el-descriptions-item label="进程ID">{{ systemInfo.pid }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>健康检查</span>
              <el-button type="primary" link @click="checkHealth">
                <el-icon><Refresh /></el-icon>
                检查
              </el-button>
            </div>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="状态">
              <el-tag :type="healthStatus.status === 'healthy' ? 'success' : 'danger'">
                {{ healthStatus.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="服务">{{ healthStatus.service }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ healthStatus.version }}</el-descriptions-item>
            <el-descriptions-item label="检查时间">{{ healthStatus.check_time }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统配置</span>
              <el-button type="primary" @click="saveConfig" :loading="savingConfig">
                <el-icon><Check /></el-icon>
                保存配置
              </el-button>
            </div>
          </template>
          <el-form :model="config" label-width="150px">
            <el-form-item label="调试模式">
              <el-switch v-model="config.debug" />
            </el-form-item>
            
            <el-form-item label="日志级别">
              <el-select v-model="config.log_level">
                <el-option label="DEBUG" value="DEBUG" />
                <el-option label="INFO" value="INFO" />
                <el-option label="WARNING" value="WARNING" />
                <el-option label="ERROR" value="ERROR" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="最大上传大小">
              <el-input-number v-model="config.max_upload_size" :min="1" :max="100" />
              <span style="margin-left: 10px">MB</span>
            </el-form-item>
            
            <el-form-item label="会话超时">
              <el-input-number v-model="config.session_timeout" :min="5" :max="120" />
              <span style="margin-left: 10px">分钟</span>
            </el-form-item>
            
            <el-form-item label="限流请求/分钟">
              <el-input-number v-model="config.rate_limit_per_minute" :min="10" :max="1000" />
            </el-form-item>
            
            <el-form-item label="启用限流">
              <el-switch v-model="config.rate_limit_enabled" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统备份</span>
            </div>
          </template>
          <el-form label-width="100px">
            <el-form-item label="备份类型">
              <el-select v-model="backupType">
                <el-option label="完整备份" value="full" />
                <el-option label="增量备份" value="incremental" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="备份描述">
              <el-input v-model="backupDescription" type="textarea" :rows="3" />
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="createBackup" :loading="backingUp">
                <el-icon><Download /></el-icon>
                创建备份
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统操作</span>
            </div>
          </template>
          <el-space direction="vertical" :size="20" style="width: 100%">
            <el-button type="warning" @click="restartSystem" :loading="restarting">
              <el-icon><RefreshRight /></el-icon>
              重启系统
            </el-button>
            
            <el-button type="danger" @click="clearLogs" :loading="clearingLogs">
              <el-icon><Delete /></el-icon>
              清除日志
            </el-button>
            
            <el-button type="info" @click="viewLogs">
              <el-icon><Document /></el-icon>
              查看日志
            </el-button>
          </el-space>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>系统日志</span>
          <el-button-group>
            <el-button size="small" @click="loadLogs">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button size="small" @click="exportLogs">
              <el-icon><Download /></el-icon>
              导出
            </el-button>
          </el-button-group>
        </div>
      </template>
      <el-table :data="logs" stripe max-height="400">
        <el-table-column prop="timestamp" label="时间" width="180" />
        <el-table-column prop="level" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="getLogLevelType(row.level)">
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="150" />
        <el-table-column prop="message" label="消息" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Cpu, MemoryCard, Files, Connection, Refresh,
  Check, Download, RefreshRight, Delete, Document
} from '@element-plus/icons-vue'

const systemInfo = ref({
  cpu_usage: 0,
  memory_usage: 0,
  disk_usage: 0,
  active_connections: 0,
  system_name: '',
  system_version: '',
  python_version: '',
  start_time: '',
  uptime: '',
  pid: 0
})

const healthStatus = ref({
  status: 'unknown',
  service: '',
  version: '',
  check_time: ''
})

const config = ref({
  debug: false,
  log_level: 'INFO',
  max_upload_size: 10,
  session_timeout: 30,
  rate_limit_per_minute: 60,
  rate_limit_enabled: true
})

const backupType = ref('full')
const backupDescription = ref('')
const logs = ref([])

const savingConfig = ref(false)
const backingUp = ref(false)
const restarting = ref(false)
const clearingLogs = ref(false)

onMounted(() => {
  loadSystemInfo()
  checkHealth()
  loadLogs()
})

async function loadSystemInfo() {
  try {
    const response = await fetch('/api/v1/system/info')
    systemInfo.value = await response.json()
  } catch (error) {
    console.error('Load system info failed:', error)
    ElMessage.error('加载系统信息失败')
  }
}

async function checkHealth() {
  try {
    const response = await fetch('/api/v1/system/health')
    healthStatus.value = await response.json()
    healthStatus.value.check_time = new Date().toLocaleString()
  } catch (error) {
    console.error('Check health failed:', error)
    healthStatus.value.status = 'unhealthy'
    ElMessage.error('健康检查失败')
  }
}

async function saveConfig() {
  savingConfig.value = true
  try {
    const response = await fetch('/api/v1/system/config', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(config.value)
    })
    
    if (response.ok) {
      ElMessage.success('配置保存成功')
    } else {
      ElMessage.error('配置保存失败')
    }
  } catch (error) {
    console.error('Save config failed:', error)
    ElMessage.error('配置保存失败')
  } finally {
    savingConfig.value = false
  }
}

async function createBackup() {
  backingUp.value = true
  try {
    const response = await fetch('/api/v1/system/backup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        backup_type: backupType.value,
        description: backupDescription.value
      })
    })
    
    if (response.ok) {
      ElMessage.success('备份创建成功')
      backupDescription.value = ''
    } else {
      ElMessage.error('备份创建失败')
    }
  } catch (error) {
    console.error('Create backup failed:', error)
    ElMessage.error('备份创建失败')
  } finally {
    backingUp.value = false
  }
}

async function restartSystem() {
  try {
    await ElMessageBox.confirm('确定要重启系统吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    restarting.value = true
    
    const response = await fetch('/api/v1/system/restart', {
      method: 'POST'
    })
    
    if (response.ok) {
      ElMessage.success('系统重启中，请稍后刷新页面')
    } else {
      ElMessage.error('系统重启失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Restart system failed:', error)
      ElMessage.error('系统重启失败')
    }
  } finally {
    restarting.value = false
  }
}

async function clearLogs() {
  try {
    await ElMessageBox.confirm('确定要清除所有日志吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    clearingLogs.value = true
    
    const response = await fetch('/api/v1/system/logs', {
      method: 'DELETE'
    })
    
    if (response.ok) {
      ElMessage.success('日志已清除')
      loadLogs()
    } else {
      ElMessage.error('日志清除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Clear logs failed:', error)
      ElMessage.error('日志清除失败')
    }
  } finally {
    clearingLogs.value = false
  }
}

function viewLogs() {
  ElMessage.info('日志查看功能开发中')
}

async function loadLogs() {
  try {
    const response = await fetch('/api/v1/system/logs')
    const data = await response.json()
    logs.value = data.logs || []
  } catch (error) {
    console.error('Load logs failed:', error)
    ElMessage.error('加载日志失败')
  }
}

async function exportLogs() {
  try {
    const response = await fetch('/api/v1/system/logs/export')
    const blob = await response.blob()
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `system_logs_${Date.now()}.txt`
    link.click()
    
    ElMessage.success('日志导出成功')
  } catch (error) {
    console.error('Export logs failed:', error)
    ElMessage.error('日志导出失败')
  }
}

function getLogLevelType(level) {
  const typeMap = {
    DEBUG: 'info',
    INFO: 'success',
    WARNING: 'warning',
    ERROR: 'danger'
  }
  return typeMap[level] || 'info'
}
</script>

<style scoped>
.system {
  padding: 20px;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 20px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 5px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
