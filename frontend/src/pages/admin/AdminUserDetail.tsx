import { useState, useEffect, useCallback } from 'react'
import { Container, Card, Row, Col, Badge, Button, Table, Spinner, Alert, Modal } from 'react-bootstrap'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Navbar from '../../components/Navbar'
import { api, ApiException } from '../../api/client'

interface ApplicationItem {
  id: number
  job_id: number
  job_title: string | null
  job_company: string | null
  status: string
  failure_reason: string | null
  created_at: string
  updated_at: string
}

interface UserDetail {
  id: number
  email: string
  name: string
  phone: string | null
  location: string | null
  role: string
  is_active: boolean
  is_verified: boolean
  email_notifications_enabled: boolean
  created_at: string
  profile: Record<string, any> | null
  cv: {
    file_name: string
    file_size: number
    file_type: string
    parsed_data?: Record<string, any>
    created_at: string
  } | null
  applications: ApplicationItem[]
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

export default function AdminUserDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [user, setUser] = useState<UserDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionSuccess, setActionSuccess] = useState('')

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const fetchUser = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError('')
    try {
      const data = await api<UserDetail>(`/api/admin/users/${id}`)
      setUser(data)
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to load user details')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  const handleToggleStatus = async () => {
    if (!user) return
    setError('')
    setActionSuccess('')
    const action = user.is_active ? 'suspend' : 'reactivate'
    try {
      await api(`/api/admin/users/${user.id}/${action}`, { method: 'PUT' })
      setActionSuccess(`User ${user.name} successfully ${action}ed.`)
      fetchUser()
    } catch (err) {
      setError(err instanceof ApiException ? err.message : `Failed to ${action} user`)
    }
  }

  const handleDelete = async () => {
    if (!user) return
    setDeleting(true)
    setError('')
    try {
      await api(`/api/admin/users/${user.id}`, { method: 'DELETE' })
      navigate('/admin/users')
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to delete user')
      setDeleting(false)
      setShowDeleteModal(false)
    }
  }

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 1000 }}>
        {/* Navigation Breadcrumb */}
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <div>
            <Link to="/admin/users" className="text-decoration-none small text-muted">
              ← Back to User List
            </Link>
            <h2 className="fw-bold mb-0 mt-1">Candidate Inspection</h2>
          </div>
          {user && (
            <div className="d-flex gap-2">
              <Button
                variant={user.is_active ? 'outline-warning' : 'outline-success'}
                size="sm"
                onClick={handleToggleStatus}
              >
                {user.is_active ? 'Suspend Account' : 'Reactivate Account'}
              </Button>
              <Button
                variant="outline-danger"
                size="sm"
                onClick={() => setShowDeleteModal(true)}
              >
                Delete Account
              </Button>
            </div>
          )}
        </div>

        {error && <Alert variant="danger">{error}</Alert>}
        {actionSuccess && <Alert variant="success" dismissible onClose={() => setActionSuccess('')}>{actionSuccess}</Alert>}

        {loading ? (
          <div className="text-center py-5">
            <Spinner animation="border" variant="primary" />
            <p className="mt-2 text-muted small">Loading candidate profile & history...</p>
          </div>
        ) : user ? (
          <Row className="g-4">
            {/* Column 1: Account & Profile Overview */}
            <Col md={5}>
              <Card className="border-0 shadow-sm mb-4">
                <Card.Header className="bg-white border-0 pt-3 pb-0">
                  <h5 className="fw-bold mb-0">Account Information</h5>
                </Card.Header>
                <Card.Body>
                  <div className="mb-3">
                    <div className="fs-5 fw-bold">{user.name}</div>
                    <div className="text-muted small">{user.email}</div>
                  </div>

                  <div className="d-flex gap-2 mb-3">
                    <Badge bg={user.is_active ? 'success' : 'danger'}>
                      {user.is_active ? 'Active' : 'Suspended'}
                    </Badge>
                    <Badge bg={user.is_verified ? 'info' : 'secondary'}>
                      {user.is_verified ? 'Verified' : 'Unverified'}
                    </Badge>
                    <Badge bg="light" text="dark">
                      Role: {user.role}
                    </Badge>
                  </div>

                  <div className="small mb-2">
                    <span className="text-muted">Phone:</span> {user.phone || user.profile?.phone || '—'}
                  </div>
                  <div className="small mb-2">
                    <span className="text-muted">Location:</span> {user.location || user.profile?.location || '—'}
                  </div>
                  <div className="small mb-2">
                    <span className="text-muted">Target Role:</span> {user.profile?.target_job_title || '—'}
                  </div>
                  <div className="small mb-2">
                    <span className="text-muted">Email Alerts:</span>{' '}
                    {user.email_notifications_enabled ? 'Enabled' : 'Disabled'}
                  </div>
                  <div className="small text-muted mt-3">
                    Registered: {new Date(user.created_at).toLocaleString()}
                  </div>
                </Card.Body>
              </Card>

              {/* CV / Resume Summary Card */}
              <Card className="border-0 shadow-sm">
                <Card.Header className="bg-white border-0 pt-3 pb-0">
                  <h5 className="fw-bold mb-0">CV / Resume Status</h5>
                </Card.Header>
                <Card.Body>
                  {user.cv ? (
                    <div>
                      <div className="fw-semibold text-dark mb-1">📄 {user.cv.file_name}</div>
                      <div className="text-muted small mb-2">
                        Size: {(user.cv.file_size / 1024).toFixed(1)} KB • Type: {user.cv.file_type.toUpperCase()}
                      </div>
                      <div className="text-muted small mb-3">
                        Uploaded: {new Date(user.cv.created_at).toLocaleDateString()}
                      </div>
                      {user.cv.parsed_data?.skills && (
                        <div>
                          <div className="text-muted small fw-semibold mb-1">Parsed Skills:</div>
                          <div className="d-flex flex-wrap gap-1">
                            {user.cv.parsed_data.skills.map((s: string, idx: number) => (
                              <Badge key={idx} bg="light" text="dark" className="border">
                                {s}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-muted small mb-0">No CV uploaded by candidate yet.</p>
                  )}
                </Card.Body>
              </Card>
            </Col>

            {/* Column 2: Application History */}
            <Col md={7}>
              <Card className="border-0 shadow-sm">
                <Card.Header className="bg-white border-0 pt-3 pb-0 d-flex justify-content-between align-items-center">
                  <h5 className="fw-bold mb-0">Application History</h5>
                  <Badge bg="primary" pill>
                    {user.applications.length} applications
                  </Badge>
                </Card.Header>
                <Card.Body className="p-0">
                  {user.applications.length === 0 ? (
                    <div className="text-center py-5 text-muted small">
                      Candidate has not initiated any applications yet.
                    </div>
                  ) : (
                    <Table hover responsive className="mb-0 align-middle">
                      <thead className="table-light">
                        <tr>
                          <th>Job / Company</th>
                          <th>Status</th>
                          <th>Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {user.applications.map((app) => (
                          <tr key={app.id}>
                            <td>
                              <div className="fw-semibold small">{app.job_title || 'Untitled Job'}</div>
                              <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                                {app.job_company || 'Unknown Company'}
                              </div>
                              {app.failure_reason && (
                                <div className="text-danger mt-1" style={{ fontSize: '0.75rem' }}>
                                  ⚠️ {app.failure_reason}
                                </div>
                              )}
                            </td>
                            <td>
                              <Badge bg={STATUS_COLORS[app.status] || 'secondary'} style={{ fontSize: '0.75rem' }}>
                                {app.status}
                              </Badge>
                            </td>
                            <td className="text-muted small" style={{ fontSize: '0.75rem' }}>
                              {new Date(app.created_at).toLocaleDateString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </Card.Body>
              </Card>
            </Col>
          </Row>
        ) : null}

        {/* Delete Confirmation Modal */}
        <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)} centered>
          <Modal.Header closeButton>
            <Modal.Title className="text-danger fw-bold">Delete Candidate Account</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <p>
              Are you sure you want to permanently delete <strong>{user?.name}</strong>?
            </p>
            <Alert variant="danger" className="mb-0 small">
              This action cascades to delete candidate profile data, CV document, saved jobs, and all application history.
            </Alert>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowDeleteModal(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Spinner size="sm" animation="border" /> : 'Delete Permanently'}
            </Button>
          </Modal.Footer>
        </Modal>
      </Container>
    </>
  )
}
