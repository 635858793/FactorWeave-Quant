<template>
  <div class="notifications-page">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409eff">
              <el-icon :size="32"><Bell /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">总通知</div>
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
              <div class="stat-value">{{ stats.read }}</div>
              <div class="stat-label">已读</div>
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
              <div class="stat-value">{{ stats.unread }}</div>
              <div class="stat-label">未读</div>
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
              <div class="stat-value">{{ stats.by_type.error || 0 }}</div>
              <div class="stat-label">错误</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>通知类型分布</span>
          </template>
          <div ref="typeChartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
      
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>最近通知</span>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="notification in recentNotifications"
              :key="notification.id"
              :timestamp="formatTime(notification.created_at)"
              placement="top"
            >
              <el-tag :type="getNotificationType(notification.type)" size="small">
                {{ notification.type }}
              </el-tag>
              <span style="margin-left: 10px">{{ notification.title }}</span>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>通知历史</span>
          <el-button-group>
            <el-button @click="loadNotifications">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button @click="markAllAsRead" :disabled="stats.unread === 0">
              <el-icon><Check /></el-icon>
              全部已读
            </el-button>
            <el-button type="danger" @click="deleteAllNotifications">
              <el-icon><Delete /></el-icon>
              清空
            </el-button>
          </el-button-group>
        </div>
      </template>
      
      <el-form :model="filters" inline>
        <el-form-item label="状态">
          <el-select v-model="filters.is_read" placeholder="请选择" clearable @change="loadNotifications">
            <el-option label="未读" :value="false" />
            <el-option label="已读" :value="true" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="类型">
          <el-select v-model="filters.type" placeholder="请选择" clearable @change="loadNotifications">
            <el-option label="信息" value="info" />
            <el-option label="警告" value="warning" />
            <el-option label="错误" value="error" />
            <el-option label="成功" value="success" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <el-table :data="notifications" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" width="200" />
        <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getNotificationType(row.type)">
              {{ row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'sent' ? 'success' : 'warning'">
              {{ row.status === 'sent' ? '已发送' : '待发送' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="read" label="已读" width="80">
          <template #default="{ row }">
            <el-tag :type="row.read ? 'success' : 'info'">
              {{ row.read ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              @click="markAsRead(row.id)"
              :disabled="row.read"
            >
              标记已读
            </el-button>
            <el-button
              link
              type="danger"
              @click="deleteNotification(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadNotifications"
        @current-change="loadNotifications"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Bell, CircleCheck, Warning, CircleClose, Refresh, Check, Delete
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { notificationsApi } from '@/api/notifications'

const stats = ref({
  total: 0,
  read: 0,
  unread: 0,
  by_type: {}
})

const recentNotifications = ref([])
const notifications = ref([])
const loading = ref(false)
const filters = ref({
  is_read: null,
  type: null
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const typeChartRef = ref(null)

onMounted(() => {
  loadStats()
  loadNotifications()
})

async function loadStats() {
  try {
    const data = await notificationsApi.getStats()
    
    stats.value = data
    recentNotifications.value = data.recent_notifications || []
    
    await nextTick()
    renderTypeChart()
  } catch (error) {
    console.error('Load stats failed:', error)
    ElMessage.error('加载统计失败')
  }
}

function loadNotifications() {
  loading.value = true
  
  const params = {
    page: pagination.value.page,
    page_size: pagination.value.pageSize,
    is_read: filters.value.is_read,
    notification_type: filters.value.type
  }
  
  notificationsApi.getNotifications(params)
    .then(data => {
      notifications.value = data.notifications
      pagination.value.total = data.total
    })
    .catch(error => {
      console.error('Load notifications failed:', error)
      ElMessage.error('加载通知失败')
    })
    .finally(() => {
      loading.value = false
    })
}

function renderTypeChart() {
  if (!typeChartRef.value) return
  
  const chart = echarts.init(typeChartRef.value)
  
  const chartData = [
    { value: stats.value.by_type.info || 0, name: '信息' },
    { value: stats.value.by_type.warning || 0, name: '警告' },
    { value: stats.value.by_type.error || 0, name: '错误' },
    { value: stats.value.by_type.success || 0, name: '成功' }
  ]
  
  chart.setOption({
    tooltip: {
      trigger: 'item'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '通知类型',
        type: 'pie',
        radius: '50%',
        data: chartData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  })
}

function markAsRead(notificationId) {
  notificationsApi.markAsRead(notificationId)
    .then(data => {
      ElMessage.success('已标记为已读')
      loadStats()
      loadNotifications()
    })
    .catch(error => {
      console.error('Mark as read failed:', error)
      ElMessage.error('标记失败')
    })
}

function markAllAsRead() {
  notificationsApi.markAllAsRead()
    .then(data => {
      ElMessage.success(data.message)
      loadStats()
      loadNotifications()
    })
    .catch(error => {
      console.error('Mark all as read failed:', error)
      ElMessage.error('标记失败')
    })
}

function deleteNotification(notificationId) {
  notificationsApi.deleteNotification(notificationId)
    .then(data => {
      ElMessage.success('通知已删除')
      loadStats()
      loadNotifications()
    })
    .catch(error => {
      console.error('Delete notification failed:', error)
      ElMessage.error('删除失败')
    })
}

function deleteAllNotifications() {
  ElMessageBox.confirm('确定要清空所有通知吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
    .then(() => {
      notificationsApi.deleteAllNotifications()
        .then(data => {
          ElMessage.success(data.message)
          loadStats()
          loadNotifications()
        })
        .catch(error => {
          console.error('Delete all notifications failed:', error)
          ElMessage.error('清空失败')
        })
    })
    .catch(() => {})
}

function getNotificationType(type) {
  const typeMap = {
    'info': 'primary',
    'warning': 'warning',
    'error': 'danger',
    'success': 'success'
  }
  return typeMap[type] || 'info'
}

function formatTime(time) {
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.notifications-page {
  padding: 20px;
}

.stat-card {
  margin-bottom: 20px;
}

.stat-content {
  display: flex;
  align-items: center;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-right: 16px;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
