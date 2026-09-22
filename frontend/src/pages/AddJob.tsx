import { useState } from 'react'
import { Container, Card, Form, Button, Spinner, Alert, Row, Col } from 'react-bootstrap'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import Navbar from '../components/Navbar'

interface ExtractedJob {
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
  extraction_method: string | null
  extraction_warning: string | null
}

export default function AddJob() {
  const navigate = useNavigate()

  // Phase 1: URL input
  const [url, setUrl] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [extractError, setExtractError] = useState('')

  // Phase 2: Review/edit
  const [extracted, setExtracted] = useState<ExtractedJob | null>(null)
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

  const handleExtract = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return

    setExtracting(true)
    setExtractError('')
    setExtracted(null)

    try {
      const data = await api<ExtractedJob>('/api/jobs/extract', {
        method: 'POST',
        body: JSON.stringify({ url: url.trim() }),
      })
      setExtracted(data)
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
      if (err.status === 409) {
        setExtractError('You have already added this job.')
      } else {
        setExtractError(err.message || 'Extraction failed. Please try again.')
      }
    } finally {
      setExtracting(false)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')

    try {
      await api('/api/jobs', {
        method: 'POST',
        body: JSON.stringify({
          url: extracted?.url || url.trim(),
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
      navigate('/jobs')
    } catch (err: any) {
      if (err.status === 409) {
        setSaveError('You have already added this job.')
      } else {
        setSaveError(err.message || 'Failed to save job.')
      }
    } finally {
      setSaving(false)
    }
  }

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const isFieldEmpty = (value: string) => !value || value.trim() === ''

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 700 }}>
        <div className="mb-4">
          <h3 style={{ color: 'var(--color-dark)', fontWeight: 700 }}>
            ➕ Add a New Job
          </h3>
          <p className="text-muted mb-0">
            Paste a public job listing URL and we'll extract the details for you.
          </p>
        </div>

        {/* Phase 1: URL Input */}
        {!extracted && (
          <Card className="shadow-sm border-0 mb-4">
            <Card.Body className="p-4">
              <Form onSubmit={handleExtract}>
                <Form.Group className="mb-3">
                  <Form.Label className="fw-semibold">Job URL</Form.Label>
                  <Form.Control
                    type="url"
                    placeholder="https://company.com/careers/job-title"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    disabled={extracting}
                    required
                    size="lg"
                  />
                  <Form.Text className="text-muted">
                    Paste a public link to a job posting (LinkedIn, Indeed, company career pages, etc.)
                  </Form.Text>
                </Form.Group>

                {extractError && <Alert variant="danger">{extractError}</Alert>}

                <Button
                  type="submit"
                  className="w-100"
                  style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                  disabled={extracting || !url.trim()}
                  size="lg"
                >
                  {extracting ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-2" />
                      Extracting... (this may take up to 30s)
                    </>
                  ) : (
                    '🔍 Extract Job Info'
                  )}
                </Button>
              </Form>
            </Card.Body>
          </Card>
        )}

        {/* Phase 2: Review & Edit */}
        {extracted && (
          <>
            {/* Extraction metadata */}
            {extracted.extraction_warning && (
              <Alert variant="warning" className="d-flex align-items-start">
                <span className="me-2">⚠️</span>
                <span>{extracted.extraction_warning}</span>
              </Alert>
            )}
            {extracted.extraction_method && !extracted.extraction_warning && (
              <Alert variant="success" className="d-flex align-items-start">
                <span className="me-2">✅</span>
                <span>
                  Job details extracted successfully
                  {extracted.extraction_method === 'gemini_url_context' && ' using AI'}
                  . Review and edit the fields below before saving.
                </span>
              </Alert>
            )}

            <Card className="shadow-sm border-0">
              <Card.Body className="p-4">
                <h5 className="fw-semibold mb-3" style={{ color: 'var(--color-dark)' }}>
                  Review Extracted Data
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
                          style={isFieldEmpty(form.title) ? { backgroundColor: '#FEF9C3' } : {}}
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
                          style={isFieldEmpty(form.company) ? { backgroundColor: '#FEF9C3' } : {}}
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
                          style={isFieldEmpty(form.location) ? { backgroundColor: '#FEF9C3' } : {}}
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
                          style={isFieldEmpty(form.work_type) ? { backgroundColor: '#FEF9C3' } : {}}
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
                          style={isFieldEmpty(form.experience_level) ? { backgroundColor: '#FEF9C3' } : {}}
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
                          placeholder="Python, React, SQL (comma-separated)"
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
                          style={isFieldEmpty(form.description) ? { backgroundColor: '#FEF9C3' } : {}}
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

                  <div className="d-flex gap-2 mt-4">
                    <Button
                      type="submit"
                      style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                      disabled={saving}
                      className="px-4"
                    >
                      {saving ? (
                        <><Spinner animation="border" size="sm" className="me-2" />Saving...</>
                      ) : (
                        '💾 Save Job'
                      )}
                    </Button>
                    <Button
                      variant="outline-secondary"
                      onClick={() => { setExtracted(null); setUrl('') }}
                    >
                      Cancel
                    </Button>
                  </div>
                </Form>
              </Card.Body>
            </Card>
          </>
        )}
      </Container>
    </>
  )
}
