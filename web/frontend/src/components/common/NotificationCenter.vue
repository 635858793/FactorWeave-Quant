<template>
  <div class="notification-center">
    <el-badge :value="unreadCount" :hidden="unreadCount === 0" class="notification-badge">
      <el-button circle @click="showNotifications = true">
        <el-icon :size="20"><Bell /></el-icon>
      </el-button>
    </el-badge>
    
    <el-drawer
      v-model="showNotifications"
      title="通知中心"
      direction="rtl"
      size="400px"
    >
      <template #header>
        <div class="notification-header">
          <span>通知中心</span>
          <el-button-group>
            <el-button size="small" @click="markAllAsRead" :disabled="unreadCount === 0">
              全部已读
            </el-button>
            <el-button size="small" @click="showPreferences = true">
              设置
            </el-button>
          </el-button-group>
        </div>
      </template>
      
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="`全部 (${totalCount})`" name="all">
          <div class="notification-list">
            <div
              v-for="notification in notifications"
              :key="notification.id"
              :class="['notification-item', { unread: !notification.read }]"
              @click="handleNotificationClick(notification)"
            >
              <div class="notification-icon" :class="`type-${notification.type}`">
                <el-icon v-if="notification.type === 'info'"><InfoFilled /></el-icon>
                <el-icon v-if="notification.type === 'warning'"><WarningFilled /></el-icon>
                <el-icon v-if="notification.type === 'error'"><CircleCloseFilled /></el-icon>
                <el-icon v-if="notification.type === 'success'"><CircleCheckFilled /></el-icon>
              </div>
              
              <div class="notification-content">
                <div class="notification-title">{{ notification.title }}</div>
                <div class="notification-message">{{ notification.content }}</div>
                <div class="notification-time">{{ formatTime(notification.created_at) }}</div>
              </div>
              
              <div class="notification-actions">
                <el-button
                  link
                  type="primary"
                  size="small"
                  @click.stop="markAsRead(notification.id)"
                  v-if="!notification.read"
                >
                  标记已读
                </el-button>
                <el-button
                  link
                  type="danger"
                  size="small"
                  @click.stop="deleteNotification(notification.id)"
                >
                  删除
                </el-button>
              </div>
            </div>
            
            <el-empty v-if="notifications.length === 0" description="暂无通知" />
          </div>
          
          <el-pagination
            v-if="totalCount > pageSize"
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="totalCount"
            layout="prev, pager, next"
            small
            @current-change="loadNotifications"
            style="margin-top: 20px; text-align: center"
          />
        </el-tab-pane>
        
        <el-tab-pane :label="`未读 (${unreadCount})`" name="unread">
          <div class="notification-list">
            <div
              v-for="notification in unreadNotifications"
              :key="notification.id"
              class="notification-item unread"
              @click="handleNotificationClick(notification)"
            >
              <div class="notification-icon" :class="`type-${notification.type}`">
                <el-icon v-if="notification.type === 'info'"><InfoFilled /></el-icon>
                <el-icon v-if="notification.type === 'warning'"><WarningFilled /></el-icon>
                <el-icon v-if="notification.type === 'error'"><CircleCloseFilled /></el-icon>
                <el-icon v-if="notification.type === 'success'"><CircleCheckFilled /></el-icon>
              </div>
              
              <div class="notification-content">
                <div class="notification-title">{{ notification.title }}</div>
                <div class="notification-message">{{ notification.content }}</div>
                <div class="notification-time">{{ formatTime(notification.created_at) }}</div>
              </div>
              
              <div class="notification-actions">
                <el-button
                  link
                  type="primary"
                  size="small"
                  @click.stop="markAsRead(notification.id)"
                >
                  标记已读
                </el-button>
                <el-button
                  link
                  type="danger"
                  size="small"
                  @click.stop="deleteNotification(notification.id)"
                >
                  删除
                </el-button>
              </div>
            </div>
            
            <el-empty v-if="unreadNotifications.length === 0" description="暂无未读通知" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
    
    <el-dialog v-model="showPreferences" title="通知设置" width="500px">
      <el-form :model="preferences" label-width="120px">
        <el-divider content-position="left">通知渠道</el-divider>
        
        <el-form-item label="邮件通知">
          <el-switch v-model="preferences.email_enabled" />
        </el-form-item>
        
        <el-form-item label="短信通知">
          <el-switch v-model="preferences.sms_enabled" />
        </el-form-item>
        
        <el-form-item label="应用内通知">
          <el-switch v-model="preferences.in_app_enabled" />
        </el-form-item>
        
        <el-divider content-position="left">通知类型</el-divider>
        
        <el-form-item label="订单通知">
          <el-switch v-model="preferences.order_notifications" />
        </el-form-item>
        
        <el-form-item label="账户通知">
          <el-switch v-model="preferences.account_notifications" />
        </el-form-item>
        
        <el-form-item label="系统通知">
          <el-switch v-model="preferences.system_notifications" />
        </el-form-item>
        
        <el-form-item label="安全通知">
          <el-switch v-model="preferences.security_notifications" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showPreferences = false">取消</el-button>
        <el-button type="primary" @click="savePreferences" :loading="savingPreferences">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Bell, InfoFilled, WarningFilled, CircleCloseFilled, CircleCheckFilled
} from '@element-plus/icons-vue'
import { notificationsApi } from '@/api/notifications'
import { useWebSocket } from '@/utils/websocket'
import { useAuthStore } from '@/stores/auth'

