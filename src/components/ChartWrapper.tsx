import type { ReactNode } from 'react'
import { ResponsiveContainer } from 'recharts'

interface ChartWrapperProps {
  height?: number;
  children: ReactNode;
}

export default function ChartWrapper({ height = 300, children }: ChartWrapperProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      {children as React.ReactElement}
    </ResponsiveContainer>
  )
}

export function DarkTooltipStyle() {
  return {
    contentStyle: {
      background: '#0f0f0f',
      border: '1px solid #252525',
      borderRadius: 8,
      fontSize: 12,
      color: '#e8e8e8',
    },
    itemStyle: { color: '#e8e8e8' },
    cursor: { fill: 'rgba(255,255,255,0.03)' },
  }
}
