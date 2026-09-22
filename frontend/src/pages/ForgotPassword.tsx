import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Container, Card, Form, Button, Alert } from 'react-bootstrap'
import { api, ApiException } from '../api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await api('/api/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
      setSubmitted(true)
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to send reset link. Please try again.')
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
        <p className="text-center text-muted mb-4">Reset your password</p>

        {submitted ? (
          <div className="text-center">
            <div style={{ fontSize: 48 }} className="mb-2">📬</div>
            <Alert variant="info">
              If an account with <strong>{email}</strong> exists, a password reset link has been sent.
            </Alert>
            <p className="text-muted small">
              (For development: check the backend terminal for the reset link)
            </p>
            <Link to="/login">
              <Button
                variant="outline-primary"
                className="w-100 mt-2"
                style={{ borderColor: 'var(--color-primary)', color: 'var(--color-primary)' }}
              >
                Back to Login
              </Button>
            </Link>
          </div>
        ) : (
          <>
            {error && <Alert variant="danger">{error}</Alert>}
            <p className="text-muted small mb-3">
              Enter your email address and we will send you a link to reset your password.
            </p>
            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3" controlId="forgotEmail">
                <Form.Label>Email address</Form.Label>
                <Form.Control
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </Form.Group>

              <Button
                type="submit"
                className="w-100 mb-3"
                disabled={loading}
                style={{
                  backgroundColor: 'var(--color-primary)',
                  borderColor: 'var(--color-primary)',
                  fontWeight: 600,
                }}
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
              </Button>

              <div className="text-center">
                <Link
                  to="/login"
                  style={{ color: 'var(--color-primary)', textDecoration: 'none', fontSize: 13 }}
                >
                  &larr; Back to Login
                </Link>
              </div>
            </Form>
          </>
        )}
      </Card>
    </Container>
  )
}
