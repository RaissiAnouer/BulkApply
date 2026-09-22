import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Container, Card, Form, Button, Alert } from 'react-bootstrap'
import { useAuth } from '../context/AuthContext'
import { ApiException } from '../api/client'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('An unexpected error occurred')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Container className="d-flex justify-content-center align-items-center vh-100">
      <Card style={{ width: '100%', maxWidth: 420, padding: 32, borderRadius: 12 }}>
        <h2
          className="text-center mb-1"
          style={{ color: 'var(--color-primary)', fontWeight: 700 }}
        >
          AutoApply
        </h2>
        <p className="text-center text-muted mb-4">Sign in to your account</p>

        {error && <Alert variant="danger">{error}</Alert>}

        <Form onSubmit={handleSubmit}>
          <Form.Group className="mb-3" controlId="loginEmail">
            <Form.Label>Email address</Form.Label>
            <Form.Control
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Form.Group>

          <Form.Group className="mb-2" controlId="loginPassword">
            <Form.Label>Password</Form.Label>
            <Form.Control
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Form.Group>

          <div className="text-end mb-3">
            <Link to="/forgot-password" style={{ fontSize: 13 }}>
              Forgot password?
            </Link>
          </div>

          <Button
            type="submit"
            className="w-100"
            style={{ backgroundColor: 'var(--color-primary)', border: 'none' }}
            disabled={loading}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </Button>
        </Form>

        <p className="text-center mt-3 mb-0" style={{ fontSize: 14 }}>
          Don't have an account?{' '}
          <Link to="/register">Sign up</Link>
        </p>
      </Card>
    </Container>
  )
}
