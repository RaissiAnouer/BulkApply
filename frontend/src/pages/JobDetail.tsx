import { useState, useEffect } from 'react'
import {
  Container,
  Card,
  Form,
  Button,
  Spinner,
  Alert,
  Row,
  Col,
  Badge,
  Modal,
  Nav,
} from 'react-bootstrap'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import Navbar from '../components/Navbar'

interface Job {
  id: number
  user_id: number
  url: string
  title: string | null
  company: string | null
  location: string | null
  work_type: string | null
  experience_level: string | null
  skills: string | null
  description: string | null
  salary: string | null
  application_url: string | null
  application_method: string | null
  status: string
  created_at: string
  updated_at: string
}

interface CompanyContact {
  id: number
  intelligence_id: number
  full_name: string
  job_title: string
  category: 'hiring' | 'leadership' | 'other'
  department: string | null
  linkedin_url: string | null
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  evidence: string | null
  is_relevant: boolean
  created_at: string
}

interface CompanyIntelligence {
  id: number
  job_id: number
  company_name: string
  website: string | null
  linkedin_url: string | null
  industry: string | null
  description: string | null
  headquarters: string | null
  company_size: string | null
  technologies: string | null
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'
  status: 'PENDING' | 'RESEARCHING' | 'COMPLETED' | 'FAILED'
  error_message: string | null
  created_at: string
  updated_at: string
  contacts: CompanyContact[]
}

const WORK_TYPE_LABELS: Record<string, string> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'On-site',
}

