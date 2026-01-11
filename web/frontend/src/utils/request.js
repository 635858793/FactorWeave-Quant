import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000
})

request.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    return response.data
  },
  async (error) => {
    const authStore = useAuthStore()
    
    if (error.response?.status === 401) {
      if (authStore.refreshToken) {
        try {
          await authApi.refreshToken()
          return request(error.config)
        } catch (refreshError) {
          await authStore.logout()
          window.location.href = '/login'
        }
      } else {
        await authStore.logout()
        window.location.href = '/login'
      }
    } else if (error.response?.status === 403) {
      ElMessage.error('权限不足')
    } else if (error.response?.status === 429) {
      ElMessage.error('请求过于频繁，请稍后再试')
    } else if (error.response?.status >= 500) {
      ElMessage.error('服务器错误，请稍后再试')
    } else {
      ElMessage.error(error.response?.data?.detail || '请求失败')
    }
    
    return Promise.reject(error)
  }
)

export default request
