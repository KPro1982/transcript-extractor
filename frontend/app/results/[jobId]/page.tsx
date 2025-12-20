'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { ArrowLeft, Loader2, BookOpen, Upload, Shield } from 'lucide-react'
import { getJobStatus, getQAItems, getDocument } from '@/lib/api'
import { useKeyboardNav } from '@/hooks/useKeyboardNav'
import { useAuth } from '@/contexts/AuthContext'
import PDFViewer from '@/components/PDFViewer'
import SummaryDisplay from '@/components/SummaryDisplay'
import UserMenu from '@/components/UserMenu'

interface QAItem {
  id: string
  page_number: number       // Printed transcript page number (for citation display)
  pdf_page_index: number    // 1-based PDF page index (for rendering)
  line_number: number
  end_page: number
  end_line: number
  question: string
  answer: string
  summary: string
  topic: string
}

/**
 * Reading Mode Results Page
 * 
 * Side-by-side display of PDF source text and summaries.
 * Navigate through Q&A pairs using arrow keys.
 */
export default function ResultsPage() {
  const router = useRouter()
  const params = useParams()
  const jobId = params?.jobId as string
  const { user } = useAuth()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [qaItems, setQAItems] = useState<QAItem[]>([])
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [totalPages, setTotalPages] = useState(1)
  const [filename, setFilename] = useState<string>('')

  // Keyboard navigation hook
  const { 
    currentIndex, 
    setCurrentIndex, 
    goToNext, 
    goToPrevious 
  } = useKeyboardNav({
    totalItems: qaItems.length,
    enabled: !loading && qaItems.length > 0
  })

  // Current item and its page info
  const currentItem = qaItems[currentIndex] || null
  // Use pdf_page_index for rendering, fall back to page_number for compatibility
  const currentPdfPageIndex = currentItem?.pdf_page_index || currentItem?.page_number || 1
  // Keep printed page number for citation display
  const currentPageNumber = currentItem?.page_number || 1
  const highlightStartLine = currentItem?.line_number || 1
  const highlightEndLine = currentItem?.end_line || highlightStartLine
  const endPage = currentItem?.end_page || currentPageNumber
  // Calculate the PDF page index for the end page based on the offset between printed and PDF pages
  const pageOffset = currentPdfPageIndex - currentPageNumber
  const endPdfPageIndex = endPage + pageOffset

  // Fetch results on mount
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
        
        // Fetch document info
        const docInfo = await getDocument(jobStatus.document_id)
        setTotalPages(docInfo.total_pages || 1)
        setFilename(docInfo.filename || 'Document')
        
        // Fetch Q&A items with line ranges
        try {
          const response = await getQAItems(jobStatus.document_id)
          console.log('Q&A items response:', response)
          console.log('Number of items:', response?.qa_items?.length || 0)
          if (response?.qa_items && response.qa_items.length > 0) {
            console.log('First item summary:', response.qa_items[0]?.summary || 'MISSING')
            console.log('First item:', response.qa_items[0])
          }
          setQAItems(response.qa_items || [])
        } catch (err: any) {
          console.error('Failed to fetch Q&A items:', err)
          console.error('Error details:', err.response?.data || err.message)
          setError(`Failed to load Q&A items: ${err.message}`)
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

  // Handle page change from PDF viewer (when navigating pages directly)
  const handlePageChange = useCallback((newPage: number) => {
    // Find the first Q&A item on this page
    const firstItemOnPage = qaItems.findIndex(item => item.page_number === newPage)
    if (firstItemOnPage !== -1) {
      setCurrentIndex(firstItemOnPage)
    }
  }, [qaItems, setCurrentIndex])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-accent animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading reading mode...</p>
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

  if (qaItems.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md w-full bg-bg-card border border-gray-800 rounded-2xl p-8 text-center">
          <BookOpen className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h1 className="text-2xl font-serif mb-2">No Q&A Pairs Found</h1>
          <p className="text-gray-400 mb-6">
            The document was processed but no Q&A format content was detected.
          </p>
          <button
            onClick={() => router.push('/upload')}
            className="px-6 py-3 bg-accent hover:bg-accent-hover text-bg-base font-semibold rounded-xl transition-all"
          >
            Try Another Document
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col bg-bg-base">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 bg-bg-card border-b border-gray-800">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push('/')}
            className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Back</span>
          </button>
          
          <div className="h-6 w-px bg-gray-700" />
          
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-accent" />
            <h1 className="font-serif text-lg truncate max-w-[300px]" title={filename}>
              {filename}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Stats */}
          <div className="hidden md:flex items-center gap-4 text-sm text-gray-400">
            <span>{qaItems.length} Q&A pairs</span>
            <span className="text-gray-600">•</span>
            <span>{totalPages} pages</span>
          </div>
          
          <button
            onClick={() => router.push('/upload')}
            className="flex items-center gap-2 px-4 py-2 bg-bg-elevated hover:bg-accent/10 border border-gray-700 hover:border-accent/50 rounded-xl transition-all"
          >
            <Upload className="w-4 h-4" />
            <span className="hidden sm:inline">New Document</span>
          </button>

          {/* User Menu with Sign Out */}
          <UserMenu />
        </div>
      </header>

      {/* Main Content - Side by Side */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left Pane - PDF Viewer */}
        <div className="w-1/2 p-4 pr-2">
          {documentId && (
            <PDFViewer
              documentId={documentId}
              pageNumber={currentPdfPageIndex}
              displayPageNumber={currentPageNumber}
              totalPages={totalPages}
              highlightStartLine={highlightStartLine}
              highlightEndLine={highlightEndLine}
              endPage={endPage}
              endPdfPageIndex={endPdfPageIndex}
              onPageChange={handlePageChange}
            />
          )}
        </div>

        {/* Right Pane - Summary Display */}
        <div className="w-1/2 p-4 pl-2">
          <SummaryDisplay
            item={currentItem}
            currentIndex={currentIndex}
            totalItems={qaItems.length}
            onPrevious={goToPrevious}
            onNext={goToNext}
          />
        </div>
      </main>

      {/* Progress Bar */}
      <div className="h-1 bg-bg-card">
        <div 
          className="h-full bg-accent transition-all duration-300"
          style={{ width: `${((currentIndex + 1) / qaItems.length) * 100}%` }}
        />
      </div>
    </div>
  )
}
