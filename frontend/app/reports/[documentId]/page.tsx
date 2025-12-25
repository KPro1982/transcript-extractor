'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { FileText, Users, Calendar, ArrowLeft, Loader2, Download, Tag, BookOpen } from 'lucide-react'
import ProtectedRoute from '@/components/ProtectedRoute'
import UserMenu from '@/components/UserMenu'
import PeopleReport from '@/components/reports/PeopleReport'
import ChronologicalReport from '@/components/reports/ChronologicalReport'
import PageLineReport from '@/components/reports/PageLineReport'
import TopicsReport from '@/components/reports/TopicsReport'
import NarrativeReport from '@/components/reports/NarrativeReport'

type TabType = 'narrative' | 'page-line' | 'topics' | 'people' | 'chronological'

export default function ReportsPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = params?.documentId as string
  const [activeTab, setActiveTab] = useState<TabType>('narrative')
  const [loading, setLoading] = useState(false)

  const tabs = [
    { id: 'narrative' as TabType, label: 'Narrative Report', icon: BookOpen },
    { id: 'page-line' as TabType, label: 'Page/Line Report', icon: FileText },
    { id: 'topics' as TabType, label: 'Topics Report', icon: Tag },
    { id: 'people' as TabType, label: 'People Report', icon: Users },
    { id: 'chronological' as TabType, label: 'Chronological Report', icon: Calendar }
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
                      flex items-center gap-2 px-6 py-3 border-b-2 transition-colors
                      ${activeTab === tab.id
                        ? 'border-accent text-white'
                        : 'border-transparent text-gray-400 hover:text-white'
                      }
                    `}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="max-w-7xl mx-auto px-6 py-8">
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

