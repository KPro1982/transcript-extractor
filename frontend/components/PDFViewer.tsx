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
  endPage?: number            // End page for cross-page Q/A (printed page number)
  endPdfPageIndex?: number    // PDF page index for end page (for cross-page rendering)
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
  endPage,
  endPdfPageIndex,
  onPageChange
}: PDFViewerProps) {
  // Check if this is a cross-page Q/A
  // Compare using displayPageNumber (printed page) since endPage is also a printed page number
  // This avoids false positives when pdf_page_index differs from page_number (e.g., cover sheets)
  const printedStartPage = displayPageNumber ?? pageNumber
  const isCrossPage = endPage && endPage !== printedStartPage
  // Use endPdfPageIndex for loading the second page (falls back to endPage for backward compatibility)
  const secondPagePdfIndex = isCrossPage ? (endPdfPageIndex ?? endPage) : null
  // Use displayPageNumber for header if provided, otherwise use pageNumber
  const shownPageNumber = displayPageNumber ?? pageNumber
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [imageUrl2, setImageUrl2] = useState<string | null>(null) // Second page for cross-page Q/A
  const [displayDimensions, setDisplayDimensions] = useState({ width: 0, height: 0 })
  const [displayDimensions2, setDisplayDimensions2] = useState({ width: 0, height: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)
  const imageRef2 = useRef<HTMLImageElement>(null)
  const highlightRef = useRef<HTMLDivElement>(null)
  const highlightRef2 = useRef<HTMLDivElement>(null)

  // Load the PDF page image(s)
  useEffect(() => {
    if (!documentId || pageNumber < 1) return

    setLoading(true)
    setError(null)

    const url = getPDFPageUrl(documentId, pageNumber)
    setImageUrl(url)
    
    // Load second page for cross-page Q/A
    if (secondPagePdfIndex && secondPagePdfIndex <= totalPages) {
      const url2 = getPDFPageUrl(documentId, secondPagePdfIndex)
      setImageUrl2(url2)
    } else {
      setImageUrl2(null)
    }
  }, [documentId, pageNumber, secondPagePdfIndex, totalPages])

  const handleImageLoad = useCallback(() => {
    // Use displayed dimensions, not natural dimensions
    if (imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect()
      setDisplayDimensions({
        width: rect.width,
        height: rect.height
      })
    }
    // Only set loading to false when all required images are loaded
    if (!isCrossPage || (isCrossPage && imageRef2.current)) {
      setLoading(false)
    }
  }, [isCrossPage])
  
  const handleImageLoad2 = useCallback(() => {
    if (imageRef2.current) {
      const rect = imageRef2.current.getBoundingClientRect()
      setDisplayDimensions2({
        width: rect.width,
        height: rect.height
      })
    }
    setLoading(false)
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

    // Adjust highlighting to be between line numbers (move up 1.5 lines)
    const startY = topMargin + (highlightStartLine - 1.5) * lineHeight
    
    // For cross-page Q/A, highlight to end of first page
    const endLine = isCrossPage ? LINES_PER_PAGE : highlightEndLine
    const endY = topMargin + (endLine - 0.5) * lineHeight

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
  }, [displayDimensions.height, highlightStartLine, highlightEndLine, isCrossPage])
  
  // Calculate highlight for second page (cross-page Q/A continuation)
  const calculateHighlightStyle2 = useCallback(() => {
    if (!isCrossPage || !displayDimensions2.height) {
      return { display: 'none' as const }
    }

    const topMarginPercent = 0.12
    const bottomMarginPercent = 0.08
    const contentHeight = displayDimensions2.height * (1 - topMarginPercent - bottomMarginPercent)
    const lineHeight = contentHeight / LINES_PER_PAGE
    const topMargin = displayDimensions2.height * topMarginPercent

    // Start from line 1 on second page, continue to highlightEndLine (between line numbers)
    const startY = topMargin + (1 - 1.5) * lineHeight
    const endY = topMargin + (highlightEndLine - 0.5) * lineHeight

    return {
      position: 'absolute' as const,
      left: 0,
      top: startY,
      height: Math.max(endY - startY, lineHeight),
      width: '100%',
      backgroundColor: 'rgba(201, 166, 107, 0.2)',
      borderLeft: '4px solid #c9a66b',
      borderRadius: '0 4px 4px 0',
      boxShadow: '0 0 20px rgba(201, 166, 107, 0.6), 0 0 40px rgba(201, 166, 107, 0.3)',
      transition: 'all 0.3s ease-out',
      zIndex: 10
    }
  }, [displayDimensions2.height, highlightEndLine, isCrossPage])

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
  const highlightStyle2 = calculateHighlightStyle2()

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
          <div className="space-y-0">
            {/* First Page */}
            <div className="relative">
              {/* Line Highlight Indicator - Thick gold bar */}
              {highlightStyle.display !== 'none' && (
                <div 
                  ref={highlightRef}
                  style={highlightStyle} 
                />
              )}
              
              {/* Wrapper to crop footer when cross-page */}
              {isCrossPage && displayDimensions.height ? (
                <div className="overflow-hidden" style={{ height: `${displayDimensions.height * 0.92}px` }}>
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
              ) : (
                <img
                  ref={imageRef}
                  src={imageUrl}
                  alt={`Page ${pageNumber}`}
                  onLoad={handleImageLoad}
                  onError={handleImageError}
                  className={`w-full h-auto ${loading ? 'opacity-0' : 'opacity-100'} transition-opacity duration-300`}
                  draggable={false}
                />
              )}
            </div>
            
            {/* Second Page (for cross-page Q/A) */}
            {isCrossPage && imageUrl2 && (
              <div 
                className="relative"
                style={displayDimensions.height ? {
                  marginTop: `-${displayDimensions.height * 0.08}px`
                } : undefined}
              >
                {/* Line Highlight Indicator for second page */}
                {highlightStyle2.display !== 'none' && (
                  <div 
                    ref={highlightRef2}
                    style={highlightStyle2} 
                  />
                )}
                
                {/* Wrapper to crop header when cross-page */}
                {displayDimensions2.height ? (
                  <div className="overflow-hidden" style={{ height: `${displayDimensions2.height * 0.88}px` }}>
                    <img
                      ref={imageRef2}
                      src={imageUrl2}
                      alt={`Page ${endPage}`}
                      onLoad={handleImageLoad2}
                      onError={handleImageError}
                      className={`w-full h-auto ${loading ? 'opacity-0' : 'opacity-100'} transition-opacity duration-300`}
                      style={{ marginTop: `-${displayDimensions2.height * 0.12}px` }}
                      draggable={false}
                    />
                  </div>
                ) : (
                  <img
                    ref={imageRef2}
                    src={imageUrl2}
                    alt={`Page ${endPage}`}
                    onLoad={handleImageLoad2}
                    onError={handleImageError}
                    className={`w-full h-auto ${loading ? 'opacity-0' : 'opacity-100'} transition-opacity duration-300`}
                    draggable={false}
                  />
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Line Number Indicator Footer */}
      <div className="px-4 py-2 bg-bg-card border-t border-gray-800 text-xs text-gray-500 text-center">
        {isCrossPage ? (
          <>Lines {highlightStartLine} (Page {shownPageNumber}) - {highlightEndLine} (Page {endPage})</>
        ) : (
          <>Lines {highlightStartLine}-{highlightEndLine}</>
        )}
      </div>
    </div>
  )
}
