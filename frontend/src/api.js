import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('knigoluby_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const authApi = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
}

export const booksApi = {
  list: (params) => api.get('/books', { params }),
  get: (id) => api.get(`/books/${id}`),
  create: (data) => api.post('/books', data),
  update: (id, data) => api.put(`/books/${id}`, data),
  remove: (id) => api.delete(`/books/${id}`),
  borrow: (id) => api.post(`/books/${id}/borrow`),
  queue: (id) => api.post(`/books/${id}/queue`),
  leaveQueue: (id) => api.delete(`/books/${id}/queue`),
  returnBook: (id, finished = true) => api.post(`/books/${id}/return`, null, { params: { finished } }),
  reviews: (id) => api.get(`/books/${id}/reviews`),
  addReview: (id, data) => api.post(`/books/${id}/reviews`, data),
  deleteReview: (bookId, reviewId) => api.delete(`/books/${bookId}/reviews/${reviewId}`),
}

export const notificationsApi = {
  list: () => api.get('/users/me/notifications'),
  borrowed: () => api.get('/users/me/borrowed'),
}

export const proposalsApi = {
  create: (data) => api.post('/proposals', data),
  mine: () => api.get('/proposals/mine'),
}

export const profilesApi = {
  mine: () => api.get('/users/me/profile'),
  get: (id) => api.get(`/users/${id}/profile`),
  update: (data) => api.put('/users/me/profile', data),
  toggleFavorite: (bookId) => api.post(`/users/me/favorites/${bookId}`),
}

export const moderationApi = {
  users: () => api.get('/moderation/users'),
  updateRole: (id, role) => api.patch(`/moderation/users/${id}/role`, null, { params: { role } }),
  proposals: () => api.get('/moderation/proposals'),
  editProposal: (id, data) => api.patch(`/moderation/proposals/${id}/edit`, data),
  decideProposal: (id, data) => api.patch(`/moderation/proposals/${id}`, data),
}

export default api
