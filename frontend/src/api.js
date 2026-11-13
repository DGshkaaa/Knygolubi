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
  resendVerification: (data) => api.post('/auth/resend-verification', data),
  verifyEmail: (token) => api.get('/auth/verify-email', { params: { token } }),
  me: () => api.get('/auth/me'),
}

export const booksApi = {
  list: (params) => api.get('/books', { params }),
  announcements: (params) => api.get('/books/announcements', { params }),
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

export const boardApi = {
  list: (params) => api.get('/board', { params }),
  mine: (params) => api.get('/board/mine', { params }),
  get: (id) => api.get(`/board/${id}`),
  create: (data) => api.post('/board', data),
  update: (id, data) => api.put(`/board/${id}`, data),
  status: (id, status) => api.patch(`/board/${id}/status`, { status }),
  remove: (id) => api.delete(`/board/${id}`),
  responses: (id) => api.get(`/board/${id}/responses`),
  respond: (id, text) => api.post(`/board/${id}/responses`, { text }),
  message: (id, text) => api.post(`/board/threads/${id}/messages`, { text }),
}

export const notificationsApi = {
  list: () => api.get('/users/me/notifications'),
  markRead: () => api.patch('/users/me/notifications/read'),
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
  users: (params) => api.get('/moderation/users', { params }),
  deleteUser: (id) => api.delete(`/moderation/users/${id}`),
  updateApproval: (id, isApproved) => api.patch(`/moderation/users/${id}/approval`, null, { params: { is_approved: isApproved } }),
  updateRole: (id, role) => api.patch(`/moderation/users/${id}/role`, null, { params: { role } }),
  proposals: () => api.get('/moderation/proposals'),
  editProposal: (id, data) => api.patch(`/moderation/proposals/${id}/edit`, data),
  decideProposal: (id, data) => api.patch(`/moderation/proposals/${id}`, data),
}

export default api
