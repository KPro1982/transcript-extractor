'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react'
import { getPDFPageUrl } from '@/lib/api'

interface PDFViewerProps {
  documentId: string
  pageNumber: number           // PDF page index (1-based) - used for fetching the image
  displayPageNumber?: number   // Printed transcript page number - shown in the header
  totalPages: number
  highlightStartLine: number
  highlightEndLine: number
  onPageChange?: (page: number) => void
}

const LINES_PER_PAGE = 25

/**
 * PDF page viewer with line highlighting for reading mode.
 * Displays PDF pages as images with a thick left border indicator showing
 * which lines correspond to the current summary.
 * 
 * Note: pageNumber is the PDF file index (for fetching), while displayPageNumber
 * is the printed transcript page (for display). This handles transcripts with
 * cover sheets, index pages, or partial uploads.
 */
export default function PDFViewer({
  documentId,
  pageNumber,
  displayPageNumber,
  totalPages,
  highlightStartLine,
  highlightEndLine,
  onPageChange
}: PDFViewerProps) {
  // Use displayPageNumber for header if provided, otherwise use pageNumber
  const shownPageNumber = displayPageNumber ?? pageNumber
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [displayDimensions, setDisplayDimensions] = useState({ width: 0, height: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)
  const highlightRef = useRef<HTMLDivElement>(null)

  // Load the PDF page image
  useEffect(() => {
    if (!documentId || pageNumber < 1) return

    setLoading(true)
    setError(null)

    const url = getPDFPageUrl(documentId, pageNumber)
    setImageUrl(url)
  }, [documentId, pageNumber])

  const handleImageLoad = useCallback(() => {
    setLoading(false)
    // Use displayed dimensions, not natural dimensions
    if (imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect()
      setDisplayDimensions({
        width: rect.width,
        height: rect.height
      })
    }
  }, [])

  const handleImageError = useCallback(() => {
    setLoading(false)
    setError('Failed to load PDF page. The document may need to be re-uploaded.')
  }, [])

  // Calculate highlight position based on line numbers
  const calculateHighlightStyle = useCallback(() => {
    if (!displayDimensions.height || highlightStartLine < 1) {
      return { display: 'none' as const }
    }

    // Calculate line positions based on legal transcript standard (25 lines/page)
    // Account for margins (approximately 12% top, 8% bottom for legal transcripts)
    const topMarginPercent = 0.12
    const bottomMarginPercent = 0.08
    const contentHeight = displayDimensions.height * (1 - topMarginPercent - bottomMarginPercent)
    const lineHeight = contentHeight / LINES_PER_PAGE
    const topMargin = displayDimensions.height * topMarginPercent

    // Adjust highlighting to move up by 1 line to fix offset issue
    const startY = topMargin + (highlightStartLine - 2) * lineHeight
    const endY = topMargin + (highlightEndLine - 1) * lineHeight

    return {
      position: 'absolute' as const,
      left: 0,
      top: startY,
      height: Math.max(endY - startY, lineHeight), // Minimum one line height
      width: '100%', // Full width highlight
      backgroundColor: 'rgba(201, 166, 107, 0.2)', // Semi-transparent overlay
      borderLeft: '4px solid #c9a66b', // Thick left border for visibility
      borderRadius: '0 4px 4px 0',
      boxShadow: '0 0 20px rgba(201, 166, 107, 0.6), 0 0 40px rgba(201, 166, 107, 0.3)',
      transition: 'all 0.3s ease-out',
      zIndex: 10
    }
  }, [displayDimensions.height, highlightStartLine, highlightEndLine])

  // Scroll to highlight when it changes or image loads
  useEffect(() => {
    if (!containerRef.current || !displayDimensions.height || highlightStartLine < 1 || loading) return

    // Small delay to ensure DOM is updated
    const timer = setTimeout(() => {
      const topMarginPercent = 0.12
      const bottomMarginPercent = 0.08
      const contentHeight = displayDimensions.height * (1 - topMarginPercent - bottomMarginPercent)
      const lineHeight = contentHeight / LINES_PER_PAGE
      const topMargin = displayDimensions.height * topMarginPercent

      const startY = topMargin + (highlightStartLine - 1) * lineHeight
      
      // Scroll to position the highlight about 1/4 from the top of the visible area
      const container = containerRef.current
      if (container) {
        const visibleHeight = container.clientHeight
        const scrollTarget = startY - visibleHeight * 0.25

        container.scrollTo({
          top: Math.max(0, scrollTarget),
          behavior: 'smooth'
        })
      }
    }, 100)

    return () => clearTimeout(timer)
  }, [highlightStartLine, displayDimensions.height, loading])

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (imageRef.current && !loading) {
        const rect = imageRef.current.getBoundingClientRect()
        setDisplayDimensions({
          width: rect.width,
          height: rect.height
        })
      }
    }

    window.addEventListener('resize', updateDimensions)
    return () => window.removeEventListener('resize', updateDimensions)
  }, [loading])

  const goToPreviousPage = useCallback(() => {
    if (pageNumber > 1) {
      onPageChange?.(pageNumber - 1)
    }
  }, [pageNumber, onPageChange])

  const goToNextPage = useCallback(() => {
    if (pageNumber < totalPages) {
      onPageChange?.(pageNumber + 1)
    }
  }, [pageNumber, totalPages, onPageChange])

  const highlightStyle = calculateHighlightStyle()

  return (
    <div className="flex flex-col h-full bg-bg-elevated rounded-xl overflow-hidden">
      {/* Page Navigation Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-bg-card border-b border-gray-800">
        <button
          onClick={goToPreviousPage}
          disabled={pageNumber <= 1}
          className="p-2 rounded-lg hover:bg-bg-elevated disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
        
        <div className="text-sm font-mono text-gray-400">
          Page <span className="text-white font-semibold">{shownPageNumber}</span> of {totalPages}
        </div>
        
        <button
          onClick={goToNextPage}
          disabled={pageNumber >= totalPages}
          className="p-2 rounded-lg hover:bg-bg-elevated disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* PDF Page Display */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-auto relative"
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-elevated z-20">
            <div className="text-center">
              <Loader2 className="w-8 h-8 text-accent animate-spin mx-auto mb-2" />
              <p className="text-sm text-gray-400">Loading page {pageNumber}...</p>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-elevated p-8 z-20">
            <div className="text-center">
              <div className="text-red-400 mb-2">⚠️</div>
              <p className="text-sm text-red-400">{error}</p>
            </div>
          </div>
        )}

        {imageUrl && (
          <div className="relative">
            {/* Line Highlight Indicator - Thick gold bar */}
            {highlightStyle.display !== 'none' && (
              <div 
                ref={highlightRef}
                style={highlightStyle} 
              />
            )}
            
            {/* PDF Page Image */}
            <img
              ref={imageRef}
              src={imageUrl}
              alt={`Page ${pageNumber}`}
              onLoad={handleImageLoad}
              onError={handleImageError}
              className={`w-full h-auto ${loading ? 'opacity-0' : 'opacity-100'} transition-opacity duration-300`}
              draggable={false}
            />
          </div>
        )}
      </div>

      {/* Line Number Indicator Footer */}
      <div className="px-4 py-2 bg-bg-card border-t border-gray-800 text-xs text-gray-500 text-center">
        Lines {highlightStartLine}-{highlightEndLine}
      </div>
    </div>
  )
}
