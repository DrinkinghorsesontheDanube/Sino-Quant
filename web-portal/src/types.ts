/** 与后端 quant-gateway 的 JSON 契约一一对应。 */

export interface RunListItem {
  run_id: string
  strategy: string
  start: string
  end: string
  has_trades: boolean
  created_at: string
}

export type MetricKey =
  | 'cumulative_return'
  | 'annualized_return'
  | 'annualized_volatility'
  | 'sharpe_ratio'
  | 'max_drawdown'
  | 'turnover_rate'

export type Metrics = Partial<Record<MetricKey, number | null>>

export interface CurvePoint {
  date: string | null
  equity: number | null
  drawdown: number | null
}

export interface RunSummary {
  run_id: string
  strategy: string
  start: string
  end: string
  metrics: Metrics
  curve: CurvePoint[]
}

export interface TradeRow {
  date: string | null
  symbol: string | null
  side: 'BUY' | 'SELL' | null
  shares: number | null
  price: number | null
  commission: number | null
  tax: number | null
  fee: number | null
}

export interface TradesPayload {
  count: number
  trades: TradeRow[]
}

export interface BacktestParams {
  start: string
  end: string
  lookback: number
  holdings: number
  rebalance: number
  source: 'synthetic' | 'real'
}

export interface JobStatus {
  job_id: string
  kind: string
  status: 'running' | 'succeeded' | 'failed'
  error: string | null
  result: {
    run_id: string
    metrics: Record<string, number | null>
    trades: number
    days: number
  } | null
}
