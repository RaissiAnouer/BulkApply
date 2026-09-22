import { useState, useEffect, useCallback } from 'react'
import { Container, Row, Col, Card, Badge, ProgressBar, Spinner, Alert, Button } from 'react-bootstrap'
import { Link } from 'react-router-dom'
import { api, ApiException } from '../../api/client'
import Navbar from '../../components/Navbar'

interface DashboardMetrics {
  total_users: number
  active_users: number
  suspended_users: number
  total_jobs: number
  applications_today: number
  total_applications: number
  failure_rate_percent: number
  status_breakdown: Record<string, number>
}

const STATUS_COLORS: Record<string, string> = {
  ready: 'secondary',
  applying: 'info',
  submitted: 'primary',
  failed: 'danger',
  interview: 'warning',
  offer: 'success',
  rejected: 'dark',
}

export default function AdminDashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchMetrics = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api<DashboardMetrics>('/api/admin/metrics')
      setMetrics(data)
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to load admin metrics')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMetrics()
  }, [fetchMetrics])

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 1100 }}>
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <div>
            <h2 className="fw-bold mb-1">📊 System Administration Dashboard</h2>
            <p className="text-muted mb-0">Live health, usage statistics, and automation performance</p>
          </div>
          <div className="d-flex gap-2">
            <Link to="/admin/users">
              <Button variant="outline-primary" size="sm">
                👥 Manage Users
              </Button>
            </Link>
            <Link to="/admin/settings">
              <Button variant="outline-secondary" size="sm">
                ⚙️ Settings & Audit Logs
              </Button>
            </Link>
            <Button variant="light" size="sm" onClick={fetchMetrics}>
              🔄 Refresh
            </Button>
          </div>
        </div>

        {error && <Alert variant="danger">{error}</Alert>}

        {loading ? (
          <div className="text-center py-5">
            <Spinner animation="border" variant="primary" />
            <p className="mt-2 text-muted small">Loading system metrics...</p>
          </div>
        ) : metrics ? (
          <>
            {/* Metric Summary Cards */}
            <Row className="g-3 mb-4">
              <Col xs={12} sm={6} md={3}>
                <Card className="border-0 shadow-sm h-100 p-3">
                  <div className="text-muted small fw-semibold">Total Job Seekers</div>
                  <div className="fs-2 fw-bold text-dark mt-1">{metrics.total_users}</div>
                  <div className="small text-muted mt-auto pt-2">
                    <span className="text-success fw-semibold">{metrics.active_users} active</span>
                    {metrics.suspended_users > 0 && (
                      <span className="text-danger ms-2">({metrics.suspended_users} suspended)</span>
                    )}
                  </div>
                </Card>
              </Col>

              <Col xs={12} sm={6} md={3}>
                <Card className="border-0 shadow-sm h-100 p-3">
                  <div className="text-muted small fw-semibold">Total Jobs Added</div>
                  <div className="fs-2 fw-bold text-primary mt-1">{metrics.total_jobs}</div>
                  <div className="small text-muted mt-auto pt-2">Across all candidates</div>
                </Card>
              </Col>

              <Col xs={12} sm={6} md={3}>
                <Card className="border-0 shadow-sm h-100 p-3">
                  <div className="text-muted small fw-semibold">Applications Today (UTC)</div>
                  <div className="fs-2 fw-bold text-success mt-1">{metrics.applications_today}</div>
                  <div className="small text-muted mt-auto pt-2">
                    Total lifetime: {metrics.total_applications}
                  </div>
                </Card>
              </Col>

              <Col xs={12} sm={6} md={3}>
                <Card className="border-0 shadow-sm h-100 p-3">
                  <div className="text-muted small fw-semibold">Automation Failure Rate</div>
                  <div className={`fs-2 fw-bold mt-1 ${metrics.failure_rate_percent > 20 ? 'text-danger' : 'text-dark'}`}>
                    {metrics.failure_rate_percent}%
                  </div>
                  <div className="small text-muted mt-auto pt-2">
                    {metrics.status_breakdown.failed || 0} failed / {metrics.total_applications} total
                  </div>
                </Card>
              </Col>
            </Row>

            {/* Application Status Distribution */}
            <Card className="border-0 shadow-sm mb-4">
              <Card.Header className="bg-white border-0 pt-3 pb-0">
                <h5 className="fw-bold mb-0">Application Status Distribution</h5>
              </Card.Header>
              <Card.Body className="p-4">
                {metrics.total_applications === 0 ? (
                  <p className="text-muted small mb-0">No applications recorded yet.</p>
                ) : (
                  <>
                    <ProgressBar className="mb-3" style={{ height: 24, borderRadius: 8 }}>
                      {Object.entries(metrics.status_breakdown).map(([status, count]) => {
                        if (count === 0) return null
                        const pct = (count / metrics.total_applications) * 100
                        return (
                          <ProgressBar
                            key={status}
                            variant={STATUS_COLORS[status] || 'secondary'}
                            now={pct}
                            label={`${count}`}
                          />
                        )
                      })}
                    </ProgressBar>
                    <div className="d-flex flex-wrap gap-3 mt-3">
                      {Object.entries(metrics.status_breakdown).map(([status, count]) => (
                        <div key={status} className="d-flex align-items-center gap-2 small">
                          <Badge bg={STATUS_COLORS[status] || 'secondary'} style={{ width: 12, height: 12, padding: 0 }}>
                            &nbsp;
                          </Badge>
                          <span className="text-capitalize fw-medium">{status}:</span>
                          <span className="fw-bold">{count}</span>
                          <span className="text-muted">
                            ({metrics.total_applications > 0 ? ((count / metrics.total_applications) * 100).toFixed(1) : 0}%)
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </Card.Body>
            </Card>

            {/* Quick Actions Panel */}
            <Row className="g-3">
              <Col md={6}>
                <Card className="border-0 shadow-sm p-4 h-100">
                  <h5 className="fw-bold mb-2">👥 Candidate User Management</h5>
                  <p className="text-muted small mb-3">
                    Search registered Job Seekers, inspect their parsed profile & resume data, view complete job application history, or suspend/delete accounts.
                  </p>
                  <Link to="/admin/users" className="mt-auto">
                    <Button variant="primary" size="sm">
                      Go to User Management →
                    </Button>
                  </Link>
                </Card>
              </Col>

              <Col md={6}>
                <Card className="border-0 shadow-sm p-4 h-100">
                  <h5 className="fw-bold mb-2">⚙️ System Limits & Audit Trail</h5>
                  <p className="text-muted small mb-3">
                    Configure the global daily application limit enforced per candidate (default: 20) and review administrative audit logs.
                  </p>
                  <Link to="/admin/settings" className="mt-auto">
                    <Button variant="outline-dark" size="sm">
                      System Settings & Logs →
                    </Button>
                  </Link>
                </Card>
              </Col>
            </Row>
          </>
        ) : null}
      </Container>
    </>
  )
}
