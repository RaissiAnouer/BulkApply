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
  Modal,
} from 'react-bootstrap'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import Navbar from '../components/Navbar'

export interface CompanyContactData {
  full_name: string
  job_title: string
  category: 'hiring' | 'leadership' | 'other'
  department?: string | null
  linkedin_url?: string | null
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  evidence?: string | null
  is_relevant?: boolean
}

export interface CompanyIntelligenceData {
  company_name: string
  website?: string | null
  linkedin_url?: string | null
  industry?: string | null
  description?: string | null
  headquarters?: string | null
  company_size?: string | null
  technologies?: string | null
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'
  contacts: CompanyContactData[]
}

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
  company_intelligence?: CompanyIntelligenceData | null
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
  company_intelligence?: CompanyIntelligenceData | null
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
  const [selectedBulkIntel, setSelectedBulkIntel] = useState<CompanyIntelligenceData | null>(null)

  // --- On-demand Company Employee Scanning State ---
  const [singleScanningEmployees, setSingleScanningEmployees] = useState(false)
  const [singleScanError, setSingleScanError] = useState('')
  const [scanningItemIds, setScanningItemIds] = useState<Set<string>>(new Set())
  const [bulkScanningSelected, setBulkScanningSelected] = useState(false)

  // Handle on-demand employee scanning for single job review
  const handleScanSingleEmployees = async () => {
    const comp = singleForm.company || singleExtracted?.company
    if (!comp && !singleUrl) return

    setSingleScanningEmployees(true)
    setSingleScanError('')

    try {
      const data = await api<CompanyIntelligenceData | null>('/api/jobs/scan-company', {
        method: 'POST',
        body: JSON.stringify({
          company_name: comp || null,
          title: singleForm.title || singleExtracted?.title || null,
          location: singleForm.location || singleExtracted?.location || null,
          url: singleExtracted?.url || singleUrl.trim() || null,
          skills: singleForm.skills || singleExtracted?.skills || null,
        }),
      })

      if (singleExtracted) {
        setSingleExtracted({
          ...singleExtracted,
          company_intelligence: data,
        })
      }
    } catch (err: any) {
      setSingleScanError(err.message || 'Failed to scan for company employees.')
    } finally {
      setSingleScanningEmployees(false)
    }
  }

  // Handle on-demand employee scanning for a single row in bulk staging
  const handleScanBulkItemEmployees = async (item: BulkStagingItem) => {
    const comp = item.company
    if (!comp && !item.url) return

    setScanningItemIds((prev) => new Set(prev).add(item.id))

    try {
      const data = await api<CompanyIntelligenceData | null>('/api/jobs/scan-company', {
        method: 'POST',
        body: JSON.stringify({
          company_name: comp || null,
          title: item.title || null,
          location: item.location || null,
          url: item.url || null,
          skills: item.skills || null,
        }),
      })

      setBulkItems((prev) =>
        prev.map((it) => (it.id === item.id ? { ...it, company_intelligence: data } : it))
      )
    } catch (err: any) {
      console.error('Scan failed for item', item.id, err)
    } finally {
      setScanningItemIds((prev) => {
        const next = new Set(prev)
        next.delete(item.id)
        return next
      })
    }
  }

  // Handle batch scanning of employees for selected bulk jobs
  const handleScanSelectedBulkEmployees = async () => {
    const targets = bulkItems.filter(
      (i) => i.selected && i.status === 'extracted' && !i.company_intelligence
    )
    if (targets.length === 0) return

    setBulkScanningSelected(true)
    try {
      for (const item of targets) {
        setScanningItemIds((prev) => new Set(prev).add(item.id))
        try {
          const data = await api<CompanyIntelligenceData | null>('/api/jobs/scan-company', {
            method: 'POST',
            body: JSON.stringify({
              company_name: item.company || null,
              title: item.title || null,
              location: item.location || null,
              url: item.url || null,
              skills: item.skills || null,
            }),
          })
          setBulkItems((prev) =>
            prev.map((it) => (it.id === item.id ? { ...it, company_intelligence: data } : it))
          )
        } catch (e) {
          console.error('Scan error for item', item.id, e)
        } finally {
          setScanningItemIds((prev) => {
            const next = new Set(prev)
            next.delete(item.id)
            return next
          })
        }
      }
    } finally {
      setBulkScanningSelected(false)
    }
  }

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
          company_intelligence: singleExtracted?.company_intelligence || null,
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
        company_intelligence: item.data?.company_intelligence || null,
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
          company_intelligence: item.company_intelligence || null,
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

                    {/* On-Demand Company & Employee Worker Scan */}
                    <div className="mt-4 p-3 rounded border bg-light d-flex flex-column gap-2">
                      <div className="d-flex justify-content-between align-items-center flex-wrap gap-2">
                        <div>
                          <div className="fw-semibold small d-flex align-items-center gap-2">
                            <span>🏢 Company & Employee Intelligence</span>
                            {singleExtracted?.company_intelligence && (
                              <Badge bg="success" style={{ fontSize: 10 }}>Scanned</Badge>
                            )}
                          </div>
                          <div className="text-muted" style={{ fontSize: 12 }}>
                            {singleExtracted?.company_intelligence
                              ? `Identified ${singleExtracted.company_intelligence.contacts?.length || 0} employees & recruiters with public LinkedIn profiles.`
                              : `Trigger worker to discover company details, key recruiters, and hiring managers.`}
                          </div>
                        </div>

                        <Button
                          type="button"
                          variant={singleExtracted?.company_intelligence ? "outline-primary" : "primary"}
                          size="sm"
                          disabled={singleScanningEmployees || (!singleForm.company && !singleExtracted?.company)}
                          onClick={handleScanSingleEmployees}
                          style={{
                            backgroundColor: singleExtracted?.company_intelligence ? undefined : 'var(--color-primary)',
                            borderColor: 'var(--color-primary)',
                          }}
                        >
                          {singleScanningEmployees ? (
                            <>
                              <Spinner animation="border" size="sm" className="me-2" />
                              Scanning Employees...
                            </>
                          ) : singleExtracted?.company_intelligence ? (
                            '🔄 Re-scan for Employees'
                          ) : (
                            '🔍 Scan for Employees'
                          )}
                        </Button>
                      </div>

                      {singleScanError && (
                        <Alert variant="danger" className="py-1 px-2 mb-0 small mt-1">
                          {singleScanError}
                        </Alert>
                      )}
                    </div>

                    {/* Inline Company & Contacts Intelligence Preview */}
                    {singleExtracted?.company_intelligence && (
                      <div className="mt-4 p-3 rounded border bg-light">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                          <div className="d-flex align-items-center gap-2">
                            <span className="fs-5">🏢</span>
                            <span className="fw-bold fs-6">
                              {singleExtracted.company_intelligence.company_name}
                            </span>
                            <Badge
                              bg={
                                singleExtracted.company_intelligence.confidence === 'HIGH'
                                  ? 'success'
                                  : 'secondary'
                              }
                              style={{ fontSize: 10 }}
                            >
                              {singleExtracted.company_intelligence.confidence} Confidence
                            </Badge>
                          </div>
                          <div className="d-flex gap-2">
                            {singleExtracted.company_intelligence.website && (
                              <a
                                href={singleExtracted.company_intelligence.website}
                                target="_blank"
                                rel="noreferrer"
                                className="btn btn-sm btn-outline-primary py-0 px-2"
                                style={{ fontSize: 12 }}
                              >
                                🌐 Website
                              </a>
                            )}
                            {singleExtracted.company_intelligence.linkedin_url && (
                              <a
                                href={singleExtracted.company_intelligence.linkedin_url}
                                target="_blank"
                                rel="noreferrer"
                                className="btn btn-sm btn-outline-primary py-0 px-2"
                                style={{ fontSize: 12 }}
                              >
                                💼 LinkedIn
                              </a>
                            )}
                          </div>
                        </div>

                        <div className="d-flex flex-wrap gap-3 small text-muted mb-2">
                          {singleExtracted.company_intelligence.industry && (
                            <div><strong>Industry:</strong> {singleExtracted.company_intelligence.industry}</div>
                          )}
                          {singleExtracted.company_intelligence.headquarters && (
                            <div><strong>HQ:</strong> {singleExtracted.company_intelligence.headquarters}</div>
                          )}
                          {singleExtracted.company_intelligence.company_size && (
                            <div><strong>Size:</strong> {singleExtracted.company_intelligence.company_size}</div>
                          )}
                        </div>

                        {singleExtracted.company_intelligence.description && (
                          <div className="small text-secondary mb-3">
                            {singleExtracted.company_intelligence.description}
                          </div>
                        )}

                        <div className="mt-3">
                          <div className="d-flex justify-content-between align-items-center mb-2">
                            <span className="fw-semibold small">
                              Discovered Employees ({singleExtracted.company_intelligence.contacts?.length || 0})
                            </span>
                            <span className="text-muted" style={{ fontSize: 11 }}>
                              Public professional research for outreach preparation
                            </span>
                          </div>

                          {(!singleExtracted.company_intelligence.contacts ||
                            singleExtracted.company_intelligence.contacts.length === 0) ? (
                            <div className="text-muted small py-2">
                              No public employee profiles identified during extraction.
                            </div>
                          ) : (
                            <div className="d-flex flex-column gap-2">
                              {singleExtracted.company_intelligence.contacts.map((contact, idx) => (
                                <Card key={idx} className="border bg-white p-2" style={{ borderRadius: 6 }}>
                                  <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                      <div className="d-flex align-items-center gap-2 mb-1">
                                        <span className="fw-semibold small">{contact.full_name}</span>
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
                                            ? 'Hiring'
                                            : contact.category === 'leadership'
                                            ? 'Leadership'
                                            : 'Team'}
                                        </Badge>
                                      </div>
                                      <div className="text-muted" style={{ fontSize: 12 }}>
                                        {contact.job_title}
                                        {contact.department && ` • ${contact.department}`}
                                      </div>
                                      {contact.evidence && (
                                        <div className="text-secondary fst-italic" style={{ fontSize: 11 }}>
                                          💡 {contact.evidence}
                                        </div>
                                      )}
                                    </div>
                                    <div>
                                      {contact.linkedin_url ? (
                                        <a
                                          href={contact.linkedin_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="btn btn-sm btn-outline-primary py-0 px-2"
                                          style={{ fontSize: 12 }}
                                        >
                                          🔗 LinkedIn
                                        </a>
                                      ) : (
                                        <Badge bg="light" text="muted" className="border">
                                          No public link
                                        </Badge>
                                      )}
                                    </div>
                                  </div>
                                </Card>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

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
                    <div className="d-flex align-items-center gap-2 flex-wrap">
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
                      <Button
                        variant="outline-primary"
                        size="sm"
                        className="ms-1"
                        disabled={
                          bulkScanningSelected ||
                          bulkItems.filter((i) => i.selected && i.status === 'extracted' && !i.company_intelligence).length === 0
                        }
                        onClick={handleScanSelectedBulkEmployees}
                      >
                        {bulkScanningSelected ? (
                          <>
                            <Spinner animation="border" size="sm" className="me-1" />
                            Scanning Employees...
                          </>
                        ) : (
                          '👥 Scan Employees for Selected'
                        )}
                      </Button>
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
                          <th style={{ minWidth: '150px' }}>Company & Contacts</th>
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
                              {item.company_intelligence ? (
                                <Button
                                  variant="outline-primary"
                                  size="sm"
                                  className="py-0 px-2 text-start"
                                  style={{ fontSize: 11 }}
                                  onClick={() => setSelectedBulkIntel(item.company_intelligence!)}
                                  title="View discovered company details and employees"
                                >
                                  🏢 {item.company_intelligence.contacts?.length || 0} Contacts
                                </Button>
                              ) : item.status === 'extracted' ? (
                                <Button
                                  variant="outline-secondary"
                                  size="sm"
                                  className="py-0 px-2 text-start"
                                  style={{ fontSize: 11 }}
                                  disabled={scanningItemIds.has(item.id) || (!item.company && !item.url)}
                                  onClick={() => handleScanBulkItemEmployees(item)}
                                  title="Scan for company information and key employees"
                                >
                                  {scanningItemIds.has(item.id) ? (
                                    <>
                                      <Spinner
                                        animation="border"
                                        size="sm"
                                        className="me-1"
                                        style={{ width: '10px', height: '10px' }}
                                      />
                                      Scanning...
                                    </>
                                  ) : (
                                    '🔍 Scan Employees'
                                  )}
                                </Button>
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

        {/* Bulk Intelligence Modal Preview */}
        <Modal
          show={!!selectedBulkIntel}
          onHide={() => setSelectedBulkIntel(null)}
          size="lg"
          centered
        >
          <Modal.Header closeButton>
            <Modal.Title className="fs-6 fw-bold">
              🏢 {selectedBulkIntel?.company_name} — Intelligence Preview
            </Modal.Title>
          </Modal.Header>
          <Modal.Body className="p-3">
            {selectedBulkIntel && (
              <div>
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div>
                    <Badge
                      bg={selectedBulkIntel.confidence === 'HIGH' ? 'success' : 'secondary'}
                      className="me-2"
                    >
                      {selectedBulkIntel.confidence} Confidence
                    </Badge>
                    {selectedBulkIntel.industry && (
                      <span className="text-muted small me-2">• {selectedBulkIntel.industry}</span>
                    )}
                    {selectedBulkIntel.headquarters && (
                      <span className="text-muted small">• {selectedBulkIntel.headquarters}</span>
                    )}
                  </div>
                  <div className="d-flex gap-2">
                    {selectedBulkIntel.website && (
                      <a
                        href={selectedBulkIntel.website}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-sm btn-outline-primary py-0 px-2"
                        style={{ fontSize: 12 }}
                      >
                        🌐 Website
                      </a>
                    )}
                    {selectedBulkIntel.linkedin_url && (
                      <a
                        href={selectedBulkIntel.linkedin_url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-sm btn-outline-primary py-0 px-2"
                        style={{ fontSize: 12 }}
                      >
                        💼 LinkedIn
                      </a>
                    )}
                  </div>
                </div>

                {selectedBulkIntel.description && (
                  <p className="small text-secondary mb-3">{selectedBulkIntel.description}</p>
                )}

                <h6 className="fw-semibold small mb-2">
                  Discovered Public Contacts ({selectedBulkIntel.contacts?.length || 0})
                </h6>

                {(!selectedBulkIntel.contacts || selectedBulkIntel.contacts.length === 0) ? (
                  <div className="text-muted small py-3 text-center bg-light rounded">
                    No public contacts identified for this company during extraction.
                  </div>
                ) : (
                  <div className="d-flex flex-column gap-2">
                    {selectedBulkIntel.contacts.map((contact, idx) => (
                      <Card key={idx} className="border bg-light p-2" style={{ borderRadius: 6 }}>
                        <div className="d-flex justify-content-between align-items-start">
                          <div>
                            <div className="d-flex align-items-center gap-2 mb-1">
                              <span className="fw-semibold small">{contact.full_name}</span>
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
                                  ? 'Hiring'
                                  : contact.category === 'leadership'
                                  ? 'Leadership'
                                  : 'Team'}
                              </Badge>
                            </div>
                            <div className="text-muted" style={{ fontSize: 12 }}>
                              {contact.job_title}
                              {contact.department && ` • ${contact.department}`}
                            </div>
                            {contact.evidence && (
                              <div className="text-secondary fst-italic" style={{ fontSize: 11 }}>
                                💡 {contact.evidence}
                              </div>
                            )}
                          </div>
                          <div>
                            {contact.linkedin_url ? (
                              <a
                                href={contact.linkedin_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn btn-sm btn-outline-primary py-0 px-2"
                                style={{ fontSize: 12 }}
                              >
                                🔗 LinkedIn
                              </a>
                            ) : (
                              <Badge bg="light" text="muted" className="border">
                                No public link
                              </Badge>
                            )}
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" size="sm" onClick={() => setSelectedBulkIntel(null)}>
              Close
            </Button>
          </Modal.Footer>
        </Modal>
      </Container>
    </>
  )
}
