import { useState, useEffect } from 'react'
import { Container, Card, Form, Button, Spinner, Alert, Row, Col, Badge, Modal } from 'react-bootstrap'
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

  // Delete
  const [showDelete, setShowDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchJob()
  }, [id])

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
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
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
        <Container className="py-4" style={{ maxWidth: 700 }}>
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
      <Container className="py-4" style={{ maxWidth: 700 }}>
        {/* Header */}
        <div className="d-flex justify-content-between align-items-start mb-4">
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
              {job.company && <span>{job.company}</span>}
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
              className="fw-semibold"
            >
              Apply to this Job ✨
            </Button>
          </div>
        </div>

        {/* Meta */}
        <Card className="shadow-sm border-0 mb-3">
          <Card.Body className="py-2 px-3">
            <Row className="small text-muted">
              <Col>
                <strong>URL:</strong>{' '}
                <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-truncate d-inline-block" style={{ maxWidth: 350, verticalAlign: 'bottom' }}>
                  {job.url}
                </a>
              </Col>
              <Col xs="auto">Added {formatDate(job.created_at)}</Col>
            </Row>
          </Card.Body>
        </Card>

        {/* Edit Form */}
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
                    <Form.Control value={form.title} onChange={(e) => updateField('title', e.target.value)} placeholder="Software Engineer" />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Company</Form.Label>
                    <Form.Control value={form.company} onChange={(e) => updateField('company', e.target.value)} placeholder="Acme Corp" />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Location</Form.Label>
                    <Form.Control value={form.location} onChange={(e) => updateField('location', e.target.value)} placeholder="New York, NY" />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Salary</Form.Label>
                    <Form.Control value={form.salary} onChange={(e) => updateField('salary', e.target.value)} placeholder="$80k–$120k" />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Work Type</Form.Label>
                    <Form.Select value={form.work_type} onChange={(e) => updateField('work_type', e.target.value)}>
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
                    <Form.Select value={form.experience_level} onChange={(e) => updateField('experience_level', e.target.value)}>
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
                    <Form.Control value={form.skills} onChange={(e) => updateField('skills', e.target.value)} placeholder="Python, React, SQL" />
                  </Form.Group>
                </Col>
                <Col md={12}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Description</Form.Label>
                    <Form.Control as="textarea" rows={6} value={form.description} onChange={(e) => updateField('description', e.target.value)} placeholder="Full job description..." />
                  </Form.Group>
                </Col>
                <Col md={8}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Application URL</Form.Label>
                    <Form.Control value={form.application_url} onChange={(e) => updateField('application_url', e.target.value)} placeholder="https://company.com/apply/123" />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label className="small fw-semibold">Application Method</Form.Label>
                    <Form.Select value={form.application_method} onChange={(e) => updateField('application_method', e.target.value)}>
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
                    {saving ? <><Spinner animation="border" size="sm" className="me-2" />Saving...</> : '💾 Save Changes'}
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

        {/* Delete Modal */}
        <Modal show={showDelete} onHide={() => setShowDelete(false)} centered>
          <Modal.Header closeButton>
            <Modal.Title style={{ fontSize: 18 }}>Delete Job</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            Are you sure you want to delete <strong>{job.title || 'this job'}</strong>
            {job.company && <> at <strong>{job.company}</strong></>}?
            This action cannot be undone.
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowDelete(false)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Spinner animation="border" size="sm" /> : 'Delete'}
            </Button>
          </Modal.Footer>
        </Modal>
      </Container>
    </>
  )
}
