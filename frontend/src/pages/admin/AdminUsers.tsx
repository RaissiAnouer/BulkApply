import { useState, useEffect, useCallback } from 'react'
import { Container, Table, Button, Badge, Alert, Spinner, Modal, Form, Row, Col } from 'react-bootstrap'
import { Link } from 'react-router-dom'
import Navbar from '../../components/Navbar'
import { api, ApiException } from '../../api/client'

interface UserSummary {
  id: number
  email: string
  name: string
  role: string
  is_active: boolean
  is_verified: boolean
  created_at: string
  profile: {
    full_name: string
    phone: string
    location: string
    target_job_title: string | null
    work_authorization: boolean | null
  } | null
}

interface UserListResponse {
  items: UserSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

export default function AdminUsers() {
  const [users, setUsers] = useState<UserSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionSuccess, setActionSuccess] = useState('')

  // Delete modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [userToDelete, setUserToDelete] = useState<UserSummary | null>(null)
  const [deleting, setDeleting] = useState(false)

  const loadUsers = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const query = new URLSearchParams({
        page: page.toString(),
        page_size: '15',
        ...(searchQuery.trim() ? { q: searchQuery.trim() } : {}),
      })
      const data = await api<UserListResponse>(`/api/admin/users?${query.toString()}`)
      setUsers(data.items)
      setTotal(data.total)
      setPages(data.pages)
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [page, searchQuery])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  const handleToggleStatus = async (user: UserSummary) => {
    setError('')
    setActionSuccess('')
    const action = user.is_active ? 'suspend' : 'reactivate'
    try {
      await api(`/api/admin/users/${user.id}/${action}`, { method: 'PUT' })
      setActionSuccess(`User ${user.name} (${user.email}) successfully ${action}ed.`)
      loadUsers()
    } catch (err) {
      setError(err instanceof ApiException ? err.message : `Failed to ${action} user`)
    }
  }

  const confirmDelete = (user: UserSummary) => {
    setUserToDelete(user)
    setShowDeleteModal(true)
  }

  const handleDelete = async () => {
    if (!userToDelete) return
    setDeleting(true)
    setError('')
    setActionSuccess('')
    try {
      await api(`/api/admin/users/${userToDelete.id}`, { method: 'DELETE' })
      setActionSuccess(`User ${userToDelete.name} and their records were permanently deleted.`)
      setShowDeleteModal(false)
      setUserToDelete(null)
      loadUsers()
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to delete user')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 1100 }}>
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <div>
            <h2 className="fw-bold mb-1">👥 Candidate User Management</h2>
            <p className="text-muted mb-0">Search, monitor, inspect, and manage Job Seeker accounts</p>
          </div>
          <div className="d-flex gap-2">
            <Link to="/admin">
              <Button variant="outline-secondary" size="sm">
                ← Dashboard
              </Button>
            </Link>
            <Link to="/admin/settings">
              <Button variant="outline-dark" size="sm">
                Settings & Logs ⚙️
              </Button>
            </Link>
          </div>
        </div>

        {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
        {actionSuccess && <Alert variant="success" dismissible onClose={() => setActionSuccess('')}>{actionSuccess}</Alert>}

        {/* Search Bar */}
        <Row className="mb-3">
          <Col md={6}>
            <Form.Control
              type="text"
              placeholder="Search by candidate name or email..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setPage(1) }}
            />
          </Col>
          <Col md={6} className="text-md-end text-muted small d-flex align-items-center justify-content-md-end mt-2 mt-md-0">
            Total Candidates: <strong>{total}</strong>
          </Col>
        </Row>

        {loading ? (
          <div className="text-center py-5">
            <Spinner animation="border" variant="primary" />
            <p className="mt-2 text-muted small">Loading candidates...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="text-center py-5 text-muted border rounded bg-light">
            No Job Seekers found matching your search.
          </div>
        ) : (
          <div className="table-responsive shadow-sm rounded border bg-white">
            <Table hover className="mb-0 align-middle">
              <thead className="table-light">
                <tr>
                  <th>Candidate</th>
                  <th>Contact / Location</th>
                  <th>Target Role</th>
                  <th>Status</th>
                  <th className="text-end">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div className="fw-semibold text-dark">{u.name}</div>
                      <div className="text-muted small">{u.email}</div>
                    </td>
                    <td>
                      <div className="small">{u.profile?.phone || '—'}</div>
                      <div className="text-muted small">{u.profile?.location || '—'}</div>
                    </td>
                    <td>
                      {u.profile?.target_job_title ? (
                        <span className="small fw-medium">{u.profile.target_job_title}</span>
                      ) : (
                        <span className="text-muted small">Not specified</span>
                      )}
                    </td>
                    <td>
                      <Badge bg={u.is_active ? 'success' : 'danger'} className="me-1">
                        {u.is_active ? 'Active' : 'Suspended'}
                      </Badge>
                      <Badge bg={u.is_verified ? 'info' : 'secondary'}>
                        {u.is_verified ? 'Verified' : 'Unverified'}
                      </Badge>
                    </td>
                    <td className="text-end">
                      <div className="d-flex justify-content-end gap-1 flex-wrap">
                        <Link to={`/admin/users/${u.id}`}>
                          <Button variant="outline-primary" size="sm" title="View Candidate Profile & History">
                            Inspect 🔍
                          </Button>
                        </Link>
                        <Button
                          variant={u.is_active ? 'outline-warning' : 'outline-success'}
                          size="sm"
                          onClick={() => handleToggleStatus(u)}
                        >
                          {u.is_active ? 'Suspend' : 'Reactivate'}
                        </Button>
                        <Button
                          variant="outline-danger"
                          size="sm"
                          onClick={() => confirmDelete(u)}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="d-flex justify-content-between align-items-center mt-3">
            <Button
              variant="outline-secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              ← Previous
            </Button>
            <span className="text-muted small">Page {page} of {pages}</span>
            <Button
              variant="outline-secondary"
              size="sm"
              disabled={page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
            >
              Next →
            </Button>
          </div>
        )}

        {/* Delete Modal */}
        <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)} centered>
          <Modal.Header closeButton>
            <Modal.Title className="text-danger fw-bold">Confirm Account Deletion</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <p>
              Are you sure you want to permanently delete the account for <strong>{userToDelete?.name}</strong> ({userToDelete?.email})?
            </p>
            <Alert variant="danger" className="mb-0 small">
              <strong>Warning:</strong> This will delete all associated profile data, CV files, saved jobs, cover letters, and application records. This action cannot be undone.
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
