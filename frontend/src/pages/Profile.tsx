import { useState, useEffect, type FormEvent } from 'react'
import { Container, Card, Form, Button, Alert, Row, Col, Spinner, Badge } from 'react-bootstrap'
import Navbar from '../components/Navbar'
import { api, ApiException } from '../api/client'

interface ProfileData {
  id: number
  user_id: number
  email: string
  role: string
  is_active: boolean
  is_verified: boolean
  full_name: string
  phone: string
  location: string
  linkedin_url: string | null
  github_url: string | null
  portfolio_url: string | null
  work_authorization: boolean | null
  requires_sponsorship: boolean | null
  years_of_experience: number | null
  salary_expectation: string | null
  education_level: string | null
  languages: string | null
  target_job_title: string | null
  work_preference: string | null
  employment_type: string | null
  preferred_locations: string | null
}

export default function Profile() {
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  // Form fields
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [location, setLocation] = useState('')
  const [linkedinUrl, setLinkedinUrl] = useState('')
  const [githubUrl, setGithubUrl] = useState('')
  const [portfolioUrl, setPortfolioUrl] = useState('')
  const [workAuth, setWorkAuth] = useState<string>('null')
  const [sponsorship, setSponsorship] = useState<string>('null')
  const [yearsExp, setYearsExp] = useState<string>('')
  const [salaryExp, setSalaryExp] = useState('')
  const [educationLevel, setEducationLevel] = useState('')
  const [languages, setLanguages] = useState('')
  const [targetTitle, setTargetTitle] = useState('')
  const [workPref, setWorkPref] = useState('remote')
  const [employmentType, setEmploymentType] = useState('full-time')
  const [prefLocations, setPrefLocations] = useState('')

  useEffect(() => {
    api<ProfileData>('/api/profile')
      .then((data) => {
        setProfile(data)
        setFullName(data.full_name || '')
        setPhone(data.phone || '')
        setLocation(data.location || '')
        setLinkedinUrl(data.linkedin_url || '')
        setGithubUrl(data.github_url || '')
        setPortfolioUrl(data.portfolio_url || '')
        setWorkAuth(data.work_authorization === null ? 'null' : data.work_authorization ? 'true' : 'false')
        setSponsorship(data.requires_sponsorship === null ? 'null' : data.requires_sponsorship ? 'true' : 'false')
        setYearsExp(data.years_of_experience !== null ? String(data.years_of_experience) : '')
        setSalaryExp(data.salary_expectation || '')
        setEducationLevel(data.education_level || '')
        setLanguages(data.languages || '')
        setTargetTitle(data.target_job_title || '')
        setWorkPref(data.work_preference || 'remote')
        setEmploymentType(data.employment_type || 'full-time')
        setPrefLocations(data.preferred_locations || '')
      })
      .catch((err) => {
        setError(err instanceof ApiException ? err.message : 'Failed to load profile')
      })
      .finally(() => setLoading(false))
  }, [])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (!fullName.trim()) {
      setError('Full Name is required.')
      return
    }
    if (!phone.trim()) {
      setError('Phone Number is required.')
      return
    }
    if (!location.trim()) {
      setError('Location is required.')
      return
    }

    setSaving(true)
    try {
      const payload = {
        full_name: fullName.trim(),
        phone: phone.trim(),
        location: location.trim(),
        linkedin_url: linkedinUrl.trim() || null,
        github_url: githubUrl.trim() || null,
        portfolio_url: portfolioUrl.trim() || null,
        work_authorization: workAuth === 'null' ? null : workAuth === 'true',
        requires_sponsorship: sponsorship === 'null' ? null : sponsorship === 'true',
        years_of_experience: yearsExp.trim() !== '' ? parseInt(yearsExp, 10) : null,
        salary_expectation: salaryExp.trim() || null,
        education_level: educationLevel.trim() || null,
        languages: languages.trim() || null,
        target_job_title: targetTitle.trim() || null,
        work_preference: workPref,
        employment_type: employmentType,
        preferred_locations: prefLocations.trim() || null,
      }

      const updated = await api<ProfileData>('/api/profile', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setProfile(updated)
      setSuccess('Profile updated successfully!')
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to update profile')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <>
        <Navbar />
        <Container className="text-center py-5">
          <Spinner animation="border" role="status" />
          <p className="mt-3 text-muted">Loading profile...</p>
        </Container>
      </>
    )
  }

  return (
    <>
      <Navbar />
      <Container className="pb-5" style={{ maxWidth: 880 }}>
        <div className="mb-4">
          <h2 style={{ fontWeight: 700, color: 'var(--color-dark)' }}>Candidate Profile</h2>
          <p className="text-muted">
            Manage your personal contact details, links, and job application preferences.
          </p>
        </div>

        {error && <Alert variant="danger" onClose={() => setError('')} dismissible>{error}</Alert>}
        {success && <Alert variant="success" onClose={() => setSuccess('')} dismissible>{success}</Alert>}

        <Form onSubmit={handleSubmit}>
          {/* Section 1: Account Info (Read-Only) */}
          <Card className="shadow-sm mb-4 border-0">
            <Card.Body className="p-4">
              <h5 className="mb-3 text-primary">1. Account Information</h5>
              <Row className="g-3">
                <Col md={6}>
                  <Form.Label className="text-muted small mb-1">Email Address (Login)</Form.Label>
                  <Form.Control type="text" value={profile?.email || ''} disabled readOnly />
                </Col>
                <Col md={6}>
                  <Form.Label className="text-muted small mb-1">Account Status & Role</Form.Label>
                  <div className="pt-2 d-flex gap-2 align-items-center">
                    <Badge bg={profile?.role === 'admin' ? 'danger' : 'primary'}>
                      {profile?.role}
                    </Badge>
                    <Badge bg={profile?.is_verified ? 'success' : 'warning'}>
                      {profile?.is_verified ? 'Verified Email' : 'Unverified'}
                    </Badge>
                    <Badge bg={profile?.is_active ? 'success' : 'secondary'}>
                      {profile?.is_active ? 'Active' : 'Suspended'}
                    </Badge>
                  </div>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {/* Section 2: Contact & Identity (Required for MVP) */}
          <Card className="shadow-sm mb-4 border-0">
            <Card.Body className="p-4">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="mb-0 text-primary">2. Contact & Identity</h5>
                <Badge bg="danger">Required for MVP</Badge>
              </div>
              <Row className="g-3">
                <Col md={4}>
                  <Form.Group controlId="fullName">
                    <Form.Label>Full Name <span className="text-danger">*</span></Form.Label>
                    <Form.Control
                      type="text"
                      placeholder="e.g. Jane Doe"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group controlId="phone">
                    <Form.Label>Phone Number <span className="text-danger">*</span></Form.Label>
                    <Form.Control
                      type="tel"
                      placeholder="e.g. +1 555-0199"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      required
                    />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group controlId="location">
                    <Form.Label>Location <span className="text-danger">*</span></Form.Label>
                    <Form.Control
                      type="text"
                      placeholder="City, Country"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      required
                    />
                  </Form.Group>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {/* Section 3: Professional Links (Optional) */}
          <Card className="shadow-sm mb-4 border-0">
            <Card.Body className="p-4">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="mb-0 text-primary">3. Professional Links</h5>
                <Badge bg="secondary">Optional</Badge>
              </div>
              <Row className="g-3">
                <Col md={4}>
                  <Form.Group controlId="linkedinUrl">
                    <Form.Label>LinkedIn URL</Form.Label>
                    <Form.Control
                      type="url"
                      placeholder="https://linkedin.com/in/..."
                      value={linkedinUrl}
                      onChange={(e) => setLinkedinUrl(e.target.value)}
                    />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group controlId="githubUrl">
                    <Form.Label>GitHub URL</Form.Label>
                    <Form.Control
                      type="url"
                      placeholder="https://github.com/..."
                      value={githubUrl}
                      onChange={(e) => setGithubUrl(e.target.value)}
                    />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group controlId="portfolioUrl">
                    <Form.Label>Portfolio / Website</Form.Label>
                    <Form.Control
                      type="url"
                      placeholder="https://myportfolio.com"
                      value={portfolioUrl}
                      onChange={(e) => setPortfolioUrl(e.target.value)}
                    />
                  </Form.Group>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {/* Section 4: Eligibility & Screening (Conditional) */}
          <Card className="shadow-sm mb-4 border-0">
            <Card.Body className="p-4">
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h5 className="mb-0 text-primary">4. Eligibility & Qualifications</h5>
                <Badge bg="info">Required only when job asks</Badge>
              </div>
              <p className="text-muted small mb-3">
                These fields can remain empty now. They will be used when a specific job application asks for them.
              </p>
              <Row className="g-3 mb-3">
                <Col md={6}>
                  <Form.Group controlId="workAuth">
                    <Form.Label>Are you legally authorized to work in your target country?</Form.Label>
                    <Form.Select value={workAuth} onChange={(e) => setWorkAuth(e.target.value)}>
                      <option value="null">Not answered yet</option>
                      <option value="true">Yes — Authorized to work</option>
                      <option value="false">No — Not authorized</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group controlId="sponsorship">
                    <Form.Label>Will you require visa sponsorship now or in the future?</Form.Label>
                    <Form.Select value={sponsorship} onChange={(e) => setSponsorship(e.target.value)}>
                      <option value="null">Not answered yet</option>
                      <option value="false">No — Do not require sponsorship</option>
                      <option value="true">Yes — Require sponsorship</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
              </Row>
              <Row className="g-3">
                <Col md={3}>
                  <Form.Group controlId="yearsExp">
                    <Form.Label>Years of Experience</Form.Label>
                    <Form.Control
                      type="number"
                      min={0}
                      max={70}
                      placeholder="e.g. 5"
                      value={yearsExp}
                      onChange={(e) => setYearsExp(e.target.value)}
                    />
                  </Form.Group>
                </Col>
                <Col md={3}>
                  <Form.Group controlId="salaryExp">
                    <Form.Label>Salary Expectation</Form.Label>
                    <Form.Control
                      type="text"
                      placeholder="e.g. $90,000 / yr"
                      value={salaryExp}
                      onChange={(e) => setSalaryExp(e.target.value)}
                    />
                  </Form.Group>
                </Col>
                <Col md={3}>
                  <Form.Group controlId="educationLevel">
                    <Form.Label>Highest Education</Form.Label>
                    <Form.Control
                      type="text"
                      placeholder="e.g. Bachelor's Degree"
                      value={educationLevel}
                      onChange={(e) => setEducationLevel(e.target.value)}
                    />
                  </Form.Group>
                </Col>
                <Col md={3}>
                  <Form.Group controlId="languages">
                    <Form.Label>Languages</Form.Label>
                    <Form.Control
                      type="text"
                      placeholder="e.g. English, French"
                      value={languages}
                      onChange={(e) => setLanguages(e.target.value)}
                    />
                  </Form.Group>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {/* Section 5: Job Preferences (Optional) */}
          <Card className="shadow-sm mb-4 border-0">
            <Card.Body className="p-4">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="mb-0 text-primary">5. Job Preferences</h5>
                <Badge bg="secondary">Optional</Badge>
              </div>
              <Row className="g-3">
                <Col md={3}>
                  <Form.Group controlId="targetTitle">
                    <Form.Label>Target Job Title</Form.Label>
                    <Form.Control
                      type="text"
                      placeholder="e.g. Full-Stack Developer"
                      value={targetTitle}
                      onChange={(e) => setTargetTitle(e.target.value)}
                    />
                  </Form.Group>
                </Col>
                <Col md={3}>
                  <Form.Group controlId="workPref">
                    <Form.Label>Work Arrangement</Form.Label>
                    <Form.Select value={workPref} onChange={(e) => setWorkPref(e.target.value)}>
                      <option value="remote">Remote</option>
                      <option value="hybrid">Hybrid</option>
                      <option value="onsite">On-site</option>
                      <option value="any">Any / Flexible</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={3}>
                  <Form.Group controlId="employmentType">
                    <Form.Label>Employment Type</Form.Label>
                    <Form.Select value={employmentType} onChange={(e) => setEmploymentType(e.target.value)}>
                      <option value="full-time">Full-Time</option>
                      <option value="contract">Contract / Freelance</option>
                      <option value="part-time">Part-Time</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={3}>
                  <Form.Group controlId="prefLocations">
                    <Form.Label>Preferred Locations</Form.Label>
                    <Form.Control
                      type="text"
                      placeholder="e.g. New York, Remote"
                      value={prefLocations}
                      onChange={(e) => setPrefLocations(e.target.value)}
                    />
                  </Form.Group>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          <div className="d-flex justify-content-end gap-2">
            <Button
              type="submit"
              disabled={saving}
              style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)', minWidth: 140 }}
            >
              {saving ? 'Saving...' : 'Save Profile'}
            </Button>
          </div>
        </Form>
      </Container>
    </>
  )
}
