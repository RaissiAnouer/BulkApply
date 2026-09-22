import { useEffect, useState, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Container, Card, Button, Alert, Spinner } from 'react-bootstrap'
import { api, ApiException } from '../api/client'

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [loading, setLoading] = useState(true)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  const verifiedRef = useRef(false)

  useEffect(() => {
    if (!token) {
      setError('No verification token provided in the link.')
      setLoading(false)
      return
    }

    if (verifiedRef.current) return
    verifiedRef.current = true

    api('/api/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    })
      .then(() => {
        setSuccess(true)
      })
      .catch((err) => {
        if (err instanceof ApiException) {
          setError(err.message)
        } else {
          setError('Verification failed. Please try again.')
        }
      })
      .finally(() => {
        setLoading(false)
      })
  }, [token])

  return (
    <Container className="d-flex justify-content-center align-items-center vh-100">
      <Card style={{ width: '100%', maxWidth: 420, padding: 32, borderRadius: 12 }}>
        <div className="text-center">
          <h2
            className="mb-3"
            style={{ color: 'var(--color-primary)', fontWeight: 700 }}
          >
            AutoApply
          </h2>
          <h4 className="mb-4">Email Verification</h4>

          {loading && (
            <div className="py-4">
              <Spinner animation="border" role="status" className="mb-3" />
              <p className="text-muted">Verifying your email address...</p>
            </div>
          )}

          {!loading && success && (
            <div>
              <div style={{ fontSize: 48 }} className="mb-2">✅</div>
              <Alert variant="success">Your email has been verified successfully!</Alert>
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

          {!loading && error && (
            <div>
              <div style={{ fontSize: 48 }} className="mb-2">❌</div>
              <Alert variant="danger">{error}</Alert>
              <div className="d-flex gap-2 justify-content-center mt-3">
                <Link to="/login">
                  <Button variant="outline-secondary">Go to Login</Button>
                </Link>
                <Link to="/register">
                  <Button
                    style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                  >
                    Register Again
                  </Button>
                </Link>
              </div>
            </div>
          )}
        </div>
      </Card>
    </Container>
  )
}
