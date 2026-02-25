import { useState, lazy, Suspense } from 'react'
import { Calendar } from 'lucide-react'
import { ReportProvider, useReport } from './context/ReportContext'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import UploadZone from './components/UploadZone'
import { formatCurrency } from './lib/utils'

const Overview = lazy(() => import('./pages/Overview'))
const PerformanceAttribution = lazy(() => import('./pages/PerformanceAttribution'))
const InstrumentBreakdown = lazy(() => import('./pages/InstrumentBreakdown'))
const ChargesCosts = lazy(() => import('./pages/ChargesCosts'))
const OpenPortfolio = lazy(() => import('./pages/OpenPortfolio'))
const TraderAdvice = lazy(() => import('./pages/TraderAdvice'))

function TabContent() {
  const { state } = useReport()

  if (!state.report) return <UploadZone />

  const page = (() => {
    switch (state.activeTab) {
      case 0: return <Overview data={state.report.overview} />
      case 1: return <PerformanceAttribution data={state.report.performance} />
      case 2: return <InstrumentBreakdown data={state.report.instruments} />
      case 3: return <ChargesCosts data={state.report.charges} />
      case 4: return <OpenPortfolio data={state.report.open_portfolio} />
      case 5: return <TraderAdvice report={state.report} />
      default: return <Overview data={state.report.overview} />
    }
  })()

  return (
    <Suspense fallback={<LoadingShimmer />}>
      {page}
    </Suspense>
  )
}

function LoadingShimmer() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="shimmer h-28 rounded-xl" />
        ))}
      </div>
      <div className="shimmer h-80 rounded-xl" />
    </div>
  )
}

function DateRangeBar() {
  const { state } = useReport()
  if (!state.report) return null

  const { date_range, total_symbols } = state.report.metadata
  const netPnl = state.report.overview.net_realized_pnl

  return (
    <div className="mx-3 md:mx-6 mt-3 md:mt-4 flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl"
      style={{
        background: 'linear-gradient(135deg, rgba(235, 59, 59, 0.06) 0%, rgba(59, 130, 246, 0.04) 100%)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      <div className="flex items-center gap-2">
        <Calendar size={14} color="var(--text-secondary)" />
        <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
          Analysis Period:
        </span>
        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          {date_range}
        </span>
      </div>
      <div className="hidden md:block w-px h-4" style={{ background: 'var(--border-medium)' }} />
      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
        {total_symbols} symbols
      </span>
      <div className="hidden md:block w-px h-4" style={{ background: 'var(--border-medium)' }} />
      <div className="flex items-center gap-2">
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Net P&L:</span>
        <span className="text-sm font-bold font-mono"
          style={{ color: netPnl >= 0 ? '#22c55e' : '#eb3b3b' }}
        >
          {formatCurrency(netPnl)}
        </span>
      </div>
    </div>
  )
}

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-depth">
      <div className="ambient-glow" />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="main-content flex-1 md:ml-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <DateRangeBar />
        <div className="p-3 md:p-6">
          <TabContent />
        </div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <ReportProvider>
      <AppContent />
    </ReportProvider>
  )
}
