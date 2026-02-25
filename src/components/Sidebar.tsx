import { useState } from 'react'
import { LayoutDashboard, TrendingUp, Layers, Receipt, Briefcase, BrainCircuit, FilePlus, MessageSquare } from 'lucide-react'
import { useReport } from '../context/ReportContext'
import { cn } from '../lib/utils'
import FeedbackModal from './FeedbackModal'

const navItems = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Performance Attribution', icon: TrendingUp },
  { label: 'Instrument Breakdown', icon: Layers },
  { label: 'Charges & Costs', icon: Receipt },
  { label: 'Open Portfolio', icon: Briefcase },
  { label: 'AI Trader Advice', icon: BrainCircuit },
]

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { state, dispatch } = useReport()
  const [feedbackOpen, setFeedbackOpen] = useState(false)

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
          {state.report && (
            <div
              className="sidebar-nav-item"
              onClick={() => { dispatch({ type: 'CLEAR' }); onClose(); }}
            >
              <FilePlus />
              New Report
            </div>
          )}
          <div className="mt-auto pt-4 border-t border-border-subtle mx-4" />
          <div
            className="sidebar-nav-item"
            onClick={() => setFeedbackOpen(true)}
          >
            <MessageSquare />
            Send Feedback
          </div>
        </div>
      </nav>
      <FeedbackModal open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </>
  )
}
