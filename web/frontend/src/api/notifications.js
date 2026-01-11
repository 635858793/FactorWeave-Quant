import request from '@/utils/request'

export const notificationsApi = {
  getStats() {
    return request({
      url: '/notifications/stats',
      method: 'get'
    })
  },
  
  getNotifications(params) {
    return request({
      url: '/notifications',
      method: 'get',
      params
    })
  },
  
  getNotificationById(id) {
    return request({
      url: `/notifications/${id}`,
      method: 'get'
    })
  },
  
  createNotification(data) {
    return request({
      url: '/notifications',
      method: 'post',
      data
    })
  },
  
  markAsRead(id) {
    return request({
      url: `/notifications/${id}/read`,
      method: 'put'
    })
  },
  
  markAllAsRead() {
    return request({
      url: '/notifications/read-all',
      method: 'put'
    })
  },
  
  deleteNotification(id) {
    return request({
      url: `/notifications/${id}`,
      method: 'delete'
    })
  },
  
  deleteAllNotifications() {
    return request({
      url: '/notifications/all',
      method: 'delete'
    })
  },
  
  getPreferences() {
    return request({
      url: '/notifications/preferences',
      method: 'get'
    })
  },
  
  updatePreferences(data) {
    return request({
      url: '/notifications/preferences',
      method: 'put',
      data
    })
  }
}
