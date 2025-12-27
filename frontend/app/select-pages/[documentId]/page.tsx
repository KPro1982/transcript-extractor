'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useParams } from 'next/navigation'
import { Loader2, ChevronLeft, ChevronRight, Plus, X, Play, FileText, BookOpen, Eye } from 'lucide-react'
import { getDocument, getPDFPage, startJob, getQAPageRange, getQATestLog } from '@/lib/api'
import CaseInfoPanel from '@/components/CaseInfoPanel'

interface PageRange {
  start: number
  end: number
}

export default function SelectPagesPage() {
  const router = useRouter()
  const params = useParams()
  const documentId = params.documentId as string

  // PDF viewer state
  const [currentPage, setCurrentPage] = useState(1)
  const [pdfImage, setPdfImage] = useState<string>('')
  const [loadingPage, setLoadingPage] = useState(false)
  const [totalPages, setTotalPages] = useState(0)
  const [documentName, setDocumentName] = useState('')
  const [caseInfo, setCaseInfo] = useState<any>(null)

  // Range selection state
  const [rangeInput, setRangeInput] = useState('')
  const [pageRanges, setPageRanges] = useState<PageRange[]>([])
  const [parseError, setParseError] = useState('')
  const [starting, setStarting] = useState(false)
  const [loadingQARange, setLoadingQARange] = useState(false)
  const [qaPageRange, setQAPageRange] = useState<{ first: number, last: number } | null>(null)
  
  // New: Examination detection data
  const [examinationDetection, setExaminationDetection] = useState<{
    first_page: number | null
    last_page: number | null
    confidence: string | null
    frontpages_count: number | null
    examination_count: number | null
    backpages_count: number | null
  } | null>(null)
  
  // Q/A test log viewing
  const [qaTestLogFile, setQATestLogFile] = useState<string | null>(null)
  const [showLogModal, setShowLogModal] = useState(false)
  const [logContent, setLogContent] = useState<string>('')
  const [loadingLog, setLoadingLog] = useState(false)

  // Load document info and first page
  useEffect(() => {
    loadDocument()
  }, [documentId])

  // Load PDF page when current page changes
  useEffect(() => {
    if (currentPage > 0 && totalPages > 0) {
      loadPDFPage(currentPage)
    }
  }, [currentPage, documentId])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return // Don't interfere with input fields
      }

      if (e.key === 'ArrowLeft' || e.key === 'h') {
        e.preventDefault()
        jumpToPage(currentPage - 1)
      } else if (e.key === 'ArrowRight' || e.key === 'l') {
        e.preventDefault()
        jumpToPage(currentPage + 1)
      }
    }

    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [currentPage, totalPages])

  const loadDocument = async () => {
    try {
      const doc = await getDocument(documentId)
      setDocumentName(doc.filename)
      setTotalPages(doc.total_pages)
      
      // Store case info
      setCaseInfo({
        case_name: doc.case_name,
        case_number: doc.case_number,
        deposition_date: doc.deposition_date,
        attorneys: doc.attorneys,
        witness_name: doc.witness_name
      })
      
      // Store examination detection data
      if (doc.examination_first_page && doc.examination_last_page) {
        setExaminationDetection({
          first_page: doc.examination_first_page,
          last_page: doc.examination_last_page,
          confidence: doc.examination_detection_confidence,
          frontpages_count: doc.frontpages_count || 0,
          examination_count: doc.examination_count || 0,
          backpages_count: doc.backpages_count || 0
        })
        
        // Store Q/A test log file if available
        if (doc.qa_test_log_file) {
          setQATestLogFile(doc.qa_test_log_file)
          console.log('Q/A test log file found:', doc.qa_test_log_file)
        } else {
          console.log('No Q/A test log file found in document. Document may have been uploaded before Q/A test feature was added.')
        }
        
        // Set default range to detected examination bounds
        setRangeInput(`${doc.examination_first_page}-${doc.examination_last_page}`)
        
        // Auto-parse to show preview
        try {
          const ranges = parseRangeInput(`${doc.examination_first_page}-${doc.examination_last_page}`)
          setPageRanges(ranges)
        } catch (err) {
          // Ignore parsing errors on initial load
        }
      }
      
      if (doc.total_pages > 0) {
        loadPDFPage(1)
        // Load Q/A page range for smart defaults (backward compatibility)
        if (!doc.examination_first_page) {
          loadQAPageRange()
        }
      }
    } catch (error) {
      console.error('Failed to load document:', error)
      alert('Failed to load document')
    }
  }

  const loadQAPageRange = async () => {
    try {
      setLoadingQARange(true)
      const range = await getQAPageRange(documentId)
      setQAPageRange({ first: range.first_qa_page, last: range.last_qa_page })
      
      // Set default range input
      setRangeInput(`${range.first_qa_page}-${range.last_qa_page}`)
      
      // Auto-parse to show preview
      try {
        const ranges = parseRangeInput(`${range.first_qa_page}-${range.last_qa_page}`)
        setPageRanges(ranges)
      } catch (err) {
        // Ignore parsing errors on initial load
      }
    } catch (error) {
      console.error('Failed to load Q/A page range:', error)
      // Non-critical - just don't set default
    } finally {
      setLoadingQARange(false)
    }
  }

  const loadPDFPage = async (pageNum: number) => {
    try {
      setLoadingPage(true)
      const pageData = await getPDFPage(documentId, pageNum)
      setPdfImage(pageData.imageUrl)
      setTotalPages(pageData.totalPages)
      setLoadingPage(false)
    } catch (err) {
      console.error('Failed to load PDF page:', err)
      setLoadingPage(false)
    }
  }

  const jumpToPage = (pageNum: number) => {
    if (pageNum >= 1 && pageNum <= totalPages) {
      setCurrentPage(pageNum)
    }
  }

  const parseRangeInput = (input: string): PageRange[] => {
    if (!input.trim()) {
      return []
    }

    const ranges: PageRange[] = []
    const parts = input.split(/[;,]/).map(p => p.trim()).filter(p => p)

    for (const part of parts) {
      const match = part.match(/^(\d+)-(\d+)$/)
      if (!match) {
        throw new Error(`Invalid range format: "${part}". Use format like "5-10" or "5-10; 15-20"`)
      }

      const start = parseInt(match[1])
      const end = parseInt(match[2])

      if (start < 1 || end < 1) {
        throw new Error(`Page numbers must be positive: "${part}"`)
      }

      if (start > end) {
        throw new Error(`Start page must be <= end page: "${part}"`)
      }

      if (start > totalPages || end > totalPages) {
        throw new Error(`Page range ${start}-${end} exceeds document length (${totalPages} pages)`)
      }

      ranges.push({ start, end })
    }

    // Check for overlaps
    const sorted = ranges.sort((a, b) => a.start - b.start)
    for (let i = 0; i < sorted.length - 1; i++) {
      if (sorted[i].end >= sorted[i + 1].start) {
        throw new Error(`Overlapping ranges: ${sorted[i].start}-${sorted[i].end} and ${sorted[i + 1].start}-${sorted[i + 1].end}`)
      }
    }

    return ranges
  }

  const handleAddRanges = () => {
    try {
      const ranges = parseRangeInput(rangeInput)
      if (ranges.length === 0) {
        setParseError('Please enter at least one page range')
        return
      }

      setPageRanges(ranges)
      setParseError('')
    } catch (error: any) {
      setParseError(error.message)
    }
  }

  const handleAddCurrentPage = () => {
    setRangeInput(`${currentPage}-${currentPage}`)
    setParseError('')
  }

  const handleAddToEnd = () => {
    setRangeInput(`${currentPage}-${totalPages}`)
    setParseError('')
  }

  const handleJumpToFirstQA = () => {
    if (qaPageRange) {
      jumpToPage(qaPageRange.first)
    }
  }

  const handleJumpToLastQA = () => {
    if (qaPageRange) {
      jumpToPage(qaPageRange.last)
    }
  }

  const handleSetQARange = () => {
    if (qaPageRange) {
      setRangeInput(`${qaPageRange.first}-${qaPageRange.last}`)
      setParseError('')
    }
  }

  const removeRange = (index: number) => {
    const newRanges = pageRanges.filter((_, i) => i !== index)
    setPageRanges(newRanges)
    
    // Update input to reflect remaining ranges
    if (newRanges.length > 0) {
      setRangeInput(newRanges.map(r => `${r.start}-${r.end}`).join('; '))
    } else {
      setRangeInput('')
    }
  }

  const calculateTotalPages = (): number => {
    return pageRanges.reduce((sum, range) => sum + (range.end - range.start + 1), 0)
  }
  
  const handleViewLog = async () => {
    if (!qaTestLogFile) return
    
    setLoadingLog(true)
    setShowLogModal(true)
    
    try {
      const content = await getQATestLog(qaTestLogFile)
      setLogContent(content)
    } catch (error) {
      console.error('Failed to load log:', error)
      setLogContent('Error loading log file. The file may have been cleaned up.')
    } finally {
      setLoadingLog(false)
    }
  }

  const handleStartProcessing = async () => {
    if (pageRanges.length === 0) {
      alert('Please add at least one page range')
      return
    }

    try {
      setStarting(true)
      const result = await startJob(documentId, undefined, undefined, pageRanges)
      router.push(`/process/${result.job_id}`)
    } catch (error: any) {
      console.error('Failed to start job:', error)
      alert('Failed to start processing: ' + (error?.response?.data?.detail || error.message))
      setStarting(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left side: PDF Viewer */}
      <div className="w-1/2 border-r border-gray-800 sticky top-0 h-screen flex flex-col bg-gray-950">
        <div className="p-4 border-b border-gray-800">
          <div className="mb-2">
            <h2 className="text-xl font-semibold">Document Preview</h2>
            <p className="text-sm text-gray-400 truncate">{documentName}</p>
          </div>
          <div className="flex items-center justify-between">
            <button
              onClick={() => jumpToPage(currentPage - 1)}
              disabled={currentPage <= 1 || loadingPage}
              className="p-2 bg-bg-elevated hover:bg-gray-700 disabled:bg-gray-800 disabled:opacity-50 text-gray-300 rounded transition-all"
              title="Previous page (← or H)"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max={totalPages}
                value={currentPage}
                onChange={(e) => {
                  const page = parseInt(e.target.value)
                  if (page >= 1 && page <= totalPages) {
                    jumpToPage(page)
                  }
                }}
                className="w-16 px-2 py-1 bg-bg-elevated border border-gray-700 rounded text-center text-sm"
              />
              <span className="text-sm text-gray-400">of {totalPages}</span>
            </div>
            
            <button
              onClick={() => jumpToPage(currentPage + 1)}
              disabled={currentPage >= totalPages || loadingPage}
              className="p-2 bg-bg-elevated hover:bg-gray-700 disabled:bg-gray-800 disabled:opacity-50 text-gray-300 rounded transition-all"
              title="Next page (→ or L)"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
        
        <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-gray-900">
          {loadingPage ? (
            <Loader2 className="w-8 h-8 animate-spin text-accent" />
          ) : pdfImage ? (
            <img 
              src={pdfImage} 
              alt={`Page ${currentPage}`}
              className="max-w-full h-auto shadow-2xl"
            />
          ) : (
            <div className="text-gray-500 text-center">
              <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p>No preview available</p>
            </div>
          )}
        </div>
      </div>

      {/* Right side: Range Selection */}
      <div className="w-1/2 overflow-auto">
        <div className="p-8">
          <div className="mb-8">
            <h1 className="text-4xl font-serif mb-2">Select Pages to Summarize</h1>
            <p className="text-gray-400">
              Choose specific page ranges to process. This saves time and cost by excluding cover pages, indexes, etc.
            </p>
          </div>

          {/* Case Information */}
          {caseInfo && (
            <CaseInfoPanel
              documentId={documentId}
              caseInfo={caseInfo}
              onUpdate={setCaseInfo}
              editable={true}
            />
          )}

          {/* Range Input */}
          <div className="bg-bg-card border border-gray-800 rounded-2xl p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Enter Page Ranges</h3>
            
            {/* Examination Detection Info */}
            {examinationDetection && examinationDetection.first_page && (
              <div className="mb-4 p-4 bg-blue-950/30 border border-blue-800/50 rounded-lg">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <BookOpen className="w-4 h-4 text-blue-400" />
                      <span className="text-sm font-semibold text-blue-300">
                        Auto-detected Q&A Section
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        examinationDetection.confidence === 'high' 
                          ? 'bg-green-900/50 text-green-300' 
                          : examinationDetection.confidence === 'medium'
                          ? 'bg-yellow-900/50 text-yellow-300'
                          : 'bg-gray-800 text-gray-400'
                      }`}>
                        {examinationDetection.confidence} confidence
                      </span>
                    </div>
                    <p className="text-sm text-gray-300">
                      Pages {examinationDetection.first_page}-{examinationDetection.last_page}
                    </p>
                    
                    {/* Classification breakdown */}
                    <div className="mt-2 flex flex-wrap gap-3 text-xs">
                      {(examinationDetection.frontpages_count ?? 0) > 0 && (
                        <span className="text-gray-400">
                          📄 Frontpages: {examinationDetection.frontpages_count} (auto-excluded)
                        </span>
                      )}
                      {(examinationDetection.examination_count ?? 0) > 0 && (
                        <span className="text-green-400">
                          ✅ Examination: {examinationDetection.examination_count} pages
                        </span>
                      )}
                      {(examinationDetection.backpages_count ?? 0) > 0 && (
                        <span className="text-gray-400">
                          📑 Backpages: {examinationDetection.backpages_count} (auto-excluded)
                        </span>
                      )}
                    </div>
                    
                    <p className="text-xs text-gray-400 mt-2">
                      Pre-filled below. You can modify the range if needed.
                    </p>
                  </div>
                  
                  {/* View Test Log Button */}
                  {qaTestLogFile ? (
                    <button
                      onClick={handleViewLog}
                      className="ml-auto px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded-lg transition-all flex items-center gap-1.5 flex-shrink-0"
                      title="View Q/A extraction test log"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      View Test Log
                    </button>
                  ) : (
                    <div className="ml-auto text-xs text-gray-500 flex-shrink-0">
                      No test log available
                    </div>
                  )}
                </div>
              </div>
            )}
            
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">
                Format: &quot;5-10&quot; or &quot;5-10; 15-20; 30-50&quot;
              </label>
              <input
                type="text"
                value={rangeInput}
                onChange={(e) => {
                  setRangeInput(e.target.value)
                  setParseError('')
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleAddRanges()
                  }
                }}
                placeholder="e.g., 5-10; 15-20"
                className="w-full px-4 py-3 bg-bg-elevated border border-gray-700 rounded-lg focus:outline-none focus:border-accent"
              />
              {parseError && (
                <p className="mt-2 text-sm text-red-500">{parseError}</p>
              )}
            </div>

            <div className="flex gap-2 mb-4">
              <button
                onClick={handleAddRanges}
                className="flex-1 px-4 py-2 bg-accent hover:bg-accent-hover text-bg-base font-semibold rounded-lg transition-all"
              >
                Set Ranges
              </button>
            </div>

            <div className="space-y-2">
              {/* Examination Detection Buttons (new) */}
              {examinationDetection && examinationDetection.first_page && (
                <>
                  <button
                    onClick={() => {
                      if (examinationDetection.first_page && examinationDetection.last_page) {
                        setRangeInput(`${examinationDetection.first_page}-${examinationDetection.last_page}`)
                        setParseError('')
                      }
                    }}
                    className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-all flex items-center justify-center gap-2 font-medium"
                    title={`Use detected examination range: ${examinationDetection.first_page}-${examinationDetection.last_page}`}
                  >
                    <BookOpen className="w-4 h-4" />
                    Use Detected Range ({examinationDetection.first_page}-{examinationDetection.last_page})
                  </button>
                  
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => examinationDetection.first_page && jumpToPage(examinationDetection.first_page)}
                      className="px-3 py-2 bg-bg-elevated hover:bg-gray-700 text-sm rounded-lg transition-all flex items-center justify-center gap-2"
                      title={`Jump to examination start (page ${examinationDetection.first_page})`}
                    >
                      <ChevronLeft className="w-4 h-4" />
                      First Q&A ({examinationDetection.first_page})
                    </button>
                    <button
                      onClick={() => examinationDetection.last_page && jumpToPage(examinationDetection.last_page)}
                      className="px-3 py-2 bg-bg-elevated hover:bg-gray-700 text-sm rounded-lg transition-all flex items-center justify-center gap-2"
                      title={`Jump to examination end (page ${examinationDetection.last_page})`}
                    >
                      Last Q&A ({examinationDetection.last_page})
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </>
              )}
              
              {/* Q/A Detection Buttons (legacy - show only if no examination detection) */}
              {!examinationDetection && qaPageRange && (
                <>
                  <button
                    onClick={handleSetQARange}
                    disabled={loadingQARange}
                    className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-all flex items-center justify-center gap-2 font-medium"
                    title={`Detected Q&A on pages ${qaPageRange.first}-${qaPageRange.last}`}
                  >
                    <BookOpen className="w-4 h-4" />
                    Q&A Pages ({qaPageRange.first}-{qaPageRange.last})
                  </button>
                  
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={handleJumpToFirstQA}
                      disabled={!qaPageRange || loadingQARange}
                      className="px-3 py-2 bg-bg-elevated hover:bg-gray-700 disabled:bg-gray-800 disabled:opacity-50 text-sm rounded-lg transition-all flex items-center justify-center gap-2"
                      title={qaPageRange ? `Jump to first Q&A (page ${qaPageRange.first})` : 'Detecting Q&A pages...'}
                    >
                      <ChevronLeft className="w-4 h-4" />
                      First Q&A
                    </button>
                    <button
                      onClick={handleJumpToLastQA}
                      disabled={!qaPageRange || loadingQARange}
                      className="px-3 py-2 bg-bg-elevated hover:bg-gray-700 disabled:bg-gray-800 disabled:opacity-50 text-sm rounded-lg transition-all flex items-center justify-center gap-2"
                      title={qaPageRange ? `Jump to last Q&A (page ${qaPageRange.last})` : 'Detecting Q&A pages...'}
                    >
                      Last Q&A
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </>
              )}

              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={handleAddCurrentPage}
                  className="px-3 py-2 bg-bg-elevated hover:bg-gray-700 text-sm rounded-lg transition-all flex items-center justify-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Current ({currentPage})
                </button>
                <button
                  onClick={handleAddToEnd}
                  className="px-3 py-2 bg-bg-elevated hover:bg-gray-700 text-sm rounded-lg transition-all flex items-center justify-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  {currentPage} to End
                </button>
              </div>
            </div>
          </div>

          {/* Current Ranges */}
          {pageRanges.length > 0 && (
            <div className="bg-bg-card border border-gray-800 rounded-2xl p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">Selected Ranges</h3>
              
              <div className="space-y-2 mb-4">
                {pageRanges.map((range, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between bg-bg-elevated border border-gray-700 rounded-lg px-4 py-3"
                  >
                    <div>
                      <span className="font-medium">Pages {range.start}-{range.end}</span>
                      <span className="text-sm text-gray-400 ml-2">
                        ({range.end - range.start + 1} page{range.end - range.start + 1 !== 1 ? 's' : ''})
                      </span>
                    </div>
                    <button
                      onClick={() => removeRange(index)}
                      className="p-1 hover:bg-gray-700 rounded transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="pt-4 border-t border-gray-800">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-400">Total pages to process:</span>
                  <span className="text-xl font-bold text-accent">{calculateTotalPages()}</span>
                </div>
                <div className="flex items-center justify-between text-sm mt-2">
                  <span className="text-gray-400">Estimated time:</span>
                  <span className="font-medium">~{Math.ceil(calculateTotalPages() * 0.25)} min</span>
                </div>
              </div>
            </div>
          )}

          {/* Start Button */}
          <button
            onClick={handleStartProcessing}
            disabled={starting || pageRanges.length === 0}
            className="w-full px-6 py-4 bg-accent hover:bg-accent-hover disabled:bg-gray-800 disabled:opacity-50 text-bg-base font-bold text-lg rounded-xl transition-all flex items-center justify-center gap-3"
          >
            {starting ? (
              <>
                <Loader2 className="w-6 h-6 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Play className="w-6 h-6" />
                Summarize {pageRanges.length > 0 ? `${calculateTotalPages()} Page${calculateTotalPages() !== 1 ? 's' : ''}` : 'Pages'}
              </>
            )}
          </button>

          {pageRanges.length === 0 && (
            <p className="text-center text-sm text-gray-500 mt-4">
              Add at least one page range to continue
            </p>
          )}
        </div>
      </div>
      
      {/* Q/A Test Log Modal */}
      {showLogModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-bg-card border border-gray-800 rounded-2xl max-w-4xl w-full max-h-[80vh] flex flex-col">
            {/* Header */}
            <div className="p-6 border-b border-gray-800 flex items-center justify-between">
              <h2 className="text-2xl font-semibold">Q/A Extraction Test Log</h2>
              <button
                onClick={() => setShowLogModal(false)}
                className="text-gray-400 hover:text-white text-2xl leading-none"
              >
                ×
              </button>
            </div>
            
            {/* Content */}
            <div className="p-6 overflow-auto flex-1">
              {loadingLog ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-accent" />
                </div>
              ) : (
                <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono bg-bg-elevated p-4 rounded-lg">
                  {logContent}
                </pre>
              )}
            </div>
            
            {/* Footer */}
            <div className="p-6 border-t border-gray-800 flex justify-end">
              <button
                onClick={() => setShowLogModal(false)}
                className="px-6 py-2 bg-accent hover:bg-accent-hover text-bg-base font-semibold rounded-lg transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

