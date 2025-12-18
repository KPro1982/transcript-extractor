'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react'
import { getPDFPageUrl } from '@/lib/api'

interface PDFViewerProps {
  documentId: string
  pageNumber: number
  totalPages: number
  highlightStartLine: number
  highlightEndLine: number
  onPageChange?: (page: number) => void
}

const LINES_PER_PAGE = 25

/**
 * PDF page viewer with line highlighting for reading mode.
 * Displays PDF pages as images with a left border indicator showing
 * which lines correspond to the current summary.
 */
export default function PDFViewer({
  documentId,
  pageNumber,
  totalPages,
  highlightStartLine,
  highlightEndLine,
  onPageChange
}: PDFViewerProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)

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
    if (imageRef.current) {
      setImageDimensions({
        width: imageRef.current.naturalWidth,
        height: imageRef.current.naturalHeight
      })
    }
  }, [])

  const handleImageError = useCallback(() => {
    setLoading(false)
    setError('Failed to load PDF page. The document may need to be re-uploaded.')
  }, [])

  // Calculate highlight position based on line numbers
  const calculateHighlightStyle = useCallback(() => {
    if (!imageDimensions.height || highlightStartLine < 1) {
      return { display: 'none' as const }
    }

    // Calculate line positions based on legal transcript standard (25 lines/page)
    // Account for margins (approximately 10% top/bottom)
    const marginPercent = 0.10
    const contentHeight = imageDimensions.height * (1 - 2 * marginPercent)
    const lineHeight = contentHeight / LINES_PER_PAGE
    const topMargin = imageDimensions.height * marginPercent

    const startY = topMargin + (highlightStartLine - 1) * lineHeight
    const endY = topMargin + highlightEndLine * lineHeight

    return {
      position: 'absolute' as const,
      left: 0,
      top: `${(startY / imageDimensions.height) * 100}%`,
      height: `${((endY - startY) / imageDimensions.height) * 100}%`,
      width: '4px',
      backgroundColor: '#c9a66b',
      borderRadius: '0 2px 2px 0',
      boxShadow: '0 0 10px rgba(201, 166, 107, 0.5)',
      transition: 'all 0.3s ease-out'
    }
  }, [imageDimensions.height, highlightStartLine, highlightEndLine])

  // Scroll to highlight when it changes
  useEffect(() => {
    if (!containerRef.current || !imageDimensions.height || highlightStartLine < 1) return

    const marginPercent = 0.10
    const contentHeight = imageDimensions.height * (1 - 2 * marginPercent)
    const lineHeight = contentHeight / LINES_PER_PAGE
    const topMargin = imageDimensions.height * marginPercent

    const startY = topMargin + (highlightStartLine - 1) * lineHeight
    
    // Get the container's visible area
    const container = containerRef.current
    const containerRect = container.getBoundingClientRect()
    const scrollTarget = startY - containerRect.height / 3 // Position highlight 1/3 from top

    container.scrollTo({
      top: Math.max(0, scrollTarget),
      behavior: 'smooth'
    })
  }, [highlightStartLine, imageDimensions.height])

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
          Page <span className="text-white font-semibold">{pageNumber}</span> of {totalPages}
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
        style={{ scrollBehavior: 'smooth' }}
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-elevated">
            <div className="text-center">
              <Loader2 className="w-8 h-8 text-accent animate-spin mx-auto mb-2" />
              <p className="text-sm text-gray-400">Loading page {pageNumber}...</p>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-elevated p-8">
            <div className="text-center">
              <div className="text-red-400 mb-2">⚠️</div>
              <p className="text-sm text-red-400">{error}</p>
            </div>
          </div>
        )}

        {imageUrl && (
          <div className="relative inline-block min-w-full">
            {/* Line Highlight Indicator */}
            <div style={calculateHighlightStyle()} />
            
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
        Highlighting lines {highlightStartLine}-{highlightEndLine}
      </div>
    </div>
  )
}

