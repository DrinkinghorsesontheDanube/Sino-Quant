<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItem,
  NInputNumber,
  NModal,
  NSelect,
  NSpin,
  NTag,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'
import { fetchJob, fetchReports, postBacktest } from '@/services/api'
import type { BacktestParams, JobStatus, RunListItem } from '@/types'

const router = useRouter()
const message = useMessage()

const runs = ref<RunListItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const showModal = ref(false)
const submitting = ref(false)
const job = ref<JobStatus | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const DEFAULT_PARAMS: BacktestParams = {
  start: '20240102',
  end: new Date().toISOString().slice(0, 10).replace(/-/g, ''),
  lookback: 60,
  holdings: 10,
  rebalance: 5,
  source: 'synthetic',
}
const form = ref<BacktestParams>({ ...DEFAULT_PARAMS })
const dateRange = ref<[number, number] | null>(null)

const sourceOptions = [
  { label: '合成数据（秒级演示，无需联网）', value: 'synthetic' },
  { label: '真实行情（AkShare/腾讯，首次下载较慢）', value: 'real' },
]

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

async function load() {
  try {
    runs.value = (await fetchReports()).runs
    error.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function openModal() {
  form.value = { ...DEFAULT_PARAMS }
  job.value = null
  const end = new Date()
  const start = new Date(end.getTime() - 365 * 24 * 3600 * 1000)
  dateRange.value = [start.getTime(), end.getTime()]
  showModal.value = true
}

function syncDates() {
  if (!dateRange.value) return
  const fmt = (ms: number) => new Date(ms).toISOString().slice(0, 10).replace(/-/g, '')
  form.value.start = fmt(dateRange.value[0])
  form.value.end = fmt(dateRange.value[1])
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function submit() {
  syncDates()
  submitting.value = true
  job.value = null
  try {
    const { job_id } = await postBacktest(form.value)
    pollTimer = setInterval(async () => {
      try {
        job.value = await fetchJob(job_id)
        if (job.value.status === 'succeeded') {
          stopPolling()
          submitting.value = false
          message.success(`回测完成：${job.value.result?.trades ?? 0} 笔成交，已加入报告列表`)
          await load()
        } else if (job.value.status === 'failed') {
          stopPolling()
          submitting.value = false
        }
      } catch {
        /* 网络抖动时下一轮轮询会重试 */
      }
    }, 1200)
  } catch (err) {
    submitting.value = false
    message.error(err instanceof Error ? err.message : String(err))
  }
}

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

<template>
  <div>
    <div style="display: flex; align-items: center; justify-content: space-between; margin: 4px 0 16px">
      <h1 class="page-title" style="margin: 0">A 股量化 · 回测报告</h1>
      <n-button type="primary" @click="openModal">+ 新建回测</n-button>
    </div>

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
          empty-description="reports/ 目录下暂无回测报告，点击右上角新建回测跑一个"
        />
      </n-card>
    </n-spin>

    <n-modal
      v-model:show="showModal"
      preset="card"
      title="新建回测 · 动量策略"
      style="width: 560px"
      :mask-closable="!submitting"
    >
      <n-form label-placement="left" label-width="110" :disabled="submitting">
        <n-form-item label="回测区间">
          <n-date-picker v-model:value="dateRange" type="daterange" clearable style="width: 100%" @update:value="syncDates" />
        </n-form-item>
        <n-form-item label="数据源">
          <n-select v-model:value="form.source" :options="sourceOptions" />
        </n-form-item>
        <n-form-item label="动量回看天数">
          <n-input-number v-model:value="form.lookback" :min="5" :max="250" style="width: 100%" />
        </n-form-item>
        <n-form-item label="持仓数量">
          <n-input-number v-model:value="form.holdings" :min="1" :max="15" style="width: 100%" />
        </n-form-item>
        <n-form-item label="调仓间隔(日)">
          <n-input-number v-model:value="form.rebalance" :min="1" :max="60" style="width: 100%" />
        </n-form-item>
      </n-form>

      <div v-if="submitting && job" style="text-align: center; padding: 8px 0 4px">
        <n-spin size="small" />
        <p style="opacity: 0.7; margin-top: 8px">正在运行回测，合成数据约需数秒，真实行情首次下载数分钟…</p>
      </div>
      <n-alert v-if="job?.status === 'failed'" type="error" style="margin-top: 8px">
        回测失败：{{ job.error }}
      </n-alert>

      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 10px">
          <n-button :disabled="submitting" @click="showModal = false">关闭</n-button>
          <n-button type="primary" :loading="submitting" @click="submit">开始回测</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

