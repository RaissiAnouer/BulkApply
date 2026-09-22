import { useState, useMemo } from 'react'
import {
  Container,
  Card,
  Form,
  Button,
  Spinner,
  Alert,
  Row,
  Col,
  Nav,
  Table,
  Badge,
  ProgressBar,
} from 'react-bootstrap'
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

interface BulkJobItemResult {
  url: string
  status: 'extracted' | 'duplicate' | 'failed'
  error?: string | null
  data?: ExtractedJob | null
  existing_job_id?: number | null
}

interface BulkJobExtractResponse {
  total: number
  extracted_count: number
  duplicate_count: number
  failed_count: number
  items: BulkJobItemResult[]
}

interface BulkStagingItem {
  id: string
  url: string
  status: 'extracted' | 'duplicate' | 'failed'
  error?: string | null
  title: string
  company: string
  location: string
  work_type: string
  experience_level: string
  skills: string
  description: string
  salary: string
  application_url: string
  application_method: string
  selected: boolean
}

export default function AddJob() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'single' | 'bulk'>('single')

  // --- Single URL State ---
  const [singleUrl, setSingleUrl] = useState('')
  const [singleExtracting, setSingleExtracting] = useState(false)
  const [singleExtractError, setSingleExtractError] = useState('')
  const [singleExtracted, setSingleExtracted] = useState<ExtractedJob | null>(null)
  const [singleForm, setSingleForm] = useState({
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
  const [singleSaving, setSingleSaving] = useState(false)
  const [singleSaveError, setSingleSaveError] = useState('')

  // --- Bulk URLs State ---
  const [bulkRawText, setBulkRawText] = useState('')
  const [bulkExtracting, setBulkExtracting] = useState(false)
  const [bulkExtractError, setBulkExtractError] = useState('')
  const [bulkItems, setBulkItems] = useState<BulkStagingItem[]>([])
  const [bulkSaving, setBulkSaving] = useState(false)
  const [bulkSaveError, setBulkSaveError] = useState('')
  const [bulkSaveSuccess, setBulkSaveSuccess] = useState('')

  // Parse valid URLs from raw textarea in real-time
  const parsedUrls = useMemo(() => {
    const rawTokens = bulkRawText
      .split(/[\r\n,\s]+/)
      .map((t) => t.trim())
      .filter((t) => t.length > 0)

    const validList: string[] = []
    const seen = new Set<string>()

    for (const token of rawTokens) {
      if (/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(token) && !seen.has(token)) {
        seen.add(token)
        validList.push(token)
      }
    }
    return validList
  }, [bulkRawText])

  // Handle single URL extraction
  const handleSingleExtract = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!singleUrl.trim()) return

    setSingleExtracting(true)
    setSingleExtractError('')
    setSingleExtracted(null)

    try {
      const data = await api<ExtractedJob>('/api/jobs/extract', {
        method: 'POST',
        body: JSON.stringify({ url: singleUrl.trim() }),
      })
      setSingleExtracted(data)
      setSingleForm({
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
        setSingleExtractError('You have already added this job.')
      } else {
        setSingleExtractError(err.message || 'Extraction failed. Please try again.')
      }
    } finally {
      setSingleExtracting(false)
    }
  }

  // Handle single URL save
  const handleSingleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSingleSaving(true)
    setSingleSaveError('')

    try {
      await api('/api/jobs', {
        method: 'POST',
        body: JSON.stringify({
          url: singleExtracted?.url || singleUrl.trim(),
          title: singleForm.title || null,
          company: singleForm.company || null,
          location: singleForm.location || null,
          work_type: singleForm.work_type || null,
          experience_level: singleForm.experience_level || null,
          skills: singleForm.skills || null,
          description: singleForm.description || null,
          salary: singleForm.salary || null,
          application_url: singleForm.application_url || null,
          application_method: singleForm.application_method || null,
        }),
      })
      navigate('/jobs')
    } catch (err: any) {
      if (err.status === 409) {
        setSingleSaveError('You have already added this job.')
      } else {
        setSingleSaveError(err.message || 'Failed to save job.')
      }
    } finally {
      setSingleSaving(false)
    }
  }

  // Handle file drop/upload for bulk URLs
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target?.result as string
      if (text) {
        setBulkRawText((prev) => (prev ? `${prev}\n${text}` : text))
      }
    }
    reader.readAsText(file)
  }

  // Handle Bulk Extraction request
  const handleBulkExtract = async (e: React.FormEvent) => {
    e.preventDefault()
    if (parsedUrls.length === 0) return

    setBulkExtracting(true)
    setBulkExtractError('')
    setBulkSaveSuccess('')
    setBulkItems([])

    try {
      const res = await api<BulkJobExtractResponse>('/api/jobs/bulk-extract', {
        method: 'POST',
        body: JSON.stringify({ urls: parsedUrls }),
      })

      const staging: BulkStagingItem[] = res.items.map((item, idx) => ({
        id: `bulk-${idx}-${Date.now()}`,
        url: item.url,
        status: item.status,
        error: item.error,
        title: item.data?.title || '',
        company: item.data?.company || '',
        location: item.data?.location || '',
        work_type: item.data?.work_type || '',
        experience_level: item.data?.experience_level || '',
        skills: item.data?.skills || '',
        description: item.data?.description || '',
        salary: item.data?.salary || '',
        application_url: item.data?.application_url || item.url,
        application_method: item.data?.application_method || 'form',
        selected: item.status === 'extracted',
      }))

      setBulkItems(staging)
    } catch (err: any) {
      setBulkExtractError(err.message || 'Bulk extraction failed. Please try again.')
    } finally {
      setBulkExtracting(false)
    }
  }

  // Toggle selection for a single staging row
  const toggleSelect = (id: string) => {
    setBulkItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, selected: !item.selected } : item))
    )
  }

  // Toggle master selection
  const toggleSelectAll = () => {
    const extractable = bulkItems.filter((i) => i.status === 'extracted')
    const allSelected = extractable.every((i) => i.selected)
    setBulkItems((prev) =>
      prev.map((item) =>
        item.status === 'extracted' ? { ...item, selected: !allSelected } : item
      )
    )
  }

  // Update field in staging table
  const updateStagingField = (id: string, field: 'title' | 'company' | 'location', val: string) => {
    setBulkItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, [field]: val } : item))
    )
  }

  // Bulk save selected jobs
  const handleBulkSave = async () => {
    const selectedJobs = bulkItems.filter((i) => i.selected && i.status === 'extracted')
    if (selectedJobs.length === 0) return

    setBulkSaving(true)
    setBulkSaveError('')

    try {
      const payload = {
        jobs: selectedJobs.map((item) => ({
          url: item.url,
          title: item.title || null,
          company: item.company || null,
          location: item.location || null,
          work_type: item.work_type || null,
          experience_level: item.experience_level || null,
          skills: item.skills || null,
          description: item.description || null,
          salary: item.salary || null,
          application_url: item.application_url || null,
          application_method: item.application_method || null,
        })),
      }

      const res = await api<{ saved_count: number; skipped_count: number }>(
        '/api/jobs/bulk-save',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      )

      setBulkSaveSuccess(`Successfully imported ${res.saved_count} jobs!`)
      setTimeout(() => {
        navigate('/jobs')
      }, 1200)
    } catch (err: any) {
      setBulkSaveError(err.message || 'Failed to save bulk jobs.')
    } finally {
      setBulkSaving(false)
    }
  }

  const selectedCount = bulkItems.filter((i) => i.selected && i.status === 'extracted').length

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: activeTab === 'bulk' && bulkItems.length > 0 ? 1100 : 780 }}>
        {/* Header */}
        <div className="d-flex justify-content-between align-items-center mb-3">
          <div>
            <h3 style={{ color: 'var(--color-dark)', fontWeight: 700 }}>
              ➕ Add Job Postings
            </h3>
            <p className="text-muted mb-0">
              Extract details automatically with AI and prepare them for one-click application.
            </p>
          </div>
        </div>

        {/* Tab Navigation */}
        <Nav
          variant="pills"
          className="mb-4 bg-light p-1 rounded-3"
          activeKey={activeTab}
          onSelect={(k) => setActiveTab(k as 'single' | 'bulk')}
        >
          <Nav.Item className="flex-fill text-center">
            <Nav.Link eventKey="single" className="fw-semibold">
              🔗 Single URL
            </Nav.Link>
          </Nav.Item>
          <Nav.Item className="flex-fill text-center">
            <Nav.Link eventKey="bulk" className="fw-semibold">
              📋 Bulk Import URLs
            </Nav.Link>
          </Nav.Item>
        </Nav>

        {/* ========================================================================= */}
        {/* TAB 1: SINGLE URL                                                         */}
        {/* ========================================================================= */}
        {activeTab === 'single' && (
          <>
            {!singleExtracted ? (
              <Card className="shadow-sm border-0 mb-4">
                <Card.Body className="p-4">
                  <Form onSubmit={handleSingleExtract}>
                    <Form.Group className="mb-3">
                      <Form.Label className="fw-semibold">Job URL</Form.Label>
                      <Form.Control
                        type="url"
                        placeholder="https://company.com/careers/job-title"
                        value={singleUrl}
                        onChange={(e) => setSingleUrl(e.target.value)}
                        disabled={singleExtracting}
                        required
                        size="lg"
                      />
                      <Form.Text className="text-muted">
                        Paste a link from LinkedIn, Indeed, Greenhouse, Lever, or company career sites.
                      </Form.Text>
                    </Form.Group>

                    {singleExtractError && <Alert variant="danger">{singleExtractError}</Alert>}

                    <Button
                      type="submit"
                      className="w-100"
                      style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                      disabled={singleExtracting || !singleUrl.trim()}
                      size="lg"
                    >
                      {singleExtracting ? (
                        <>
                          <Spinner animation="border" size="sm" className="me-2" />
                          Extracting job with AI... (this may take 10-20s)
                        </>
                      ) : (
                        '🔍 Extract Job Info'
                      )}
                    </Button>
                  </Form>
                </Card.Body>
              </Card>
            ) : (
              /* Review & Edit Single Extracted Job */
              <Card className="shadow-sm border-0">
                <Card.Body className="p-4">
                  {singleExtracted.extraction_warning ? (
                    <Alert variant="warning" className="d-flex align-items-start mb-3">
                      <span className="me-2">⚠️</span>
                      <span>{singleExtracted.extraction_warning}</span>
                    </Alert>
                  ) : (
                    <Alert variant="success" className="d-flex align-items-start mb-3">
                      <span className="me-2">✅</span>
                      <span>Job details extracted successfully using AI. Review and save below.</span>
                    </Alert>
                  )}

                  <h5 className="fw-semibold mb-3">Review Extracted Data</h5>
                  <Form onSubmit={handleSingleSave}>
                    <Row className="g-3">
                      <Col md={6}>
                        <Form.Group>
                          <Form.Label className="small fw-semibold">Job Title</Form.Label>
                          <Form.Control
                            value={singleForm.title}
                            onChange={(e) => setSingleForm((p) => ({ ...p, title: e.target.value }))}
                            placeholder="Software Engineer"
                          />
                        </Form.Group>
                      </Col>
                      <Col md={6}>
                        <Form.Group>
                          <Form.Label className="small fw-semibold">Company</Form.Label>
                          <Form.Control
                            value={singleForm.company}
                            onChange={(e) => setSingleForm((p) => ({ ...p, company: e.target.value }))}
                            placeholder="Acme Corp"
                          />
                        </Form.Group>
                      </Col>
                      <Col md={6}>
                        <Form.Group>
                          <Form.Label className="small fw-semibold">Location</Form.Label>
                          <Form.Control
                            value={singleForm.location}
                            onChange={(e) => setSingleForm((p) => ({ ...p, location: e.target.value }))}
                            placeholder="Remote / New York, NY"
                          />
                        </Form.Group>
                      </Col>
                      <Col md={6}>
                        <Form.Group>
                          <Form.Label className="small fw-semibold">Work Type</Form.Label>
                          <Form.Select
                            value={singleForm.work_type}
                            onChange={(e) => setSingleForm((p) => ({ ...p, work_type: e.target.value }))}
                          >
                            <option value="">— Select —</option>
                            <option value="remote">Remote</option>
                            <option value="hybrid">Hybrid</option>
                            <option value="onsite">On-site</option>
                          </Form.Select>
                        </Form.Group>
                      </Col>
                      <Col md={12}>
                        <Form.Group>
                          <Form.Label className="small fw-semibold">Skills</Form.Label>
                          <Form.Control
                            value={singleForm.skills}
                            onChange={(e) => setSingleForm((p) => ({ ...p, skills: e.target.value }))}
                            placeholder="Python, React, SQL (comma-separated)"
                          />
                        </Form.Group>
                      </Col>
                      <Col md={12}>
                        <Form.Group>
                          <Form.Label className="small fw-semibold">Description</Form.Label>
                          <Form.Control
                            as="textarea"
                            rows={5}
                            value={singleForm.description}
                            onChange={(e) => setSingleForm((p) => ({ ...p, description: e.target.value }))}
                            placeholder="Full job description..."
                          />
                        </Form.Group>
                      </Col>
                    </Row>

                    {singleSaveError && <Alert variant="danger" className="mt-3">{singleSaveError}</Alert>}

                    <div className="d-flex gap-2 mt-4">
                      <Button
                        type="submit"
                        style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                        disabled={singleSaving}
                        className="px-4"
                      >
                        {singleSaving ? (
                          <><Spinner animation="border" size="sm" className="me-2" />Saving...</>
                        ) : (
                          '💾 Save Job'
                        )}
                      </Button>
                      <Button
                        variant="outline-secondary"
                        onClick={() => { setSingleExtracted(null); setSingleUrl('') }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </Form>
                </Card.Body>
              </Card>
            )}
          </>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: BULK IMPORT URLS                                                   */}
        {/* ========================================================================= */}
        {activeTab === 'bulk' && (
          <>
            {bulkItems.length === 0 ? (
              <Card className="shadow-sm border-0 mb-4">
                <Card.Body className="p-4">
                  <Form onSubmit={handleBulkExtract}>
                    <div className="d-flex justify-content-between align-items-center mb-2">
                      <Form.Label className="fw-semibold mb-0">Job URLs List</Form.Label>
                      <Badge bg={parsedUrls.length > 0 ? 'primary' : 'secondary'} className="px-2 py-1">
                        {parsedUrls.length} Valid URL{parsedUrls.length === 1 ? '' : 's'} Detected
                      </Badge>
                    </div>

                    <Form.Control
                      as="textarea"
                      rows={8}
                      placeholder={`https://linkedin.com/jobs/view/12345678\nhttps://company.com/careers/software-engineer\nhttps://boards.greenhouse.io/corp/jobs/987654`}
                      value={bulkRawText}
                      onChange={(e) => setBulkRawText(e.target.value)}
                      disabled={bulkExtracting}
                      className="font-monospace mb-3"
                      style={{ fontSize: '13px', resize: 'vertical' }}
                    />

                    {/* File Upload Helper */}
                    <div className="d-flex align-items-center justify-content-between bg-light p-3 rounded mb-3">
                      <div>
                        <div className="fw-semibold small">Upload URLs file</div>
                        <div className="text-muted small">Import links from a .txt or .csv file</div>
                      </div>
                      <div>
                        <Form.Control
                          type="file"
                          accept=".txt,.csv"
                          onChange={handleFileUpload}
                          disabled={bulkExtracting}
                          size="sm"
                        />
                      </div>
                    </div>

                    {bulkExtractError && <Alert variant="danger">{bulkExtractError}</Alert>}

                    {bulkExtracting && (
                      <div className="mb-3">
                        <div className="d-flex justify-content-between small text-muted mb-1">
                          <span>Processing batch with AI workers...</span>
                          <span>Concurrent pool active</span>
                        </div>
                        <ProgressBar animated now={100} style={{ height: '8px' }} />
                      </div>
                    )}

                    <Button
                      type="submit"
                      className="w-100"
                      style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                      disabled={bulkExtracting || parsedUrls.length === 0}
                      size="lg"
                    >
                      {bulkExtracting ? (
                        <>
                          <Spinner animation="border" size="sm" className="me-2" />
                          Extracting {parsedUrls.length} Job{parsedUrls.length === 1 ? '' : 's'}...
                        </>
                      ) : (
                        `⚡ Extract All (${parsedUrls.length} URL${parsedUrls.length === 1 ? '' : 's'})`
                      )}
                    </Button>
                  </Form>
                </Card.Body>
              </Card>
            ) : (
              /* Bulk Review & Staging Table */
              <Card className="shadow-sm border-0">
                <Card.Body className="p-4">
                  {/* Summary Metric Badges */}
                  <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3 pb-3 border-bottom">
                    <div>
                      <h5 className="fw-bold mb-1">Review Extracted Jobs</h5>
                      <span className="text-muted small">
                        Select the jobs you want to import into your saved jobs library.
                      </span>
                    </div>
                    <div className="d-flex gap-2">
                      <Badge bg="success" className="p-2">
                        {bulkItems.filter((i) => i.status === 'extracted').length} Extracted
                      </Badge>
                      <Badge bg="warning" text="dark" className="p-2">
                        {bulkItems.filter((i) => i.status === 'duplicate').length} Duplicates
                      </Badge>
                      {bulkItems.filter((i) => i.status === 'failed').length > 0 && (
                        <Badge bg="danger" className="p-2">
                          {bulkItems.filter((i) => i.status === 'failed').length} Failed
                        </Badge>
                      )}
                    </div>
                  </div>

                  {bulkSaveError && <Alert variant="danger">{bulkSaveError}</Alert>}
                  {bulkSaveSuccess && <Alert variant="success">{bulkSaveSuccess}</Alert>}

                  {/* Staging Table */}
                  <div className="table-responsive mb-4">
                    <Table hover className="border align-middle">
                      <thead className="table-light">
                        <tr>
                          <th style={{ width: '40px' }} className="text-center">
                            <Form.Check
                              type="checkbox"
                              checked={
                                bulkItems.filter((i) => i.status === 'extracted').length > 0 &&
                                bulkItems
                                  .filter((i) => i.status === 'extracted')
                                  .every((i) => i.selected)
                              }
                              onChange={toggleSelectAll}
                            />
                          </th>
                          <th style={{ width: '110px' }}>Status</th>
                          <th style={{ minWidth: '220px' }}>Job Title</th>
                          <th style={{ minWidth: '180px' }}>Company</th>
                          <th style={{ minWidth: '140px' }}>Location</th>
                          <th>Source Link</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bulkItems.map((item) => (
                          <tr
                            key={item.id}
                            className={item.status === 'duplicate' ? 'table-light text-muted' : ''}
                          >
                            <td className="text-center">
                              <Form.Check
                                type="checkbox"
                                checked={item.selected}
                                disabled={item.status !== 'extracted'}
                                onChange={() => toggleSelect(item.id)}
                              />
                            </td>
                            <td>
                              {item.status === 'extracted' && (
                                <Badge bg="success">Ready</Badge>
                              )}
                              {item.status === 'duplicate' && (
                                <Badge bg="warning" text="dark">Duplicate</Badge>
                              )}
                              {item.status === 'failed' && (
                                <Badge bg="danger">Failed</Badge>
                              )}
                            </td>
                            <td>
                              {item.status === 'extracted' ? (
                                <Form.Control
                                  size="sm"
                                  value={item.title}
                                  placeholder="Untitled Position"
                                  onChange={(e) =>
                                    updateStagingField(item.id, 'title', e.target.value)
                                  }
                                />
                              ) : (
                                <span className="small text-muted">{item.error || 'N/A'}</span>
                              )}
                            </td>
                            <td>
                              {item.status === 'extracted' ? (
                                <Form.Control
                                  size="sm"
                                  value={item.company}
                                  placeholder="Company Name"
                                  onChange={(e) =>
                                    updateStagingField(item.id, 'company', e.target.value)
                                  }
                                />
                              ) : (
                                <span className="small text-muted">—</span>
                              )}
                            </td>
                            <td>
                              {item.status === 'extracted' ? (
                                <Form.Control
                                  size="sm"
                                  value={item.location}
                                  placeholder="Location"
                                  onChange={(e) =>
                                    updateStagingField(item.id, 'location', e.target.value)
                                  }
                                />
                              ) : (
                                <span className="small text-muted">—</span>
                              )}
                            </td>
                            <td>
                              <a
                                href={item.url}
                                target="_blank"
                                rel="noreferrer"
                                className="small text-truncate d-inline-block"
                                style={{ maxWidth: '180px' }}
                                title={item.url}
                              >
                                {item.url}
                              </a>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </div>

                  {/* Actions */}
                  <div className="d-flex justify-content-between align-items-center">
                    <Button
                      variant="outline-secondary"
                      onClick={() => {
                        setBulkItems([])
                        setBulkRawText('')
                      }}
                      disabled={bulkSaving}
                    >
                      ↺ Clear & Re-import
                    </Button>
                    <Button
                      style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                      disabled={bulkSaving || selectedCount === 0}
                      onClick={handleBulkSave}
                      className="px-4"
                    >
                      {bulkSaving ? (
                        <>
                          <Spinner animation="border" size="sm" className="me-2" />
                          Saving...
                        </>
                      ) : (
                        `💾 Save Selected Jobs (${selectedCount})`
                      )}
                    </Button>
                  </div>
                </Card.Body>
              </Card>
            )}
          </>
        )}
      </Container>
    </>
  )
}
