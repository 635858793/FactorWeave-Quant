<template>
  <div class="security">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409eff">
              <el-icon :size="32"><Lock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ securitySummary.total_logs }}</div>
              <div class="stat-label">审计日志</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #67c23a">
              <el-icon :size="32"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ securitySummary.successful_logins }}</div>
              <div class="stat-label">成功登录</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6a23c">
              <el-icon :size="32"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ securitySummary.failed_logins }}</div>
              <div class="stat-label">失败登录</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f56c6c">
              <el-icon :size="32"><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ securitySummary.security_alerts }}</div>
              <div class="stat-label">安全告警</div>
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
              <span>安全配置</span>
              <el-button type="primary" @click="saveSecurityConfig" :loading="savingConfig">
                <el-icon><Check /></el-icon>
                保存配置
              </el-button>
            </div>
          </template>
          <el-form :model="securityConfig" label-width="150px">
            <el-form-item label="IP白名单">
              <el-switch v-model="securityConfig.ip_whitelist_enabled" />
            </el-form-item>
            
            <el-form-item label="IP黑名单">
              <el-switch v-model="securityConfig.ip_blacklist_enabled" />
            </el-form-item>
            
            <el-form-item label="请求签名">
              <el-switch v-model="securityConfig.request_signature_enabled" />
            </el-form-item>
            
            <el-form-item label="HTTPS强制">
              <el-switch v-model="securityConfig.https_force" />
            </el-form-item>
            
            <el-form-item label="HSTS最大年龄">
              <el-input-number v-model="securityConfig.hsts_max_age" :min="0" :max="31536000" />
              <span style="margin-left: 10px">秒</span>
            </el-form-item>
            
            <el-divider />
            
            <el-form-item label="SQL注入防护">
              <el-switch v-model="securityConfig.sql_injection_enabled" />
            </el-form-item>
            
            <el-form-item label="XSS防护">
              <el-switch v-model="securityConfig.xss_enabled" />
            </el-form-item>
            
            <el-form-item label="CSRF防护">
              <el-switch v-model="securityConfig.csrf_enabled" />
            </el-form-item>
            
            <el-form-item label="文件上传防护">
              <el-switch v-model="securityConfig.file_upload_enabled" />
            </el-form-item>
            
            <el-form-item label="命令注入防护">
              <el-switch v-model="securityConfig.command_injection_enabled" />
            </el-form-item>
            
            <el-form-item label="路径遍历防护">
              <el-switch v-model="securityConfig.path_traversal_enabled" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>IP管理</span>
              <el-button-group>
                <el-button type="primary" @click="showIpDialog('whitelist')">
                  <el-icon><Plus /></el-icon>
                  添加白名单
                </el-button>
                <el-button type="danger" @click="showIpDialog('blacklist')">
                  <el-icon><Plus /></el-icon>
                  添加黑名单
                </el-button>
              </el-button-group>
            </div>
          </template>
          <el-tabs v-model="activeIpTab">
            <el-tab-pane label="IP白名单" name="whitelist">
              <el-table :data="ipWhitelist" stripe>
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="ip_address" label="IP地址" width="150" />
                <el-table-column prop="description" label="描述" />
                <el-table-column prop="created_at" label="创建时间" width="180" />
                <el-table-column label="操作" width="100">
                  <template #default="{ row }">
                    <el-button link type="danger" @click="removeIp('whitelist', row.id)">
                      移除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            
            <el-tab-pane label="IP黑名单" name="blacklist">
              <el-table :data="ipBlacklist" stripe>
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="ip_address" label="IP地址" width="150" />
                <el-table-column prop="description" label="描述" />
                <el-table-column prop="created_at" label="创建时间" width="180" />
                <el-table-column label="操作" width="100">
                  <template #default="{ row }">
                    <el-button link type="danger" @click="removeIp('blacklist', row.id)">
                      移除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>审计日志</span>
              <el-button-group>
                <el-button @click="loadAuditLogs">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
                <el-button @click="exportAuditLogs">
                  <el-icon><Download /></el-icon>
                  导出
                </el-button>
              </el-button-group>
            </div>
          </template>
          
          <el-form :model="auditFilters" inline>
            <el-form-item label="用户">
              <el-input v-model="auditFilters.username" placeholder="请输入用户名" clearable />
            </el-form-item>
            
            <el-form-item label="操作">
              <el-select v-model="auditFilters.action" placeholder="请选择" clearable>
                <el-option label="登录" value="login" />
                <el-option label="登出" value="logout" />
                <el-option label="创建" value="create" />
                <el-option label="更新" value="update" />
                <el-option label="删除" value="delete" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="资源类型">
              <el-select v-model="auditFilters.resource_type" placeholder="请选择" clearable>
                <el-option label="用户" value="user" />
                <el-option label="订单" value="order" />
                <el-option label="账户" value="account" />
                <el-option label="系统" value="system" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="auditFilters.dateRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始时间"
                end-placeholder="结束时间"
              />
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="loadAuditLogs">查询</el-button>
              <el-button @click="resetAuditFilters">重置</el-button>
            </el-form-item>
          </el-form>
          
          <el-table :data="auditLogs" stripe v-loading="loadingLogs" max-height="500">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="用户" width="120" />
            <el-table-column prop="action" label="操作" width="100">
              <template #default="{ row }">
                <el-tag :type="getActionType(row.action)">
                  {{ getActionText(row.action) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="resource_type" label="资源类型" width="100" />
            <el-table-column prop="resource_id" label="资源ID" width="150" />
            <el-table-column prop="ip_address" label="IP地址" width="120" />
            <el-table-column prop="request_method" label="请求方法" width="80" />
            <el-table-column prop="request_path" label="请求路径" width="200" />
            <el-table-column prop="response_status" label="状态码" width="80">
              <template #default="{ row }">
                <el-tag :type="row.response_status >= 200 && row.response_status < 300 ? 'success' : 'danger'">
                  {{ row.response_status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="success" label="成功" width="80">
              <template #default="{ row }">
                <el-tag :type="row.success ? 'success' : 'danger'">
                  {{ row.success ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="180" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button link type="primary" @click="viewAuditLog(row)">
                  查看
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-pagination
            v-model:current-page="auditPagination.page"
            v-model:page-size="auditPagination.pageSize"
            :total="auditPagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="loadAuditLogs"
            @current-change="loadAuditLogs"
            style="margin-top: 20px; justify-content: flex-end"
          />
        </el-card>
      </el-col>
    </el-row>
    
    <el-dialog
      v-model="showIpDialogVisible"
      :title="ipDialogType === 'whitelist' ? '添加IP白名单' : '添加IP黑名单'"
      width="500px"
    >
      <el-form
        ref="ipFormRef"
        :model="ipForm"
        :rules="ipRules"
        label-width="100px"
      >
        <el-form-item label="IP地址" prop="ip_address">
          <el-input v-model="ipForm.ip_address" placeholder="请输入IP地址或IP段" />
          <div style="margin-top: 5px; font-size: 12px; color: #999">
            支持单个IP（如：192.168.1.1）或IP段（如：192.168.1.0/24）
          </div>
        </el-form-item>
        
        <el-form-item label="描述" prop="description">
          <el-input v-model="ipForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showIpDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="addIp" :loading="addingIp">
          添加
        </el-button>
      </template>
    </el-dialog>
    
    <el-dialog v-model="showAuditLogDialog" title="审计日志详情" width="800px">
      <el-descriptions v-if="currentAuditLog" :column="2" border>
        <el-descriptions-item label="日志ID">{{ currentAuditLog.id }}</el-descriptions-item>
        <el-descriptions-item label="用户">{{ currentAuditLog.username }}</el-descriptions-item>
        <el-descriptions-item label="操作">
          <el-tag :type="getActionType(currentAuditLog.action)">
            {{ getActionText(currentAuditLog.action) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="资源类型">{{ currentAuditLog.resource_type }}</el-descriptions-item>
        <el-descriptions-item label="资源ID">{{ currentAuditLog.resource_id }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ currentAuditLog.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="请求方法">{{ currentAuditLog.request_method }}</el-descriptions-item>
        <el-descriptions-item label="请求路径">{{ currentAuditLog.request_path }}</el-descriptions-item>
        <el-descriptions-item label="请求参数">{{ currentAuditLog.request_params }}</el-descriptions-item>
        <el-descriptions-item label="响应状态">{{ currentAuditLog.response_status }}</el-descriptions-item>
        <el-descriptions-item label="响应时间">{{ currentAuditLog.response_time }}ms</el-descriptions-item>
        <el-descriptions-item label="成功">
          <el-tag :type="currentAuditLog.success ? 'success' : 'danger'">
            {{ currentAuditLog.success ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2">
          {{ currentAuditLog.error_message || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="用户代理" :span="2">
          {{ currentAuditLog.user_agent }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">
          {{ currentAuditLog.created_at }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Lock, CircleCheck, Warning, CircleClose, Plus,
  Refresh, Download, Check
} from '@element-plus/icons-vue'

const securitySummary = ref({
  total_logs: 0,
  successful_logins: 0,
  failed_logins: 0,
  security_alerts: 0
})

const securityConfig = ref({
  ip_whitelist_enabled: false,
  ip_blacklist_enabled: false,
  request_signature_enabled: false,
  https_force: false,
  hsts_max_age: 31536000,
  sql_injection_enabled: true,
  xss_enabled: true,
  csrf_enabled: true,
  file_upload_enabled: true,
  command_injection_enabled: true,
  path_traversal_enabled: true
})

const activeIpTab = ref('whitelist')
const ipWhitelist = ref([])
const ipBlacklist = ref([])

const loadingLogs = ref(false)
const auditLogs = ref([])
const auditFilters = ref({
  username: '',
  action: '',
  resource_type: '',
  dateRange: []
})

const auditPagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const showIpDialogVisible = ref(false)
const ipDialogType = ref('whitelist')
const addingIp = ref(false)
const ipFormRef = ref(null)
const ipForm = ref({
  ip_address: '',
  description: ''
})

const ipRules = {
  ip_address: [
    { required: true, message: '请输入IP地址', trigger: 'blur' }
  ],
  description: [
    { required: true, message: '请输入描述', trigger: 'blur' }
  ]
}

const showAuditLogDialog = ref(false)
const currentAuditLog = ref(null)
const savingConfig = ref(false)

onMounted(() => {
  loadSecuritySummary()
  loadSecurityConfig()
  loadIpWhitelist()
  loadIpBlacklist()
  loadAuditLogs()
})

async function loadSecuritySummary() {
  try {
    const response = await fetch('/api/v1/security/summary')
    securitySummary.value = await response.json()
  } catch (error) {
    console.error('Load security summary failed:', error)
    ElMessage.error('加载安全摘要失败')
  }
}

async function loadSecurityConfig() {
  try {
    const response = await fetch('/api/v1/security/config')
    securityConfig.value = await response.json()
  } catch (error) {
    console.error('Load security config failed:', error)
    ElMessage.error('加载安全配置失败')
  }
}

async function saveSecurityConfig() {
  savingConfig.value = true
  try {
    const response = await fetch('/api/v1/security/config', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(securityConfig.value)
    })
    
    if (response.ok) {
      ElMessage.success('安全配置保存成功')
    } else {
      ElMessage.error('安全配置保存失败')
    }
  } catch (error) {
    console.error('Save security config failed:', error)
    ElMessage.error('安全配置保存失败')
  } finally {
    savingConfig.value = false
  }
}

async function loadIpWhitelist() {
  try {
    const response = await fetch('/api/v1/security/ip-whitelist')
    ipWhitelist.value = await response.json()
  } catch (error) {
    console.error('Load IP whitelist failed:', error)
    ElMessage.error('加载IP白名单失败')
  }
}

async function loadIpBlacklist() {
  try {
    const response = await fetch('/api/v1/security/ip-blacklist')
    ipBlacklist.value = await response.json()
  } catch (error) {
    console.error('Load IP blacklist failed:', error)
    ElMessage.error('加载IP黑名单失败')
  }
}

function showIpDialog(type) {
  ipDialogType.value = type
  showIpDialogVisible.value = true
}

async function addIp() {
  try {
    await ipFormRef.value.validate()
    
    addingIp.value = true
    
    const endpoint = ipDialogType.value === 'whitelist' 
      ? '/api/v1/security/ip-whitelist' 
      : '/api/v1/security/ip-blacklist'
    
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(ipForm.value)
    })
    
    if (response.ok) {
      ElMessage.success('IP添加成功')
      showIpDialogVisible.value = false
      ipForm.value = { ip_address: '', description: '' }
      
      if (ipDialogType.value === 'whitelist') {
        loadIpWhitelist()
      } else {
        loadIpBlacklist()
      }
    } else {
      ElMessage.error('IP添加失败')
    }
  } catch (error) {
    console.error('Add IP failed:', error)
    ElMessage.error('IP添加失败')
  } finally {
    addingIp.value = false
  }
}

async function removeIp(type, id) {
  try {
    await ElMessageBox.confirm('确定要移除该IP吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const endpoint = type === 'whitelist'
      ? `/api/v1/security/ip-whitelist/${id}`
      : `/api/v1/security/ip-blacklist/${id}`
    
    const response = await fetch(endpoint, {
      method: 'DELETE'
    })
    
    if (response.ok) {
      ElMessage.success('IP已移除')
      
      if (type === 'whitelist') {
        loadIpWhitelist()
      } else {
        loadIpBlacklist()
      }
    } else {
      ElMessage.error('IP移除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Remove IP failed:', error)
      ElMessage.error('IP移除失败')
    }
  }
}

async function loadAuditLogs() {
  loadingLogs.value = true
  try {
    const params = new URLSearchParams({
      page: auditPagination.value.page,
      page_size: auditPagination.value.pageSize,
      username: auditFilters.value.username,
      action: auditFilters.value.action,
      resource_type: auditFilters.value.resource_type,
      start_time: auditFilters.value.dateRange?.[0] || '',
      end_time: auditFilters.value.dateRange?.[1] || ''
    })
    
    const response = await fetch(`/api/v1/security/audit-logs?${params}`)
    const data = await response.json()
    
    auditLogs.value = data.logs
    auditPagination.value.total = data.total
  } catch (error) {
    console.error('Load audit logs failed:', error)
    ElMessage.error('加载审计日志失败')
  } finally {
    loadingLogs.value = false
  }
}

function resetAuditFilters() {
  auditFilters.value = {
    username: '',
    action: '',
    resource_type: '',
    dateRange: []
  }
  loadAuditLogs()
}

function viewAuditLog(log) {
  currentAuditLog.value = log
  showAuditLogDialog.value = true
}

async function exportAuditLogs() {
  try {
    const params = new URLSearchParams({
      username: auditFilters.value.username,
      action: auditFilters.value.action,
      resource_type: auditFilters.value.resource_type,
      start_time: auditFilters.value.dateRange?.[0] || '',
      end_time: auditFilters.value.dateRange?.[1] || ''
    })
    
    const response = await fetch(`/api/v1/security/audit-logs/export?${params}`)
    const blob = await response.blob()
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `audit_logs_${Date.now()}.csv`
    link.click()
    
    ElMessage.success('审计日志导出成功')
  } catch (error) {
    console.error('Export audit logs failed:', error)
    ElMessage.error('审计日志导出失败')
  }
}

function getActionType(action) {
  const typeMap = {
    login: 'success',
    logout: 'info',
    create: 'success',
    update: 'warning',
    delete: 'danger'
  }
  return typeMap[action] || 'info'
}

function getActionText(action) {
  const textMap = {
    login: '登录',
    logout: '登出',
    create: '创建',
    update: '更新',
    delete: '删除'
  }
  return textMap[action] || action
}
</script>

<style scoped>
.security {
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
