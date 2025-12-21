import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 second timeout for uploads
})

// API functions
export const uploadDocument = async (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/api/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  
  return response.data
}

export const startJob = async (documentId: string, firstPage: number = 1, lastPage?: number) => {
  const response = await api.post('/api/jobs/start', {
    document_id: documentId,
    first_page: firstPage,
    last_page: lastPage,
  })
  
  return response.data
}

export const getJobStatus = async (jobId: string) => {
  const response = await api.get(`/api/jobs/${jobId}/status`)
  return response.data
}

export const getDocument = async (documentId: string) => {
  const response = await api.get(`/api/documents/${documentId}`)
  return response.data
}

export const getQAItems = async (documentId: string) => {
  const response = await api.get(`/api/documents/${documentId}/qa-items`)
  return response.data
}

/**
 * Get PDF page as image URL for reading mode display.
 * Returns the URL that can be used in an <img> tag.
 */
export const getPDFPageUrl = (documentId: string, pageNumber: number): string => {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  return `${baseUrl}/api/documents/${documentId}/page/${pageNumber}`
}

/**
 * Fetch PDF page image as blob (for more control over loading).
 */
export const getPDFPage = async (documentId: string, pageNumber: number): Promise<{
  imageUrl: string
  pageNumber: number
  totalPages: number
  imageWidth: number
  imageHeight: number
  originalWidth: number
  originalHeight: number
}> => {
  const response = await api.get(`/api/documents/${documentId}/page/${pageNumber}`, {
    responseType: 'blob'
  })
  
  const imageUrl = URL.createObjectURL(response.data)
  
  return {
    imageUrl,
    pageNumber: parseInt(response.headers['x-page-number'] || '1'),
    totalPages: parseInt(response.headers['x-total-pages'] || '1'),
    imageWidth: parseInt(response.headers['x-image-width'] || '0'),
    imageHeight: parseInt(response.headers['x-image-height'] || '0'),
    originalWidth: parseFloat(response.headers['x-original-width'] || '0'),
    originalHeight: parseFloat(response.headers['x-original-height'] || '0')
  }
}




