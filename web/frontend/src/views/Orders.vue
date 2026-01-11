<template>
  <div class="orders">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>订单管理</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            创建订单
          </el-button>
        </div>
      </template>
      
      <el-form :model="filters" inline>
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
        
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="请选择" clearable>
            <el-option label="待处理" value="pending" />
            <el-option label="已成交" value="filled" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="已拒绝" value="rejected" />
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
          <el-button type="primary" @click="loadOrders">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
      
      <el-table
        :data="orders"
        stripe
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="order_id" label="订单ID" width="150" />
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="asset_type" label="资产类型" width="100" />
        <el-table-column prop="side" label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.side === 'buy' ? 'success' : 'danger'">
              {{ row.side === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="order_type" label="类型" width="100">
          <template #default="{ row }">
            {{ getOrderTypeText(row.order_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="price" label="价格" width="100" />
        <el-table-column prop="filled_quantity" label="已成交" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" fixed="right" width="200">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewOrder(row)">
              查看
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              link
              type="warning"
              @click="cancelOrder(row)"
            >
              取消
            </el-button>
            <el-button link type="primary" @click="viewFills(row)">
              成交
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadOrders"
        @current-change="loadOrders"
        style="margin-top: 20px; justify-content: flex-end"
      />
      
      <div v-if="selectedOrders.length > 0" style="margin-top: 20px">
        <el-button type="danger" @click="batchCancelOrders">
          批量取消 ({{ selectedOrders.length }})
        </el-button>
      </div>
    </el-card>
    
    <el-dialog
      v-model="showCreateDialog"
      title="创建订单"
      width="600px"
      @close="resetCreateForm"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
      >
        <el-form-item label="账户" prop="account_id">
          <el-select v-model="createForm.account_id" placeholder="请选择账户" style="width: 100%">
            <el-option
              v-for="account in accounts"
              :key="account.id"
              :label="account.account_name"
              :value="account.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="资产类型" prop="asset_type">
          <el-select v-model="createForm.asset_type" placeholder="请选择资产类型" style="width: 100%">
            <el-option label="股票" value="stock" />
            <el-option label="期货" value="futures" />
            <el-option label="期权" value="options" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="代码" prop="symbol">
          <el-input v-model="createForm.symbol" placeholder="请输入代码" />
        </el-form-item>
        
        <el-form-item label="方向" prop="side">
          <el-radio-group v-model="createForm.side">
            <el-radio label="buy">买入</el-radio>
            <el-radio label="sell">卖出</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item label="订单类型" prop="order_type">
          <el-select v-model="createForm.order_type" placeholder="请选择订单类型" style="width: 100%">
            <el-option label="市价单" value="market" />
            <el-option label="限价单" value="limit" />
            <el-option label="止损单" value="stop" />
            <el-option label="止损限价单" value="stop_limit" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="createForm.quantity" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        
        <el-form-item v-if="createForm.order_type !== 'market'" label="价格" prop="price">
          <el-input-number v-model="createForm.price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        
        <el-form-item v-if="createForm.order_type.includes('stop')" label="止损价格" prop="stop_price">
          <el-input-number v-model="createForm.stop_price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        
        <el-form-item label="有效期" prop="time_in_force">
          <el-select v-model="createForm.time_in_force" placeholder="请选择有效期" style="width: 100%">
            <el-option label="当日有效" value="DAY" />
            <el-option label="立即成交或取消" value="IOC" />
            <el-option label="全部成交或取消" value="FOK" />
            <el-option label="撤销前有效" value="GTC" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateOrder" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>
    
    <el-dialog v-model="showDetailDialog" title="订单详情" width="800px">
      <el-descriptions v-if="currentOrder" :column="2" border>
        <el-descriptions-item label="订单ID">{{ currentOrder.order_id }}</el-descriptions-item>
        <el-descriptions-item label="账户">{{ currentOrder.account_name }}</el-descriptions-item>
        <el-descriptions-item label="代码">{{ currentOrder.symbol }}</el-descriptions-item>
        <el-descriptions-item label="资产类型">{{ currentOrder.asset_type }}</el-descriptions-item>
        <el-descriptions-item label="方向">
          <el-tag :type="currentOrder.side === 'buy' ? 'success' : 'danger'">
            {{ currentOrder.side === 'buy' ? '买入' : '卖出' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="订单类型">{{ getOrderTypeText(currentOrder.order_type) }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ currentOrder.quantity }}</el-descriptions-item>
        <el-descriptions-item label="价格">{{ currentOrder.price }}</el-descriptions-item>
        <el-descriptions-item label="已成交">{{ currentOrder.filled_quantity }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentOrder.status)">
            {{ getStatusText(currentOrder.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentOrder.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ currentOrder.updated_at }}</el-descriptions-item>
        <el-descriptions-item label="有效期">{{ currentOrder.time_in_force }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentOrder.remark }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
    
    <el-dialog v-model="showFillsDialog" title="成交记录" width="800px">
      <el-table :data="fills" stripe>
        <el-table-column prop="fill_id" label="成交ID" width="150" />
        <el-table-column prop="side" label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.side === 'buy' ? 'success' : 'danger'">
              {{ row.side === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="成交价" width="100" />
        <el-table-column prop="quantity" label="成交数量" width="100" />
        <el-table-column prop="commission" label="手续费" width="100" />
        <el-table-column prop="fill_time" label="成交时间" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { orderApi } from '@/api/order'
import { accountApi } from '@/api/account'

const loading = ref(false)
const creating = ref(false)
const orders = ref([])
const accounts = ref([])
const selectedOrders = ref([])

const filters = ref({
  asset_type: '',
  account_id: '',
  status: '',
  dateRange: []
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const showFillsDialog = ref(false)
const createFormRef = ref(null)
const currentOrder = ref(null)
const fills = ref([])

const createForm = ref({
  account_id: '',
  asset_type: '',
  symbol: '',
  side: 'buy',
  order_type: 'market',
  quantity: 0,
  price: 0,
  stop_price: 0,
  time_in_force: 'DAY',
  remark: ''
})

const createRules = {
  account_id: [{ required: true, message: '请选择账户', trigger: 'change' }],
  asset_type: [{ required: true, message: '请选择资产类型', trigger: 'change' }],
  symbol: [{ required: true, message: '请输入代码', trigger: 'blur' }],
  side: [{ required: true, message: '请选择方向', trigger: 'change' }],
  order_type: [{ required: true, message: '请选择订单类型', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  price: [{ required: true, message: '请输入价格', trigger: 'blur' }],
  time_in_force: [{ required: true, message: '请选择有效期', trigger: 'change' }]
}

onMounted(() => {
  loadAccounts()
  loadOrders()
})

async function loadAccounts() {
  try {
    const response = await accountApi.getAccounts()
    accounts.value = response.accounts
  } catch (error) {
    console.error('Load accounts failed:', error)
  }
}

async function loadOrders() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      asset_type: filters.value.asset_type,
      account_id: filters.value.account_id,
      status: filters.value.status,
      start_time: filters.value.dateRange?.[0],
      end_time: filters.value.dateRange?.[1]
    }
    
    const response = await orderApi.getOrders(params)
    orders.value = response.orders
    pagination.value.total = response.total
  } catch (error) {
    console.error('Load orders failed:', error)
    ElMessage.error('加载订单失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = {
    asset_type: '',
    account_id: '',
    status: '',
    dateRange: []
  }
  loadOrders()
}

function handleSelectionChange(selection) {
  selectedOrders.value = selection
}

async function handleCreateOrder() {
  try {
    await createFormRef.value.validate()
    
    creating.value = true
    
    await orderApi.createOrder(createForm.value)
    
    ElMessage.success('订单创建成功')
    showCreateDialog.value = false
    resetCreateForm()
    loadOrders()
  } catch (error) {
    console.error('Create order failed:', error)
    ElMessage.error('订单创建失败')
  } finally {
    creating.value = false
  }
}

function resetCreateForm() {
  createForm.value = {
    account_id: '',
    asset_type: '',
    symbol: '',
    side: 'buy',
    order_type: 'market',
    quantity: 0,
    price: 0,
    stop_price: 0,
    time_in_force: 'DAY',
    remark: ''
  }
  createFormRef.value?.resetFields()
}

async function cancelOrder(order) {
  try {
    await ElMessageBox.confirm('确定要取消该订单吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await orderApi.cancelOrder(order.order_id)
    
    ElMessage.success('订单已取消')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Cancel order failed:', error)
      ElMessage.error('取消订单失败')
    }
  }
}

async function batchCancelOrders() {
  try {
    await ElMessageBox.confirm(`确定要取消选中的${selectedOrders.value.length}个订单吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const orderIds = selectedOrders.value.map(order => order.order_id)
    
    await orderApi.batchCancelOrders({ order_ids: orderIds })
    
    ElMessage.success('批量取消成功')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Batch cancel orders failed:', error)
      ElMessage.error('批量取消失败')
    }
  }
}

function viewOrder(order) {
  currentOrder.value = order
  showDetailDialog.value = true
}

async function viewFills(order) {
  try {
    const response = await orderApi.getOrderFills(order.order_id)
    fills.value = response
    showFillsDialog.value = true
  } catch (error) {
    console.error('Load fills failed:', error)
    ElMessage.error('加载成交记录失败')
  }
}

function getOrderTypeText(type) {
  const typeMap = {
    market: '市价单',
    limit: '限价单',
    stop: '止损单',
    stop_limit: '止损限价单'
  }
  return typeMap[type] || type
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
.orders {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
