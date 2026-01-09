import request from '@/utils/request'

export const accountApi = {
  getAccounts(params) {
    return request({
      url: '/accounts',
      method: 'get',
      params
    })
  },
  
  getAccount(accountId) {
    return request({
      url: `/accounts/${accountId}`,
      method: 'get'
    })
  },
  
  createAccount(data) {
    return request({
      url: '/accounts',
      method: 'post',
      data
    })
  },
  
  updateAccount(accountId, data) {
    return request({
      url: `/accounts/${accountId}`,
      method: 'put',
      data
    })
  },
  
  deleteAccount(accountId) {
    return request({
      url: `/accounts/${accountId}`,
      method: 'delete'
    })
  },
  
  testConnection(accountId) {
    return request({
      url: `/accounts/${accountId}/test`,
      method: 'post'
    })
  },
  
  getPositions(accountId) {
    return request({
      url: `/accounts/${accountId}/positions`,
      method: 'get'
    })
  },
  
  getBalance(accountId) {
    return request({
      url: `/accounts/${accountId}/balance`,
      method: 'get'
    })
  }
}
