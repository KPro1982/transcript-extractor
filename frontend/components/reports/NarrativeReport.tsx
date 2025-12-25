'use client'

import { useState, useEffect } from 'react'
import { Loader2, FileText } from 'lucide-react'

interface Citation {
  id: string
  page: number
  line: number
  page_line_ref: string
  summary: string
}

interface TopicNarrative {
  topic: string
  narrative: string
  citations: Record<string, Citation>
  item_count: number
}

export default function NarrativeReport({ documentId }: { documentId: string }) {
  const [narratives, setNarratives] = useState<TopicNarrative[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)

  useEffect(() => {
    fetchNarrativeReport()
  }, [documentId])

  const fetchNarrativeReport = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const token = localStorage.getItem('access_token')
      
      const response = await fetch(`${apiUrl}/api/documents/${documentId}/reports/narrative`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Failed to fetch narrative report')
      
      const data = await response.json()
      setNarratives(data.narratives || [])
    } catch (error) {
      console.error('Error fetching narrative report:', error)
    } finally {
      setLoading(false)
    }
  }

  const renderNarrativeWithCitations = (narrative: string, citations: Record<string, Citation>) => {
    // Split narrative by citation markers [1], [2], etc.
    const parts = narrative.split(/(\[\d+\])/g)
    
    return parts.map((part, idx) => {
      // Check if part is a citation marker
      const citationMatch = part.match(/\[(\d+)\]/)
      if (citationMatch) {
        const citationKey = part
        const citation = citations[citationKey]
        
        if (citation) {
          return (
            <button
              key={idx}
              onClick={() => setSelectedCitation(citation)}
              className="inline-flex items-center text-accent hover:text-accent-hover font-semibold cursor-pointer transition-colors mx-0.5"
              title={`${citation.page_line_ref}: ${citation.summary}`}
            >
              {part}
            </button>
          )
        }
      }
      
      return <span key={idx}>{part}</span>
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }

  if (narratives.length === 0) {
    return <div className="text-center py-8 text-gray-400">No narrative content available.</div>
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Narrative Summary</h2>
        <div className="text-sm text-gray-400">{narratives.length} sections</div>
      </div>

      {narratives.map((topicNarrative, idx) => (
        <div key={idx} className="bg-bg-card border border-gray-800 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4 pb-3 border-b border-gray-800">
            <FileText className="w-5 h-5 text-accent" />
            <h3 className="text-lg font-semibold">{topicNarrative.topic}</h3>
            <span className="text-sm text-gray-400">({topicNarrative.item_count} items)</span>
          </div>
          
          <div className="prose prose-invert max-w-none">
            <p className="text-white leading-relaxed">
              {renderNarrativeWithCitations(topicNarrative.narrative, topicNarrative.citations)}
            </p>
          </div>
        </div>
      ))}

      {/* Citation Tooltip/Modal */}
      {selectedCitation && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedCitation(null)}
        >
          <div 
            className="bg-bg-card border border-accent/30 rounded-lg p-6 max-w-2xl w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-accent font-semibold">{selectedCitation.page_line_ref}</span>
              </div>
              <button
                onClick={() => setSelectedCitation(null)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>
            
            <p className="text-white">{selectedCitation.summary}</p>
          </div>
        </div>
      )}
    </div>
  )
}

