import { useState, useEffect, useCallback } from 'react'
import { Container, Card, Table, Button, Form, InputGroup, Badge, Modal, Pagination, Row, Col, Spinner } from 'react-bootstrap'
import { Link, useNavigate } from 'react-router-dom'
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

interface JobListResponse {
  items: Job[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

const WORK_TYPE_LABELS: Record<string, string> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'On-site',
}

const WORK_TYPE_COLORS: Record<string, string> = {
  remote: 'success',
  hybrid: 'warning',
  onsite: 'info',
}

const EXP_LABELS: Record<string, string> = {
  entry: 'Entry',
  mid: 'Mid',
  senior: 'Senior',
  lead: 'Lead',
  executive: 'Executive',
}

export default function Jobs() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Filters
  const [search, setSearch] = useState('')
  const [workType, setWorkType] = useState('')
  const [experienceLevel, setExperienceLevel] = useState('')
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState('created_at')
  const [sortOrder, setSortOrder] = useState('desc')

  // Delete modal
  const [deleteTarget, setDeleteTarget] = useState<Job | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Batch selection for applications
  const [selectedJobIds, setSelectedJobIds] = useState<number[]>([])

  const toggleSelectJob = (id: number) => {
    setSelectedJobIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const toggleSelectAll = () => {
    if (selectedJobIds.length === jobs.length) {
      setSelectedJobIds([])
    } else {
      setSelectedJobIds(jobs.map((j) => j.id))
    }
  }

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (search.trim()) params.set('q', search.trim())
      if (workType) params.set('work_type', workType)
      if (experienceLevel) params.set('experience_level', experienceLevel)
      params.set('sort_by', sortBy)
      params.set('sort_order', sortOrder)
      params.set('page', String(page))
      params.set('page_size', '20')

      const data = await api<JobListResponse>(`/api/jobs?${params.toString()}`)
      setJobs(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch (err: any) {
      setError(err.message || 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [search, workType, experienceLevel, sortBy, sortOrder, page])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchJobs()
  }

  const clearFilters = () => {
    setSearch('')
    setWorkType('')
    setExperienceLevel('')
    setSortBy('created_at')
    setSortOrder('desc')
    setPage(1)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api(`/api/jobs/${deleteTarget.id}`, { method: 'DELETE' })
      setDeleteTarget(null)
      fetchJobs()
    } catch (err: any) {
      setError(err.message || 'Failed to delete job')
    } finally {
      setDeleting(false)
    }
  }

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    })
  }

  const renderPagination = () => {
    if (totalPages <= 1) return null
    const items = []
    const maxVisible = 5
    let start = Math.max(1, page - Math.floor(maxVisible / 2))
    const end = Math.min(totalPages, start + maxVisible - 1)
    if (end - start + 1 < maxVisible) start = Math.max(1, end - maxVisible + 1)

    items.push(
      <Pagination.Prev key="prev" disabled={page === 1} onClick={() => setPage(page - 1)} />
    )
    for (let i = start; i <= end; i++) {
      items.push(
        <Pagination.Item key={i} active={i === page} onClick={() => setPage(i)}>{i}</Pagination.Item>
      )
    }
    items.push(
      <Pagination.Next key="next" disabled={page === totalPages} onClick={() => setPage(page + 1)} />
    )
    return <Pagination className="justify-content-center mb-0">{items}</Pagination>
  }

  return (
    <>
      <Navbar />
      <Container className="py-4">
        {/* Header */}
        <div className="d-flex justify-content-between align-items-center mb-4">
          <div>
            <h3 className="mb-1" style={{ color: 'var(--color-dark)', fontWeight: 700 }}>
              💼 Jobs
            </h3>
            <p className="text-muted mb-0 small">Manage your saved job listings</p>
          </div>
          <div className="d-flex gap-2">
            {selectedJobIds.length > 0 && (
              <Button
                variant="success"
                onClick={() => navigate(`/apply?job_ids=${selectedJobIds.join(',')}`)}
                className="fw-semibold shadow-sm"
              >
                Apply Selected ({selectedJobIds.length}) ✨
              </Button>
            )}
            <Link to="/jobs/add">
              <Button style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}>
                + Add Job
              </Button>
            </Link>
          </div>
        </div>

        {/* Search & Filters */}
        <Card className="shadow-sm border-0 mb-4">
          <Card.Body>
            <Form onSubmit={handleSearch}>
              <InputGroup className="mb-3">
                <Form.Control
                  placeholder="Search by title, company, or description..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <Button type="submit" variant="outline-secondary">🔍 Search</Button>
              </InputGroup>
            </Form>
            <Row className="g-2 align-items-end">
              <Col md={3}>
                <Form.Label className="small text-muted mb-1">Work Type</Form.Label>
                <Form.Select size="sm" value={workType} onChange={(e) => { setWorkType(e.target.value); setPage(1) }}>
                  <option value="">All</option>
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="onsite">On-site</option>
                </Form.Select>
              </Col>
              <Col md={3}>
                <Form.Label className="small text-muted mb-1">Experience Level</Form.Label>
                <Form.Select size="sm" value={experienceLevel} onChange={(e) => { setExperienceLevel(e.target.value); setPage(1) }}>
                  <option value="">All</option>
                  <option value="entry">Entry</option>
                  <option value="mid">Mid</option>
                  <option value="senior">Senior</option>
                  <option value="lead">Lead</option>
                  <option value="executive">Executive</option>
                </Form.Select>
              </Col>
              <Col md={3}>
                <Form.Label className="small text-muted mb-1">Sort By</Form.Label>
                <Form.Select size="sm" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                  <option value="created_at">Date Added</option>
                  <option value="title">Title</option>
                  <option value="company">Company</option>
                </Form.Select>
              </Col>
              <Col md={2}>
                <Form.Label className="small text-muted mb-1">Order</Form.Label>
                <Form.Select size="sm" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)}>
                  <option value="desc">Newest</option>
                  <option value="asc">Oldest</option>
                </Form.Select>
              </Col>
              <Col md={1} className="text-end">
                <Button variant="link" size="sm" onClick={clearFilters} className="text-muted p-0">
                  Clear
                </Button>
              </Col>
            </Row>
          </Card.Body>
        </Card>

        {/* Error */}
        {error && (
          <div className="alert alert-danger">{error}</div>
        )}

        {/* Jobs Table */}
        <Card className="shadow-sm border-0">
          <Card.Body className="p-0">
            {loading ? (
              <div className="text-center py-5">
                <Spinner animation="border" style={{ color: 'var(--color-primary)' }} />
                <p className="text-muted mt-2 mb-0">Loading jobs...</p>
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-5">
                <div style={{ fontSize: 48, opacity: 0.3 }}>💼</div>
                <h5 className="text-muted mt-2">No jobs yet</h5>
                <p className="text-muted mb-3">Click "Add Job" to get started.</p>
                <Link to="/jobs/add">
                  <Button size="sm" style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}>
                    + Add Your First Job
                  </Button>
                </Link>
              </div>
            ) : (
              <>
                <Table hover responsive className="mb-0 align-middle" style={{ fontSize: 14 }}>
                  <thead style={{ backgroundColor: '#f8fafc' }}>
                    <tr>
                      <th style={{ width: 40 }}>
                        <Form.Check
                          type="checkbox"
                          checked={jobs.length > 0 && selectedJobIds.length === jobs.length}
                          onChange={toggleSelectAll}
                        />
                      </th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Title</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Company</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Location</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Work Type</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Status</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Date Added</th>
                      <th style={{ fontWeight: 600, color: 'var(--color-dark)' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => (
                      <tr key={job.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/jobs/${job.id}`)}>
                        <td onClick={(e) => e.stopPropagation()}>
                          <Form.Check
                            type="checkbox"
                            checked={selectedJobIds.includes(job.id)}
                            onChange={() => toggleSelectJob(job.id)}
                          />
                        </td>
                        <td className="fw-semibold" style={{ color: 'var(--color-primary)' }}>
                          {job.title || '(Untitled)'}
                        </td>
                        <td>{job.company || '—'}</td>
                        <td>{job.location || '—'}</td>
                        <td>
                          <div className="d-flex flex-column gap-1 align-items-start">
                            {job.work_type ? (
                              <Badge bg={WORK_TYPE_COLORS[job.work_type] || 'secondary'} className="fw-normal">
                                {WORK_TYPE_LABELS[job.work_type] || job.work_type}
                              </Badge>
                            ) : null}
                            {job.experience_level ? (
                              <Badge bg="light" text="dark" className="border fw-normal" style={{ fontSize: 11 }}>
                                {EXP_LABELS[job.experience_level] || job.experience_level}
                              </Badge>
                            ) : null}
                            {!job.work_type && !job.experience_level && '—'}
                          </div>
                        </td>
                        <td>
                          <Badge
                            bg={job.status === 'ready' ? 'primary' : 'success'}
                            className="fw-normal"
                            style={{ opacity: 0.85 }}
                          >
                            {job.status === 'ready' ? 'Ready' : 'Applied'}
                          </Badge>
                        </td>
                        <td className="text-muted">{formatDate(job.created_at)}</td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="outline-success"
                            size="sm"
                            className="me-1"
                            onClick={() => navigate(`/apply?job_id=${job.id}`)}
                          >
                            Apply
                          </Button>
                          <Button
                            variant="outline-primary"
                            size="sm"
                            className="me-1"
                            onClick={() => navigate(`/jobs/${job.id}`)}
                          >
                            View
                          </Button>
                          <Button
                            variant="outline-danger"
                            size="sm"
                            onClick={() => setDeleteTarget(job)}
                          >
                            🗑
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>

                {/* Footer: count + pagination */}
                <div className="d-flex justify-content-between align-items-center px-3 py-3 border-top">
                  <small className="text-muted">
                    Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total} jobs
                  </small>
                  {renderPagination()}
                </div>
              </>
            )}
          </Card.Body>
        </Card>

        {/* Delete Confirmation Modal */}
        <Modal show={!!deleteTarget} onHide={() => setDeleteTarget(null)} centered>
          <Modal.Header closeButton>
            <Modal.Title style={{ fontSize: 18 }}>Delete Job</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            Are you sure you want to delete <strong>{deleteTarget?.title || 'this job'}</strong>
            {deleteTarget?.company && <> at <strong>{deleteTarget.company}</strong></>}?
            This action cannot be undone.
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Spinner animation="border" size="sm" /> : 'Delete'}
            </Button>
          </Modal.Footer>
        </Modal>
      </Container>
    </>
  )
}
