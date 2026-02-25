import { useState, lazy, Suspense } from 'react'
import { ReportProvider, useReport } from './context/ReportContext'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import UploadZone from './components/UploadZone'

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

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-depth">
      <div className="ambient-glow" />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="main-content flex-1 md:ml-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
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
