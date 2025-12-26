'use client'

import { useState, useEffect } from 'react'
import { Calendar } from 'lucide-react'

interface QAItem {
  id: string
  page: number
  line: number
  summary: string
  topic: string
  event_date: string
}

interface ChronologicalReportData {
  items: QAItem[]
  contradictions?: Array<{
    id: string
    severity: number
    explanation: string
  }>
  contradiction_count?: number
}

export default function ChronologicalReport({ documentId }: { documentId: string }) {
  const [reportData, setReportData] = useState<ChronologicalReportData>({ items: [] })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchChronologicalReport()
  }, [documentId])

  const fetchChronologicalReport = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const token = localStorage.getItem('access_token')
      
      const response = await fetch(`${apiUrl}/api/documents/${documentId}/reports/chronological`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Failed to fetch chronological report')
      
      const data = await response.json()
      setReportData(data)
    } catch (error) {
      console.error('Error fetching chronological report:', error)
    } finally {
      setLoading(false)
    }
  }

  const items = reportData.items || []

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading chronological report...</div>
  }

  if (items.length === 0) {
    return <div className="text-center py-8 text-gray-400">No items with event dates found.</div>
  }

  // Group by date
  const groupedByDate = items.reduce((acc, item) => {
    const date = item.event_date || 'No Date'
    if (!acc[date]) {
      acc[date] = []
    }
    acc[date].push(item)
    return acc
  }, {} as Record<string, QAItem[]>)

  return (
    <div className="space-y-6">
      {reportData.contradiction_count && reportData.contradiction_count > 0 && (
        <div className="bg-red-900 bg-opacity-20 border border-red-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-red-400">
            <span className="font-semibold">⚠️ {reportData.contradiction_count} contradictions detected</span>
            <span className="text-sm text-gray-400">- See Contradictions tab for details</span>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Timeline ({items.length} events)</h2>
      </div>

      {Object.entries(groupedByDate).map(([date, dateItems]) => (
        <div key={date} className="relative">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-32 pt-1">
              <div className="flex items-center gap-2 text-accent font-semibold">
                <Calendar className="w-4 h-4" />
                {date}
              </div>
            </div>
            <div className="flex-1 space-y-4">
              {dateItems.map((item) => (
                <div key={item.id} className="bg-bg-card border border-gray-800 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-2">
                    Page {item.page}, Line {item.line} · {item.topic}
                  </div>
                  <p className="text-white">{item.summary}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

