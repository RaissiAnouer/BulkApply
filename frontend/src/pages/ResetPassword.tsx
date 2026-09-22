import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Container, Card, Form, Button, Alert } from 'react-bootstrap'
import { api, ApiException } from '../api/client'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!token) {
      setError('Invalid or missing password reset token.')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      await api('/api/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password }),
      })
      setSuccess(true)
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to reset password. The link may have expired.')
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
        <p className="text-center text-muted mb-4">Set a new password</p>

        {!token && (
          <div>
            <Alert variant="danger">
              No reset token found in the URL. Please request a new password reset link.
            </Alert>
            <Link to="/forgot-password">
              <Button
                variant="outline-primary"
                className="w-100 mt-2"
                style={{ borderColor: 'var(--color-primary)', color: 'var(--color-primary)' }}
              >
                Request New Reset Link
              </Button>
            </Link>
          </div>
        )}

        {token && success && (
          <div className="text-center">
            <div style={{ fontSize: 48 }} className="mb-2">🎉</div>
            <Alert variant="success">Your password has been reset successfully!</Alert>
            <Link to="/login">
              <Button
                className="w-100 mt-2"
                style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
              >
                Proceed to Login
              </Button>
            </Link>
          </div>
        )}

        {token && !success && (
          <>
            {error && <Alert variant="danger">{error}</Alert>}
            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3" controlId="resetPassword">
                <Form.Label>New Password</Form.Label>
                <Form.Control
                  type="password"
                  placeholder="Min 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </Form.Group>

              <Form.Group className="mb-4" controlId="resetConfirmPassword">
                <Form.Label>Confirm New Password</Form.Label>
                <Form.Control
                  type="password"
                  placeholder="Confirm password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
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
                {loading ? 'Resetting Password...' : 'Reset Password'}
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
