<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NCard, NDataTable, NSpin, NTag, type DataTableColumns } from 'naive-ui'
import { fetchReports } from '@/services/api'
import type { RunListItem } from '@/types'

const router = useRouter()
const runs = ref<RunListItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

function formatWindow(row: RunListItem) {
  const pretty = (raw: string) => `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`
  return `${pretty(row.start)} → ${pretty(row.end)}`
}

const columns = computed<DataTableColumns<RunListItem>>(() => [
  { title: '策略', key: 'strategy', render: (row) => h(NTag, { size: 'small', bordered: false }, { default: () => row.strategy }) },
  { title: '回测区间', key: 'window', render: (row) => formatWindow(row) },
  { title: '生成时间', key: 'created_at', width: 180 },
  {
    title: '操作',
    key: 'actions',
    width: 110,
    render: (row) =>
      h(
        NButton,
        { size: 'small', secondary: true, type: 'primary', onClick: () => router.push(`/a-share/${row.run_id}`) },
        { default: () => '查看详情' },
      ),
  },
])

onMounted(async () => {
  try {
    runs.value = (await fetchReports()).runs
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="page-title">A 股量化 · 回测报告</h1>
    <n-alert v-if="error" type="error" :show-icon="true" style="margin-bottom: 16px">
      无法加载报告列表：{{ error }}（请确认网关已在 8600 端口运行）
    </n-alert>
    <n-spin :show="loading">
      <n-card :bordered="false" content-style="padding: 8px 12px;">
        <n-data-table
          :columns="columns"
          :data="runs"
          :bordered="false"
          :single-line="false"
          :pagination="{ pageSize: 15 }"
          empty-description="reports/ 目录下暂无回测报告"
        />
      </n-card>
    </n-spin>
  </div>
</template>
