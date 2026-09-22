import { useState, useEffect, useCallback } from 'react'
import { Container, Card, Button, Badge, Row, Col, Spinner, Alert, Form, Modal, Nav, Table } from 'react-bootstrap'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api, ApiException } from '../api/client'
import Navbar from '../components/Navbar'
import { STATUS_COLORS, STATUS_LABELS } from './Applications'

interface JobSummary {
  id: number
  title: string | null
  company: string | null
  location: string | null
  work_type: string | null
  url: string
  application_url: string | null
}

interface StatusHistoryEntry {
  id: number
  status: string
  notes: string | null
  created_at: string
}

interface ActionLogEntry {
  timestamp: string
  phase: string
  action: string
  status: string
  details?: string
  url?: string
  discovery_step?: number
}

interface ApplicationDetail {
  id: number
  user_id: number
  job_id: number
  status: string
  cover_letter: string | null
  failure_reason: string | null
  discovered_form_url?: string | null
  execution_id?: string | null
  error_type?: string | null
  error_phase?: string | null
  technical_error?: string | null
  last_action?: string | null
  discovery_step?: number | null
  manual_intervention_required?: boolean
  action_log?: string | null
  error_details?: string | null
  screenshot_path?: string | null
  has_screenshot?: boolean
  created_at: string
  updated_at: string
  job: JobSummary | null
  status_history: StatusHistoryEntry[]
}

const ALLOWED_MANUAL_STATUSES = [
  { value: 'interview', label: 'Interview Scheduled' },
  { value: 'offer', label: 'Offer Received' },
  { value: 'rejected', label: 'Application Rejected' },
]

