import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘' }
      },
      {
        path: 'orders',
        name: 'Orders',
        component: () => import('@/views/Orders.vue'),
        meta: { title: '订单管理' }
      },
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('@/views/Accounts.vue'),
        meta: { title: '账户管理' }
      },
      {
        path: 'analysis',
        name: 'Analysis',
        component: () => import('@/views/Analysis.vue'),
        meta: { title: '分析报告' }
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/Users.vue'),
        meta: { title: '用户管理', permission: 'user:read' }
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/System.vue'),
        meta: { title: '系统管理', permission: 'system:read' }
      },
      {
        path: 'security',
        name: 'Security',
        component: () => import('@/views/Security.vue'),
        meta: { title: '安全管理', permission: 'security:read' }
      },
      {
        path: 'notifications',
        name: 'Notifications',
        component: () => import('@/views/Notifications.vue'),
        meta: { title: '通知中心' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
  } else if (to.meta.permission && !authStore.hasPermission(to.meta.permission)) {
    next('/')
  } else {
    next()
  }
})

export default router
