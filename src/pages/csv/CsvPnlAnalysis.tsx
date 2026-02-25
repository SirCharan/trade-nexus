import { useMemo } from 'react'
import Card from '../../components/Card'
import ChartWrapper, { DarkTooltipStyle } from '../../components/ChartWrapper'
import DataTable from '../../components/DataTable'
import { formatCurrency, formatCurrencyFull, formatPercent, pnlColor } from '../../lib/utils'
import type { CsvPnlAnalysis, MonthlyRow, DayOfWeekRow } from '../../types/csvReport'
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from 'recharts'
import type { ColumnDef } from '@tanstack/react-table'

export default function CsvPnlAnalysisPage({ data }: { data: CsvPnlAnalysis }) {
  const monthlyColumns = useMemo<ColumnDef<MonthlyRow, unknown>[]>(() => [
    { accessorKey: 'month', header: 'Month' },
    { accessorKey: 'trades', header: 'Trades' },
    { accessorKey: 'gross_pnl', header: 'Gross P&L', cell: i => <span style={{ color: pnlColor(i.getValue() as number) }}>{formatCurrencyFull(i.getValue() as number)}</span> },
    { accessorKey: 'win_rate', header: 'Win Rate', cell: i => formatPercent(i.getValue() as number) },
    { accessorKey: 'avg_pnl', header: 'Avg P&L', cell: i => <span style={{ color: pnlColor(i.getValue() as number) }}>{formatCurrency(i.getValue() as number)}</span> },
    { accessorKey: 'largest_win', header: 'Best', cell: i => <span style={{ color: 'var(--accent-green)' }}>{formatCurrency(i.getValue() as number)}</span> },
    { accessorKey: 'largest_loss', header: 'Worst', cell: i => <span style={{ color: 'var(--accent-red)' }}>{formatCurrency(i.getValue() as number)}</span> },
    { accessorKey: 'profit_factor', header: 'PF', cell: i => (i.getValue() as number).toFixed(2) },
  ], [])

  const dowColumns = useMemo<ColumnDef<DayOfWeekRow, unknown>[]>(() => [
    { accessorKey: 'day', header: 'Day' },
    { accessorKey: 'trade_count', header: 'Trades' },
    { accessorKey: 'total_pnl', header: 'Total P&L', cell: i => <span style={{ color: pnlColor(i.getValue() as number) }}>{formatCurrencyFull(i.getValue() as number)}</span> },
    { accessorKey: 'avg_pnl', header: 'Avg P&L', cell: i => <span style={{ color: pnlColor(i.getValue() as number) }}>{formatCurrency(i.getValue() as number)}</span> },
    { accessorKey: 'win_rate', header: 'Win Rate', cell: i => formatPercent(i.getValue() as number) },
  ], [])

  // Heatmap: group by month
  const heatmapMonths = useMemo(() => {
    const months: Record<string, { date: string; pnl: number }[]> = {}
    for (const d of data.daily_heatmap) {
      const m = d.date.slice(0, 7)
      if (!months[m]) months[m] = []
      months[m].push(d)
    }
    return Object.entries(months).sort(([a], [b]) => a.localeCompare(b))
  }, [data.daily_heatmap])

  const maxAbsPnl = useMemo(() => {
    const vals = data.daily_heatmap.map(d => Math.abs(d.pnl))
    return vals.length ? Math.max(...vals) : 1
  }, [data.daily_heatmap])

  return (
    <div className="space-y-6">
      {/* Monthly Performance Table */}
      <Card title="Monthly Performance">
        <DataTable data={data.monthly_table} columns={monthlyColumns} pageSize={24} />
      </Card>

      {/* Daily P&L Heatmap */}
      <Card title="Daily P&L Heatmap">
        <div className="space-y-3">
          {heatmapMonths.map(([month, days]) => (
            <div key={month}>
              <div className="text-xs font-semibold mb-1" style={{ color: 'var(--text-secondary)' }}>{month}</div>
              <div className="flex flex-wrap gap-1">
                {days.map(d => {
                  const alpha = 0.2 + (Math.abs(d.pnl) / maxAbsPnl) * 0.8
                  const color = d.pnl >= 0 ? `rgba(34, 197, 94, ${alpha})` : `rgba(235, 59, 59, ${alpha})`
                  return (
                    <div
                      key={d.date}
                      title={`${d.date}: ${formatCurrencyFull(d.pnl)}`}
                      className="rounded-sm cursor-default"
                      style={{ width: 14, height: 14, background: color }}
                    />
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Day of Week */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="P&L by Day of Week">
          <ChartWrapper height={250}>
            <BarChart data={data.day_of_week}>
              <CartesianGrid strokeDasharray="3 3" stroke="#252525" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#555' }} />
              <YAxis tick={{ fontSize: 11, fill: '#555' }} tickFormatter={(v: number) => formatCurrency(v)} />
              <Tooltip {...DarkTooltipStyle()} formatter={(v: number) => [formatCurrencyFull(v), 'Total P&L']} />
              <Bar dataKey="total_pnl" radius={[4, 4, 0, 0]}>
                {data.day_of_week.map((d, i) => (
                  <Cell key={i} fill={d.total_pnl >= 0 ? '#22c55e' : '#eb3b3b'} />
                ))}
              </Bar>
            </BarChart>
          </ChartWrapper>
          <DataTable data={data.day_of_week} columns={dowColumns} pageSize={7} />
        </Card>

        <Card title="Trades per Day">
          <ChartWrapper height={250}>
            <BarChart data={data.trades_per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="#252525" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#555' }} />
              <YAxis tick={{ fontSize: 11, fill: '#555' }} />
              <Tooltip {...DarkTooltipStyle()} formatter={(v: number) => [v, 'Trades']} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} fill="#3b82f6" />
            </BarChart>
          </ChartWrapper>
        </Card>
      </div>
    </div>
  )
}