export default function ApplicationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [app, setApp] = useState<ApplicationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Cover Letter Edit State
  const [isEditingLetter, setIsEditingLetter] = useState(false)
  const [letterDraft, setLetterDraft] = useState('')
  const [letterSaving, setLetterSaving] = useState(false)

  // Status Update State
  const [selectedStatus, setSelectedStatus] = useState('')
  const [statusNotes, setStatusNotes] = useState('')
  const [statusUpdating, setStatusUpdating] = useState(false)

  // Automation Submit State
  const [submittingAutomation, setSubmittingAutomation] = useState(false)
  const [cancellingAutomation, setCancellingAutomation] = useState(false)

  // Diagnostics Modal State (AUT-19 to AUT-32)
  const [showDiagModal, setShowDiagModal] = useState(false)
  const [diagTab, setDiagTab] = useState<'actionLog' | 'technical' | 'screenshot' | 'raw'>('actionLog')
  const [copiedJson, setCopiedJson] = useState(false)

  // Interactive Login & Cookie Modal State
  const [openingBrowser, setOpeningBrowser] = useState(false)
  const [showCookieModal, setShowCookieModal] = useState(false)
  const [cookieInput, setCookieInput] = useState('')
  const [savingCookie, setSavingCookie] = useState(false)

  // Delete Application State
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deletingApp, setDeletingApp] = useState(false)

  const handleDeleteApplication = async () => {
    if (!id) return
    setDeletingApp(true)
    setError('')
    try {
      await api(`/api/applications/${id}`, { method: 'DELETE' })
      navigate('/applications')
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to delete application.')
      }
      setShowDeleteModal(false)
    } finally {
      setDeletingApp(false)
    }
  }


  const handleAutoSubmit = async () => {
    if (!id || !app) return
    setSubmittingAutomation(true)
    setError('')
    setSuccessMsg('')
    try {
      await api<{ message: string; status: string }>(`/api/applications/${id}/submit`, {
        method: 'POST',
      })
      setSuccessMsg('Automated browser submission started! Tracking progress...')
      setApp((prev) => (prev ? { ...prev, status: 'applying' } : null))
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to start automated submission.')
      }
    } finally {
      setSubmittingAutomation(false)
    }
  }

  // Poll for status updates when in 'applying' status
  useEffect(() => {
    if (app?.status !== 'applying') return
    const interval = setInterval(() => {
      api<ApplicationDetail>(`/api/applications/${id}`)
        .then((updated) => {
          setApp(updated)
        })
        .catch(() => {})
    }, 3000)
    return () => clearInterval(interval)
  }, [app?.status, id])

  const fetchApplication = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError('')
    try {
      const data = await api<ApplicationDetail>(`/api/applications/${id}`)
      setApp(data)
      setLetterDraft(data.cover_letter || '')
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to load application details.')
      }
    } finally {
      setLoading(false)
    }
  }, [id])

  const handleCancelAutomation = async () => {
    if (!id || !app) return
    setCancellingAutomation(true)
    setError('')
    try {
      await api<{ message: string; status: string }>(`/api/applications/${id}/cancel`, {
        method: 'POST',
      })
      setSuccessMsg('Automation cancelled. Application reset to Ready.')
      await fetchApplication()
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to cancel automated application.')
      }
    } finally {
      setCancellingAutomation(false)
    }
  }

  const handleOpenLoginBrowser = async () => {
    if (!id || !app) return
    setOpeningBrowser(true)
    setError('')
    setSuccessMsg('')
    try {
      const res = await api<{ message: string; url: string }>(`/api/applications/${id}/open-login-browser`, {
        method: 'POST',
      })
      setSuccessMsg(res.message || 'Brave browser opened! Please log in to your account. Your session will remain saved.')
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to open browser for login.')
      }
    } finally {
      setOpeningBrowser(false)
    }
  }

  const handleSaveCookie = async () => {
    if (!cookieInput.trim()) return
    setSavingCookie(true)
    setError('')
    try {
      const res = await api<{ message: string }>(`/api/applications/save-linkedin-cookie`, {
        method: 'POST',
        body: JSON.stringify({ cookie_value: cookieInput.trim() }),
      })
      setSuccessMsg(res.message || 'Cookie saved successfully!')
      setShowCookieModal(false)
      setCookieInput('')
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to save session cookie.')
      }
    } finally {
      setSavingCookie(false)
    }
  }

  useEffect(() => {
    fetchApplication()
  }, [fetchApplication])

  const handleSaveCoverLetter = async () => {
    if (!id || !app) return
    setLetterSaving(true)
    setError('')
    setSuccessMsg('')
    try {
      const updated = await api<ApplicationDetail>(`/api/applications/${id}/cover-letter`, {
        method: 'PUT',
        body: JSON.stringify({ cover_letter: letterDraft }),
      })
      setApp(updated)
      setIsEditingLetter(false)
      setSuccessMsg('Cover letter updated successfully.')
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to update cover letter.')
      }
    } finally {
      setLetterSaving(false)
    }
  }

  const handleUpdateStatus = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || !app || !selectedStatus) return
    setStatusUpdating(true)
    setError('')
    setSuccessMsg('')
    try {
      const updated = await api<ApplicationDetail>(`/api/applications/${id}/status`, {
        method: 'PUT',
        body: JSON.stringify({ status: selectedStatus, notes: statusNotes.trim() || null }),
      })
      setApp(updated)
      setSelectedStatus('')
      setStatusNotes('')
      setSuccessMsg(`Status updated to ${STATUS_LABELS[updated.status] || updated.status}.`)
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError(err instanceof Error ? err.message : 'Failed to update status.')
      }
    } finally {
      setStatusUpdating(false)
    }
  }

  if (loading) {
    return (
      <>
        <Navbar />
        <Container className="py-5 text-center">
          <Spinner animation="border" style={{ color: 'var(--color-primary)' }} />
          <p className="text-muted mt-2">Loading application details...</p>
        </Container>
      </>
    )
  }

  if (error && !app) {
    return (
      <>
        <Navbar />
        <Container className="py-5" style={{ maxWidth: 700 }}>
          <Alert variant="danger">{error}</Alert>
          <Button variant="outline-primary" onClick={() => navigate('/applications')}>
            &larr; Back to Applications
          </Button>
        </Container>
      </>
    )
  }

  if (!app) return null

  const isTerminal = app.status === 'offer' || app.status === 'rejected'
  const isReady = app.status === 'ready' || app.status === 'failed'

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 960 }}>
        {/* Navigation Breadcrumb */}
        <div className="mb-3">
          <Link to="/applications" className="text-decoration-none small text-muted">
            &larr; Back to Applications
          </Link>
        </div>

        {/* Notifications */}
        {error && (
          <Alert variant="danger" dismissible onClose={() => setError('')} className="mb-4">
            {error}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" dismissible onClose={() => setSuccessMsg('')} className="mb-4">
            {successMsg}
          </Alert>
        )}

        {/* Application Header Card */}
        <Card className="shadow-sm border-0 mb-4 p-3 p-md-4 rounded-3">
          <Row className="align-items-center g-3">
            <Col md={8}>
              <div className="d-flex align-items-center gap-2 mb-2">
                <Badge
                  bg={STATUS_COLORS[app.status] || 'secondary'}
                  className="px-2 py-1 fw-normal"
                  style={{ fontSize: 13 }}
                >
                  {STATUS_LABELS[app.status] || app.status}
                </Badge>
                <span className="text-muted small">
                  Applied on{' '}
                  {new Date(app.created_at).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </span>
              </div>
              <h3 className="mb-1" style={{ color: 'var(--color-dark)', fontWeight: 700 }}>
                {app.job?.title || 'Job Application'}
              </h3>
              <div className="text-muted fs-6">
                <strong>{app.job?.company || 'Unknown Company'}</strong>
                {app.job?.location ? ` • ${app.job.location}` : ''}
              </div>
            </Col>
            <Col md={4} className="text-md-end">
              {(app.status === 'ready' || app.status === 'failed') && (
                <Button
                  variant={app.status === 'failed' ? 'outline-danger' : 'success'}
                  className="me-2 fw-semibold"
                  disabled={submittingAutomation}
                  onClick={handleAutoSubmit}
                >
                  {submittingAutomation ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-1" />
                      Queuing...
                    </>
                  ) : app.status === 'failed' ? (
                    'Retry Automation 🔄'
                  ) : (
                    'Run Auto-Apply 🚀'
                  )}
                </Button>
              )}
              {app.status === 'applying' && (
                <>
                  <Badge bg="warning" text="dark" className="px-3 py-2 me-2" style={{ fontSize: 13 }}>
                    <Spinner animation="border" size="sm" className="me-2" />
                    Auto-Applying in Browser...
                  </Badge>
                  <Button
                    variant="outline-danger"
                    className="me-2 fw-semibold"
                    disabled={cancellingAutomation}
                    onClick={handleCancelAutomation}
                  >
                    {cancellingAutomation ? (
                      <>
                        <Spinner animation="border" size="sm" className="me-1" />
                        Cancelling...
                      </>
                    ) : (
                      'Cancel ⏹'
                    )}
                  </Button>
                </>
              )}
              {app.job?.url && (
                <a href={app.job.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline-secondary btn-sm me-2">
                  View Posting ↗
                </a>
              )}
              {app.job?.id && (
                <Link to={`/jobs/${app.job.id}`} className="btn btn-outline-primary btn-sm me-2">
                  Job Details
                </Link>
              )}
              {app.status !== 'applying' && (
                <Button
                  variant="outline-danger"
                  size="sm"
                  disabled={deletingApp}
                  onClick={() => setShowDeleteModal(true)}
                >
                  Delete 🗑
                </Button>
              )}
            </Col>
          </Row>

          {/* Live In-Progress Automation Banner */}
          {app.status === 'applying' && (
            <div
              className="mt-3 p-3 rounded-3"
              style={{
                backgroundColor: app.last_action?.toLowerCase().includes('login') || app.last_action?.toLowerCase().includes('captcha')
                  ? '#fffbeb'
                  : '#f0f9ff',
                border: app.last_action?.toLowerCase().includes('login') || app.last_action?.toLowerCase().includes('captcha')
                  ? '1px solid #fef3c7'
                  : '1px solid #bae6fd',
              }}
            >
              <div className="d-flex align-items-center justify-content-between flex-wrap gap-2">
                <div className="d-flex align-items-center gap-2">
                  <Spinner
                    animation="border"
                    size="sm"
                    variant={
                      app.last_action?.toLowerCase().includes('login')
                        ? 'warning'
                        : app.last_action?.toLowerCase().includes('captcha')
                        ? 'danger'
                        : 'primary'
                    }
                  />
                  <div>
                    <span className="fw-bold">
                      {app.last_action?.toLowerCase().includes('login')
                        ? 'Action Needed: Sign In in the Open Browser Window 🔑'
                        : app.last_action?.toLowerCase().includes('captcha')
                        ? 'Action Needed: Solve Verification Challenge in Browser Window 🧩'
                        : 'Browser Automation Active 🌐'}
                    </span>
                    <div className="small text-muted mt-1">
                      {app.last_action || 'Working in browser...'}
                    </div>
                  </div>
                </div>
                {app.execution_id && (
                  <div className="font-monospace small text-muted">
                    ID: {app.execution_id}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Enhanced Automation Diagnostics Card (AUT-19 to AUT-32) */}
          {app.status === 'failed' && (
            <div
              className="mt-3 p-3 rounded-3"
              style={{
                backgroundColor: '#fff5f5',
                border: '1px solid #fecaca',
                boxShadow: '0 1px 3px rgba(220, 38, 38, 0.08)',
              }}
            >
              <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
                <div className="d-flex align-items-center gap-2 flex-wrap">
                  <Badge bg="danger" className="px-2 py-1" style={{ fontSize: 12 }}>
                    {app.error_type || 'AUTOMATION_FAILED'}
                  </Badge>
                  {app.error_phase && (
                    <Badge bg="secondary" className="px-2 py-1" style={{ fontSize: 12 }}>
                      Phase: {app.error_phase}
                    </Badge>
                  )}
                  {app.execution_id && (
                    <span className="font-monospace text-muted small" style={{ fontSize: 12 }}>
                      ID: {app.execution_id}
                    </span>
                  )}
                  {app.manual_intervention_required && (
                    <Badge bg="warning" text="dark" className="px-2 py-1" style={{ fontSize: 12 }}>
                      ⚠️ Manual Action Required
                    </Badge>
                  )}
                </div>

                <div className="d-flex gap-2 flex-wrap">
                  {(app.error_type === 'LOGIN_REQUIRED' || app.manual_intervention_required) && (
                    <>
                      <Button
                        variant="warning"
                        size="sm"
                        className="fw-bold text-dark"
                        disabled={openingBrowser}
                        onClick={handleOpenLoginBrowser}
                      >
                        {openingBrowser ? (
                          <>
                            <Spinner animation="border" size="sm" className="me-1" />
                            Opening...
                          </>
                        ) : (
                          'Open Browser to Log In 🔑'
                        )}
                      </Button>
                      <Button
                        variant="outline-secondary"
                        size="sm"
                        className="fw-semibold"
                        onClick={() => setShowCookieModal(true)}
                      >
                        Paste Session Cookie 🍪
                      </Button>
                    </>
                  )}
                  <Button
                    variant="outline-danger"
                    size="sm"
                    className="fw-semibold"
                    onClick={() => setShowDiagModal(true)}
                  >
                    View Full Diagnostics & Logs 🔍
                  </Button>
                </div>
              </div>

              {app.error_type === 'LOGIN_REQUIRED' && (
                <div className="alert alert-warning py-2 px-3 mt-2 mb-2" style={{ fontSize: 13 }}>
                  <strong>Login Required: </strong>
                  LinkedIn requires an active login session to view this application form.
                  Click <strong>Open Browser to Log In 🔑</strong> to sign in once (your session will remain permanently saved in your automation profile), or click <strong>Paste Session Cookie 🍪</strong> to provide your <code>li_at</code> cookie.
                </div>
              )}

              <div className="mb-2 text-dark" style={{ fontSize: 14, lineHeight: 1.5 }}>
                <strong>Issue: </strong>
                {app.failure_reason || 'Unknown error occurred during automated submission.'}
              </div>

              {/* Diagnostic Key Values Bar */}
              <div
                className="d-flex flex-wrap gap-3 py-2 px-3 rounded-2"
                style={{ backgroundColor: '#ffffff', border: '1px solid #fed7d7', fontSize: 12 }}
              >
                {app.job?.url && (
                  <div>
                    <span className="text-muted">Target URL: </span>
                    <a href={app.job.url} target="_blank" rel="noopener noreferrer" className="text-truncate d-inline-block" style={{ maxWidth: 220, verticalAlign: 'bottom' }}>
                      {app.job.url}
                    </a>
                  </div>
                )}
                {app.discovery_step !== undefined && app.discovery_step !== null && (
                  <div>
                    <span className="text-muted">Discovery Step: </span>
                    <strong>{app.discovery_step} / 5</strong>
                  </div>
                )}
                {app.last_action && (
                  <div>
                    <span className="text-muted">Last Action: </span>
                    <span className="text-dark fw-semibold">{app.last_action}</span>
                  </div>
                )}
                {app.has_screenshot && (
                  <div className="text-success fw-semibold">
                    📷 Screenshot Captured
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>

        <Row className="g-4">
          {/* Left Column: Cover Letter & Status Management */}
          <Col lg={7}>
            {/* Cover Letter Card */}
            <Card className="shadow-sm border-0 mb-4 rounded-3">
              <Card.Header className="bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
                <div>
                  <h5 className="mb-0 fw-bold" style={{ color: 'var(--color-dark)' }}>
                    Tailored Cover Letter
                  </h5>
                  <small className="text-muted">
                    {isReady ? 'Generated by AI. You may edit this letter before applying.' : 'Cover letter attached to this application.'}
                  </small>
                </div>
                {isReady && !isEditingLetter && (
                  <Button
                    variant="outline-primary"
                    size="sm"
                    onClick={() => setIsEditingLetter(true)}
                  >
                    Edit Letter
                  </Button>
                )}
              </Card.Header>
              <Card.Body className="p-4">
                {isEditingLetter ? (
                  <div>
                    <Form.Group className="mb-3">
                      <Form.Control
                        as="textarea"
                        rows={12}
                        value={letterDraft}
                        onChange={(e) => setLetterDraft(e.target.value)}
                        style={{ fontSize: 14, lineHeight: 1.6 }}
                      />
                    </Form.Group>
                    <div className="d-flex justify-content-end gap-2">
                      <Button
                        variant="outline-secondary"
                        size="sm"
                        disabled={letterSaving}
                        onClick={() => {
                          setLetterDraft(app.cover_letter || '')
                          setIsEditingLetter(false)
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        disabled={letterSaving || !letterDraft.trim()}
                        onClick={handleSaveCoverLetter}
                      >
                        {letterSaving ? <Spinner animation="border" size="sm" /> : 'Save Changes'}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div
                    className="p-3 bg-light rounded"
                    style={{
                      whiteSpace: 'pre-line',
                      fontSize: 14,
                      lineHeight: 1.7,
                      color: '#334155',
                    }}
                  >
                    {app.cover_letter || 'No cover letter content.'}
                  </div>
                )}
              </Card.Body>
            </Card>

            {/* Manual Status Transition Control */}
            <Card className="shadow-sm border-0 rounded-3">
              <Card.Header className="bg-white py-3 border-bottom">
                <h5 className="mb-0 fw-bold" style={{ color: 'var(--color-dark)' }}>
                  Update Application Status
                </h5>
                <small className="text-muted">
                  Keep track of interview invites, job offers, or status updates.
                </small>
              </Card.Header>
              <Card.Body className="p-4">
                {isTerminal ? (
                  <Alert variant="info" className="mb-0">
                    This application is currently in terminal status (<strong>{STATUS_LABELS[app.status]}</strong>). No further status transitions can be made.
                  </Alert>
                ) : (
                  <Form onSubmit={handleUpdateStatus}>
                    <Form.Group className="mb-3">
                      <Form.Label className="fw-semibold small">New Status</Form.Label>
                      <Form.Select
                        value={selectedStatus}
                        onChange={(e) => setSelectedStatus(e.target.value)}
                        required
                      >
                        <option value="">Select manual status transition...</option>
                        {ALLOWED_MANUAL_STATUSES.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </Form.Select>
                      <Form.Text className="text-muted">
                        Note: Automations manage 'applying', 'submitted', and 'failed' states.
                      </Form.Text>
                    </Form.Group>

                    <Form.Group className="mb-3">
                      <Form.Label className="fw-semibold small">Notes / Reflection (Optional)</Form.Label>
                      <Form.Control
                        as="textarea"
                        rows={2}
                        placeholder="e.g. Scheduled first round with hiring manager for Tuesday at 2 PM..."
                        value={statusNotes}
                        onChange={(e) => setStatusNotes(e.target.value)}
                      />
                    </Form.Group>

                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      disabled={statusUpdating || !selectedStatus}
                    >
                      {statusUpdating ? <Spinner animation="border" size="sm" /> : 'Update Status'}
                    </Button>
                  </Form>
                )}
              </Card.Body>
            </Card>
          </Col>

          {/* Right Column: Status History Timeline */}
          <Col lg={5}>
            <Card className="shadow-sm border-0 rounded-3">
              <Card.Header className="bg-white py-3 border-bottom">
                <h5 className="mb-0 fw-bold" style={{ color: 'var(--color-dark)' }}>
                  Status History Timeline
                </h5>
              </Card.Header>
              <Card.Body className="p-4">
                {app.status_history.length === 0 ? (
                  <p className="text-muted small mb-0">No history events recorded.</p>
                ) : (
                  <div className="timeline position-relative ps-3" style={{ borderLeft: '2px solid #e2e8f0' }}>
                    {app.status_history.map((entry) => (
                      <div key={entry.id} className="position-relative mb-4 ps-3">
                        {/* Timeline dot */}
                        <div
                          className="position-absolute"
                          style={{
                            left: -24,
                            top: 2,
                            width: 14,
                            height: 14,
                            borderRadius: '50%',
                            backgroundColor: 'var(--color-primary)',
                            border: '2px solid #fff',
                            boxShadow: '0 0 0 2px #cbd5e1',
                          }}
                        />
                        <div className="d-flex justify-content-between align-items-center mb-1">
                          <Badge
                            bg={STATUS_COLORS[entry.status] || 'secondary'}
                            className="px-2 py-1 fw-normal"
                            style={{ fontSize: 11 }}
                          >
                            {STATUS_LABELS[entry.status] || entry.status}
                          </Badge>
                          <small className="text-muted" style={{ fontSize: 11 }}>
                            {new Date(entry.created_at).toLocaleString(undefined, {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </small>
                        </div>
                        {entry.notes && (
                          <div className="text-muted small mt-1" style={{ fontSize: 12 }}>
                            {entry.notes}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </Container>

      {/* Automation Diagnostics Modal */}
      <Modal
        show={showDiagModal}
        onHide={() => setShowDiagModal(false)}
        size="lg"
        centered
      >
        <Modal.Header closeButton className="border-bottom py-3">
          <Modal.Title className="fs-5 fw-bold d-flex align-items-center gap-2">
            <span>Automation Diagnostics & Action Log</span>
            {app?.execution_id && (
              <Badge bg="light" text="dark" className="border font-monospace fs-6">
                {app.execution_id}
              </Badge>
            )}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-0">
          <Nav variant="tabs" className="px-3 pt-2 bg-light border-bottom">
            <Nav.Item>
              <Nav.Link
                active={diagTab === 'actionLog'}
                onClick={() => setDiagTab('actionLog')}
                className="fw-semibold small"
              >
                Action Log ({app?.action_log ? (() => { try { return JSON.parse(app.action_log).length } catch { return 0 } })() : 0})
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link
                active={diagTab === 'technical'}
                onClick={() => setDiagTab('technical')}
                className="fw-semibold small"
              >
                Technical Details
              </Nav.Link>
            </Nav.Item>
            {app?.has_screenshot && (
              <Nav.Item>
                <Nav.Link
                  active={diagTab === 'screenshot'}
                  onClick={() => setDiagTab('screenshot')}
                  className="fw-semibold small text-danger"
                >
                  📷 Failure Screenshot
                </Nav.Link>
              </Nav.Item>
            )}
            <Nav.Item>
              <Nav.Link
                active={diagTab === 'raw'}
                onClick={() => setDiagTab('raw')}
                className="fw-semibold small"
              >
                Raw JSON
              </Nav.Link>
            </Nav.Item>
          </Nav>

          <div className="p-4" style={{ maxHeight: '65vh', overflowY: 'auto' }}>
            {diagTab === 'actionLog' && (
              <div>
                {(!app?.action_log || (() => { try { return JSON.parse(app.action_log).length === 0 } catch { return true } })()) ? (
                  <div className="text-muted text-center py-4">No action log entries recorded yet.</div>
                ) : (
                  <div className="timeline-container">
                    {(JSON.parse(app.action_log) as ActionLogEntry[]).map((log, idx) => (
                      <div key={idx} className="d-flex gap-3 mb-3 position-relative pb-2 border-bottom">
                        <div style={{ minWidth: 70 }} className="text-muted font-monospace small">
                          {log.timestamp ? new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                        </div>
                        <div style={{ minWidth: 90 }}>
                          <Badge
                            bg={
                              log.status === 'SUCCESS' ? 'success' :
                              log.status === 'RETRY' ? 'warning' :
                              log.status === 'FAILED' ? 'danger' : 'secondary'
                            }
                            className="px-2 py-1"
                            style={{ fontSize: 10 }}
                          >
                            {log.phase}
                          </Badge>
                        </div>
                        <div className="flex-grow-1">
                          <div className="fw-semibold text-dark" style={{ fontSize: 13 }}>
                            {log.action}
                          </div>
                          {log.details && (
                            <div className="text-muted small mt-1 font-monospace" style={{ fontSize: 11 }}>
                              {log.details}
                            </div>
                          )}
                          {log.url && (
                            <div className="text-truncate text-muted small mt-1" style={{ maxWidth: 450, fontSize: 11 }}>
                              🔗 {log.url}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {diagTab === 'technical' && (
              <div>
                <Table bordered responsive hover size="sm" className="align-middle">
                  <tbody>
                    <tr>
                      <th style={{ width: '30%', backgroundColor: '#f8fafc' }}>Execution ID</th>
                      <td className="font-monospace">{app?.execution_id || 'N/A'}</td>
                    </tr>
                    <tr>
                      <th style={{ backgroundColor: '#f8fafc' }}>Error Type</th>
                      <td>
                        <Badge bg="danger">{app?.error_type || 'N/A'}</Badge>
                      </td>
                    </tr>
                    <tr>
                      <th style={{ backgroundColor: '#f8fafc' }}>Error Phase</th>
                      <td>{app?.error_phase || 'N/A'}</td>
                    </tr>
                    <tr>
                      <th style={{ backgroundColor: '#f8fafc' }}>Last Successful Action</th>
                      <td>{app?.last_action || 'None'}</td>
                    </tr>
                    <tr>
                      <th style={{ backgroundColor: '#f8fafc' }}>Discovery Step</th>
                      <td>{app?.discovery_step !== undefined && app?.discovery_step !== null ? `${app.discovery_step} of 5` : 'N/A'}</td>
                    </tr>
                    <tr>
                      <th style={{ backgroundColor: '#f8fafc' }}>Manual Intervention</th>
                      <td>
                        {app?.manual_intervention_required ? (
                          <Badge bg="warning" text="dark">Required</Badge>
                        ) : (
                          <Badge bg="secondary">No</Badge>
                        )}
                      </td>
                    </tr>
                    {app?.discovered_form_url && (
                      <tr>
                        <th style={{ backgroundColor: '#f8fafc' }}>Discovered Form URL</th>
                        <td>
                          <a href={app.discovered_form_url} target="_blank" rel="noopener noreferrer">
                            {app.discovered_form_url}
                          </a>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </Table>

                {app?.technical_error && (
                  <div className="mt-3">
                    <h6 className="fw-bold text-danger mb-2">Technical Exception / Trace:</h6>
                    <pre
                      className="p-3 bg-dark text-light rounded-3 small"
                      style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 250 }}
                    >
                      {app.technical_error}
                    </pre>
                  </div>
                )}
              </div>
            )}

            {diagTab === 'screenshot' && (
              <div className="text-center">
                {app?.has_screenshot ? (
                  <div>
                    <div className="mb-2 text-muted small">
                      Captured at failure state ({app.execution_id})
                    </div>
                    <img
                      src={`/api/applications/${app.id}/screenshot`}
                      alt="Failure Screenshot"
                      className="img-fluid rounded-3 border shadow-sm"
                      style={{ maxHeight: 400 }}
                    />
                  </div>
                ) : (
                  <div className="text-muted py-4">No screenshot available.</div>
                )}
              </div>
            )}

            {diagTab === 'raw' && (
              <div>
                <div className="d-flex justify-content-between align-items-center mb-2">
                  <span className="text-muted small">Complete JSON diagnostic record</span>
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={() => {
                      const dataToCopy = app?.error_details ? JSON.parse(app.error_details) : app
                      navigator.clipboard.writeText(JSON.stringify(dataToCopy, null, 2))
                      setCopiedJson(true)
                      setTimeout(() => setCopiedJson(false), 2000)
                    }}
                  >
                    {copiedJson ? '✓ Copied!' : 'Copy JSON'}
                  </Button>
                </div>
                <pre
                  className="p-3 bg-light border rounded-3 small font-monospace"
                  style={{ maxHeight: 350, overflowY: 'auto' }}
                >
                  {JSON.stringify(app?.error_details ? JSON.parse(app.error_details) : app, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </Modal.Body>
        <Modal.Footer className="border-top py-2 d-flex justify-content-between">
          <div className="small text-muted">
            Requirement AUT-19 to AUT-32 Compliant
          </div>
          <Button variant="secondary" size="sm" onClick={() => setShowDiagModal(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>

      {/* LinkedIn Session Cookie Modal */}
      <Modal show={showCookieModal} onHide={() => setShowCookieModal(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title style={{ fontSize: 18, fontWeight: 700 }}>
            Save LinkedIn Session Cookie 🍪
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p className="text-muted small mb-3">
            If you are already signed in to LinkedIn in your primary browser, you can copy your <code>li_at</code> session cookie and paste it below. The automated browser will automatically inject this cookie to access LinkedIn as your logged-in user without asking for credentials.
          </p>
          <Form.Group className="mb-3">
            <Form.Label className="fw-semibold" style={{ fontSize: 13 }}>
              LinkedIn <code>li_at</code> Cookie Value
            </Form.Label>
            <Form.Control
              type="password"
              placeholder="Paste your li_at cookie here..."
              value={cookieInput}
              onChange={(e) => setCookieInput(e.target.value)}
              autoFocus
            />
            <Form.Text className="text-muted" style={{ fontSize: 11 }}>
              💡 <strong>How to get it:</strong> In your Brave/Chrome browser where you are logged in to LinkedIn, press <kbd>F12</kbd> → go to <strong>Application</strong> tab → <strong>Storage</strong> → <strong>Cookies</strong> → <code>https://www.linkedin.com</code> → copy the <strong>Value</strong> of <code>li_at</code>.
            </Form.Text>
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" size="sm" onClick={() => setShowCookieModal(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={savingCookie || !cookieInput.trim()}
            onClick={handleSaveCookie}
          >
            {savingCookie ? (
              <>
                <Spinner animation="border" size="sm" className="me-1" />
                Saving...
              </>
            ) : (
              'Save Cookie & Continue'
            )}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title style={{ fontSize: 18, fontWeight: 700 }}>
            Delete Application?
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p className="mb-2">
            Are you sure you want to delete this application for <strong>{app.job?.title || 'this job'}</strong> at <strong>{app.job?.company || 'Unknown Company'}</strong>?
          </p>
          <p className="text-muted small mb-0">
            This will permanently remove the application record, tailored cover letter, status history, and any saved automation logs and screenshots.
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" size="sm" onClick={() => setShowDeleteModal(false)} disabled={deletingApp}>
            Cancel
          </Button>
          <Button
            variant="danger"
            size="sm"
            disabled={deletingApp}
            onClick={handleDeleteApplication}
          >
            {deletingApp ? (
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
    </>
  )
}
