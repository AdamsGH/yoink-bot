import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

export const apiClient = axios.create({ baseURL: BASE_URL })

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (r) => r,
  (err: unknown) => {
    if (
      axios.isAxiosError(err) &&
      err.response?.status === 401
    ) {
      localStorage.removeItem('access_token')
      window.location.reload()
    }
    return Promise.reject(err)
  }
)