const showNotifications = ref(false)
const showPreferences = ref(false)
const activeTab = ref('all')
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)
const unreadCount = ref(0)
const notifications = ref([])
const unreadNotifications = ref([])
const savingPreferences = ref(false)

const preferences = ref({
  email_enabled: true,
  sms_enabled: false,
  in_app_enabled: true,
  order_notifications: true,
  account_notifications: true,
  system_notifications: true,
  security_notifications: true
})

const authStore = useAuthStore()
const { connect: connectWebSocket, disconnect: disconnectWebSocket, on, isConnected } = useWebSocket()

onMounted(() => {
  loadNotificationStats()
  loadNotifications()
  loadPreferences()
  
  setupWebSocketNotifications()
})

onUnmounted(() => {
  disconnectWebSocket()
})

function setupWebSocketNotifications() {
  if (authStore.token && !isConnected()) {
    connectWebSocket()
  }
  
  on('notification', (notificationData) => {
    ElMessage({
      title: notificationData.title,
      message: notificationData.content,
      type: notificationData.type,
      duration: 5000
    })
    
    loadNotificationStats()
    loadNotifications()
  })
}

function loadNotificationStats() {
  notificationsApi.getStats()
    .then(data => {
      totalCount.value = data.total
      unreadCount.value = data.unread
    })
    .catch(error => {
      console.error('Load notification stats failed:', error)
    })
}

function loadNotifications() {
  const params = {
    page: currentPage.value,
    page_size: pageSize.value,
    is_read: activeTab.value === 'unread' ? false : null
  }
  
  notificationsApi.getNotifications(params)
    .then(data => {
      if (activeTab.value === 'unread') {
        unreadNotifications.value = data.notifications
      } else {
        notifications.value = data.notifications
      }
      totalCount.value = data.total
      unreadCount.value = data.unread_count
    })
    .catch(error => {
      console.error('Load notifications failed:', error)
      ElMessage.error('加载通知失败')
    })
}

function loadPreferences() {
  notificationsApi.getPreferences()
    .then(data => {
      preferences.value = data
    })
    .catch(error => {
      console.error('Load preferences failed:', error)
    })
}

function markAsRead(notificationId) {
  notificationsApi.markAsRead(notificationId)
    .then(data => {
      ElMessage.success('已标记为已读')
      loadNotificationStats()
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
      loadNotificationStats()
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
      loadNotificationStats()
      loadNotifications()
    })
    .catch(error => {
      console.error('Delete notification failed:', error)
      ElMessage.error('删除失败')
    })
}

function handleNotificationClick(notification) {
  if (!notification.read) {
    markAsRead(notification.id)
  }
  
  if (notification.title.includes('订单')) {
    window.location.href = '/orders'
  } else if (notification.title.includes('账户')) {
    window.location.href = '/accounts'
  } else if (notification.title.includes('安全')) {
    window.location.href = '/security'
  }
}

function savePreferences() {
  savingPreferences.value = true
  
  notificationsApi.updatePreferences(preferences.value)
    .then(data => {
      ElMessage.success('设置已保存')
      showPreferences.value = false
    })
    .catch(error => {
      console.error('Save preferences failed:', error)
      ElMessage.error('保存失败')
    })
    .finally(() => {
      savingPreferences.value = false
    })
}

function formatTime(time) {
  const date = new Date(time)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) {
    return '刚刚'
  } else if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  } else if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  } else if (diff < 604800000) {
    return `${Math.floor(diff / 86400000)}天前`
  } else {
    return date.toLocaleDateString()
  }
}
</script>

<style scoped>
.notification-center {
  display: inline-block;
}

.notification-badge {
  cursor: pointer;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.notification-list {
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
  transition: background-color 0.3s;
}

.notification-item:hover {
  background-color: #f5f7fa;
}

.notification-item.unread {
  background-color: #ecf5ff;
}

.notification-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
}

.notification-icon.type-info {
  background-color: #409eff;
  color: white;
}

.notification-icon.type-warning {
  background-color: #e6a23c;
  color: white;
}

.notification-icon.type-error {
  background-color: #f56c6c;
  color: white;
}

.notification-icon.type-success {
  background-color: #67c23a;
  color: white;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-weight: 500;
  margin-bottom: 4px;
  color: #303133;
}

.notification-message {
  font-size: 14px;
  color: #606266;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notification-time {
  font-size: 12px;
  color: #909399;
}

.notification-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
