import { useMemo, useState } from 'react'
import Card from '../../components/Card'
import DataTable from '../../components/DataTable'
import { formatCurrency, formatCurrencyFull, formatPercent, pnlColor } from '../../lib/utils'
import type { CsvTradeLog, MatchedTrade, CsvOpenPosition } from '../../types/csvReport'
import type { ColumnDef } from '@tanstack/react-table'

export default function CsvTradeLogPage({ data }: { data: CsvTradeLog }) {
  const [filter, setFilter] = useState({ search: '', type: '', direction: '' })

  const filteredTrades = useMemo(() => {
    let trades = data.completed_trades
    if (filter.search) {
      const q = filter.search.toLowerCase()
      trades = trades.filter(t => t.underlying.toLowerCase().includes(q) || t.symbol.toLowerCase().includes(q))
    }
    if (filter.type) trades = trades.filter(t => t.instrument_type === filter.type)
    if (filter.direction) trades = trades.filter(t => t.direction === filter.direction)
    return trades
  }, [data.completed_trades, filter])

  const tradeColumns = useMemo<ColumnDef<MatchedTrade, unknown>[]>(() => [
    { accessorKey: 'underlying', header: 'Underlying' },
    { accessorKey: 'instrument_type', header: 'Type' },
    { accessorKey: 'strike', header: 'Strike' },
    { accessorKey: 'direction', header: 'Dir', cell: i => {
      const v = i.getValue() as string
      return <span style={{ color: v === 'long' ? 'var(--accent-green)' : 'var(--accent-red)' }}>{v}</span>
    }},
    { accessorKey: 'entry_date', header: 'Entry', cell: i => (i.getValue() as string).slice(0, 10) },
    { accessorKey: 'exit_date', header: 'Exit', cell: i => (i.getValue() as string).slice(0, 10) },
    { accessorKey: 'quantity', header: 'Qty', cell: i => (i.getValue() as number).toLocaleString() },
    { accessorKey: 'entry_price', header: 'Entry ₹', cell: i => (i.getValue() as number).toFixed(2) },
    { accessorKey: 'exit_price', header: 'Exit ₹', cell: i => (i.getValue() as number).toFixed(2) },
    { accessorKey: 'pnl', header: 'P&L', cell: i => <span style={{ color: pnlColor(i.getValue() as number) }}>{formatCurrencyFull(i.getValue() as number)}</span> },
    { accessorKey: 'pnl_pct', header: 'P&L %', cell: i => <span style={{ color: pnlColor(i.getValue() as number) }}>{formatPercent(i.getValue() as number)}</span> },
    { accessorKey: 'capital', header: 'Capital', cell: i => formatCurrency(i.getValue() as number) },
    { accessorKey: 'hold_days', header: 'Hold', cell: i => `${i.getValue()}d` },
    { accessorKey: 'dte', header: 'DTE', cell: i => `${i.getValue()}d` },
  ], [])

  const openColumns = useMemo<ColumnDef<CsvOpenPosition, unknown>[]>(() => [
    { accessorKey: 'underlying', header: 'Underlying' },
    { accessorKey: 'instrument_type', header: 'Type' },
    { accessorKey: 'strike', header: 'Strike' },
    { accessorKey: 'side', header: 'Side' },
    { accessorKey: 'quantity', header: 'Qty', cell: i => (i.getValue() as number).toLocaleString() },
    { accessorKey: 'price', header: 'Price', cell: i => (i.getValue() as number).toFixed(2) },
    { accessorKey: 'entry_date', header: 'Entry', cell: i => (i.getValue() as string).slice(0, 10) },
    { accessorKey: 'expiry_date', header: 'Expiry' },
  ], [])

  return (
    <div className="space-y-6">
      {/* Filter Bar */}
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            placeholder="Search symbol or underlying..."
            value={filter.search}
            onChange={e => setFilter(f => ({ ...f, search: e.target.value }))}
            className="modal-input"
            style={{ maxWidth: 240 }}
          />
          <select
            value={filter.type}
            onChange={e => setFilter(f => ({ ...f, type: e.target.value }))}
            className="modal-input"
            style={{ maxWidth: 120 }}
          >
            <option value="">All Types</option>
            <option value="CE">CE</option>
            <option value="PE">PE</option>
            <option value="FUT">FUT</option>
          </select>
          <select
            value={filter.direction}
            onChange={e => setFilter(f => ({ ...f, direction: e.target.value }))}
            className="modal-input"
            style={{ maxWidth: 120 }}
          >
            <option value="">All Dirs</option>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {filteredTrades.length} of {data.completed_trades.length} trades
          </span>
        </div>
      </Card>

      {/* Trade Table */}
      <Card title="Completed Trades">
        <DataTable data={filteredTrades} columns={tradeColumns} pageSize={25} />
      </Card>

      {/* Open Positions */}
      {data.open_positions.length > 0 && (
        <Card title={`Open Positions (${data.open_positions.length})`}>
          <DataTable data={data.open_positions} columns={openColumns} pageSize={25} />
        </Card>
      )}
    </div>
  )
}
