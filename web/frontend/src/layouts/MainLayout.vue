<template>
  <el-container class="main-layout">
    <el-aside width="200px" class="sidebar">
      <div class="logo">
        <h3>Hikyuu UI</h3>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        
        <el-menu-item index="/orders">
          <el-icon><Document /></el-icon>
          <span>订单管理</span>
        </el-menu-item>
        
        <el-menu-item index="/accounts">
          <el-icon><Wallet /></el-icon>
          <span>账户管理</span>
        </el-menu-item>
        
        <el-menu-item index="/analysis">
          <el-icon><TrendCharts /></el-icon>
          <span>分析报告</span>
        </el-menu-item>
        
        <el-menu-item v-if="hasPermission('user:read')" index="/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        
        <el-menu-item v-if="hasPermission('system:read')" index="/system">
          <el-icon><Setting /></el-icon>
          <span>系统管理</span>
        </el-menu-item>
        
        <el-menu-item v-if="hasPermission('security:read')" index="/security">
          <el-icon><Lock /></el-icon>
          <span>安全管理</span>
        </el-menu-item>
        
        <el-menu-item index="/notifications">
          <el-icon><Bell /></el-icon>
          <span>通知中心</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="header-right">
          <NotificationCenter />
          
          <el-dropdown @command="handleCommand">
            <span class="user-dropdown">
              <el-avatar :size="32" :src="userAvatar">
                {{ authStore.user?.username?.charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="username">{{ authStore.user?.username }}</span>
            </span>
            
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人资料</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import {
  DataBoard, Document, Wallet, TrendCharts,
  User, Setting, Lock, Bell
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import NotificationCenter from '@/components/common/NotificationCenter.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '仪表盘')
const userAvatar = computed(() => authStore.user?.avatar)

function hasPermission(permission) {
  return authStore.hasPermission(permission)
}

async function handleCommand(command) {
  switch (command) {
    case 'profile':
      router.push('/profile')
      break
    case 'password':
      router.push('/password')
      break
    case 'logout':
      try {
        await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        
        await authStore.logout()
        ElMessage.success('已退出登录')
        router.push('/login')
      } catch (error) {
        console.error('Logout error:', error)
      }
      break
  }
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #1f2d3d;
}

.logo h3 {
  margin: 0;
  color: #fff;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 20px;
}

.header-left {
  flex: 1;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.username {
  font-size: 14px;
  color: #333;
}

.main-content {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
