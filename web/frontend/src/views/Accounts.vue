<template>
  <div class="accounts">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>账户管理</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            添加账户
          </el-button>
        </div>
      </template>
      
      <el-table :data="accounts" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="account_name" label="账户名称" width="150" />
        <el-table-column prop="account_type" label="账户类型" width="120" />
        <el-table-column prop="institution" label="机构" width="150" />
        <el-table-column prop="account_code" label="账户代码" width="150" />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" fixed="right" width="300">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewAccount(row)">
              查看
            </el-button>
            <el-button link type="primary" @click="editAccount(row)">
              编辑
            </el-button>
            <el-button link type="warning" @click="testConnection(row)">
              测试连接
            </el-button>
            <el-button link type="danger" @click="deleteAccount(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <el-dialog
      v-model="showCreateDialog"
      :title="editingAccount ? '编辑账户' : '添加账户'"
      width="600px"
      @close="resetCreateForm"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
      >
        <el-form-item label="账户名称" prop="account_name">
          <el-input v-model="createForm.account_name" placeholder="请输入账户名称" />
        </el-form-item>
        
        <el-form-item label="账户类型" prop="account_type">
          <el-select v-model="createForm.account_type" placeholder="请选择账户类型" style="width: 100%">
            <el-option label="证券账户" value="securities" />
            <el-option label="期货账户" value="futures" />
            <el-option label="期权账户" value="options" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="机构" prop="institution">
          <el-input v-model="createForm.institution" placeholder="请输入机构名称" />
        </el-form-item>
        
        <el-form-item label="账户代码" prop="account_code">
          <el-input v-model="createForm.account_code" placeholder="请输入账户代码" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveAccount" :loading="saving">
          保存
        </el-button>
      </template>
    </el-dialog>
    
    <el-dialog v-model="showDetailDialog" title="账户详情" width="900px">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <el-descriptions v-if="currentAccount" :column="2" border>
            <el-descriptions-item label="账户ID">{{ currentAccount.id }}</el-descriptions-item>
            <el-descriptions-item label="账户名称">{{ currentAccount.account_name }}</el-descriptions-item>
            <el-descriptions-item label="账户类型">{{ currentAccount.account_type }}</el-descriptions-item>
            <el-descriptions-item label="机构">{{ currentAccount.institution }}</el-descriptions-item>
            <el-descriptions-item label="账户代码">{{ currentAccount.account_code }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="currentAccount.is_active ? 'success' : 'danger'">
                {{ currentAccount.is_active ? '启用' : '禁用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ currentAccount.created_at }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ currentAccount.updated_at }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        
        <el-tab-pane label="持仓信息" name="positions">
          <el-table :data="positions" stripe v-loading="positionsLoading">
            <el-table-column prop="symbol" label="代码" width="100" />
            <el-table-column prop="asset_type" label="资产类型" width="100" />
            <el-table-column prop="side" label="方向" width="80">
              <template #default="{ row }">
                <el-tag :type="row.side === 'long' ? 'success' : 'danger'">
                  {{ row.side === 'long' ? '多头' : '空头' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="quantity" label="数量" width="100" />
            <el-table-column prop="available_quantity" label="可用数量" width="100" />
            <el-table-column prop="avg_price" label="均价" width="100" />
            <el-table-column prop="current_price" label="现价" width="100" />
            <el-table-column prop="market_value" label="市值" width="100" />
            <el-table-column prop="profit_loss" label="盈亏" width="100">
              <template #default="{ row }">
                <span :style="{ color: row.profit_loss >= 0 ? '#67c23a' : '#f56c6c' }">
                  {{ row.profit_loss.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="profit_loss_ratio" label="盈亏比例" width="100">
              <template #default="{ row }">
                <span :style="{ color: row.profit_loss_ratio >= 0 ? '#67c23a' : '#f56c6c' }">
                  {{ (row.profit_loss_ratio * 100).toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        
        <el-tab-pane label="余额信息" name="balance">
          <el-descriptions v-if="balance" :column="2" border>
            <el-descriptions-item label="总余额">{{ balance.total_balance.toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="可用余额">{{ balance.available_balance.toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="冻结余额">{{ balance.frozen_balance.toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="市值">{{ balance.market_value.toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="总资产">{{ balance.total_asset.toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="盈亏">
              <span :style="{ color: balance.profit_loss >= 0 ? '#67c23a' : '#f56c6c' }">
                {{ balance.profit_loss.toFixed(2) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="盈亏比例">
              <span :style="{ color: balance.profit_loss_ratio >= 0 ? '#67c23a' : '#f56c6c' }">
                {{ (balance.profit_loss_ratio * 100).toFixed(2) }}%
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ balance.updated_at }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { accountApi } from '@/api/account'

const loading = ref(false)
const saving = ref(false)
const positionsLoading = ref(false)
const accounts = ref([])
const currentAccount = ref(null)
const positions = ref([])
const balance = ref(null)

const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const editingAccount = ref(null)
const activeTab = ref('basic')
const createFormRef = ref(null)

const createForm = ref({
  account_name: '',
  account_type: '',
  institution: '',
  account_code: ''
})

const createRules = {
  account_name: [{ required: true, message: '请输入账户名称', trigger: 'blur' }],
  account_type: [{ required: true, message: '请选择账户类型', trigger: 'change' }],
  institution: [{ required: true, message: '请输入机构名称', trigger: 'blur' }],
  account_code: [{ required: true, message: '请输入账户代码', trigger: 'blur' }]
}

onMounted(() => {
  loadAccounts()
})

async function loadAccounts() {
  loading.value = true
  try {
    const response = await accountApi.getAccounts()
    accounts.value = response.accounts
  } catch (error) {
    console.error('Load accounts failed:', error)
    ElMessage.error('加载账户失败')
  } finally {
    loading.value = false
  }
}

async function handleSaveAccount() {
  try {
    await createFormRef.value.validate()
    
    saving.value = true
    
    if (editingAccount.value) {
      await accountApi.updateAccount(editingAccount.value.id, createForm.value)
      ElMessage.success('账户更新成功')
    } else {
      await accountApi.createAccount(createForm.value)
      ElMessage.success('账户创建成功')
    }
    
    showCreateDialog.value = false
    resetCreateForm()
    loadAccounts()
  } catch (error) {
    console.error('Save account failed:', error)
    ElMessage.error('保存账户失败')
  } finally {
    saving.value = false
  }
}

function resetCreateForm() {
  createForm.value = {
    account_name: '',
    account_type: '',
    institution: '',
    account_code: ''
  }
  editingAccount.value = null
  createFormRef.value?.resetFields()
}

function editAccount(account) {
  editingAccount.value = account
  createForm.value = {
    account_name: account.account_name,
    account_type: account.account_type,
    institution: account.institution,
    account_code: account.account_code
  }
  showCreateDialog.value = true
}

async function viewAccount(account) {
  currentAccount.value = account
  activeTab.value = 'basic'
  showDetailDialog.value = true
  
  await loadPositions(account.id)
  await loadBalance(account.id)
}

async function loadPositions(accountId) {
  positionsLoading.value = true
  try {
    const response = await accountApi.getPositions(accountId)
    positions.value = response
  } catch (error) {
    console.error('Load positions failed:', error)
    ElMessage.error('加载持仓失败')
  } finally {
    positionsLoading.value = false
  }
}

async function loadBalance(accountId) {
  try {
    const response = await accountApi.getBalance(accountId)
    balance.value = response
  } catch (error) {
    console.error('Load balance failed:', error)
    ElMessage.error('加载余额失败')
  }
}

async function testConnection(account) {
  try {
    const response = await accountApi.testConnection(account.id)
    if (response.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error(response.message || '连接测试失败')
    }
  } catch (error) {
    console.error('Test connection failed:', error)
    ElMessage.error('连接测试失败')
  }
}

async function deleteAccount(account) {
  try {
    await ElMessageBox.confirm('确定要删除该账户吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await accountApi.deleteAccount(account.id)
    
    ElMessage.success('账户已删除')
    loadAccounts()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete account failed:', error)
      ElMessage.error('删除账户失败')
    }
  }
}
</script>

<style scoped>
.accounts {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
