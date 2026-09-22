import { useState, useEffect, useCallback } from 'react'
import { Container, Card, Table, Button, Badge, Pagination, Row, Col, Spinner, Alert, Nav, Modal } from 'react-bootstrap'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiException } from '../api/client'
import Navbar from '../components/Navbar'

interface JobSummary {
  id: number
  title: string | null
  company: string | null
  location: string | null
  work_type: string | null
  url: string
  application_url: string | null
}

interface ApplicationItem {
  id: number
  user_id: number
  job_id: number
  status: string
  cover_letter: string | null
  failure_reason: string | null
  execution_id?: string | null
  error_type?: string | null
  error_phase?: string | null
  discovery_step?: number | null
  manual_intervention_required?: boolean
  created_at: string
  updated_at: string
  job: JobSummary | null
}

interface ApplicationListResponse {
  items: ApplicationItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface DailyQuotaResponse {
  limit: number
  used_today: number
  remaining: number
}

export const STATUS_COLORS: Record<string, string> = {
  ready: 'primary',
  applying: 'warning',
  submitted: 'info',
  failed: 'danger',
  interview: 'success',
  offer: 'success',
  rejected: 'secondary',
}

export const STATUS_LABELS: Record<string, string> = {
  ready: 'Ready',
  applying: 'Applying',
  submitted: 'Submitted',
  failed: 'Failed',
  interview: 'Interview',
  offer: 'Offer Received',
  rejected: 'Rejected',
}

const FILTER_TABS = [
  { key: '', label: 'All Applications' },
  { key: 'ready', label: 'Ready' },
  { key: 'applying', label: 'Applying' },
  { key: 'submitted', label: 'Submitted' },
  { key: 'interview', label: 'Interview' },
  { key: 'offer', label: 'Offer' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'failed', label: 'Failed' },
]

export default function Applications() {
  const navigate = useNavigate()
  const [applications, setApplications] = useState<ApplicationItem[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [quota, setQuota] = useState<DailyQuotaResponse | null>(null)

  const fetchQuota = async () => {
    try {
      const res = await api<DailyQuotaResponse>('/api/applications/quota')
      setQuota(res)
    } catch {
      // quota is non-critical for page render
    }
  }

  const fetchApplications = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.append('status', statusFilter)
      params.append('page', String(page))
      params.append('page_size', '15')

      const res = await api<ApplicationListResponse>(`/api/applications?${params.toString()}`)
      setApplications(res.items)
      setTotal(res.total)
      setTotalPages(res.pages || 1)
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to load applications.')
      }
    } finally {
      setLoading(false)
    }
  }, [statusFilter, page])

  useEffect(() => {
    fetchQuota()
  }, [])

  useEffect(() => {
    fetchApplications()
  }, [fetchApplications])

  const [batchSubmitting, setBatchSubmitting] = useState(false)
  const readyApps = applications.filter((a) => a.status === 'ready')
  const failedApps = applications.filter((a) => a.status === 'failed')
  const [retryingId, setRetryingId] = useState<number | null>(null)
  const [cancellingId, setCancellingId] = useState<number | null>(null)

  const handleSingleCancel = async (e: React.MouseEvent, appId: number) => {
    e.stopPropagation()
    setCancellingId(appId)
    setError('')
    try {
      await api(`/api/applications/${appId}/cancel`, { method: 'POST' })
      fetchApplications()
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to cancel application.')
      }
    } finally {
      setCancellingId(null)
    }
  }

  const handleSingleRetry = async (e: React.MouseEvent, appId: number) => {
    e.stopPropagation()
    setRetryingId(appId)
    setError('')
    try {
      await api(`/api/applications/${appId}/retry`, { method: 'POST' })
      fetchApplications()
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to trigger retry.')
      }
    } finally {
      setRetryingId(null)
    }
  }

  const handleBatchRetryFailed = async () => {
    const failedIds = failedApps.map((a) => a.id)
    if (failedIds.length === 0) return
    setBatchSubmitting(true)
    setError('')
    try {
      await api('/api/applications/batch-submit', {
        method: 'POST',
        body: JSON.stringify({ application_ids: failedIds }),
      })
      fetchApplications()
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Batch retry failed.')
      }
    } finally {
      setBatchSubmitting(false)
    }
  }

  const handleBatchSubmit = async () => {
    const readyIds = readyApps.map((a) => a.id)
    if (readyIds.length === 0) return
    setBatchSubmitting(true)
    setError('')
    try {
      await api('/api/applications/batch-submit', {
        method: 'POST',
        body: JSON.stringify({ application_ids: readyIds }),
      })
      fetchApplications()
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Batch automation submission failed.')
      }
    } finally {
      setBatchSubmitting(false)
    }
  }

  // Delete State & Handlers
  const [deleteTargetApp, setDeleteTargetApp] = useState<ApplicationItem | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [showBatchDeleteSubmittedModal, setShowBatchDeleteSubmittedModal] = useState(false)
  const [batchDeleting, setBatchDeleting] = useState(false)

  const submittedApps = applications.filter((a) => a.status === 'submitted')

  const handleDeleteSingle = async () => {
    if (!deleteTargetApp) return
    setDeletingId(deleteTargetApp.id)
    setError('')
    try {
      await api(`/api/applications/${deleteTargetApp.id}`, { method: 'DELETE' })
      setDeleteTargetApp(null)
      fetchApplications()
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to delete application.')
      }
    } finally {
      setDeletingId(null)
    }
  }

  const handleBatchDeleteSubmitted = async () => {
    const submittedIds = submittedApps.map((a) => a.id)
    if (submittedIds.length === 0) return
    setBatchDeleting(true)
    setError('')
    try {
      await api('/api/applications/batch-delete', {
        method: 'POST',
        body: JSON.stringify({ application_ids: submittedIds }),
      })
      setShowBatchDeleteSubmittedModal(false)
      fetchApplications()
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to delete submitted applications.')
      }
    } finally {
      setBatchDeleting(false)
    }
  }

  // Poll when any application is currently applying
  useEffect(() => {
    const hasApplying = applications.some((a) => a.status === 'applying')
    if (!hasApplying) return
    const timer = setInterval(() => {
      fetchApplications()
    }, 4000)
    return () => clearInterval(timer)
  }, [applications, fetchApplications])

  const handleTabChange = (key: string | null) => {
    setStatusFilter(key || '')
    setPage(1)
  }

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 1100 }}>
        {/* Header & Quota summary */}
        <Row className="align-items-center mb-4 g-3">
          <Col md={7}>
            <h2 className="mb-1" style={{ color: 'var(--color-dark)', fontWeight: 700 }}>
              Job Applications
            </h2>
            <p className="text-muted mb-0">
              Track your tailored applications, AI cover letters, and recruitment status.
            </p>
          </Col>
          <Col md={5} className="text-md-end">
            {quota && (
              <div
                className="d-inline-block px-3 py-2 rounded-3 border bg-white shadow-sm text-start"
                style={{ fontSize: 13 }}
              >
                <div className="text-muted small fw-semibold text-uppercase" style={{ letterSpacing: '0.5px' }}>
                  Daily Application Quota
                </div>
                <div className="d-flex align-items-center gap-2 mt-1">
                  <span className="fw-bold" style={{ color: 'var(--color-primary)', fontSize: 16 }}>
                    {quota.used_today} / {quota.limit}
                  </span>
                  <span className="text-muted">used today</span>
                  <Badge bg={quota.remaining > 5 ? 'success' : quota.remaining > 0 ? 'warning' : 'danger'}>
                    {quota.remaining} left
                  </Badge>
                </div>
              </div>
            )}
          </Col>
        </Row>

        {error && (
          <Alert variant="danger" dismissible onClose={() => setError('')} className="mb-4">
            {error}
          </Alert>
        )}

        {/* Status Filter Tabs & Batch Submit Action */}
        <Card className="shadow-sm border-0 mb-3">
          <Card.Body className="p-2 d-flex flex-wrap justify-content-between align-items-center gap-2">
            <Nav variant="pills" activeKey={statusFilter} onSelect={handleTabChange} className="flex-wrap gap-1">
              {FILTER_TABS.map((tab) => (
                <Nav.Item key={tab.key}>
                  <Nav.Link
                    eventKey={tab.key}
                    className="py-1 px-3"
                    style={{
                      fontSize: 13,
                      fontWeight: 500,
                      borderRadius: 20,
                      backgroundColor: statusFilter === tab.key ? 'var(--color-primary)' : 'transparent',
                      color: statusFilter === tab.key ? '#fff' : 'var(--color-dark)',
                    }}
                  >
                    {tab.label}
                  </Nav.Link>
                </Nav.Item>
              ))}
            </Nav>

            <div className="d-flex gap-2">
              {submittedApps.length > 0 && (
                <Button
                  variant="outline-danger"
                  size="sm"
                  className="fw-semibold px-3"
                  disabled={batchDeleting}
                  onClick={() => setShowBatchDeleteSubmittedModal(true)}
                >
                  {batchDeleting ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-1" />
                      Deleting...
                    </>
                  ) : (
                    `Delete Submitted (${submittedApps.length}) 🗑`
                  )}
                </Button>
              )}
              {failedApps.length > 0 && (
                <Button
                  variant="outline-danger"
                  size="sm"
                  className="fw-semibold px-3"
                  disabled={batchSubmitting}
                  onClick={handleBatchRetryFailed}
                >
                  {batchSubmitting ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-1" />
                      Retrying...
                    </>
                  ) : (
                    `Retry All Failed (${failedApps.length}) 🔄`
                  )}
                </Button>
              )}
              {readyApps.length > 0 && (
                <Button
                  variant="success"
                  size="sm"
                  className="fw-semibold px-3"
                  disabled={batchSubmitting}
                  onClick={handleBatchSubmit}
                >
                  {batchSubmitting ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-1" />
                      Starting Batch...
                    </>
                  ) : (
                    `Auto-Submit Ready (${readyApps.length}) 🚀`
                  )}
                </Button>
              )}
            </div>
          </Card.Body>
        </Card>

        {/* Applications List */}
        <Card className="shadow-sm border-0">
          <Card.Body className="p-0">
            {loading ? (
              <div className="text-center py-5">
                <Spinner animation="border" style={{ color: 'var(--color-primary)' }} />
                <p className="text-muted mt-2 mb-0">Loading applications...</p>
              </div>
            ) : applications.length === 0 ? (
              <div className="text-center py-5">
                <div style={{ fontSize: 48, opacity: 0.3 }}>📄</div>
                <h5 className="text-muted mt-2">No applications found</h5>
                <p className="text-muted mb-3">
                  {statusFilter
                    ? `No applications with status "${STATUS_LABELS[statusFilter] || statusFilter}".`
                    : 'You have not submitted any applications yet.'}
                </p>
                <Link to="/jobs">
                  <Button style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}>
                    Browse Saved Jobs to Apply
                  </Button>
                </Link>
              </div>
            ) : (
              <>
                <Table hover responsive className="mb-0 align-middle" style={{ fontSize: 14 }}>
                  <thead style={{ backgroundColor: '#f8fafc' }}>
                    <tr>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Role & Company</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Location</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Status</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Cover Letter</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Applied Date</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applications.map((app) => (
                      <tr
                        key={app.id}
                        style={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/applications/${app.id}`)}
                      >
                        <td>
                          <div className="fw-semibold" style={{ color: 'var(--color-primary)' }}>
                            {app.job?.title || '(Untitled Position)'}
                          </div>
                          <div className="text-muted small">{app.job?.company || 'Unknown Company'}</div>
                        </td>
                        <td>{app.job?.location || '—'}</td>
                        <td>
                          <div>
                            <Badge
                              bg={STATUS_COLORS[app.status] || 'secondary'}
                              className="px-2 py-1 fw-normal"
                              style={{ fontSize: 12 }}
                            >
                              {app.status === 'applying' && (
                                <Spinner animation="border" size="sm" className="me-1" style={{ width: 10, height: 10 }} />
                              )}
                              {STATUS_LABELS[app.status] || app.status}
                            </Badge>
                            {app.error_type && (
                              <Badge bg="danger" className="ms-1 px-1 py-0 font-monospace" style={{ fontSize: 10 }}>
                                {app.error_type}
                              </Badge>
                            )}
                          </div>
                          {app.status === 'failed' && app.failure_reason && (
                            <div className="text-danger mt-1 text-truncate" style={{ fontSize: 11, maxWidth: 220 }} title={app.failure_reason}>
                              {app.failure_reason}
                            </div>
                          )}
                        </td>
                        <td>
                          <div
                            className="text-truncate text-muted"
                            style={{ maxWidth: 220, fontSize: 13 }}
                            title={app.cover_letter || 'No cover letter'}
                          >
                            {app.cover_letter ? app.cover_letter.slice(0, 70) + '...' : '—'}
                          </div>
                        </td>
                        <td className="text-muted small">
                          {new Date(app.created_at).toLocaleDateString(undefined, {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                          })}
                        </td>
                        <td>
                          <div className="d-flex gap-2">
                            {app.status === 'applying' && (
                              <Button
                                variant="outline-danger"
                                size="sm"
                                disabled={cancellingId === app.id}
                                onClick={(e) => handleSingleCancel(e, app.id)}
                              >
                                {cancellingId === app.id ? (
                                  <Spinner animation="border" size="sm" />
                                ) : (
                                  'Cancel ⏹'
                                )}
                              </Button>
                            )}
                            {app.status === 'failed' && (
                              <Button
                                variant="outline-danger"
                                size="sm"
                                disabled={retryingId === app.id}
                                onClick={(e) => handleSingleRetry(e, app.id)}
                              >
                                {retryingId === app.id ? (
                                  <Spinner animation="border" size="sm" />
                                ) : (
                                  'Retry 🔄'
                                )}
                              </Button>
                            )}
                            <Button
                              variant="outline-primary"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation()
                                navigate(`/applications/${app.id}`)
                              }}
                            >
                              View Details
                            </Button>
                            {app.status !== 'applying' && (
                              <Button
                                variant="outline-danger"
                                size="sm"
                                title="Delete application"
                                disabled={deletingId === app.id}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setDeleteTargetApp(app)
                                }}
                              >
                                {deletingId === app.id ? (
                                  <Spinner animation="border" size="sm" />
                                ) : (
                                  '🗑'
                                )}
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="d-flex justify-content-between align-items-center p-3 border-top">
                    <span className="text-muted small">
                      Showing {applications.length} of {total} applications
                    </span>
                    <Pagination size="sm" className="mb-0">
                      <Pagination.Prev disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))} />
                      {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                        <Pagination.Item key={p} active={p === page} onClick={() => setPage(p)}>
                          {p}
                        </Pagination.Item>
                      ))}
                      <Pagination.Next
                        disabled={page === totalPages}
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      />
                    </Pagination>
                  </div>
                )}
              </>
            )}
          </Card.Body>
        </Card>

        {/* Single Delete Confirmation Modal */}
        <Modal show={!!deleteTargetApp} onHide={() => setDeleteTargetApp(null)} centered>
          <Modal.Header closeButton>
            <Modal.Title style={{ fontSize: 18, fontWeight: 700 }}>
              Delete Application?
            </Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <p className="mb-2">
              Are you sure you want to delete this application for{' '}
              <strong>{deleteTargetApp?.job?.title || 'this job'}</strong> at{' '}
              <strong>{deleteTargetApp?.job?.company || 'Unknown Company'}</strong>?
            </p>
            <p className="text-muted small mb-0">
              This will permanently remove the application record, tailored cover letter, status history, and any saved automation logs.
            </p>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" size="sm" onClick={() => setDeleteTargetApp(null)} disabled={deletingId !== null}>
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={deletingId !== null}
              onClick={handleDeleteSingle}
            >
              {deletingId !== null ? (
                <>
                  <Spinner animation="border" size="sm" className="me-1" />
                  Deleting...
                </>
              ) : (
                'Confirm Delete 🗑'
              )}
            </Button>
          </Modal.Footer>
        </Modal>

        {/* Batch Delete Submitted Modal */}
        <Modal show={showBatchDeleteSubmittedModal} onHide={() => setShowBatchDeleteSubmittedModal(false)} centered>
          <Modal.Header closeButton>
            <Modal.Title style={{ fontSize: 18, fontWeight: 700 }}>
              Delete All Submitted Forms?
            </Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <p className="mb-2">
              Are you sure you want to delete all <strong>{submittedApps.length}</strong> submitted application form(s) currently listed?
            </p>
            <p className="text-muted small mb-0">
              This will permanently remove the submitted application records, cover letters, status histories, and saved logs.
            </p>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" size="sm" onClick={() => setShowBatchDeleteSubmittedModal(false)} disabled={batchDeleting}>
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={batchDeleting}
              onClick={handleBatchDeleteSubmitted}
            >
              {batchDeleting ? (
                <>
                  <Spinner animation="border" size="sm" className="me-1" />
                  Deleting...
                </>
              ) : (
                `Confirm Delete (${submittedApps.length}) 🗑`
              )}
            </Button>
          </Modal.Footer>
        </Modal>
      </Container>
    </>
  )
}
