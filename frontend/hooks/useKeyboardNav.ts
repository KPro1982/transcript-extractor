import { useEffect, useCallback, useState } from 'react'

interface UseKeyboardNavOptions {
  totalItems: number
  onIndexChange?: (index: number) => void
  enabled?: boolean
}

interface UseKeyboardNavReturn {
  currentIndex: number
  setCurrentIndex: (index: number) => void
  goToNext: () => void
  goToPrevious: () => void
  goToFirst: () => void
  goToLast: () => void
}

/**
 * Hook for keyboard navigation through Q&A items in reading mode.
 * Handles up/down arrow keys to navigate between items.
 */
export function useKeyboardNav({
  totalItems,
  onIndexChange,
  enabled = true
}: UseKeyboardNavOptions): UseKeyboardNavReturn {
  const [currentIndex, setCurrentIndexState] = useState(0)

  const setCurrentIndex = useCallback((index: number) => {
    if (index >= 0 && index < totalItems) {
      setCurrentIndexState(index)
      onIndexChange?.(index)
    }
  }, [totalItems, onIndexChange])

  const goToNext = useCallback(() => {
    if (currentIndex < totalItems - 1) {
      setCurrentIndex(currentIndex + 1)
    }
  }, [currentIndex, totalItems, setCurrentIndex])

  const goToPrevious = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }, [currentIndex, setCurrentIndex])

  const goToFirst = useCallback(() => {
    setCurrentIndex(0)
  }, [setCurrentIndex])

  const goToLast = useCallback(() => {
    setCurrentIndex(totalItems - 1)
  }, [totalItems, setCurrentIndex])

  useEffect(() => {
    if (!enabled || totalItems === 0) return

    const handleKeyDown = (event: KeyboardEvent) => {
      // Ignore if user is typing in an input/textarea
      const target = event.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return
      }

      switch (event.key) {
        case 'ArrowDown':
        case 'j': // Vim-style navigation
          event.preventDefault()
          goToNext()
          break
        case 'ArrowUp':
        case 'k': // Vim-style navigation
          event.preventDefault()
          goToPrevious()
          break
        case 'Home':
          event.preventDefault()
          goToFirst()
          break
        case 'End':
          event.preventDefault()
          goToLast()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enabled, totalItems, goToNext, goToPrevious, goToFirst, goToLast])

  // Reset index if totalItems changes and current index is out of bounds
  useEffect(() => {
    if (currentIndex >= totalItems && totalItems > 0) {
      setCurrentIndexState(totalItems - 1)
    }
  }, [totalItems, currentIndex])

  return {
    currentIndex,
    setCurrentIndex,
    goToNext,
    goToPrevious,
    goToFirst,
    goToLast
  }
}










