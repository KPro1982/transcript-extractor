'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useParams } from 'next/navigation'
import { Loader2, ChevronLeft, ChevronRight, Plus, X, Play, FileText } from 'lucide-react'
import { getDocument, getPDFPage, startJob } from '@/lib/api'

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

  // Range selection state
  const [rangeInput, setRangeInput] = useState('')
  const [pageRanges, setPageRanges] = useState<PageRange[]>([])
  const [parseError, setParseError] = useState('')
  const [starting, setStarting] = useState(false)

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
      
      if (doc.total_pages > 0) {
        loadPDFPage(1)
      }
    } catch (error) {
      console.error('Failed to load document:', error)
      alert('Failed to load document')
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

          {/* Range Input */}
          <div className="bg-bg-card border border-gray-800 rounded-2xl p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Enter Page Ranges</h3>
            
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">
                Format: "5-10" or "5-10; 15-20; 30-50"
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

            <div className="flex gap-2">
              <button
                onClick={handleAddCurrentPage}
                className="flex-1 px-3 py-2 bg-bg-elevated hover:bg-gray-700 text-sm rounded-lg transition-all flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Current Page ({currentPage})
              </button>
              <button
                onClick={handleAddToEnd}
                className="flex-1 px-3 py-2 bg-bg-elevated hover:bg-gray-700 text-sm rounded-lg transition-all flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Page {currentPage} to End
              </button>
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
    </div>
  )
}

