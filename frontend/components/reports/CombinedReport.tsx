'use client'

import { useState, useEffect, useRef } from 'react'
import { Loader2, FileText, Users, Download } from 'lucide-react'

interface CoverPage {
  witness_name: string
  deposition_date: string
  case_name: string
  case_number: string
  filename: string
}

interface TOCItem {
  section: string
  page: number
}

interface Citation {
  id: string
  page: number
  line: number
  page_line_ref: string
  summary: string
}

interface Narrative {
  topic: string
  narrative: string
  citations: Record<string, Citation>
  item_count: number
}

interface PersonNarrative {
  person: {
    display_name: string
    role: string
  }
  narrative: string
  citations: Record<string, Citation>
  count: number
}

interface PageLineItem {
  id: string
  page: number
  line: number
  page_line_ref: string
  summary: string
  topics: string[]
  topics_list?: string[]
}

interface Contradiction {
  id: string
  contradiction_type: string
  severity: number
  confidence: number
  explanation: string
  claim_a: {
    page: number
    line: number
  }
  claim_b: {
    page: number
    line: number
  }
}

interface CombinedReportData {
  cover_page: CoverPage
  table_of_contents: TOCItem[]
  contradictions?: Contradiction[]
  contradictions_count?: number
  narrative_report: { narratives: Narrative[] }
  people_report: { people: PersonNarrative[] }
  page_line_report: { items: PageLineItem[] }
}

