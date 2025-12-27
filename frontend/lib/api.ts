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

export const startJob = async (
  documentId: string, 
  firstPage: number = 1, 
  lastPage?: number,
  pageRanges?: Array<{start: number, end: number}>
) => {
  const payload: any = {
    document_id: documentId,
    first_page: firstPage,
  }
  
  if (lastPage) {
    payload.last_page = lastPage
  }
  
  if (pageRanges && pageRanges.length > 0) {
    payload.page_ranges = pageRanges
  }
  
  const response = await api.post('/api/jobs/start', payload)
  
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

/**
 * Get the first and last pages that contain Q&A pairs for smart page selection.
 */
export const getQAPageRange = async (documentId: string): Promise<{
  first_qa_page: number
  last_qa_page: number
  total_pages: number
}> => {
  const response = await api.get(`/api/documents/${documentId}/qa-page-range`)
  return response.data
}

/**
 * Update case information for a document.
 */
export const updateCaseInfo = async (
  documentId: string,
  caseInfo: {
    case_name?: string
    case_number?: string
    deposition_date?: string
    attorneys?: string[]
    witness_name?: string
  }
) => {
  const response = await api.patch(`/api/documents/${documentId}/case-info`, caseInfo)
  return response.data
}

/**
 * Get Q/A test log content from the backend.
 * Returns the raw text content of the log file.
 */
export const getQATestLog = async (logFilePath: string): Promise<string> => {
  const response = await api.get('/api/documents/qa-test-log', {
    params: { log_file: logFilePath }
  })
  return response.data
}




