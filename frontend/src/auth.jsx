import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { authApi } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('knigoluby_token'))
  const [user, setUser] = useState(null)

  useEffect(() => {
    if (!token) {
      setUser(null)
      return
    }
    authApi.me().then(({ data }) => setUser(data)).catch(() => {
      localStorage.removeItem('knigoluby_token')
      setToken(null)
    })
  }, [token])

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token),
      async login(credentials) {
        const { data } = await authApi.login(credentials)
        localStorage.setItem('knigoluby_token', data.access_token)
        setToken(data.access_token)
      },
      async register(payload) {
        await authApi.register(payload)
      },
      logout() {
        localStorage.removeItem('knigoluby_token')
        setToken(null)
        setUser(null)
      },
    }),
    [token, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
