import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { api, setToken, removeToken, getToken, ApiException } from '../api/client'

interface User {
  id: number
  email: string
  name: string
  phone: string | null
  location: string | null
  role: string
  is_active: boolean
  is_verified: boolean
}

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // On mount, check if we have a valid token with retry support while backend boots
  useEffect(() => {
    const token = getToken()
    if (!token) {
      setLoading(false)
      return
    }

    let isMounted = true

    const verifyAuth = async (retries = 3, delay = 600) => {
      for (let attempt = 0; attempt <= retries; attempt++) {
        try {
          const userData = await api<User>('/api/auth/me')
          if (isMounted) {
            setUser(userData)
            setLoading(false)
          }
          return
        } catch (err) {
          // If token is genuinely expired or invalid, clear it
          if (err instanceof ApiException && (err.status === 401 || err.status === 403)) {
            removeToken()
            if (isMounted) {
              setUser(null)
              setLoading(false)
            }
            return
          }
          // Network error or backend process still starting up — wait and retry
          if (attempt < retries) {
            await new Promise((r) => setTimeout(r, delay))
          }
        }
      }
      if (isMounted) {
        setLoading(false)
      }
    }

    verifyAuth()

    return () => {
      isMounted = false
    }
  }, [])

  const login = async (email: string, password: string) => {
    const data = await api<{ access_token: string; user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setToken(data.access_token)
    setUser(data.user)
  }

  const logout = () => {
    removeToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