export default function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [job, setJob] = useState<Job | null>(null)

  // Edit Job Form
  const [form, setForm] = useState({
    title: '',
    company: '',
    location: '',
    work_type: '',
    experience_level: '',
    skills: '',
    description: '',
    salary: '',
    application_url: '',
    application_method: '',
  })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Delete Job
  const [showDelete, setShowDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Company Intelligence State
  const [intel, setIntel] = useState<CompanyIntelligence | null>(null)
  const [intelLoading, setIntelLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [intelError, setIntelError] = useState('')
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [activeCategory, setActiveCategory] = useState<'all' | 'hiring' | 'leadership' | 'other'>('all')

  useEffect(() => {
    fetchJob()
    fetchIntelligence()
  }, [id])

  // Polling when intelligence is still researching
  useEffect(() => {
    if (intel && (intel.status === 'RESEARCHING' || intel.status === 'PENDING')) {
      const timer = setTimeout(() => {
        fetchIntelligence(false)
      }, 4000)
      return () => clearTimeout(timer)
    }
  }, [intel?.status])

  const fetchJob = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api<Job>(`/api/jobs/${id}`)
      setJob(data)
      setForm({
        title: data.title || '',
        company: data.company || '',
        location: data.location || '',
        work_type: data.work_type || '',
        experience_level: data.experience_level || '',
        skills: data.skills || '',
        description: data.description || '',
        salary: data.salary || '',
        application_url: data.application_url || '',
        application_method: data.application_method || '',
      })
    } catch (err: any) {
      setError(err.message || 'Failed to load job')
    } finally {
      setLoading(false)
    }
  }

  const fetchIntelligence = async (showLoader = true) => {
    if (showLoader) setIntelLoading(true)
    setIntelError('')
    try {
      const data = await api<CompanyIntelligence>(`/api/jobs/${id}/company-intelligence`)
      setIntel(data)
    } catch (err: any) {
      // 404 is normal if research hasn't been triggered yet
      if (err.status !== 404) {
        setIntelError(err.message || 'Could not load company intelligence')
      }
    } finally {
      if (showLoader) setIntelLoading(false)
    }
  }

  const handleRefreshIntel = async () => {
    setRefreshing(true)
    setIntelError('')
    try {
      const updated = await api<CompanyIntelligence>(`/api/jobs/${id}/company-intelligence/refresh`, {
        method: 'POST',
      })
      setIntel(updated)
    } catch (err: any) {
      setIntelError(err.message || 'Failed to trigger intelligence refresh.')
    } finally {
      setRefreshing(false)
    }
  }

  const handleToggleRelevance = async (contactId: number, current: boolean) => {
    try {
      const updated = await api<CompanyContact>(
        `/api/jobs/${id}/company-intelligence/contacts/${contactId}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ is_relevant: !current }),
        }
      )
      setIntel((prev) =>
        prev
          ? {
              ...prev,
              contacts: prev.contacts.map((c) => (c.id === contactId ? updated : c)),
            }
          : null
      )
    } catch (err: any) {
      alert(err.message || 'Failed to update contact.')
    }
  }

  const handleDeleteContact = async (contactId: number) => {
    try {
      await api(`/api/jobs/${id}/company-intelligence/contacts/${contactId}`, {
        method: 'DELETE',
      })
      setIntel((prev) =>
        prev
          ? {
              ...prev,
              contacts: prev.contacts.filter((c) => c.id !== contactId),
            }
          : null
      )
    } catch (err: any) {
      alert(err.message || 'Failed to remove contact.')
    }
  }

  const handleCopyUrl = (contactId: number, url: string) => {
    navigator.clipboard.writeText(url)
    setCopiedId(contactId)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    setSaveSuccess(false)

    try {
      const data = await api<Job>(`/api/jobs/${id}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: form.title || null,
          company: form.company || null,
          location: form.location || null,
          work_type: form.work_type || null,
          experience_level: form.experience_level || null,
          skills: form.skills || null,
          description: form.description || null,
          salary: form.salary || null,
          application_url: form.application_url || null,
          application_method: form.application_method || null,
        }),
      })
      setJob(data)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save changes')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await api(`/api/jobs/${id}`, { method: 'DELETE' })
      navigate('/jobs')
    } catch (err: any) {
      setSaveError(err.message || 'Failed to delete job')
    } finally {
      setDeleting(false)
      setShowDelete(false)
    }
  }

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })

  const filteredContacts = (intel?.contacts || []).filter((c) => {
    if (activeCategory === 'all') return true
    return c.category === activeCategory
  })

  if (loading) {
    return (
      <>
        <Navbar />
        <Container className="py-5 text-center">
          <Spinner animation="border" style={{ color: 'var(--color-primary)' }} />
          <p className="text-muted mt-2">Loading job...</p>
        </Container>
      </>
    )
  }

  if (error || !job) {
    return (
      <>
        <Navbar />
        <Container className="py-4" style={{ maxWidth: 780 }}>
          <Alert variant="danger">{error || 'Job not found'}</Alert>
          <Button variant="outline-secondary" onClick={() => navigate('/jobs')}>
            ← Back to Jobs
          </Button>
        </Container>
      </>
    )
  }

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 840 }}>
        {/* Header */}
        <div className="d-flex justify-content-between align-items-start mb-3">
          <div>
            <Button
              variant="link"
              className="p-0 mb-2 text-muted text-decoration-none"
              onClick={() => navigate('/jobs')}
              style={{ fontSize: 14 }}
            >
              ← Back to Jobs
            </Button>
            <h3 style={{ color: 'var(--color-dark)', fontWeight: 700 }} className="mb-1">
              {job.title || '(Untitled Job)'}
            </h3>
            <div className="d-flex align-items-center gap-2 text-muted small">
              {job.company && <span className="fw-semibold text-dark">{job.company}</span>}
              {job.work_type && (
                <Badge bg="secondary" className="fw-normal">
                  {WORK_TYPE_LABELS[job.work_type] || job.work_type}
                </Badge>
              )}
              <Badge
                bg={job.status === 'ready' ? 'primary' : 'success'}
                className="fw-normal"
              >
                {job.status === 'ready' ? 'Ready' : 'Applied'}
              </Badge>
            </div>
          </div>
          <div>
            <Button
              style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
              onClick={() => navigate(`/apply?job_id=${job.id}`)}
              className="fw-semibold px-3"
            >
              Apply to this Job ✨
            </Button>
          </div>
        </div>

        {/* URL Meta Bar */}
        <Card className="shadow-sm border-0 mb-4 bg-light">
          <Card.Body className="py-2 px-3">
            <Row className="small text-muted align-items-center">
              <Col>
                <strong>Source:</strong>{' '}
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-truncate d-inline-block"
                  style={{ maxWidth: 450, verticalAlign: 'bottom' }}
                >
                  {job.url}
                </a>
              </Col>
              <Col xs="auto">Added {formatDate(job.created_at)}</Col>
            </Row>
          </Card.Body>
        </Card>

        {/* ========================================================================= */}
        {/* COMPANY & CONTACT INTELLIGENCE SECTION                                     */}
        {/* ========================================================================= */}
        <Card className="shadow-sm border-0 mb-4">
          <Card.Header className="bg-white py-3 border-0 d-flex justify-content-between align-items-center">
            <div className="d-flex align-items-center gap-2">
              <span style={{ fontSize: '20px' }}>🏢</span>
              <h5 className="fw-bold mb-0" style={{ color: 'var(--color-dark)' }}>
                Company Intelligence & Outreach
              </h5>
              {intel?.confidence && (
                <Badge
                  bg={
                    intel.confidence === 'HIGH'
                      ? 'success'
                      : intel.confidence === 'MEDIUM'
                      ? 'primary'
                      : 'warning'
                  }
                  text={intel.confidence === 'LOW' ? 'dark' : undefined}
                  style={{ fontSize: 11 }}
                >
                  {intel.confidence} Confidence
                </Badge>
              )}
            </div>

            <div className="d-flex align-items-center gap-2">
              {intel?.status === 'RESEARCHING' && (
                <span className="text-primary small d-flex align-items-center gap-1">
                  <Spinner animation="border" size="sm" />
                  Researching...
                </span>
              )}
              {intel?.status === 'COMPLETED' && (
                <Badge bg="light" text="success" className="border border-success small">
                  Complete
                </Badge>
              )}
              {intel?.status === 'FAILED' && (
                <Badge bg="danger" className="small">
                  Incomplete
                </Badge>
              )}

              <Button
                variant="outline-secondary"
                size="sm"
                onClick={handleRefreshIntel}
                disabled={refreshing || intel?.status === 'RESEARCHING'}
                title="Re-run company research and employee discovery"
              >
                {refreshing ? (
                  <Spinner animation="border" size="sm" />
                ) : (
                  '🔄 Refresh Research'
                )}
              </Button>
            </div>
          </Card.Header>

          <Card.Body className="p-4 pt-1">
            {intelError && <Alert variant="danger" className="py-2 small">{intelError}</Alert>}

            {intelLoading ? (
              <div className="text-center py-4 text-muted">
                <Spinner animation="border" size="sm" className="me-2" />
                Loading company intelligence...
              </div>
            ) : !intel ? (
              <div className="text-center py-4 bg-light rounded p-3">
                <p className="text-muted mb-2">No company intelligence gathered yet.</p>
                <Button
                  size="sm"
                  style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                  onClick={handleRefreshIntel}
                  disabled={refreshing}
                >
                  🚀 Run Company Intelligence
                </Button>
              </div>
            ) : (
              <>
                {/* Company Profile Details */}
                <div className="bg-light rounded p-3 mb-4 border">
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <div>
                      <h6 className="fw-bold mb-1" style={{ color: 'var(--color-primary)' }}>
                        {intel.company_name}
                      </h6>
                      <div className="text-muted small">
                        {intel.industry || 'General Industry'}
                        {intel.headquarters && ` • 📍 ${intel.headquarters}`}
                        {intel.company_size && ` • 👥 ${intel.company_size}`}
                      </div>
                    </div>
                    <div className="d-flex gap-2">
                      {intel.website && (
                        <a
                          href={intel.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-sm btn-outline-primary"
                          style={{ fontSize: 12 }}
                        >
                          🌐 Website ↗
                        </a>
                      )}
                      {intel.linkedin_url && (
                        <a
                          href={intel.linkedin_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-sm btn-outline-info"
                          style={{ fontSize: 12 }}
                        >
                          💼 Company LinkedIn ↗
                        </a>
                      )}
                    </div>
                  </div>

                  {intel.description && (
                    <p className="small text-secondary mb-2 mt-2" style={{ lineHeight: 1.5 }}>
                      {intel.description}
                    </p>
                  )}

                  {intel.technologies && (
                    <div className="d-flex flex-wrap gap-1 mt-2 align-items-center">
                      <span className="text-muted small me-1">Stack:</span>
                      {intel.technologies.split(',').map((tech, i) => (
                        <Badge key={i} bg="secondary" className="fw-normal" style={{ fontSize: 11 }}>
                          {tech.trim()}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                {/* Relevant Employees Section */}
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h6 className="fw-bold mb-0">
                    Relevant People ({intel.contacts?.length || 0})
                  </h6>

                  {/* Category Filter Tabs */}
                  <Nav
                    variant="pills"
                    activeKey={activeCategory}
                    onSelect={(k) => setActiveCategory(k as any)}
                    className="small"
                  >
                    <Nav.Item>
                      <Nav.Link eventKey="all" className="py-1 px-2">
                        All ({intel.contacts?.length || 0})
                      </Nav.Link>
                    </Nav.Item>
                    <Nav.Item>
                      <Nav.Link eventKey="hiring" className="py-1 px-2">
                        🎯 Recruiting ({intel.contacts?.filter((c) => c.category === 'hiring').length || 0})
                      </Nav.Link>
                    </Nav.Item>
                    <Nav.Item>
                      <Nav.Link eventKey="leadership" className="py-1 px-2">
                        👔 Leadership ({intel.contacts?.filter((c) => c.category === 'leadership').length || 0})
                      </Nav.Link>
                    </Nav.Item>
                    <Nav.Item>
                      <Nav.Link eventKey="other" className="py-1 px-2">
                        👥 Team ({intel.contacts?.filter((c) => c.category === 'other').length || 0})
                      </Nav.Link>
                    </Nav.Item>
                  </Nav>
                </div>

                {filteredContacts.length === 0 ? (
                  <div className="text-center py-4 bg-light rounded text-muted small">
                    {intel.status === 'RESEARCHING'
                      ? 'Finding and verifying public LinkedIn profiles for relevant employees...'
                      : 'No public employees found for this category.'}
                  </div>
                ) : (
                  <div className="d-flex flex-column gap-2">
                    {filteredContacts.map((contact) => (
                      <Card
                        key={contact.id}
                        className={`border ${!contact.is_relevant ? 'opacity-50 bg-light' : ''}`}
                        style={{ borderRadius: 8 }}
                      >
                        <Card.Body className="p-3">
                          <div className="d-flex justify-content-between align-items-start">
                            <div className="me-2">
                              <div className="d-flex align-items-center gap-2 mb-1">
                                <span className="fw-bold">{contact.full_name}</span>
                                <Badge
                                  bg={
                                    contact.category === 'hiring'
                                      ? 'success'
                                      : contact.category === 'leadership'
                                      ? 'primary'
                                      : 'secondary'
                                  }
                                  style={{ fontSize: 10 }}
                                >
                                  {contact.category === 'hiring'
                                    ? 'Hiring / Recruiting'
                                    : contact.category === 'leadership'
                                    ? 'Leadership'
                                    : 'Team'}
                                </Badge>
                                <Badge
                                  bg={contact.confidence === 'HIGH' ? 'light' : 'light'}
                                  text={contact.confidence === 'HIGH' ? 'success' : 'dark'}
                                  className="border"
                                  style={{ fontSize: 10 }}
                                >
                                  {contact.confidence}
                                </Badge>
                              </div>

                              <div className="text-muted small mb-1">
                                {contact.job_title}
                                {contact.department && ` • ${contact.department}`}
                              </div>

                              {contact.evidence && (
                                <div className="text-secondary small fst-italic" style={{ fontSize: 11 }}>
                                  💡 {contact.evidence}
                                </div>
                              )}
                            </div>

                            {/* Actions */}
                            <div className="d-flex align-items-center gap-2 flex-shrink-0">
                              {contact.linkedin_url ? (
                                <>
                                  <a
                                    href={contact.linkedin_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn btn-sm btn-primary"
                                    style={{ fontSize: 12 }}
                                  >
                                    🔗 LinkedIn
                                  </a>
                                  <Button
                                    variant="outline-secondary"
                                    size="sm"
                                    onClick={() => handleCopyUrl(contact.id, contact.linkedin_url!)}
                                    style={{ fontSize: 12 }}
                                    title="Copy LinkedIn URL"
                                  >
                                    {copiedId === contact.id ? '✓ Copied' : '📋 Copy'}
                                  </Button>
                                </>
                              ) : (
                                <Badge bg="light" text="muted" className="border">
                                  No public link
                                </Badge>
                              )}

                              <Button
                                variant="link"
                                size="sm"
                                className="p-0 text-muted"
                                title={contact.is_relevant ? 'Mark as not relevant' : 'Mark as relevant'}
                                onClick={() => handleToggleRelevance(contact.id, contact.is_relevant)}
                              >
                                {contact.is_relevant ? '⭐' : '☆'}
                              </Button>

                              <Button
                                variant="link"
                                size="sm"
                                className="p-0 text-danger ms-1"
                                title="Remove this person"
                                onClick={() => handleDeleteContact(contact.id)}
                              >
                                ✕
                              </Button>
                            </div>
                          </div>
                        </Card.Body>
                      </Card>
                    ))}
                  </div>
                )}
              </>
            )}
          </Card.Body>
        </Card>

        {/* ========================================================================= */}
        {/* EDIT JOB DETAILS SECTION                                                  */}
        {/* ========================================================================= */}
        <Card className="shadow-sm border-0">
          <Card.Body className="p-4">
            <h5 className="fw-semibold mb-3" style={{ color: 'var(--color-dark)' }}>
              Edit Job Details
            </h5>

            <Form onSubmit={handleSave}>
              <Row className="g-3">
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Job Title</Form.Label>
                    <Form.Control
                      value={form.title}
                      onChange={(e) => updateField('title', e.target.value)}
                      placeholder="Software Engineer"
                    />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Company</Form.Label>
                    <Form.Control
                      value={form.company}
                      onChange={(e) => updateField('company', e.target.value)}
                      placeholder="Acme Corp"
                    />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Location</Form.Label>
                    <Form.Control
                      value={form.location}
                      onChange={(e) => updateField('location', e.target.value)}
                      placeholder="New York, NY"
                    />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Salary</Form.Label>
                    <Form.Control
                      value={form.salary}
                      onChange={(e) => updateField('salary', e.target.value)}
                      placeholder="$80k–$120k"
                    />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Work Type</Form.Label>
                    <Form.Select
                      value={form.work_type}
                      onChange={(e) => updateField('work_type', e.target.value)}
                    >
                      <option value="">— Select —</option>
                      <option value="remote">Remote</option>
                      <option value="hybrid">Hybrid</option>
                      <option value="onsite">On-site</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Experience Level</Form.Label>
                    <Form.Select
                      value={form.experience_level}
                      onChange={(e) => updateField('experience_level', e.target.value)}
                    >
                      <option value="">— Select —</option>
                      <option value="entry">Entry</option>
                      <option value="mid">Mid</option>
                      <option value="senior">Senior</option>
                      <option value="lead">Lead</option>
                      <option value="executive">Executive</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={12}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Skills</Form.Label>
                    <Form.Control
                      value={form.skills}
                      onChange={(e) => updateField('skills', e.target.value)}
                      placeholder="Python, React, SQL"
                    />
                  </Form.Group>
                </Col>
                <Col md={12}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Description</Form.Label>
                    <Form.Control
                      as="textarea"
                      rows={6}
                      value={form.description}
                      onChange={(e) => updateField('description', e.target.value)}
                      placeholder="Full job description..."
                    />
                  </Form.Group>
                </Col>
                <Col md={8}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Application URL</Form.Label>
                    <Form.Control
                      value={form.application_url}
                      onChange={(e) => updateField('application_url', e.target.value)}
                      placeholder="https://company.com/apply/123"
                    />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Application Method</Form.Label>
                    <Form.Select
                      value={form.application_method}
                      onChange={(e) => updateField('application_method', e.target.value)}
                    >
                      <option value="">— Select —</option>
                      <option value="form">Form</option>
                      <option value="email">Email</option>
                      <option value="external_link">External Link</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
              </Row>

              {saveError && <Alert variant="danger" className="mt-3">{saveError}</Alert>}
              {saveSuccess && <Alert variant="success" className="mt-3">✅ Job updated successfully!</Alert>}

              <div className="d-flex justify-content-between mt-4">
                <div className="d-flex gap-2">
                  <Button
                    type="submit"
                    style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                    disabled={saving}
                    className="px-4"
                  >
                    {saving ? (
                      <>
                        <Spinner animation="border" size="sm" className="me-2" />
                        Saving...
                      </>
                    ) : (
                      '💾 Save Changes'
                    )}
                  </Button>
                  <Button variant="outline-secondary" onClick={() => navigate('/jobs')}>
                    Cancel
                  </Button>
                </div>
                <Button variant="outline-danger" onClick={() => setShowDelete(true)}>
                  🗑 Delete
                </Button>
              </div>
            </Form>
          </Card.Body>
        </Card>

        {/* Delete Confirmation Modal */}
        <Modal show={showDelete} onHide={() => setShowDelete(false)} centered>
          <Modal.Header closeButton>
            <Modal.Title style={{ fontSize: 18 }}>Delete Job</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            Are you sure you want to delete <strong>{job.title || 'this job'}</strong>
            {job.company && <> at <strong>{job.company}</strong></>}?
            This will also remove all associated company intelligence records.
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowDelete(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Spinner animation="border" size="sm" /> : 'Delete'}
            </Button>
          </Modal.Footer>
        </Modal>
      </Container>
    </>
  )
}
