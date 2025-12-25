'use client'

import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Tag } from 'lucide-react'

interface Topic {
  topic: string
  count: number
  qa_items: Array<{
    id: string
    page: number
    line: number
    page_line_ref: string
    summary: string
    event_date: string | null
  }>
}

export default function TopicsReport({ documentId }: { documentId: string }) {
  const [topics, setTopics] = useState<Topic[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchTopicsReport()
  }, [documentId])

  const fetchTopicsReport = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const token = localStorage.getItem('access_token')
      
      const response = await fetch(`${apiUrl}/api/documents/${documentId}/reports/topics`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Failed to fetch topics report')
      
      const data = await response.json()
      setTopics(data.topics || [])
    } catch (error) {
      console.error('Error fetching topics report:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleTopic = (topic: string) => {
    const newExpanded = new Set(expandedTopics)
    if (newExpanded.has(topic)) {
      newExpanded.delete(topic)
    } else {
      newExpanded.add(topic)
    }
    setExpandedTopics(newExpanded)
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading topics report...</div>
  }

  if (topics.length === 0) {
    return <div className="text-center py-8 text-gray-400">No topics found in this document.</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Topics ({topics.length})</h2>
      </div>

      {topics.map((topicData) => {
        const isExpanded = expandedTopics.has(topicData.topic)
        return (
          <div key={topicData.topic} className="bg-bg-card border border-gray-800 rounded-lg overflow-hidden">
            <button
              onClick={() => toggleTopic(topicData.topic)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-bg-base transition-colors"
            >
              <div className="flex items-center gap-4">
                <Tag className="w-5 h-5 text-accent" />
                <div className="text-left">
                  <h3 className="text-lg font-semibold">{topicData.topic}</h3>
                  <p className="text-sm text-gray-400">{topicData.count} items</p>
                </div>
              </div>
              {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>

            {isExpanded && (
              <div className="px-6 py-4 border-t border-gray-800 space-y-4">
                {topicData.qa_items.map((qa) => (
                  <div key={qa.id} className="border-l-2 border-accent/30 pl-4">
                    <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
                      <span>{qa.page_line_ref}</span>
                      {qa.event_date && (
                        <>
                          <span className="text-gray-600">•</span>
                          <span>{qa.event_date}</span>
                        </>
                      )}
                    </div>
                    <p className="text-white">{qa.summary}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

