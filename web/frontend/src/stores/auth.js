import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('access_token'))
  const refreshToken = ref(localStorage.getItem('refresh_token'))
  
  const isAuthenticated = computed(() => !!token.value)
  
  async function login(credentials) {
    try {
      const response = await authApi.login(credentials)
      
      token.value = response.access_token
      refreshToken.value = response.refresh_token
      
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)
      
      await fetchUser()
      
      return true
    } catch (error) {
      console.error('Login failed:', error)
      return false
    }
  }
  
  async function logout() {
    try {
      await authApi.logout()
    } catch (error) {
      console.error('Logout failed:', error)
    } finally {
      user.value = null
      token.value = null
      refreshToken.value = null
      
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  }
  
  async function fetchUser() {
    try {
      const response = await authApi.getCurrentUser()
      user.value = response
    } catch (error) {
      console.error('Fetch user failed:', error)
      await logout()
    }
  }
  
  async function checkAuth() {
    if (token.value) {
      await fetchUser()
    }
  }
  
  function hasPermission(permission) {
    if (!user.value) return false
    if (user.value.is_admin) return true
    
    return user.value.permissions?.includes(permission) || false
  }
  
  return {
    user,
    token,
    refreshToken,
    isAuthenticated,
    login,
    logout,
    fetchUser,
    checkAuth,
    hasPermission
  }
})
