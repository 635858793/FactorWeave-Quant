<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409eff">
              <el-icon :size="32"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalOrders }}</div>
              <div class="stat-label">总订单数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #67c23a">
              <el-icon :size="32"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.filledOrders }}</div>
              <div class="stat-label">已成交</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6a23c">
              <el-icon :size="32"><Clock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.pendingOrders }}</div>
              <div class="stat-label">待处理</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f56c6c">
              <el-icon :size="32"><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.rejectedOrders }}</div>
              <div class="stat-label">已拒绝</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>订单执行趋势</span>
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
            </div>
          </template>
          <div ref="slippageChartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近订单</span>
              <el-button type="primary" link @click="$router.push('/orders')">
                查看全部
              </el-button>
            </div>
          </template>
          <el-table :data="recentOrders" stripe>
            <el-table-column prop="order_id" label="订单ID" width="150" />
            <el-table-column prop="symbol" label="代码" width="100" />
            <el-table-column prop="side" label="方向" width="80">
              <template #default="{ row }">
                <el-tag :type="row.side === 'buy' ? 'success' : 'danger'">
                  {{ row.side === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="quantity" label="数量" width="100" />
            <el-table-column prop="price" label="价格" width="100" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Document, CircleCheck, Clock, CircleClose } from '@element-plus/icons-vue'
import Plotly from 'plotly.js-dist'

const executionChartRef = ref(null)
const slippageChartRef = ref(null)

const stats = ref({
  totalOrders: 0,
  filledOrders: 0,
  pendingOrders: 0,
  rejectedOrders: 0
})

const recentOrders = ref([])

onMounted(() => {
  loadStats()
  loadRecentOrders()
  renderExecutionChart()
  renderSlippageChart()
})

async function loadStats() {
  stats.value = {
    totalOrders: 1250,
    filledOrders: 1080,
    pendingOrders: 120,
    rejectedOrders: 50
  }
}

async function loadRecentOrders() {
  recentOrders.value = [
    {
      order_id: 'ORD001',
      symbol: '000001',
      side: 'buy',
      quantity: 1000,
      price: 10.5,
      status: 'filled',
      created_at: '2024-01-09 10:30:00'
    },
    {
      order_id: 'ORD002',
      symbol: '000002',
      side: 'sell',
      quantity: 500,
      price: 20.3,
      status: 'pending',
      created_at: '2024-01-09 10:25:00'
    },
    {
      order_id: 'ORD003',
      symbol: '000003',
      side: 'buy',
      quantity: 2000,
      price: 15.8,
      status: 'filled',
      created_at: '2024-01-09 10:20:00'
    }
  ]
}

function renderExecutionChart() {
  const data = [
    {
      x: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      y: [150, 230, 224, 218, 135, 147, 260],
      type: 'scatter',
      mode: 'lines+markers',
      name: '订单数'
    }
  ]
  
  const layout = {
    margin: { t: 20, r: 20, b: 40, l: 40 },
    showlegend: false
  }
  
  Plotly.newPlot(executionChartRef.value, data, layout, { responsive: true })
}

function renderSlippageChart() {
  const data = [
    {
      x: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      y: [0.05, 0.08, 0.06, 0.04, 0.07, 0.05, 0.06],
      type: 'bar',
      name: '滑点(%)'
    }
  ]
  
  const layout = {
    margin: { t: 20, r: 20, b: 40, l: 40 },
    showlegend: false
  }
  
  Plotly.newPlot(slippageChartRef.value, data, layout, { responsive: true })
}

function getStatusType(status) {
  const typeMap = {
    filled: 'success',
    pending: 'warning',
    cancelled: 'info',
    rejected: 'danger'
  }
  return typeMap[status] || 'info'
}

function getStatusText(status) {
  const textMap = {
    filled: '已成交',
    pending: '待处理',
    cancelled: '已取消',
    rejected: '已拒绝'
  }
  return textMap[status] || status
}
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 20px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 5px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
