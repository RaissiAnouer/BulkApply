import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Container, Card, Form, Button, Alert } from 'react-bootstrap'
import { api, ApiException } from '../api/client'

export default function Register() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      await api('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      })
      setSuccess(true)
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

  if (success) {
    return (
      <Container className="d-flex justify-content-center align-items-center vh-100">
        <Card style={{ width: '100%', maxWidth: 420, padding: 32, borderRadius: 12 }}>
          <div className="text-center">
            <div style={{ fontSize: 48 }}>✉️</div>
            <h3 className="mt-3">Check your email</h3>
            <p className="text-muted">
              We sent a verification link to <strong>{email}</strong>.
              Please verify your email before logging in.
            </p>
            <Link to="/login">
              <Button
                variant="outline-primary"
                style={{ borderColor: 'var(--color-primary)', color: 'var(--color-primary)' }}
              >
                Go to Login
              </Button>
            </Link>
          </div>
        </Card>
      </Container>
    )
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
        <p className="text-center text-muted mb-4">Create your account</p>

        {error && <Alert variant="danger">{error}</Alert>}

        <Form onSubmit={handleSubmit}>
          <Form.Group className="mb-3" controlId="registerName">
            <Form.Label>Full name</Form.Label>
            <Form.Control
              type="text"
              placeholder="John Doe"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </Form.Group>

          <Form.Group className="mb-3" controlId="registerEmail">
            <Form.Label>Email address</Form.Label>
            <Form.Control
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Form.Group>

          <Form.Group className="mb-3" controlId="registerPassword">
            <Form.Label>Password</Form.Label>
            <Form.Control
              type="password"
              placeholder="Min 8 chars, upper, lower, digit, special"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Form.Group>

          <Form.Group className="mb-3" controlId="registerConfirmPassword">
            <Form.Label>Confirm password</Form.Label>
            <Form.Control
              type="password"
              placeholder="Re-enter your password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </Form.Group>

          <Button
            type="submit"
            className="w-100"
            style={{ backgroundColor: 'var(--color-primary)', border: 'none' }}
            disabled={loading}
          >
            {loading ? 'Creating account...' : 'Create account'}
          </Button>
        </Form>

        <p className="text-center mt-3 mb-0" style={{ fontSize: 14 }}>
          Already have an account?{' '}
          <Link to="/login">Sign in</Link>
        </p>
      </Card>
    </Container>
  )
}
