import request from '@/utils/request'

export const orderApi = {
  getOrders(params) {
    return request({
      url: '/orders',
      method: 'get',
      params
    })
  },
  
  getOrder(orderId) {
    return request({
      url: `/orders/${orderId}`,
      method: 'get'
    })
  },
  
  createOrder(data) {
    return request({
      url: '/orders',
      method: 'post',
      data
    })
  },
  
  updateOrder(orderId, data) {
    return request({
      url: `/orders/${orderId}`,
      method: 'put',
      data
    })
  },
  
  cancelOrder(orderId) {
    return request({
      url: `/orders/${orderId}/cancel`,
      method: 'post'
    })
  },
  
  batchCancelOrders(data) {
    return request({
      url: '/orders/batch-cancel',
      method: 'post',
      data
    })
  },
  
  getOrderFills(orderId) {
    return request({
      url: `/orders/${orderId}/fills`,
      method: 'get'
    })
  }
}
