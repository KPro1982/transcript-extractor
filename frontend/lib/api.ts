import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
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

