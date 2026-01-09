import request from '@/utils/request'

export const analysisApi = {
  getComprehensiveReport(params) {
    return request({
      url: '/analysis/comprehensive',
      method: 'get',
      params
    })
  },
  
  getExecutionAnalysis(params) {
    return request({
      url: '/analysis/execution',
      method: 'get',
      params
    })
  },
  
  getSlippageAnalysis(params) {
    return request({
      url: '/analysis/slippage',
      method: 'get',
      params
    })
  },
  
  getVolumeAnalysis(params) {
    return request({
      url: '/analysis/volume',
      method: 'get',
      params
    })
  },
  
  getEfficiencyAnalysis(params) {
    return request({
      url: '/analysis/efficiency',
      method: 'get',
      params
    })
  },
  
  generateChart(data) {
    return request({
      url: '/analysis/charts/generate',
      method: 'post',
      data
    })
  },
  
  exportPdfReport(data) {
    return request({
      url: '/analysis/export/pdf',
      method: 'post',
      data,
      responseType: 'blob'
    })
  },
  
  exportHtmlReport(data) {
    return request({
      url: '/analysis/export/html',
      method: 'post',
      data,
      responseType: 'blob'
    })
  },
  
  exportCsvReport(data) {
    return request({
      url: '/analysis/export/csv',
      method: 'post',
      data,
      responseType: 'blob'
    })
  }
}
