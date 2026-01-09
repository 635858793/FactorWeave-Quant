<template>
  <div class="error-boundary">
    <slot v-if="!hasError" />
    
    <div v-else class="error-fallback">
      <el-result
        icon="error"
        title="页面出错了"
        :sub-title="errorMessage"
      >
        <template #extra>
          <el-button type="primary" @click="handleReload">
            刷新页面
          </el-button>
          <el-button @click="handleGoHome">
            返回首页
          </el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const props = defineProps({
  onError: {
    type: Function,
    default: null
  },
  fallbackComponent: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['error'])

const router = useRouter()
const hasError = ref(false)
const errorInfo = ref(null)
const errorMessage = ref('抱歉，页面加载时发生了错误')

onErrorCaptured((err, instance, info) => {
  console.error('ErrorBoundary捕获到错误:', err, info)
  
  hasError.value = true
  errorInfo.value = {
    error: err,
    instance,
    info
  }
  
  errorMessage.value = err.message || '抱歉，页面加载时发生了错误'
  
  emit('error', { error: err, instance, info })
  
  if (props.onError) {
    props.onError(err, instance, info)
  }
  
  ElMessage.error('页面发生错误，请刷新重试')
})

function handleReload() {
  window.location.reload()
}

function handleGoHome() {
  router.push('/')
}
</script>

<style scoped>
.error-boundary {
  width: 100%;
  height: 100%;
}

.error-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 20px;
}
</style>
