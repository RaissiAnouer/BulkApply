import { useState, useEffect } from 'react'
import { Container, Card, Button, Badge, Spinner, Alert, ListGroup } from 'react-bootstrap'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { api, ApiException } from '../api/client'
import Navbar from '../components/Navbar'

interface JobDetail {
  id: number
  title: string | null
  company: string | null
  location: string | null
  work_type: string | null
  url: string
}

interface DailyQuotaResponse {
  limit: number
  used_today: number
  remaining: number
}

interface ApplicationCreateResponse {
  message: string
  application_ids: number[]
  count: number
}

export default function Apply() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const [jobIds, setJobIds] = useState<number[]>([])
  const [jobs, setJobs] = useState<JobDetail[]>([])
  const [quota, setQuota] = useState<DailyQuotaResponse | null>(null)
  const [hasCV, setHasCV] = useState<boolean | null>(null)

  const [loading, setLoading] = useState(true)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    // Parse job_ids from query params (supports ?job_id=1 or ?job_ids=1,2,3)
    const singleId = searchParams.get('job_id')
    const multiIds = searchParams.get('job_ids')

    let ids: number[] = []
    if (multiIds) {
      ids = multiIds
        .split(',')
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !isNaN(n))
    } else if (singleId) {
      const parsed = parseInt(singleId, 10)
      if (!isNaN(parsed)) ids = [parsed]
    }

    setJobIds(ids)
  }, [searchParams])

  useEffect(() => {
    const initApplyData = async () => {
      setLoading(true)
      setError('')

      try {
        // 1. Fetch CV status to verify prerequisite
        try {
          const cvData = await api<any>('/api/cv')
          setHasCV(!!cvData && !!cvData.parsed_data)
        } catch {
          setHasCV(false)
        }

        // 2. Fetch daily quota
        try {
          const quotaData = await api<DailyQuotaResponse>('/api/applications/quota')
          setQuota(quotaData)
        } catch {
          // non-blocking
        }

        // 3. Fetch details for each job in the apply batch
        if (jobIds.length > 0) {
          const loadedJobs: JobDetail[] = []
          for (const jid of jobIds) {
            try {
              const j = await api<JobDetail>(`/api/jobs/${jid}`)
              loadedJobs.push(j)
            } catch {
              // skip unowned / not found
            }
          }
          setJobs(loadedJobs)
        }
      } catch (err) {
        if (err instanceof ApiException) {
          setError(err.message)
        } else {
          setError('Failed to prepare application details.')
        }
      } finally {
        setLoading(false)
      }
    }

    if (jobIds.length > 0) {
      initApplyData()
    } else {
      setLoading(false)
    }
  }, [jobIds])

  const handleConfirmApply = async () => {
    if (jobs.length === 0) return
    setApplying(true)
    setError('')

    try {
      const idsToApply = jobs.map((j) => j.id)
      const res = await api<ApplicationCreateResponse>('/api/applications', {
        method: 'POST',
        body: JSON.stringify({ job_ids: idsToApply }),
      })

      // If single application, redirect to its detail view; if batch, to list
      if (res.application_ids.length === 1) {
        navigate(`/applications/${res.application_ids[0]}`)
      } else {
        navigate('/applications')
      }
    } catch (err) {
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError(err instanceof Error ? err.message : 'Application submission failed.')
      }
    } finally {
      setApplying(false)
    }
  }

  if (loading) {
    return (
      <>
        <Navbar />
        <Container className="py-5 text-center">
          <Spinner animation="border" style={{ color: 'var(--color-primary)' }} />
          <p className="text-muted mt-2">Preparing application details...</p>
        </Container>
      </>
    )
  }

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 760 }}>
        <div className="mb-3">
          <Link to="/jobs" className="text-decoration-none small text-muted">
            &larr; Back to Saved Jobs
          </Link>
        </div>

        <h2 className="mb-1" style={{ color: 'var(--color-dark)', fontWeight: 700 }}>
          Confirm Application{jobs.length > 1 ? 's' : ''}
        </h2>
        <p className="text-muted mb-4">
          Review your selected job opportunities before generating your tailored cover letter.
        </p>

        {error && (
          <Alert variant="danger" dismissible onClose={() => setError('')} className="mb-4">
            {error}
          </Alert>
        )}

        {/* Optional CV Notice */}
        {hasCV === false && (
          <Alert variant="info" className="mb-4">
            <h5 className="alert-heading">💡 Tip: Upload Your CV for Better Results</h5>
            <p className="mb-2">
              You can apply without a CV, but uploading one allows our AI to craft a more personalized cover letter tailored to your skills and experience.
            </p>
            <Link to="/cv" className="btn btn-outline-primary btn-sm">
              Upload CV &rarr;
            </Link>
          </Alert>
        )}

        {/* Quota Exceeded Warning */}
        {quota && quota.remaining < jobs.length && (
          <Alert variant="danger" className="mb-4">
            <h5 className="alert-heading">Daily Quota Exceeded</h5>
            <p className="mb-0">
              You have requested <strong>{jobs.length}</strong> applications, but only <strong>{quota.remaining}</strong> remain in your daily allowance today ({quota.used_today} / {quota.limit} used). Please adjust your selection or try again tomorrow.
            </p>
          </Alert>
        )}

        {jobs.length === 0 ? (
          <Card className="shadow-sm border-0 text-center py-5">
            <div style={{ fontSize: 42, opacity: 0.3 }}>💼</div>
            <h5 className="text-muted mt-2">No jobs selected</h5>
            <p className="text-muted mb-3">Please select one or more jobs from your saved jobs list.</p>
            <div>
              <Link to="/jobs">
                <Button style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}>
                  Go to Jobs List
                </Button>
              </Link>
            </div>
          </Card>
        ) : (
          <>
            {/* Selected Jobs Summary */}
            <Card className="shadow-sm border-0 mb-4 rounded-3">
              <Card.Header className="bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
                <span className="fw-bold" style={{ color: 'var(--color-dark)' }}>
                  Selected Positions ({jobs.length})
                </span>
                {quota && (
                  <span className="text-muted small">
                    Remaining Quota Today: <strong>{quota.remaining}</strong>
                  </span>
                )}
              </Card.Header>
              <ListGroup variant="flush">
                {jobs.map((job) => (
                  <ListGroup.Item key={job.id} className="py-3 px-4">
                    <div className="d-flex justify-content-between align-items-start">
                      <div>
                        <h6 className="mb-1 fw-bold" style={{ color: 'var(--color-primary)' }}>
                          {job.title || '(Untitled Role)'}
                        </h6>
                        <div className="text-muted small">
                          <strong>{job.company || 'Unknown Company'}</strong>
                          {job.location ? ` • ${job.location}` : ''}
                        </div>
                      </div>
                      <Badge bg="light" text="dark" className="border">
                        {job.work_type || 'Job'}
                      </Badge>
                    </div>
                  </ListGroup.Item>
                ))}
              </ListGroup>
            </Card>

            {/* AI Generation Notice Card */}
            <Card className="shadow-sm border-0 mb-4 bg-light rounded-3 p-3">
              <div className="d-flex gap-3 align-items-start">
                <div style={{ fontSize: 28 }}>✨</div>
                <div>
                  <h6 className="fw-bold mb-1" style={{ color: 'var(--color-dark)' }}>
                    AI-Tailored Cover Letter Generation
                  </h6>
                  <p className="text-muted small mb-0">
                    When you submit, our Gemini AI will synthesize your CV skills, professional history, and the job requirements into a personalized cover letter. You can preview and edit the letter on the next screen.
                  </p>
                </div>
              </div>
            </Card>

            {/* Actions */}
            <div className="d-flex justify-content-between align-items-center">
              <Button
                variant="outline-secondary"
                disabled={applying}
                onClick={() => navigate('/jobs')}
              >
                Cancel
              </Button>
              <Button
                style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                disabled={applying || (quota !== null && quota.remaining < jobs.length)}
                onClick={handleConfirmApply}
              >
                {applying ? (
                  <>
                    <Spinner animation="border" size="sm" className="me-2" />
                    Generating with Gemini...
                  </>
                ) : (
                  `Generate Cover Letter & Apply (${jobs.length})`
                )}
              </Button>
            </div>
          </>
        )}
      </Container>
    </>
  )
}
