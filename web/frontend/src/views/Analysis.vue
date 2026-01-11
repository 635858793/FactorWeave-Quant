<template>
  <div class="analysis">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>分析报告</span>
          <el-button type="primary" @click="generateReport">
            <el-icon><Refresh /></el-icon>
            生成报告
          </el-button>
        </div>
      </template>
      
      <el-form :model="filters" inline>
        <el-form-item label="分析周期">
          <el-select v-model="filters.period" placeholder="请选择">
            <el-option label="今日" value="day" />
            <el-option label="本周" value="week" />
            <el-option label="本月" value="month" />
            <el-option label="本季度" value="quarter" />
            <el-option label="本年" value="year" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="资产类型">
          <el-select v-model="filters.asset_type" placeholder="请选择" clearable>
            <el-option label="股票" value="stock" />
            <el-option label="期货" value="futures" />
            <el-option label="期权" value="options" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="账户">
          <el-select v-model="filters.account_id" placeholder="请选择" clearable>
            <el-option
              v-for="account in accounts"
              :key="account.id"
              :label="account.account_name"
              :value="account.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="loadReport">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
      
      <el-row :gutter="20" v-if="report">
        <el-col :span="6">
          <el-card class="summary-card">
            <div class="summary-item">
              <div class="summary-label">总订单数</div>
              <div class="summary-value">{{ report.summary?.total_orders || 0 }}</div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card class="summary-card">
            <div class="summary-item">
              <div class="summary-label">成交率</div>
              <div class="summary-value">{{ (report.summary?.fill_rate * 100 || 0).toFixed(2) }}%</div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card class="summary-card">
            <div class="summary-item">
              <div class="summary-label">平均滑点</div>
              <div class="summary-value">{{ (report.summary?.avg_slippage * 100 || 0).toFixed(4) }}%</div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card class="summary-card">
            <div class="summary-item">
              <div class="summary-label">效率评分</div>
              <div class="summary-value">{{ (report.summary?.efficiency_score * 100 || 0).toFixed(2) }}%</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
      
      <el-row :gutter="20" style="margin-top: 20px" v-if="report">
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>订单执行分析</span>
                <el-button-group>
                  <el-button size="small" @click="generateChart('execution', 'bar')">柱状图</el-button>
                  <el-button size="small" @click="generateChart('execution', 'pie')">饼图</el-button>
                </el-button-group>
              </div>
            </template>
            <div ref="executionChartRef" style="height: 300px"></div>
          </el-card>
        </el-col>
        
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>滑点分析</span>
                <el-button-group>
                  <el-button size="small" @click="generateChart('slippage', 'line')">折线图</el-button>
                  <el-button size="small" @click="generateChart('slippage', 'bar')">柱状图</el-button>
                </el-button-group>
              </div>
            </template>
            <div ref="slippageChartRef" style="height: 300px"></div>
          </el-card>
        </el-col>
      </el-row>
      
      <el-row :gutter="20" style="margin-top: 20px" v-if="report">
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>成交量分析</span>
                <el-button-group>
                  <el-button size="small" @click="generateChart('volume', 'bar')">柱状图</el-button>
                  <el-button size="small" @click="generateChart('volume', 'line')">折线图</el-button>
                </el-button-group>
              </div>
            </template>
            <div ref="volumeChartRef" style="height: 300px"></div>
          </el-card>
        </el-col>
        
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>订单效率分析</span>
                <el-button-group>
                  <el-button size="small" @click="generateChart('efficiency', 'radar')">雷达图</el-button>
                  <el-button size="small" @click="generateChart('efficiency', 'bar')">柱状图</el-button>
                </el-button-group>
              </div>
            </template>
            <div ref="efficiencyChartRef" style="height: 300px"></div>
          </el-card>
        </el-col>
      </el-row>
      
      <el-card style="margin-top: 20px" v-if="report">
        <template #header>
          <div class="card-header">
            <span>优化建议</span>
            <el-button-group>
              <el-button type="primary" @click="exportPdf">
                <el-icon><Download /></el-icon>
                导出PDF
              </el-button>
              <el-button type="success" @click="exportHtml">
                <el-icon><Download /></el-icon>
                导出HTML
              </el-button>
              <el-button type="warning" @click="exportCsv">
                <el-icon><Download /></el-icon>
                导出CSV
              </el-button>
            </el-button-group>
          </div>
        </template>
        
        <el-timeline>
          <el-timeline-item
            v-for="(recommendation, index) in report.recommendations || []"
            :key="index"
            :timestamp="report.report_time"
            placement="top"
          >
            {{ recommendation }}
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Download } from '@element-plus/icons-vue'
import Plotly from 'plotly.js-dist'
import { analysisApi } from '@/api/analysis'
import { accountApi } from '@/api/account'

