import { useState, useEffect, useCallback } from 'react'
import { Container, Card, Form, Button, Row, Col, Table, Badge, Alert, Spinner } from 'react-bootstrap'
import { Link } from 'react-router-dom'
import Navbar from '../../components/Navbar'
import { api, ApiException } from '../../api/client'

interface SystemSetting {
  id: number
  key: string
  value: string
  updated_at: string
  updated_by: number | null
}

interface AuditLogEntry {
  id: number
  admin_id: number | null
  admin_name: string | null
  action: string
  target_user_id: number | null
  details: string | null
  created_at: string
}

export default function AdminSettings() {
  const [dailyLimit, setDailyLimit] = useState('20')
  const [settingMeta, setSettingMeta] = useState<SystemSetting | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [settingsData, logsData] = await Promise.all([
        api<SystemSetting[]>('/api/admin/settings'),
        api<AuditLogEntry[]>('/api/admin/audit-logs?limit=50'),
      ])
      const limitSetting = settingsData.find((s) => s.key === 'daily_application_limit')
      if (limitSetting) {
        setDailyLimit(limitSetting.value)
        setSettingMeta(limitSetting)
      }
      setAuditLogs(logsData)
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to load system settings')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccessMsg('')
    try {
      const updated = await api<SystemSetting>('/api/admin/settings/daily_application_limit', {
        method: 'PUT',
        body: JSON.stringify({ value: dailyLimit }),
      })
      setDailyLimit(updated.value)
      setSettingMeta(updated)
      setSuccessMsg('Daily application limit updated successfully. Now active for all users.')
      // Refresh audit logs
      const freshLogs = await api<AuditLogEntry[]>('/api/admin/audit-logs?limit=50')
      setAuditLogs(freshLogs)
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to update setting')
    } finally {
      setSaving(false)
    }
  }

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'suspend_user':
        return <Badge bg="danger">User Suspended</Badge>
      case 'reactivate_user':
        return <Badge bg="success">User Reactivated</Badge>
      case 'delete_user':
        return <Badge bg="dark">User Deleted</Badge>
      case 'update_setting':
        return <Badge bg="primary">Setting Updated</Badge>
      default:
        return <Badge bg="secondary">{action}</Badge>
    }
  }

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 1000 }}>
        {/* Header */}
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <div>
            <h2 className="fw-bold mb-1">⚙️ System Settings & Audit Trail</h2>
            <p className="text-muted mb-0">Manage global automation limits and review administrative actions</p>
          </div>
          <div className="d-flex gap-2">
            <Link to="/admin">
              <Button variant="outline-secondary" size="sm">
                ← Dashboard
              </Button>
            </Link>
            <Link to="/admin/users">
              <Button variant="outline-primary" size="sm">
                👥 Users
              </Button>
            </Link>
          </div>
        </div>

        {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
        {successMsg && <Alert variant="success" dismissible onClose={() => setSuccessMsg('')}>{successMsg}</Alert>}

        {loading ? (
          <div className="text-center py-5">
            <Spinner animation="border" variant="primary" />
            <p className="mt-2 text-muted small">Loading settings and logs...</p>
          </div>
        ) : (
          <Row className="g-4">
            {/* Global Settings Form */}
            <Col md={5}>
              <Card className="border-0 shadow-sm">
                <Card.Header className="bg-white border-0 pt-3 pb-0">
                  <h5 className="fw-bold mb-0">Global Rate Limits</h5>
                </Card.Header>
                <Card.Body>
                  <Form onSubmit={handleSaveSettings}>
                    <Form.Group className="mb-3">
                      <Form.Label className="fw-semibold small">
                        Daily Application Limit per Candidate
                      </Form.Label>
                      <Form.Control
                        type="number"
                        min="1"
                        max="1000"
                        value={dailyLimit}
                        onChange={(e) => setDailyLimit(e.target.value)}
                        required
                      />
                      <Form.Text className="text-muted small">
                        Maximum number of automated job applications each candidate is permitted to initiate within a UTC calendar day (00:00:00 to 23:59:59 UTC).
                      </Form.Text>
                    </Form.Group>

                    {settingMeta && (
                      <div className="small text-muted mb-3">
                        Last modified: {new Date(settingMeta.updated_at).toLocaleString()}
                      </div>
                    )}

                    <Button type="submit" variant="primary" disabled={saving}>
                      {saving ? <Spinner size="sm" animation="border" /> : 'Save Limit Changes'}
                    </Button>
                  </Form>
                </Card.Body>
              </Card>
            </Col>

            {/* Audit Logs Table */}
            <Col md={7}>
              <Card className="border-0 shadow-sm">
                <Card.Header className="bg-white border-0 pt-3 pb-0 d-flex justify-content-between align-items-center">
                  <h5 className="fw-bold mb-0">Administrative Audit Trail</h5>
                  <Badge bg="light" text="dark" className="border">
                    {auditLogs.length} events
                  </Badge>
                </Card.Header>
                <Card.Body className="p-0">
                  {auditLogs.length === 0 ? (
                    <div className="text-center py-5 text-muted small">
                      No administrative actions logged yet.
                    </div>
                  ) : (
                    <Table hover responsive className="mb-0 align-middle">
                      <thead className="table-light">
                        <tr>
                          <th>Action</th>
                          <th>Details</th>
                          <th>Admin / Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {auditLogs.map((log) => (
                          <tr key={log.id}>
                            <td>{getActionBadge(log.action)}</td>
                            <td>
                              <div className="small text-dark fw-medium">{log.details || '—'}</div>
                            </td>
                            <td>
                              <div className="small fw-semibold">{log.admin_name}</div>
                              <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                                {new Date(log.created_at).toLocaleString()}
                              </div>
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
        )}
      </Container>
    </>
  )
}
