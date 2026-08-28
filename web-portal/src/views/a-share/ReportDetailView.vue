<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  NAlert,
  NBackTop,
  NCard,
  NDataTable,
  NGrid,
  NGridItem,
  NSpin,
  NStatistic,
  NTag,
  type DataTableColumns,
} from 'naive-ui'
import { fetchSummary, fetchTrades } from '@/services/api'
import type { Metrics, RunSummary, TradeRow, TradesPayload } from '@/types'

const props = defineProps<{ runId: string }>()

const summary = ref<RunSummary | null>(null)
const tradesPayload = ref<TradesPayload | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function pct(value: number | null | undefined): string {
  return value == null ? '—' : `${(value * 100).toFixed(2)}%`
}

function ratio(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2)
}

const metricCards = computed(() => {
  const metrics: Metrics = summary.value?.metrics ?? {}
  return [
    { label: '累计收益', value: pct(metrics.cumulative_return), tone: metrics.cumulative_return != null && metrics.cumulative_return >= 0 ? '#63e2b7' : '#e88080' },
    { label: '年化收益', value: pct(metrics.annualized_return), tone: metrics.annualized_return != null && metrics.annualized_return >= 0 ? '#63e2b7' : '#e88080' },
    { label: '年化波动', value: pct(metrics.annualized_volatility), tone: undefined },
    { label: '夏普比率', value: ratio(metrics.sharpe_ratio), tone: undefined },
    { label: '最大回撤', value: pct(metrics.max_drawdown), tone: '#e88080' },
    { label: '年化换手', value: pct(metrics.turnover_rate), tone: undefined },
  ]
})

const paramsLine = computed(() => {
  const params = summary.value?.params
  if (!params) return null
  return `动量回看 ${params.lookback ?? '—'} 日 · 持仓 ${params.holdings ?? '—'} 只 · 调仓间隔 ${params.rebalance ?? '—'} 交易日`
})

const tradeColumns = computed<DataTableColumns<TradeRow>>(() => [
  { title: '日期', key: 'date', width: 120, render: (row) => row.date?.slice(0, 10) ?? '—' },
  { title: '代码', key: 'symbol', width: 100 },
  {
    title: '方向',
    key: 'side',
    width: 90,
    render: (row) =>
      h(NTag, { size: 'small', type: row.side === 'BUY' ? 'success' : 'error', bordered: false }, { default: () => row.side ?? '—' }),
  },
  { title: '数量', key: 'shares', width: 100, render: (row) => String(row.shares ?? '—') },
  { title: '价格', key: 'price', render: (row) => row.price?.toFixed(3) ?? '—' },
  { title: '佣金', key: 'commission', render: (row) => row.commission?.toFixed(2) ?? '—' },
  { title: '印花税', key: 'tax', render: (row) => row.tax?.toFixed(2) ?? '—' },
  { title: '费用合计', key: 'fee', render: (row) => row.fee?.toFixed(2) ?? '—' },
])

function renderChart() {
  if (!chartEl.value || !summary.value || summary.value.curve.length === 0) return
  if (!chart) chart = echarts.init(chartEl.value)

  const dates = summary.value.curve.map((point) => point.date?.slice(0, 10) ?? '')
  const equity = summary.value.curve.map((point) => point.equity)
  const drawdown = summary.value.curve.map((point) => point.drawdown == null ? null : point.drawdown * 100)

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: unknown) =>
        typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value ?? '—'),
    },
    legend: { top: 4, textStyle: { color: 'rgba(255,255,255,.65)' } },
    grid: { left: 70, right: 62, top: 36, bottom: 32 },
    xAxis: { type: 'category', data: dates, boundaryGap: false, axisLabel: { color: 'rgba(255,255,255,.45)' } },
    yAxis: [
      {
        type: 'value',
        name: '净值',
        scale: true,
        axisLabel: { formatter: (v: number) => v.toLocaleString(), color: 'rgba(255,255,255,.55)' },
        splitLine: { lineStyle: { opacity: 0.12 } },
      },
      {
        type: 'value',
        name: '回撤%',
        max: 0,
        axisLabel: { formatter: '{value}', color: 'rgba(255,255,255,.35)' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '账户净值',
        type: 'line',
        yAxisIndex: 0,
        data: equity,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#5b8ff9' },
        areaStyle: { opacity: 0.12, color: '#5b8ff9' },
      },
      {
        name: '动态回撤',
        type: 'line',
        yAxisIndex: 1,
        data: drawdown,
        showSymbol: false,
        lineStyle: { width: 1.2, color: '#e88080' },
      },
    ],
  })
}

function onResize() {
  chart?.resize()
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const [summaryData, tradesData] = await Promise.all([fetchSummary(props.runId), fetchTrades(props.runId)])
    summary.value = summaryData
    tradesPayload.value = tradesData
    // 等待 v-if 的图表容器出现后再绘制
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
    renderChart()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

watch(() => props.runId, load)

onMounted(() => {
  void load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div>
    <n-back-top :right="40" />
    <h1 class="page-title">回测详情 · {{ runId }}</h1>
    <p v-if="paramsLine" style="opacity: 0.6; margin: -6px 0 14px">
      {{ paramsLine }}<template v-if="summary?.created_at"> · 生成于 {{ summary.created_at }}</template>
    </p>

    <n-spin :show="loading">
      <n-alert v-if="error" type="error" style="margin-bottom: 16px">{{ error }}</n-alert>

      <template v-if="summary">
        <n-grid x-gap="14" y-gap="14" cols="2 s:3 l:6" responsive="screen" style="margin-bottom: 18px">
          <n-grid-item v-for="card in metricCards" :key="card.label">
            <n-card size="small" content-style="padding: 12px 16px;">
              <n-statistic :label="card.label">
                <span :style="{ color: card.tone ?? 'inherit', fontSize: '20px', fontWeight: 600 }">
                  {{ card.value }}
                </span>
              </n-statistic>
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-card title="净值与动态回撤" size="small" style="margin-bottom: 18px">
          <div ref="chartEl" style="width: 100%; height: 380px" />
        </n-card>

        <n-card :title="`成交明细（${tradesPayload?.count ?? 0} 笔）`" size="small" content-style="padding: 8px 12px;">
          <n-data-table
            :columns="tradeColumns"
            :data="tradesPayload?.trades ?? []"
            :bordered="false"
            :single-line="false"
            max-height="420px"
            :pagination="{ pageSize: 50 }"
          />
        </n-card>
      </template>
    </n-spin>
  </div>
</template>
