'use client'

import { useState } from 'react'
import { AlertTriangle, Filter, FileDown, ChevronDown, ChevronUp } from 'lucide-react'

interface Claim {
  subject: string
  predicate: string
  object: string
  page: number
  line: number
  quote: string
}

interface Contradiction {
  id: string
  contradiction_type: string
  severity: number
  confidence: number
  explanation: string
  requires_human_review: boolean
  suggested_followups: string[]
  claim_a: Claim
  claim_b: Claim
}

interface ContradictionsReportProps {
  contradictions: Contradiction[]
  onNavigate?: (page: number, line: number) => void
}

const CONTRADICTION_TYPES = {
  direct_negation: 'Direct Negation',
  mutually_exclusive: 'Mutually Exclusive',
  quantity_conflict: 'Quantity Conflict',
  memory_drift: 'Memory Drift',
  scope_mismatch: 'Scope Mismatch',
}

const SEVERITY_COLORS = {
  high: 'text-red-600 bg-red-50 border-red-200',
  medium: 'text-orange-600 bg-orange-50 border-orange-200',
  low: 'text-yellow-600 bg-yellow-50 border-yellow-200',
}

function getSeverityLevel(severity: number): 'high' | 'medium' | 'low' {
  if (severity >= 70) return 'high'
  if (severity >= 40) return 'medium'
  return 'low'
}

