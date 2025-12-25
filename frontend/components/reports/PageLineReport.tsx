'use client'

import { useState, useEffect } from 'react'
import { Download } from 'lucide-react'

interface QAItem {
  id: string
  page: number
  line: number
  answer_end_page: number | null
  answer_end_line: number | null
  page_line_ref: string
  summary: string
  topic: string
}

export default function PageLineReport({ documentId }: { documentId: string }) {
  const [items, setItems] = useState<QAItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchPageLineReport()
  }, [documentId])

  const fetchPageLineReport = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const token = localStorage.getItem('access_token')
      
      const response = await fetch(`${apiUrl}/api/documents/${documentId}/reports/page-line`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Failed to fetch page/line report')
      
      const data = await response.json()
      setItems(data.items || [])
    } catch (error) {
      console.error('Error fetching page/line report:', error)
    } finally {
      setLoading(false)
    }
  }

  const exportToCSV = () => {
    const headers = ['Page/Line', 'Summary', 'Topic']
    const rows = items.map(item => [
      item.page_line_ref,
      item.summary.replace(/"/g, '""'), // Escape quotes
      item.topic
    ])
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')
    
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `page-line-report-${documentId}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading page/line report...</div>
  }

  if (items.length === 0) {
    return <div className="text-center py-8 text-gray-400">No items found.</div>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">{items.length} Q&A Items</h2>
        <button
          onClick={exportToCSV}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 hover:bg-accent/20 border border-accent/30 rounded-lg transition-colors"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </button>
      </div>

      <div className="bg-bg-card border border-gray-800 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-bg-base border-b border-gray-800">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-semibold w-1/5">Page/Line</th>
              <th className="px-4 py-3 text-left text-sm font-semibold w-3/5">Summary</th>
              <th className="px-4 py-3 text-left text-sm font-semibold w-1/5">Topic</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {items.map((item) => (
              <tr key={item.id} className="hover:bg-bg-base transition-colors">
                <td className="px-4 py-3 text-sm text-gray-400">{item.page_line_ref}</td>
                <td className="px-4 py-3 text-sm">{item.summary}</td>
                <td className="px-4 py-3 text-sm text-gray-400">{item.topic}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

