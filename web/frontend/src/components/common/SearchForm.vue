<template>
  <div class="search-form">
    <el-form :model="formData" inline>
      <el-form-item v-for="field in fields" :key="field.prop" :label="field.label">
        <el-input
          v-if="field.type === 'input'"
          v-model="formData[field.prop]"
          :placeholder="field.placeholder"
          clearable
          @clear="handleClear(field.prop)"
        />
        
        <el-select
          v-else-if="field.type === 'select'"
          v-model="formData[field.prop]"
          :placeholder="field.placeholder"
          clearable
          @clear="handleClear(field.prop)"
        >
          <el-option
            v-for="option in field.options"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        
        <el-date-picker
          v-else-if="field.type === 'date'"
          v-model="formData[field.prop]"
          type="date"
          :placeholder="field.placeholder"
          clearable
          @clear="handleClear(field.prop)"
        />
        
        <el-date-picker
          v-else-if="field.type === 'daterange'"
          v-model="formData[field.prop]"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          clearable
          @clear="handleClear(field.prop)"
        />
        
        <el-input-number
          v-else-if="field.type === 'number'"
          v-model="formData[field.prop]"
          :placeholder="field.placeholder"
          :min="field.min"
          :max="field.max"
        />
      </el-form-item>
      
      <el-form-item>
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
        <el-button @click="handleReset">
          <el-icon><Refresh /></el-icon>
          重置
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'

const props = defineProps({
  fields: {
    type: Array,
    required: true,
    default: () => []
  },
  modelValue: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue', 'search', 'reset'])

const formData = ref({ ...props.modelValue })

watch(() => props.modelValue, (newVal) => {
  formData.value = { ...newVal }
}, { deep: true })

watch(formData, (newVal) => {
  emit('update:modelValue', newVal)
}, { deep: true })

function handleSearch() {
  emit('search', formData.value)
}

function handleReset() {
  const resetData = {}
  props.fields.forEach(field => {
    resetData[field.prop] = field.defaultValue || ''
  })
  formData.value = resetData
  emit('reset', resetData)
}

function handleClear(prop) {
  formData.value[prop] = ''
}
</script>

<style scoped>
.search-form {
  margin-bottom: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
}
</style>
