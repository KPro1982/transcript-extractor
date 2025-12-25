'use client'

import { useState, useEffect } from 'react'
import { Download, ChevronDown, ChevronUp } from 'lucide-react'

interface Person {
  person: {
    id: string
    normalized_name: string
    display_name: string
    role: string
    context: string
  }
  qa_items: Array<{
    id: string
    page: number
    line: number
    summary: string
    topic: string
    mention_context: string
  }>
  count: number
}

export default function PeopleReport({ documentId }: { documentId: string }) {
  const [people, setPeople] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedPeople, setExpandedPeople] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchPeopleReport()
  }, [documentId])

  const fetchPeopleReport = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const token = localStorage.getItem('access_token')
      
      const response = await fetch(`${apiUrl}/api/documents/${documentId}/reports/people`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Failed to fetch people report')
      
      const data = await response.json()
      setPeople(data.people || [])
    } catch (error) {
      console.error('Error fetching people report:', error)
    } finally {
      setLoading(false)
    }
  }

  const togglePerson = (personId: string) => {
    const newExpanded = new Set(expandedPeople)
    if (newExpanded.has(personId)) {
      newExpanded.delete(personId)
    } else {
      newExpanded.add(personId)
    }
    setExpandedPeople(newExpanded)
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading people report...</div>
  }

  if (people.length === 0) {
    return <div className="text-center py-8 text-gray-400">No people found in this document.</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">People Mentioned ({people.length})</h2>
      </div>

      {people.map((person) => {
        const isExpanded = expandedPeople.has(person.person.id)
        return (
          <div key={person.person.id} className="bg-bg-card border border-gray-800 rounded-lg overflow-hidden">
            <button
              onClick={() => togglePerson(person.person.id)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-bg-base transition-colors"
            >
              <div className="flex items-center gap-4">
                <div>
                  <h3 className="text-lg font-semibold">{person.person.normalized_name}</h3>
                  <p className="text-sm text-gray-400">
                    {person.person.role} · {person.count} mentions
                  </p>
                </div>
              </div>
              {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>

            {isExpanded && (
              <div className="px-6 py-4 border-t border-gray-800 space-y-4">
                {person.qa_items.map((qa) => (
                  <div key={qa.id} className="border-l-2 border-accent/30 pl-4">
                    <div className="text-sm text-gray-400 mb-1">
                      Page {qa.page}, Line {qa.line} · {qa.topic}
                    </div>
                    <p className="text-white">{qa.summary}</p>
                    {qa.mention_context && (
                      <p className="text-xs text-gray-500 mt-1">Context: {qa.mention_context}</p>
                    )}
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

