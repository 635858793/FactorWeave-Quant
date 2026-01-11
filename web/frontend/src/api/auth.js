import request from '@/utils/request'

export const authApi = {
  login(data) {
    return request({
      url: '/auth/login',
      method: 'post',
      data
    })
  },
  
  logout() {
    return request({
      url: '/auth/logout',
      method: 'post'
    })
  },
  
  register(data) {
    return request({
      url: '/auth/register',
      method: 'post',
      data
    })
  },
  
  getCurrentUser() {
    return request({
      url: '/auth/me',
      method: 'get'
    })
  },
  
  refreshToken() {
    return request({
      url: '/auth/refresh',
      method: 'post'
    })
  },
  
  changePassword(data) {
    return request({
      url: '/auth/change-password',
      method: 'post',
      data
    })
  },
  
  enable2FA() {
    return request({
      url: '/auth/2fa/enable',
      method: 'post'
    })
  },
  
  disable2FA() {
    return request({
      url: '/auth/2fa/disable',
      method: 'post'
    })
  },
  
  verify2FA(data) {
    return request({
      url: '/auth/2fa/verify',
      method: 'post',
      data
    })
  }
}
