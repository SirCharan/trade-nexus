import type { ReportData } from '../types/report'
import type { AdviceResponse } from '../types/advice'

export async function uploadReport(file: File): Promise<ReportData> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch('/api/upload', {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Upload failed' }));
    throw new Error(err.error || `Upload failed (${res.status})`);
  }

  return res.json();
}

export async function fetchAdvice(report: ReportData): Promise<AdviceResponse> {
  const res = await fetch('/api/advice', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(report),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Advice generation failed' }));
    throw new Error(err.error || `Failed (${res.status})`);
  }

  return res.json();
}
