import { Upload, FileSpreadsheet, Menu, Download } from 'lucide-react'
import { useRef } from 'react'
import { useReport } from '../context/ReportContext'
import { uploadReport } from '../lib/api'
import { cn } from '../lib/utils'

const tabNames = ['Overview', 'Performance Attribution', 'Instrument Breakdown', 'Charges & Costs', 'Open Portfolio', 'AI Trader Advice']

interface HeaderProps {
  onMenuClick: () => void;
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { state, dispatch } = useReport()
  const fileRef = useRef<HTMLInputElement>(null)

  const handleUpload = async (file: File) => {
    dispatch({ type: 'SET_LOADING' })
    try {
      const data = await uploadReport(file)
      dispatch({ type: 'SET_REPORT', payload: data, fileName: file.name })
    } catch (e: unknown) {
      dispatch({ type: 'SET_ERROR', payload: e instanceof Error ? e.message : 'Upload failed' })
    }
  }

  const handleDownloadJSON = () => {
    if (!state.report) return
    const blob = new Blob([JSON.stringify(state.report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'stocky-analyse-report.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <header className="header">
      <div className="flex items-center gap-3">
        <button className="mobile-menu-btn p-2 -ml-2 rounded-lg hover:bg-white/5" onClick={onMenuClick}>
          <Menu size={20} />
        </button>
        <div className="header-breadcrumb">
          <span
            className="cursor-pointer hover:text-white transition-colors"
            onClick={() => dispatch({ type: 'CLEAR' })}
          >
            Dashboard
          </span>
          {state.report && (
            <> / <span>{tabNames[state.activeTab]}</span></>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {state.report && (
          <>
            <div className="badge">
              <FileSpreadsheet size={12} />
              {state.fileName}
            </div>
            <div className="badge">
              {state.report.metadata.date_range}
            </div>
            <div className={cn('badge', 'badge-success')}>
              {state.report.metadata.total_symbols} symbols
            </div>
            <button className="btn-secondary" onClick={handleDownloadJSON}>
              <Download size={14} />
              JSON
            </button>
          </>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".xlsx"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) handleUpload(f)
            e.target.value = ''
          }}
        />
        <button className="btn-primary" onClick={() => fileRef.current?.click()}>
          <Upload size={16} />
          Upload Report
        </button>
      </div>
    </header>
  )
}
