'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { FileText, ChevronDown, ChevronRight, ArrowLeft, Download, Loader2 } from 'lucide-react'
import { getJobStatus, getQAItems } from '@/lib/api'

interface QAItem {
  id: string
  page_number: number
  line_number: number
  question: string
  answer: string
  summary: string
  topic: string
}

interface GroupedItems {
  [topic: string]: QAItem[]
}

export default function ResultsPage() {
  const router = useRouter()
  const params = useParams()
  const jobId = params?.jobId as string

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [qaItems, setQAItems] = useState<QAItem[]>([])
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set())
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())

  useEffect(() => {
    const fetchResults = async () => {
      try {
        setLoading(true)
        
        // Get job status to get document ID
        const jobStatus = await getJobStatus(jobId)
        
        if (jobStatus.status === 'failed') {
          setError(jobStatus.error_message || 'Processing failed')
          setLoading(false)
          return
        }
        
        if (jobStatus.status !== 'completed') {
          // Job not complete, redirect back to process page
          router.push(`/process/${jobId}`)
          return
        }
        
        setDocumentId(jobStatus.document_id)
        
        // Fetch Q&A items
        const response = await getQAItems(jobStatus.document_id)
        setQAItems(response.qa_items || [])
        
        // Auto-expand first topic
        const topics = Array.from(new Set(response.qa_items?.map((item: QAItem) => item.topic) || []))
        if (topics.length > 0) {
          setExpandedTopics(new Set([topics[0]]))
        }
        
      } catch (err: any) {
        console.error('Failed to fetch results:', err)
        setError(err.message || 'Failed to load results')
      } finally {
        setLoading(false)
      }
    }

    if (jobId) {
      fetchResults()
    }
  }, [jobId, router])

  // Group items by topic
  const groupedItems: GroupedItems = qaItems.reduce((acc, item) => {
    const topic = item.topic || 'Other'
    if (!acc[topic]) {
      acc[topic] = []
    }
    acc[topic].push(item)
    return acc
  }, {} as GroupedItems)

  const toggleTopic = (topic: string) => {
    const newExpanded = new Set(expandedTopics)
    if (newExpanded.has(topic)) {
      newExpanded.delete(topic)
    } else {
      newExpanded.add(topic)
    }
    setExpandedTopics(newExpanded)
  }

  const toggleItem = (itemId: string) => {
    const newExpanded = new Set(expandedItems)
    if (newExpanded.has(itemId)) {
      newExpanded.delete(itemId)
    } else {
      newExpanded.add(itemId)
    }
    setExpandedItems(newExpanded)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-accent animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading results...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md w-full bg-bg-card border border-red-500/20 rounded-2xl p-8 text-center">
          <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">⚠️</span>
          </div>
          <h1 className="text-2xl font-serif mb-2">Error Loading Results</h1>
          <p className="text-gray-400 mb-6">{error}</p>
          <button
            onClick={() => router.push('/')}
            className="px-6 py-3 bg-accent hover:bg-accent-hover text-bg-base font-semibold rounded-xl transition-all"
          >
            Start Over
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <button
              onClick={() => router.push('/')}
              className="flex items-center gap-2 text-gray-400 hover:text-white mb-4 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </button>
            <h1 className="text-4xl font-serif">Deposition Summary</h1>
            <p className="text-gray-400 mt-2">
              {qaItems.length} Q&A pairs extracted from your document
            </p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => router.push('/upload')}
              className="px-4 py-2 bg-bg-card border border-gray-700 hover:border-accent text-gray-300 rounded-xl transition-all"
            >
              Process Another
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-bg-card border border-gray-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-accent">{qaItems.length}</div>
            <div className="text-sm text-gray-400">Q&A Pairs</div>
          </div>
          <div className="bg-bg-card border border-gray-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-accent">{Object.keys(groupedItems).length}</div>
            <div className="text-sm text-gray-400">Topics</div>
          </div>
          <div className="bg-bg-card border border-gray-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-accent">
              {qaItems.length > 0 ? Math.max(...qaItems.map(item => item.page_number)) : 0}
            </div>
            <div className="text-sm text-gray-400">Pages</div>
          </div>
          <div className="bg-bg-card border border-gray-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-accent">✓</div>
            <div className="text-sm text-gray-400">Complete</div>
          </div>
        </div>

        {/* Results */}
        {qaItems.length === 0 ? (
          <div className="bg-bg-card border border-gray-800 rounded-2xl p-12 text-center">
            <FileText className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <h2 className="text-xl font-serif mb-2">No Q&A Pairs Found</h2>
            <p className="text-gray-400">
              The document was processed but no Q&A format content was detected.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedItems).map(([topic, items]) => (
              <div
                key={topic}
                className="bg-bg-card border border-gray-800 rounded-xl overflow-hidden"
              >
                {/* Topic Header */}
                <button
                  onClick={() => toggleTopic(topic)}
                  className="w-full flex items-center justify-between p-4 hover:bg-bg-elevated transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {expandedTopics.has(topic) ? (
                      <ChevronDown className="w-5 h-5 text-accent" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-500" />
                    )}
                    <span className="font-semibold text-lg">{topic}</span>
                    <span className="text-sm text-gray-500 bg-bg-elevated px-2 py-1 rounded-full">
                      {items.length} items
                    </span>
                  </div>
                </button>

                {/* Topic Items */}
                {expandedTopics.has(topic) && (
                  <div className="border-t border-gray-800">
                    {items.map((item, idx) => (
                      <div
                        key={item.id}
                        className={`${idx > 0 ? 'border-t border-gray-800/50' : ''}`}
                      >
                        {/* Q&A Header */}
                        <button
                          onClick={() => toggleItem(item.id)}
                          className="w-full text-left p-4 hover:bg-bg-elevated transition-colors"
                        >
                          <div className="flex items-start gap-4">
                            <div className="flex-shrink-0 text-xs text-gray-500 font-mono mt-1">
                              P{item.page_number}:L{item.line_number}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start gap-2">
                                <span className="text-accent font-bold flex-shrink-0">Q:</span>
                                <span className={expandedItems.has(item.id) ? '' : 'line-clamp-2'}>
                                  {item.question}
                                </span>
                              </div>
                              
                              {item.summary && !expandedItems.has(item.id) && (
                                <div className="mt-2 text-sm text-gray-400 italic line-clamp-1">
                                  Summary: {item.summary}
                                </div>
                              )}
                            </div>
                            {expandedItems.has(item.id) ? (
                              <ChevronDown className="w-4 h-4 text-gray-500 flex-shrink-0" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-gray-500 flex-shrink-0" />
                            )}
                          </div>
                        </button>

                        {/* Expanded Answer */}
                        {expandedItems.has(item.id) && (
                          <div className="px-4 pb-4 pl-[60px]">
                            <div className="flex items-start gap-2 mb-4">
                              <span className="text-gray-400 font-bold flex-shrink-0">A:</span>
                              <span className="text-gray-300">{item.answer}</span>
                            </div>
                            
                            {item.summary && (
                              <div className="mt-4 p-3 bg-accent/5 border border-accent/20 rounded-lg">
                                <div className="text-xs text-accent mb-1 font-semibold">AI Summary</div>
                                <div className="text-sm text-gray-300">{item.summary}</div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 pt-8 border-t border-gray-800 text-center text-sm text-gray-500">
          <p>Processed by DepoDigest AI • {new Date().toLocaleDateString()}</p>
        </div>
      </div>
    </div>
  )
}

