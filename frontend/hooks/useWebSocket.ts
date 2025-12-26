import { useEffect, useState, useRef, useCallback } from 'react'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export interface JobProgress {
  status: string
  progress: number
  message?: string
  document_id?: string
  detailedProgress?: {
    current: number
    total: number
    percentage: number
  }
}

export function useJobProgress(jobId: string | null) {
  const [progress, setProgress] = useState<JobProgress>({
    status: 'queued',
    progress: 0,
  })
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()

  const connect = useCallback(() => {
    if (!jobId) return

    try {
      const ws = new WebSocket(`${WS_URL}/ws/jobs/${jobId}`)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setError(null)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'connected') {
            console.log('WebSocket handshake complete')
          } else if (data.type === 'pong') {
            // Ignore pong responses
            return
          } else if (data.type === 'progress') {
          // Parse detailed progress from message
          // Format: "AI processing: 245/856 items (28.6%)"
          const message = data.data.message || ''
          const match = message.match(/(\d+)\/(\d+) items/)
          let detailedProgress
          
          if (match) {
            const current = parseInt(match[1])
            const total = parseInt(match[2])
            detailedProgress = {
              current,
              total,
              percentage: (current / total) * 100
            }
          }
          
          setProgress({
            status: data.data.status,
            progress: data.data.progress,
            message,
            detailedProgress,
          })
        } else if (data.type === 'complete') {
          setProgress({
            status: 'completed',
            progress: 100,
            message: 'Processing complete',
            document_id: data.data?.document_id,
          })
        } else if (data.type === 'error') {
          setError(data.data.error_message)
          setProgress({
            status: 'failed',
            progress: 0,
            message: data.data.error_message,
          })
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err, event.data)
      }
    }

      ws.onerror = (event) => {
        console.error('WebSocket error:', event)
        setError('Connection error')
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)
        
        // Attempt reconnection if not completed
        if (progress.status !== 'completed' && progress.status !== 'failed') {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('Attempting to reconnect...')
            connect()
          }, 3000)
        }
      }

      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 30000)

      return () => {
        clearInterval(pingInterval)
      }
    } catch (err) {
      console.error('Failed to connect WebSocket:', err)
      setError('Failed to connect')
    }
  }, [jobId, progress.status])

  useEffect(() => {
    if (jobId) {
      connect()
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [jobId, connect])

  return {
    progress,
    isConnected,
    error,
  }
}

