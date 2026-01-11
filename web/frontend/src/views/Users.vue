<template>
  <div class="users">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            添加用户
          </el-button>
        </div>
      </template>
      
      <el-form :model="filters" inline>
        <el-form-item label="用户名">
          <el-input v-model="filters.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        
        <el-form-item label="邮箱">
          <el-input v-model="filters.email" placeholder="请输入邮箱" clearable />
        </el-form-item>
        
        <el-form-item label="状态">
          <el-select v-model="filters.is_active" placeholder="请选择" clearable>
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="loadUsers">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
      
      <el-table :data="users" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="email" label="邮箱" width="180" />
        <el-table-column prop="full_name" label="全名" width="120" />
        <el-table-column prop="phone" label="电话" width="120" />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_admin" label="管理员" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_admin ? 'warning' : 'info'">
              {{ row.is_admin ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="two_fa_enabled" label="2FA" width="80">
          <template #default="{ row }">
            <el-tag :type="row.two_fa_enabled ? 'success' : 'info'">
              {{ row.two_fa_enabled ? '已启用' : '未启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login_at" label="最后登录" width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" fixed="right" width="300">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewUser(row)">
              查看
            </el-button>
            <el-button link type="primary" @click="editUser(row)">
              编辑
            </el-button>
            <el-button link type="warning" @click="manageRoles(row)">
              角色
            </el-button>
            <el-button link type="danger" @click="deleteUser(row)">
              删除
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
        @size-change="loadUsers"
        @current-change="loadUsers"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
    
    <el-dialog
      v-model="showCreateDialog"
      :title="editingUser ? '编辑用户' : '添加用户'"
      width="600px"
      @close="resetCreateForm"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="请输入用户名" />
        </el-form-item>
        
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="createForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        
        <el-form-item v-if="!editingUser" label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        
        <el-form-item label="全名" prop="full_name">
          <el-input v-model="createForm.full_name" placeholder="请输入全名" />
        </el-form-item>
        
        <el-form-item label="电话" prop="phone">
          <el-input v-model="createForm.phone" placeholder="请输入电话" />
        </el-form-item>
        
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="createForm.is_active" />
        </el-form-item>
        
        <el-form-item label="管理员" prop="is_admin">
          <el-switch v-model="createForm.is_admin" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveUser" :loading="saving">
          保存
        </el-button>
      </template>
    </el-dialog>
    
    <el-dialog v-model="showDetailDialog" title="用户详情" width="800px">
      <el-descriptions v-if="currentUser" :column="2" border>
        <el-descriptions-item label="用户ID">{{ currentUser.id }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ currentUser.username }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ currentUser.email }}</el-descriptions-item>
        <el-descriptions-item label="全名">{{ currentUser.full_name }}</el-descriptions-item>
        <el-descriptions-item label="电话">{{ currentUser.phone }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentUser.is_active ? 'success' : 'danger'">
            {{ currentUser.is_active ? '启用' : '禁用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="管理员">
          <el-tag :type="currentUser.is_admin ? 'warning' : 'info'">
            {{ currentUser.is_admin ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="2FA">
          <el-tag :type="currentUser.two_fa_enabled ? 'success' : 'info'">
            {{ currentUser.two_fa_enabled ? '已启用' : '未启用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最后登录">{{ currentUser.last_login_at }}</el-descriptions-item>
        <el-descriptions-item label="最后登录IP">{{ currentUser.last_login_ip }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentUser.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ currentUser.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
    
    <el-dialog v-model="showRolesDialog" title="角色管理" width="600px">
      <el-transfer
        v-model="selectedRoles"
        :data="allRoles"
        :titles="['可选角色', '已选角色']"
        :props="{ key: 'id', label: 'name' }"
      />
      
      <template #footer>
        <el-button @click="showRolesDialog = false">取消</el-button>
        <el-button type="primary" @click="saveRoles" :loading="savingRoles">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { authApi } from '@/api/auth'

const loading = ref(false)
const saving = ref(false)
const savingRoles = ref(false)
const users = ref([])
const allRoles = ref([])
const selectedRoles = ref([])

const filters = ref({
  username: '',
  email: '',
  is_active: ''
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const showRolesDialog = ref(false)
const editingUser = ref(null)
const currentUser = ref(null)
const currentUserId = ref(null)
const createFormRef = ref(null)

const createForm = ref({
  username: '',
  email: '',
  password: '',
  full_name: '',
  phone: '',
  is_active: true,
  is_admin: false
})

const createRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于8位', trigger: 'blur' }
  ]
}

onMounted(() => {
  loadUsers()
  loadRoles()
})

async function loadUsers() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      username: filters.value.username,
      email: filters.value.email,
      is_active: filters.value.is_active
    }
    
    const response = await authApi.getUsers(params)
    users.value = response.users
    pagination.value.total = response.total
  } catch (error) {
    console.error('Load users failed:', error)
    ElMessage.error('加载用户失败')
  } finally {
    loading.value = false
  }
}

async function loadRoles() {
  try {
    const response = await authApi.getRoles()
    allRoles.value = response.roles
  } catch (error) {
    console.error('Load roles failed:', error)
  }
}

function resetFilters() {
  filters.value = {
    username: '',
    email: '',
    is_active: ''
  }
  loadUsers()
}

async function handleSaveUser() {
  try {
    await createFormRef.value.validate()
    
    saving.value = true
    
    if (editingUser.value) {
      await authApi.updateUser(editingUser.value.id, createForm.value)
      ElMessage.success('用户更新成功')
    } else {
      await authApi.register(createForm.value)
      ElMessage.success('用户创建成功')
    }
    
    showCreateDialog.value = false
    resetCreateForm()
    loadUsers()
  } catch (error) {
    console.error('Save user failed:', error)
    ElMessage.error('保存用户失败')
  } finally {
    saving.value = false
  }
}

function resetCreateForm() {
  createForm.value = {
    username: '',
    email: '',
    password: '',
    full_name: '',
    phone: '',
    is_active: true,
    is_admin: false
  }
  editingUser.value = null
  createFormRef.value?.resetFields()
}

function editUser(user) {
  editingUser.value = user
  createForm.value = {
    username: user.username,
    email: user.email,
    password: '',
    full_name: user.full_name,
    phone: user.phone,
    is_active: user.is_active,
    is_admin: user.is_admin
  }
  showCreateDialog.value = true
}

function viewUser(user) {
  currentUser.value = user
  showDetailDialog.value = true
}

async function manageRoles(user) {
  currentUserId.value = user.id
  
  try {
    const response = await authApi.getUserRoles(user.id)
    selectedRoles.value = response.roles.map(role => role.id)
    showRolesDialog.value = true
  } catch (error) {
    console.error('Load user roles failed:', error)
    ElMessage.error('加载用户角色失败')
  }
}

async function saveRoles() {
  savingRoles.value = true
  try {
    await authApi.updateUserRoles(currentUserId.value, { role_ids: selectedRoles.value })
    
    ElMessage.success('角色保存成功')
    showRolesDialog.value = false
  } catch (error) {
    console.error('Save roles failed:', error)
    ElMessage.error('保存角色失败')
  } finally {
    savingRoles.value = false
  }
}

async function deleteUser(user) {
  try {
    await ElMessageBox.confirm('确定要删除该用户吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await authApi.deleteUser(user.id)
    
    ElMessage.success('用户已删除')
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete user failed:', error)
      ElMessage.error('删除用户失败')
    }
  }
}
</script>

<style scoped>
.users {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
