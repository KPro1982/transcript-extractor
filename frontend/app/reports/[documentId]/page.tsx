'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { FileText, Users, Calendar, ArrowLeft, Loader2, Download, Tag, BookOpen, FileStack, AlertTriangle } from 'lucide-react'
import ProtectedRoute from '@/components/ProtectedRoute'
import UserMenu from '@/components/UserMenu'
import PeopleReport from '@/components/reports/PeopleReport'
import ChronologicalReport from '@/components/reports/ChronologicalReport'
import PageLineReport from '@/components/reports/PageLineReport'
import TopicsReport from '@/components/reports/TopicsReport'
import NarrativeReport from '@/components/reports/NarrativeReport'
import CombinedReport from '@/components/reports/CombinedReport'
import ContradictionsReport from '@/components/reports/ContradictionsReport'

type TabType = 'combined' | 'narrative' | 'page-line' | 'topics' | 'people' | 'chronological' | 'contradictions'

interface Tab {
  id: TabType
  label: string
  icon: any
  badge?: number
}

export default function ReportsPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = params?.documentId as string
  const [activeTab, setActiveTab] = useState<TabType>('combined')
  const [loading, setLoading] = useState(false)
  const [contradictions, setContradictions] = useState<any[]>([])

  // Fetch contradictions on mount
  useEffect(() => {
    fetchContradictions()
  }, [documentId])

  const fetchContradictions = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const token = localStorage.getItem('access_token')
      
      const response = await fetch(`${apiUrl}/api/documents/${documentId}/contradictions`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setContradictions(data || [])
      }
    } catch (error) {
      console.error('Error fetching contradictions:', error)
    }
  }

  const tabs: Tab[] = [
    { id: 'combined', label: 'Combined Report', icon: FileStack },
    { id: 'contradictions', label: 'Contradictions', icon: AlertTriangle, badge: contradictions.length },
    { id: 'narrative', label: 'Narrative', icon: BookOpen },
    { id: 'page-line', label: 'Page/Line', icon: FileText },
    { id: 'topics', label: 'Topics', icon: Tag },
    { id: 'people', label: 'People', icon: Users },
    { id: 'chronological', label: 'Chronological', icon: Calendar }
  ]

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-bg-base">
        {/* Header */}
        <div className="border-b border-gray-800 bg-bg-card">
          <div className="max-w-7xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => router.back()}
                  className="p-2 hover:bg-bg-base rounded-lg transition-colors"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                  <h1 className="text-2xl font-serif">Reports</h1>
                  <p className="text-sm text-gray-400">Document Analysis</p>
                </div>
              </div>
              <UserMenu />
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-800 bg-bg-card">
          <div className="max-w-7xl mx-auto px-6">
            <div className="flex gap-1">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`
                      flex items-center gap-2 px-6 py-3 border-b-2 transition-colors relative
                      ${activeTab === tab.id
                        ? 'border-accent text-white'
                        : 'border-transparent text-gray-400 hover:text-white'
                      }
                    `}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                    {tab.badge !== undefined && tab.badge > 0 && (
                      <span className="ml-1 px-2 py-0.5 bg-red-600 text-white text-xs font-semibold rounded-full">
                        {tab.badge}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="max-w-7xl mx-auto px-6 py-8">
          {activeTab === 'combined' && <CombinedReport documentId={documentId} />}
          {activeTab === 'contradictions' && <ContradictionsReport contradictions={contradictions} />}
          {activeTab === 'narrative' && <NarrativeReport documentId={documentId} />}
          {activeTab === 'page-line' && <PageLineReport documentId={documentId} />}
          {activeTab === 'topics' && <TopicsReport documentId={documentId} />}
          {activeTab === 'people' && <PeopleReport documentId={documentId} />}
          {activeTab === 'chronological' && <ChronologicalReport documentId={documentId} />}
        </div>
      </div>
    </ProtectedRoute>
  )
}

