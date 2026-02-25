import { useMemo } from 'react'
import StatCard from '../components/StatCard'
import Card from '../components/Card'
import ChartWrapper, { DarkTooltipStyle } from '../components/ChartWrapper'
import DataTable from '../components/DataTable'
import { formatCurrency, formatCurrencyFull, formatPercent, pnlColor } from '../lib/utils'
import type { OverviewData, SymbolPnl } from '../types/report'
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from 'recharts'
import type { ColumnDef } from '@tanstack/react-table'

export default function Overview({ data }: { data: OverviewData }) {
  const symbolColumns = useMemo<ColumnDef<SymbolPnl, unknown>[]>(
    () => [
      {
        accessorKey: 'symbol',
        header: 'Symbol',
        cell: (info) => info.getValue() as string,
      },
      {
        accessorKey: 'underlying',
        header: 'Underlying',
        cell: (info) => info.getValue() as string,
      },
      {
        accessorKey: 'type',
        header: 'Type',
        cell: (info) => info.getValue() as string,
      },
      {
        accessorKey: 'buy_value',
        header: 'Buy Value',
        cell: (info) => formatCurrency(info.getValue() as number),
      },
      {
        accessorKey: 'sell_value',
        header: 'Sell Value',
        cell: (info) => formatCurrency(info.getValue() as number),
      },
      {
        accessorKey: 'realized_pnl',
        header: 'Realized P&L',
        cell: (info) => {
          const value = info.getValue() as number
          return (
            <span style={{ color: pnlColor(value) }}>
              {formatCurrency(value)}
            </span>
          )
        },
      },
      {
        accessorKey: 'pnl_pct',
        header: 'P&L %',
        cell: (info) => {
          const value = info.getValue() as number
          return (
            <span style={{ color: pnlColor(value) }}>
              {formatPercent(value)}
            </span>
          )
        },
      },
    ],
    [],
  )

  const symbolTypeSubtext = Object.entries(data.symbols_by_type)
    .map(([type, count]) => `${type}: ${count}`)
    .join(' | ')

  return (
    <div className="space-y-6">
      {/* Row 1: 4 StatCards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Net Realized P&L"
          value={formatCurrency(data.net_realized_pnl)}
          accentColor={pnlColor(data.net_realized_pnl)}
        />
        <StatCard
          label="Unrealized P&L"
          value={formatCurrency(data.unrealized_pnl)}
          accentColor={pnlColor(data.unrealized_pnl)}
        />
        <StatCard
          label="Total Charges"
          value={formatCurrency(data.total_charges)}
          accentColor="var(--accent-red)"
        />
        <StatCard
          label="Net After Charges"
          value={formatCurrency(data.net_after_charges)}
          accentColor={pnlColor(data.net_after_charges)}
        />
      </div>

      {/* Row 2: Win Rate + Symbols | Buy/Sell Value | Winners/Losers/Breakeven */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="grid grid-cols-2 gap-4">
          <StatCard
            label="Win Rate"
            value={formatPercent(data.win_rate)}
            accentColor={data.win_rate >= 50 ? 'var(--accent-green)' : 'var(--accent-red)'}
          />
          <StatCard
            label="Symbols Traded"
            value={String(data.symbols_traded)}
            subtext={symbolTypeSubtext}
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <StatCard
            label="Total Buy Value"
            value={formatCurrency(data.total_buy_value)}
          />
          <StatCard
            label="Total Sell Value"
            value={formatCurrency(data.total_sell_value)}
          />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <StatCard
            label="Winners"
            value={String(data.winners)}
            accentColor="var(--accent-green)"
          />
          <StatCard
            label="Losers"
            value={String(data.losers)}
            accentColor="var(--accent-red)"
          />
          <StatCard
            label="Breakeven"
            value={String(data.breakeven)}
          />
        </div>
      </div>

      {/* Row 3: Avg Winner, Avg Loser, Win/Loss Ratio */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="Avg Winner"
          value={formatCurrency(data.avg_winner)}
          accentColor="var(--accent-green)"
        />
        <StatCard
          label="Avg Loser"
          value={formatCurrency(data.avg_loser)}
          accentColor="var(--accent-red)"
        />
        <StatCard
          label="Win/Loss Ratio"
          value={data.win_loss_ratio.toFixed(2)}
        />
      </div>

      {/* P&L Distribution */}
      <Card title="P&L Distribution">
        <ChartWrapper height={300}>
          <BarChart data={data.pnl_distribution}>
            <CartesianGrid strokeDasharray="3 3" stroke="#252525" />
            <XAxis
              dataKey="range"
              tick={{ fontSize: 11, fill: '#a0a0a0' }}
              angle={-30}
              textAnchor="end"
              height={60}
            />
            <YAxis tick={{ fontSize: 11, fill: '#a0a0a0' }} />
            <Tooltip
              {...DarkTooltipStyle()}
              formatter={(value: number) => [value, 'Count']}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {data.pnl_distribution.map((item, index) => (
                <Cell key={index} fill={item.min >= 0 ? '#22c55e' : '#eb3b3b'} />
              ))}
            </Bar>
          </BarChart>
        </ChartWrapper>
      </Card>

      {/* Return % Distribution */}
      <Card title="Return % Distribution">
        <ChartWrapper height={300}>
          <BarChart data={data.return_pct_distribution}>
            <CartesianGrid strokeDasharray="3 3" stroke="#252525" />
            <XAxis
              dataKey="range"
              tick={{ fontSize: 11, fill: '#a0a0a0' }}
              angle={-30}
              textAnchor="end"
              height={60}
            />
            <YAxis tick={{ fontSize: 11, fill: '#a0a0a0' }} />
            <Tooltip
              {...DarkTooltipStyle()}
              formatter={(value: number) => [value, 'Count']}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {data.return_pct_distribution.map((item, index) => (
                <Cell key={index} fill={item.min >= 0 ? '#22c55e' : '#eb3b3b'} />
              ))}
            </Bar>
          </BarChart>
        </ChartWrapper>
      </Card>

      {/* Symbol-wise P&L Table */}
      <Card title="Symbol-wise P&L">
        <DataTable data={data.symbol_wise_pnl} columns={symbolColumns} />
      </Card>
    </div>
  )
}
