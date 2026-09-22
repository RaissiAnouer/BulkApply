import { useState, useEffect, useCallback } from 'react'
import { Container, Card, Button, Badge, Row, Col, Spinner, Alert, Form, Nav } from 'react-bootstrap'
import { Link } from 'react-router-dom'
import { api, ApiException } from '../api/client'
import Navbar from '../components/Navbar'

interface NotificationItem {
  id: number
  user_id: number
  application_id: number | null
  type: string
  title: string
  message: string
  is_read: boolean
  email_sent: boolean
  created_at: string
}

interface NotificationListResponse {
  items: NotificationItem[]
  total: number
  unread_count: number
  page: number
  page_size: number
  pages: number
}

interface PreferencesResponse {
  email_notifications_enabled: boolean
}

const TYPE_CONFIG: Record<string, { badge: string; color: string; icon: string }> = {
  app_submitted: { badge: 'Submitted', color: 'success', icon: '✅' },
  app_failed: { badge: 'Failed', color: 'danger', icon: '⚠️' },
  manual_intervention: { badge: 'Action Required', color: 'warning', icon: '🛡️' },
}

export default function Notifications() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [total, setTotal] = useState(0)
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Filtering & Pagination
  const [filterUnread, setFilterUnread] = useState(false)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)

  // Preferences
  const [emailAlerts, setEmailAlerts] = useState(true)
  const [prefSaving, setPrefSaving] = useState(false)

  const fetchNotifications = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const query = new URLSearchParams({
        page: page.toString(),
        page_size: '15',
        ...(filterUnread ? { unread_only: 'true' } : {}),
      })
      const data = await api<NotificationListResponse>(`/api/notifications?${query.toString()}`)
      setNotifications(data.items)
      setTotal(data.total)
      setUnreadCount(data.unread_count)
      setPages(data.pages)
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to load notifications.')
      }
    } finally {
      setLoading(false)
    }
  }, [page, filterUnread])

  const fetchPreferences = useCallback(async () => {
    try {
      const data = await api<PreferencesResponse>('/api/notifications/preferences')
      setEmailAlerts(data.email_notifications_enabled)
    } catch {
      // Non-blocking
    }
  }, [])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  useEffect(() => {
    fetchPreferences()
  }, [fetchPreferences])

  const handleTogglePreferences = async (enabled: boolean) => {
    setPrefSaving(true)
    setError('')
    setSuccessMsg('')
    try {
      const updated = await api<PreferencesResponse>('/api/notifications/preferences', {
        method: 'PUT',
        body: JSON.stringify({ email_notifications_enabled: enabled }),
      })
      setEmailAlerts(updated.email_notifications_enabled)
      setSuccessMsg(enabled ? 'Email alerts enabled.' : 'Email alerts disabled.')
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to update preferences.')
      }
    } finally {
      setPrefSaving(false)
    }
  }

  const handleMarkAsRead = async (id: number) => {
    try {
      await api<NotificationItem>(`/api/notifications/${id}/read`, { method: 'PUT' })
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      )
      setUnreadCount((c) => Math.max(0, c - 1))
    } catch {
      // Non-blocking
    }
  }

  const handleMarkAllRead = async () => {
    setError('')
    setSuccessMsg('')
    try {
      const res = await api<{ message: string; count: number }>('/api/notifications/mark-all-read', {
        method: 'PUT',
      })
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnreadCount(0)
      setSuccessMsg(res.message)
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to mark all as read.')
      }
    }
  }

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 900 }}>
        {/* Header */}
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <div>
            <h2 className="fw-bold mb-1 d-flex align-items-center gap-2">
              <span>🔔 Notifications</span>
              {unreadCount > 0 && (
                <Badge pill bg="danger" style={{ fontSize: '0.8rem' }}>
                  {unreadCount} unread
                </Badge>
              )}
            </h2>
            <p className="text-muted mb-0">Stay informed on application outcomes and automation status</p>
          </div>
          <div className="d-flex gap-2">
            {unreadCount > 0 && (
              <Button variant="outline-primary" size="sm" onClick={handleMarkAllRead}>
                ✓ Mark all as read
              </Button>
            )}
          </div>
        </div>

        {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
        {successMsg && <Alert variant="success" dismissible onClose={() => setSuccessMsg('')}>{successMsg}</Alert>}

        {/* Email Preferences Card */}
        <Card className="border-0 shadow-sm mb-4 bg-light">
          <Card.Body className="py-3 px-4 d-flex justify-content-between align-items-center flex-wrap gap-2">
            <div>
              <div className="fw-semibold small mb-0">Email Notifications</div>
              <div className="text-muted small">
                Receive instant email alerts when an application fails or requires manual CAPTCHA solving.
              </div>
            </div>
            <Form.Check
              type="switch"
              id="email-alerts-switch"
              checked={emailAlerts}
              disabled={prefSaving}
              onChange={(e) => handleTogglePreferences(e.target.checked)}
              label={emailAlerts ? 'Alerts On' : 'Alerts Off'}
              className="fw-medium small"
            />
          </Card.Body>
        </Card>

        {/* Filter Tabs */}
        <Nav variant="pills" className="mb-3 gap-2">
          <Nav.Item>
            <Nav.Link
              active={!filterUnread}
              onClick={() => { setFilterUnread(false); setPage(1) }}
              className="cursor-pointer py-1 px-3"
            >
              All Notifications ({total})
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link
              active={filterUnread}
              onClick={() => { setFilterUnread(true); setPage(1) }}
              className="cursor-pointer py-1 px-3"
            >
              Unread Only ({unreadCount})
            </Nav.Link>
          </Nav.Item>
        </Nav>

        {/* Notifications List */}
        {loading ? (
          <div className="text-center py-5">
            <Spinner animation="border" variant="primary" />
            <p className="mt-2 text-muted small">Loading notifications...</p>
          </div>
        ) : notifications.length === 0 ? (
          <Card className="border-0 shadow-sm text-center py-5">
            <Card.Body>
              <div style={{ fontSize: '3rem' }}>🎉</div>
              <h5 className="fw-bold mt-2">All Caught Up!</h5>
              <p className="text-muted small mb-0">
                {filterUnread ? 'You have no unread notifications.' : 'No notifications yet. They will appear as applications run.'}
              </p>
            </Card.Body>
          </Card>
        ) : (
          <div className="d-flex flex-column gap-3">
            {notifications.map((notif) => {
              const cfg = TYPE_CONFIG[notif.type] || { badge: 'Info', color: 'secondary', icon: 'ℹ️' }
              return (
                <Card
                  key={notif.id}
                  className={`border-0 shadow-sm transition-all ${
                    !notif.is_read ? 'border-start border-4 border-' + cfg.color : ''
                  }`}
                  style={{
                    backgroundColor: !notif.is_read ? '#f8fafd' : '#ffffff',
                  }}
                >
                  <Card.Body className="p-3">
                    <Row className="align-items-start g-2">
                      <Col xs="auto" style={{ fontSize: '1.4rem', lineHeight: 1 }}>
                        {cfg.icon}
                      </Col>
                      <Col>
                        <div className="d-flex justify-content-between align-items-center flex-wrap gap-1 mb-1">
                          <div className="d-flex align-items-center gap-2">
                            <span className="fw-bold">{notif.title}</span>
                            <Badge bg={cfg.color} style={{ fontSize: '0.7rem' }}>
                              {cfg.badge}
                            </Badge>
                            {!notif.is_read && (
                              <Badge bg="primary" pill style={{ fontSize: '0.65rem' }}>
                                New
                              </Badge>
                            )}
                          </div>
                          <span className="text-muted small">
                            {new Date(notif.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-secondary small mb-2">{notif.message}</p>
                        <div className="d-flex justify-content-between align-items-center">
                          {notif.application_id ? (
                            <Link
                              to={`/applications/${notif.application_id}`}
                              className="btn btn-sm btn-link p-0 text-decoration-none fw-semibold"
                            >
                              View Application →
                            </Link>
                          ) : <div />}
                          {!notif.is_read && (
                            <Button
                              variant="link"
                              size="sm"
                              className="text-muted p-0 text-decoration-none small"
                              onClick={() => handleMarkAsRead(notif.id)}
                            >
                              Mark as read
                            </Button>
                          )}
                        </div>
                      </Col>
                    </Row>
                  </Card.Body>
                </Card>
              )
            })}
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="d-flex justify-content-between align-items-center mt-4">
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
      </Container>
    </>
  )
}