export default function ContradictionsReport({ contradictions, onNavigate }: ContradictionsReportProps) {
  const [filters, setFilters] = useState({
    type: 'all',
    severity: 'all',
    requiresReview: false,
  })
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  // Apply filters
  const filteredContradictions = contradictions.filter((contr) => {
    if (filters.type !== 'all' && contr.contradiction_type !== filters.type) {
      return false
    }

    if (filters.severity !== 'all') {
      const level = getSeverityLevel(contr.severity)
      if (level !== filters.severity) {
        return false
      }
    }

    if (filters.requiresReview && !contr.requires_human_review) {
      return false
    }

    return true
  })

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedIds)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedIds(newExpanded)
  }

  const exportToText = () => {
    const text = filteredContradictions
      .map((contr, idx) => {
        return `
CONTRADICTION ${idx + 1}
Type: ${CONTRADICTION_TYPES[contr.contradiction_type as keyof typeof CONTRADICTION_TYPES] || contr.contradiction_type}
Severity: ${contr.severity}/100
Confidence: ${contr.confidence}/100

Explanation: ${contr.explanation}

Statement A (Page ${contr.claim_a.page}, Line ${contr.claim_a.line}):
${contr.claim_a.subject} ${contr.claim_a.predicate} ${contr.claim_a.object || ''}
Quote: ${contr.claim_a.quote}

Statement B (Page ${contr.claim_b.page}, Line ${contr.claim_b.line}):
${contr.claim_b.subject} ${contr.claim_b.predicate} ${contr.claim_b.object || ''}
Quote: ${contr.claim_b.quote}

${contr.suggested_followups.length > 0 ? `Suggested Follow-ups:\n${contr.suggested_followups.map((q, i) => `${i + 1}. ${q}`).join('\n')}` : ''}

${'='.repeat(80)}
`
      })
      .join('\n')

    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `contradictions-report-${new Date().toISOString().split('T')[0]}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-6 h-6 text-red-600" />
          <h2 className="text-2xl font-bold text-gray-900">Contradictions Report</h2>
        </div>
        <button
          onClick={exportToText}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          <FileDown className="w-4 h-4" />
          Export
        </button>
      </div>

      {/* Summary */}
      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-3xl font-bold text-gray-900">{contradictions.length}</div>
            <div className="text-sm text-gray-600">Total Contradictions</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-red-600">
              {contradictions.filter((c) => getSeverityLevel(c.severity) === 'high').length}
            </div>
            <div className="text-sm text-gray-600">High Severity</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-orange-600">
              {contradictions.filter((c) => c.requires_human_review).length}
            </div>
            <div className="text-sm text-gray-600">Needs Review</div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-gray-600" />
          <span className="font-semibold text-gray-900">Filters</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              value={filters.type}
              onChange={(e) => setFilters({ ...filters, type: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="all">All Types</option>
              {Object.entries(CONTRADICTION_TYPES).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
            <select
              value={filters.severity}
              onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="all">All Severities</option>
              <option value="high">High (70+)</option>
              <option value="medium">Medium (40-69)</option>
              <option value="low">Low (&lt;40)</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.requiresReview}
                onChange={(e) => setFilters({ ...filters, requiresReview: e.target.checked })}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Requires Review Only</span>
            </label>
          </div>
        </div>
      </div>

      {/* Results count */}
      <div className="text-sm text-gray-600">
        Showing {filteredContradictions.length} of {contradictions.length} contradictions
      </div>

      {/* Contradictions List */}
      <div className="space-y-4">
        {filteredContradictions.length === 0 ? (
          <div className="text-center py-12 text-gray-500">No contradictions found matching the selected filters.</div>
        ) : (
          filteredContradictions.map((contr, idx) => {
            const severityLevel = getSeverityLevel(contr.severity)
            const isExpanded = expandedIds.has(contr.id)

            return (
              <div
                key={contr.id}
                className={`rounded-lg border-2 ${SEVERITY_COLORS[severityLevel]} overflow-hidden`}
              >
                {/* Header */}
                <div
                  className="p-4 cursor-pointer hover:opacity-80 transition"
                  onClick={() => toggleExpanded(contr.id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="font-semibold text-lg">Contradiction #{idx + 1}</span>
                        <span className="px-2 py-1 text-xs font-medium rounded-full bg-white border">
                          {CONTRADICTION_TYPES[contr.contradiction_type as keyof typeof CONTRADICTION_TYPES] ||
                            contr.contradiction_type}
                        </span>
                        {contr.requires_human_review && (
                          <span className="px-2 py-1 text-xs font-medium rounded-full bg-orange-100 text-orange-700 border border-orange-300">
                            Needs Review
                          </span>
                        )}
                      </div>
                      <p className="text-sm mb-2">{contr.explanation}</p>
                      <div className="flex items-center gap-4 text-xs">
                        <span>Severity: {contr.severity}/100</span>
                        <span>Confidence: {contr.confidence}/100</span>
                      </div>
                    </div>
                    <div>{isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}</div>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-0 space-y-4 bg-white bg-opacity-50">
                    {/* Claim A */}
                    <div className="p-3 bg-white rounded border">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold text-gray-900">Statement A</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onNavigate?.(contr.claim_a.page, contr.claim_a.line)
                          }}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Page {contr.claim_a.page}, Line {contr.claim_a.line}
                        </button>
                      </div>
                      <p className="text-sm mb-2">
                        <span className="font-medium">{contr.claim_a.subject}</span> {contr.claim_a.predicate}{' '}
                        {contr.claim_a.object && <span className="font-medium">{contr.claim_a.object}</span>}
                      </p>
                      <p className="text-xs text-gray-600 italic border-l-2 border-gray-300 pl-3">
                        {contr.claim_a.quote.substring(0, 200)}
                        {contr.claim_a.quote.length > 200 && '...'}
                      </p>
                    </div>

                    {/* Claim B */}
                    <div className="p-3 bg-white rounded border">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold text-gray-900">Statement B</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onNavigate?.(contr.claim_b.page, contr.claim_b.line)
                          }}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Page {contr.claim_b.page}, Line {contr.claim_b.line}
                        </button>
                      </div>
                      <p className="text-sm mb-2">
                        <span className="font-medium">{contr.claim_b.subject}</span> {contr.claim_b.predicate}{' '}
                        {contr.claim_b.object && <span className="font-medium">{contr.claim_b.object}</span>}
                      </p>
                      <p className="text-xs text-gray-600 italic border-l-2 border-gray-300 pl-3">
                        {contr.claim_b.quote.substring(0, 200)}
                        {contr.claim_b.quote.length > 200 && '...'}
                      </p>
                    </div>

                    {/* Suggested Follow-ups */}
                    {contr.suggested_followups && contr.suggested_followups.length > 0 && (
                      <div className="p-3 bg-blue-50 rounded border border-blue-200">
                        <span className="font-semibold text-gray-900 block mb-2">Suggested Follow-up Questions:</span>
                        <ol className="list-decimal list-inside space-y-1 text-sm">
                          {contr.suggested_followups.map((question, i) => (
                            <li key={i} className="text-gray-700">
                              {question}
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

