<template>
  <div class="data-table">
    <el-table
      :data="data"
      :loading="loading"
      :stripe="stripe"
      :border="border"
      :height="height"
      :max-height="maxHeight"
      @selection-change="handleSelectionChange"
      @sort-change="handleSortChange"
      v-bind="$attrs"
    >
      <slot></slot>
    </el-table>
    
    <el-pagination
      v-if="showPagination"
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="pageSizes"
      :layout="paginationLayout"
      :background="true"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      style="margin-top: 20px; justify-content: flex-end"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  stripe: {
    type: Boolean,
    default: true
  },
  border: {
    type: Boolean,
    default: true
  },
  height: {
    type: [String, Number],
    default: null
  },
  maxHeight: {
    type: [String, Number],
    default: null
  },
  showPagination: {
    type: Boolean,
    default: true
  },
  total: {
    type: Number,
    default: 0
  },
  currentPage: {
    type: Number,
    default: 1
  },
  pageSize: {
    type: Number,
    default: 20
  },
  pageSizes: {
    type: Array,
    default: () => [10, 20, 50, 100]
  },
  paginationLayout: {
    type: String,
    default: 'total, sizes, prev, pager, next, jumper'
  }
})

const emit = defineEmits(['selection-change', 'sort-change', 'size-change', 'current-change'])

function handleSelectionChange(selection) {
  emit('selection-change', selection)
}

function handleSortChange(sort) {
  emit('sort-change', sort)
}

function handleSizeChange(size) {
  emit('size-change', size)
}

function handleCurrentChange(page) {
  emit('current-change', page)
}
</script>

<style scoped>
.data-table {
  width: 100%;
}
</style>