export default function CombinedReport({ documentId }: { documentId: string }) {
  const [report, setReport] = useState<CombinedReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const sectionRefs = useRef<{ [key: string]: HTMLElement | null }>({})

  useEffect(() => {
    fetchCombinedReport()
  }, [documentId])

  const fetchCombinedReport = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const token = localStorage.getItem('access_token')
      
      const response = await fetch(`${apiUrl}/api/documents/${documentId}/reports/combined`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Failed to fetch combined report')
      
      const data = await response.json()
      setReport(data)
    } catch (error) {
      console.error('Error fetching combined report:', error)
    } finally {
      setLoading(false)
    }
  }

  const scrollToSection = (section: string) => {
    const ref = sectionRefs.current[section]
    if (ref) {
      ref.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const renderNarrativeWithCitations = (narrative: string, citations: Record<string, Citation>) => {
    const citationRegex = /(\[\d+:\d+(?:-\d+(?::\d+)?)?\])/g
    const parts = narrative.split(citationRegex)
    
    return parts.map((part, idx) => {
      if (citationRegex.test(part)) {
        const citation = citations[part]
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

  if (!report) {
    return <div className="text-center py-8 text-gray-400">Failed to load combined report.</div>
  }

  return (
    <div className="space-y-8 print:space-y-4">
      {/* Cover Page */}
      <div 
        ref={(el) => { sectionRefs.current['Cover Page'] = el }}
        className="bg-bg-card border border-gray-800 rounded-lg p-12 text-center print:border-0 print:break-after-page"
      >
        <div className="mb-8">
          <FileText className="w-16 h-16 text-accent mx-auto mb-4" />
          <h1 className="text-4xl font-serif font-bold mb-2">Deposition Summary</h1>
        </div>
        
        <div className="space-y-6 text-left max-w-2xl mx-auto">
          <div>
            <div className="text-sm text-gray-400 mb-1">Case Name</div>
            <div className="text-xl font-semibold">{report.cover_page.case_name}</div>
          </div>
          
          {report.cover_page.case_number && report.cover_page.case_number !== 'N/A' && (
            <div>
              <div className="text-sm text-gray-400 mb-1">Case Number</div>
              <div className="text-lg">{report.cover_page.case_number}</div>
            </div>
          )}
          
          <div>
            <div className="text-sm text-gray-400 mb-1">Witness/Deponent</div>
            <div className="text-xl font-semibold">{report.cover_page.witness_name}</div>
          </div>
          
          <div>
            <div className="text-sm text-gray-400 mb-1">Deposition Date</div>
            <div className="text-lg">{report.cover_page.deposition_date}</div>
          </div>
        </div>
      </div>

      {/* Table of Contents */}
      <div 
        ref={(el) => { sectionRefs.current['Table of Contents'] = el }}
        className="bg-bg-card border border-gray-800 rounded-lg p-8 print:border-0 print:break-after-page"
      >
        <h2 className="text-2xl font-serif font-bold mb-6">Table of Contents</h2>
        <div className="space-y-2">
          {report.table_of_contents.map((item, idx) => (
            <button
              key={idx}
              onClick={() => scrollToSection(item.section.trim())}
              className="flex justify-between w-full text-left hover:text-accent transition-colors print:pointer-events-none"
            >
              <span className={item.section.startsWith('  ') ? 'ml-6 text-gray-400' : 'font-semibold'}>
                {item.section.trim()}
              </span>
              <span className="text-gray-500">{item.page}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Contradictions Section */}
      {report.contradictions && report.contradictions.length > 0 && (
        <div 
          ref={(el) => { sectionRefs.current['Contradictions'] = el }}
          className="bg-bg-card border border-red-900 rounded-lg p-8 print:border-0 print:break-inside-avoid"
        >
          <div className="flex items-center gap-3 mb-6">
            <h2 className="text-2xl font-serif font-bold text-red-400">⚠️ Contradictions Detected</h2>
            <span className="px-3 py-1 bg-red-900 text-red-200 rounded-full text-sm font-semibold">
              {report.contradictions_count || report.contradictions.length} found
            </span>
          </div>
          <p className="text-gray-300 mb-4">
            The following contradictions were identified in the testimony. Review these carefully for impeachment opportunities.
          </p>
          <div className="space-y-4">
            {report.contradictions.slice(0, 5).map((contr, idx) => (
              <div key={contr.id} className="p-4 bg-bg-secondary border border-gray-700 rounded-lg">
                <div className="flex items-start justify-between mb-2">
                  <span className="font-semibold text-red-300">#{idx + 1}</span>
                  <div className="flex gap-2">
                    <span className="px-2 py-1 text-xs bg-red-900 text-red-200 rounded">
                      Severity: {contr.severity}/100
                    </span>
                    <span className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded">
                      {contr.contradiction_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>
                <p className="text-sm text-gray-300 mb-2">{contr.explanation}</p>
                <div className="flex gap-4 text-xs text-gray-400">
                  <span>Page {contr.claim_a.page}, Line {contr.claim_a.line}</span>
                  <span>vs</span>
                  <span>Page {contr.claim_b.page}, Line {contr.claim_b.line}</span>
                </div>
              </div>
            ))}
            {report.contradictions.length > 5 && (
              <p className="text-center text-sm text-gray-400 pt-2">
                + {report.contradictions.length - 5} more contradictions (see Contradictions tab for full details)
              </p>
            )}
          </div>
        </div>
      )}

      {/* Narrative Report */}
      {report.narrative_report?.narratives && report.narrative_report.narratives.length > 0 && (
        <div 
          ref={(el) => { sectionRefs.current['Narrative Report'] = el }}
          className="space-y-6"
        >
          <h2 className="text-3xl font-serif font-bold">Narrative Report</h2>
          {report.narrative_report.narratives.map((narrative, idx) => (
            <div 
              key={idx}
              ref={(el) => { sectionRefs.current[narrative.topic] = el }}
              className="bg-bg-card border border-gray-800 rounded-lg p-6 print:border-0 print:break-inside-avoid"
            >
              <div className="flex items-center gap-3 mb-4 pb-3 border-b border-gray-800">
                <h3 className="text-xl font-semibold">{narrative.topic}</h3>
                <span className="text-sm text-gray-400">({narrative.item_count} items)</span>
              </div>
              
              <div className="prose prose-invert max-w-none">
                <p className="text-white leading-relaxed">
                  {renderNarrativeWithCitations(narrative.narrative, narrative.citations)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* People Report */}
      {report.people_report?.people && report.people_report.people.length > 0 && (
        <div 
          ref={(el) => { sectionRefs.current['People Report'] = el }}
          className="space-y-6"
        >
          <h2 className="text-3xl font-serif font-bold">People Report</h2>
          {report.people_report.people.map((personData, idx) => (
            <div 
              key={idx}
              ref={(el) => { sectionRefs.current[personData.person.display_name] = el }}
              className="bg-bg-card border border-gray-800 rounded-lg p-6 print:border-0 print:break-inside-avoid"
            >
              <div className="flex items-center gap-3 mb-4 pb-3 border-b border-gray-800">
                <Users className="w-5 h-5 text-accent" />
                <div>
                  <h3 className="text-xl font-semibold">{personData.person.display_name}</h3>
                  <p className="text-sm text-gray-400 capitalize">{personData.person.role}</p>
                </div>
                <span className="text-sm text-gray-400 ml-auto">({personData.count} mentions)</span>
              </div>
              
              <div className="prose prose-invert max-w-none">
                <p className="text-white leading-relaxed">
                  {renderNarrativeWithCitations(personData.narrative, personData.citations)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Page/Line Report */}
      {report.page_line_report?.items && report.page_line_report.items.length > 0 && (
        <div 
          ref={(el) => { sectionRefs.current['Page/Line Report'] = el }}
          className="space-y-4"
        >
          <h2 className="text-3xl font-serif font-bold">Page/Line Report</h2>
          <div className="bg-bg-card border border-gray-800 rounded-lg overflow-hidden print:border-0">
            <table className="w-full">
              <thead className="bg-bg-elevated">
                <tr className="text-left border-b border-gray-800">
                  <th className="p-4 font-semibold">Page/Line</th>
                  <th className="p-4 font-semibold">Summary</th>
                  <th className="p-4 font-semibold">Topics</th>
                </tr>
              </thead>
              <tbody>
                {report.page_line_report.items.map((item, idx) => (
                  <tr key={item.id} className="border-b border-gray-800 last:border-0 print:break-inside-avoid">
                    <td className="p-4 whitespace-nowrap text-sm text-gray-400 align-top">
                      {item.page_line_ref}
                    </td>
                    <td className="p-4 text-sm">
                      {item.summary}
                    </td>
                    <td className="p-4 text-sm text-gray-400 align-top">
                      {Array.isArray(item.topics) 
                        ? item.topics.join(', ')
                        : Array.isArray(item.topics_list)
                        ? item.topics_list.join(', ')
                        : 'Other'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Citation Modal */}
      {selectedCitation && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 print:hidden"
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