const executionChartRef = ref(null)
const slippageChartRef = ref(null)
const volumeChartRef = ref(null)
const efficiencyChartRef = ref(null)

const loading = ref(false)
const accounts = ref([])
const report = ref(null)

const filters = ref({
  period: 'day',
  asset_type: '',
  account_id: '',
  dateRange: []
})

onMounted(() => {
  loadAccounts()
  loadReport()
})

async function loadAccounts() {
  try {
    const response = await accountApi.getAccounts()
    accounts.value = response.accounts
  } catch (error) {
    console.error('Load accounts failed:', error)
  }
}

async function loadReport() {
  loading.value = true
  try {
    const params = {
      period: filters.value.period,
      asset_type: filters.value.asset_type,
      account_id: filters.value.account_id,
      start_time: filters.value.dateRange?.[0],
      end_time: filters.value.dateRange?.[1]
    }
    
    report.value = await analysisApi.getComprehensiveReport(params)
    
    renderCharts()
  } catch (error) {
    console.error('Load report failed:', error)
    ElMessage.error('加载报告失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = {
    period: 'day',
    asset_type: '',
    account_id: '',
    dateRange: []
  }
  loadReport()
}

function generateReport() {
  loadReport()
  ElMessage.success('报告生成成功')
}

function renderCharts() {
  if (!report.value) return
  
  renderExecutionChart()
  renderSlippageChart()
  renderVolumeChart()
  renderEfficiencyChart()
}

async function generateChart(type, chartType) {
  try {
    const response = await analysisApi.generateChart({
      chart_type: chartType,
      period: filters.value.period,
      asset_type: filters.value.asset_type,
      account_id: filters.value.account_id,
      start_time: filters.value.dateRange?.[0],
      end_time: filters.value.dateRange?.[1]
    })
    
    ElMessage.success('图表生成成功')
    
    if (type === 'execution') {
      renderExecutionChart(response.chart_url)
    } else if (type === 'slippage') {
      renderSlippageChart(response.chart_url)
    } else if (type === 'volume') {
      renderVolumeChart(response.chart_url)
    } else if (type === 'efficiency') {
      renderEfficiencyChart(response.chart_url)
    }
  } catch (error) {
    console.error('Generate chart failed:', error)
    ElMessage.error('生成图表失败')
  }
}

function renderExecutionChart(chartUrl = null) {
  if (chartUrl) {
    executionChartRef.value.innerHTML = `<img src="${chartUrl}" style="width: 100%; height: 100%; object-fit: contain;" />`
    return
  }
  
  const execution = report.value.execution_analysis || {}
  const data = [
    {
      x: ['总订单', '已成交', '已取消', '已拒绝'],
      y: [
        execution.total_orders || 0,
        execution.filled_orders || 0,
        execution.cancelled_orders || 0,
        execution.rejected_orders || 0
      ],
      type: 'bar',
      marker: {
        color: ['#409eff', '#67c23a', '#e6a23c', '#f56c6c']
      }
    }
  ]
  
  const layout = {
    margin: { t: 20, r: 20, b: 40, l: 40 },
    showlegend: false
  }
  
  Plotly.newPlot(executionChartRef.value, data, layout, { responsive: true })
}

function renderSlippageChart(chartUrl = null) {
  if (chartUrl) {
    slippageChartRef.value.innerHTML = `<img src="${chartUrl}" style="width: 100%; height: 100%; object-fit: contain;" />`
    return
  }
  
  const slippage = report.value.slippage_analysis || {}
  const data = [
    {
      x: ['平均滑点', '最大滑点', '最小滑点'],
      y: [
        (slippage.avg_slippage * 100 || 0).toFixed(4),
        (slippage.max_slippage * 100 || 0).toFixed(4),
        (slippage.min_slippage * 100 || 0).toFixed(4)
      ],
      type: 'bar',
      marker: {
        color: ['#409eff', '#f56c6c', '#67c23a']
      }
    }
  ]
  
  const layout = {
    margin: { t: 20, r: 20, b: 40, l: 40 },
    showlegend: false
  }
  
  Plotly.newPlot(slippageChartRef.value, data, layout, { responsive: true })
}

function renderVolumeChart(chartUrl = null) {
  if (chartUrl) {
    volumeChartRef.value.innerHTML = `<img src="${chartUrl}" style="width: 100%; height: 100%; object-fit: contain;" />`
    return
  }
  
  const volume = report.value.volume_analysis || {}
  const data = [
    {
      x: ['总成交量', '买入量', '卖出量'],
      y: [
        volume.total_volume || 0,
        volume.buy_volume || 0,
        volume.sell_volume || 0
      ],
      type: 'bar',
      marker: {
        color: ['#409eff', '#67c23a', '#f56c6c']
      }
    }
  ]
  
  const layout = {
    margin: { t: 20, r: 20, b: 40, l: 40 },
    showlegend: false
  }
  
  Plotly.newPlot(volumeChartRef.value, data, layout, { responsive: true })
}

function renderEfficiencyChart(chartUrl = null) {
  if (chartUrl) {
    efficiencyChartRef.value.innerHTML = `<img src="${chartUrl}" style="width: 100%; height: 100%; object-fit: contain;" />`
    return
  }
  
  const efficiency = report.value.efficiency_analysis || {}
  const data = [
    {
      type: 'scatterpolar',
      r: [
        efficiency.fill_efficiency * 100 || 0,
        efficiency.cost_efficiency * 100 || 0,
        efficiency.time_efficiency * 100 || 0,
        efficiency.execution_efficiency * 100 || 0,
        efficiency.risk_efficiency * 100 || 0
      ],
      theta: ['成交效率', '成本效率', '时间效率', '执行效率', '风险效率'],
      fill: 'toself',
      marker: {
        color: '#409eff'
      }
    }
  ]
  
  const layout = {
    polar: {
      radialaxis: {
        visible: true,
        range: [0, 100]
      }
    },
    showlegend: false
  }
  
  Plotly.newPlot(efficiencyChartRef.value, data, layout, { responsive: true })
}

async function exportPdf() {
  try {
    const response = await analysisApi.exportPdfReport({
      period: filters.value.period,
      asset_type: filters.value.asset_type,
      account_id: filters.value.account_id,
      start_time: filters.value.dateRange?.[0],
      end_time: filters.value.dateRange?.[1]
    })
    
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.download = `analysis_report_${Date.now()}.pdf`
    link.click()
    
    ElMessage.success('PDF导出成功')
  } catch (error) {
    console.error('Export PDF failed:', error)
    ElMessage.error('导出PDF失败')
  }
}

async function exportHtml() {
  try {
    const response = await analysisApi.exportHtmlReport({
      period: filters.value.period,
      asset_type: filters.value.asset_type,
      account_id: filters.value.account_id,
      start_time: filters.value.dateRange?.[0],
      end_time: filters.value.dateRange?.[1]
    })
    
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.download = `analysis_report_${Date.now()}.html`
    link.click()
    
    ElMessage.success('HTML导出成功')
  } catch (error) {
    console.error('Export HTML failed:', error)
    ElMessage.error('导出HTML失败')
  }
}

async function exportCsv() {
  try {
    const response = await analysisApi.exportCsvReport({
      period: filters.value.period,
      asset_type: filters.value.asset_type,
      account_id: filters.value.account_id,
      start_time: filters.value.dateRange?.[0],
      end_time: filters.value.dateRange?.[1]
    })
    
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.download = `analysis_report_${Date.now()}.csv`
    link.click()
    
    ElMessage.success('CSV导出成功')
  } catch (error) {
    console.error('Export CSV failed:', error)
    ElMessage.error('导出CSV失败')
  }
}
</script>

<style scoped>
.analysis {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-card {
  cursor: pointer;
  transition: all 0.3s;
}

.summary-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.summary-item {
  text-align: center;
}

.summary-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}
</style>
