import { LayoutDashboard, TrendingUp, Layers, Receipt, Briefcase, Settings } from 'lucide-react'
import { useReport } from '../context/ReportContext'
import { cn } from '../lib/utils'

const navItems = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Performance Attribution', icon: TrendingUp },
  { label: 'Instrument Breakdown', icon: Layers },
  { label: 'Charges & Costs', icon: Receipt },
  { label: 'Open Portfolio', icon: Briefcase },
]

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { state, dispatch } = useReport()

  return (
    <>
      <div className={cn('sidebar-overlay', open && 'open')} onClick={onClose} />
      <nav className={cn('sidebar', open && 'open')}>
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">TN</div>
          <span className="sidebar-logo-text">TRADE NEXUS</span>
        </div>
        <div className="sidebar-nav">
          {navItems.map((item, i) => (
            <div
              key={item.label}
              className={cn('sidebar-nav-item', state.activeTab === i && 'active')}
              onClick={() => { dispatch({ type: 'SET_TAB', payload: i }); onClose(); }}
            >
              <item.icon />
              {item.label}
            </div>
          ))}
          <div className="mt-auto pt-4 border-t border-border-subtle mx-4" />
          <div className="sidebar-nav-item opacity-50 cursor-not-allowed">
            <Settings />
            Settings
          </div>
        </div>
      </nav>
    </>
  )
}
