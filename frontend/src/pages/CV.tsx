import { useState, useEffect, type FormEvent, type ChangeEvent } from 'react'
import { Container, Card, Form, Button, Alert, Row, Col, Spinner, Badge, Modal } from 'react-bootstrap'
import Navbar from '../components/Navbar'
import { api, ApiException, getToken, resolveApiUrl } from '../api/client'

interface ContactInfo {
  full_name: string | null
  email: string | null
  phone: string | null
  location: string | null
}

interface WorkExperience {
  company: string | null
  title: string | null
  start_date: string | null
  end_date: string | null
  description: string | null
}

interface Education {
  institution: string | null
  degree: string | null
  graduation_year: string | null
}

interface ParsedData {
  contact_info: ContactInfo
  skills: string[]
  work_experience: WorkExperience[]
  education: Education[]
}

interface CVData {
  id: number
  user_id: number
  file_name: string
  file_type: string
  file_size: number
  parsed_data: ParsedData | null
  created_at: string
  updated_at: string
}

export default function CV() {
  const [cv, setCv] = useState<CVData | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Replacement / upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  // Editable parsed data form state
  const [contactInfo, setContactInfo] = useState<ContactInfo>({
    full_name: '',
    email: '',
    phone: '',
    location: '',
  })
  const [skillsText, setSkillsText] = useState('')
  const [workExperience, setWorkExperience] = useState<WorkExperience[]>([])
  const [education, setEducation] = useState<Education[]>([])

  const loadCV = () => {
    setLoading(true)
    api<CVData>('/api/cv')
      .then((data) => {
        setCv(data)
        if (data.parsed_data) {
          setContactInfo(data.parsed_data.contact_info || { full_name: '', email: '', phone: '', location: '' })
          setSkillsText((data.parsed_data.skills || []).join(', '))
          setWorkExperience(data.parsed_data.work_experience || [])
          setEducation(data.parsed_data.education || [])
        }
      })
      .catch((err) => {
        if (err instanceof ApiException && err.status === 404) {
          setCv(null)
        } else {
          setError(err instanceof ApiException ? err.message : 'Failed to load CV.')
        }
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadCV()
  }, [])

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0])
    }
  }

  const handleUploadOrReplace = async (e: FormEvent) => {
    e.preventDefault()
    if (!selectedFile) {
      setError('Please select a PDF or DOCX file to upload.')
      return
    }

    const ext = selectedFile.name.split('.').pop()?.toLowerCase()
    if (ext !== 'pdf' && ext !== 'docx') {
      setError('Invalid file format. Only PDF and DOCX files are allowed.')
      return
    }

    if (selectedFile.size > 5 * 1024 * 1024) {
      setError('File exceeds the 5 MB maximum size limit.')
      return
    }

    setError('')
    setSuccess('')
    setUploading(true)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const token = getToken()
      const response = await fetch(resolveApiUrl('/api/cv/upload'), {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(errData.detail || 'Upload failed')
      }

      const updatedCV: CVData = await response.json()
      setCv(updatedCV)
      if (updatedCV.parsed_data) {
        setContactInfo(updatedCV.parsed_data.contact_info || { full_name: '', email: '', phone: '', location: '' })
        setSkillsText((updatedCV.parsed_data.skills || []).join(', '))
        setWorkExperience(updatedCV.parsed_data.work_experience || [])
        setEducation(updatedCV.parsed_data.education || [])
      }
      setSelectedFile(null)
      setSuccess('CV uploaded and parsed successfully!')
    } catch (err: any) {
      setError(err.message || 'Failed to upload CV.')
    } finally {
      setUploading(false)
    }
  }

  const handleSaveCorrections = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setSaving(true)

    const skillsArray = skillsText
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0)

    const payload = {
      contact_info: contactInfo,
      skills: skillsArray,
      work_experience: workExperience,
      education: education,
    }

    try {
      const updated = await api<CVData>('/api/cv/parsed-data', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setCv(updated)
      setSuccess('Parsed CV corrections saved successfully!')
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to save corrections.')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCV = async () => {
    setError('')
    setSuccess('')
    setDeleting(true)
    try {
      await api('/api/cv', { method: 'DELETE' })
      setCv(null)
      setShowDeleteModal(false)
      setSuccess('CV deleted successfully.')
    } catch (err) {
      setError(err instanceof ApiException ? err.message : 'Failed to delete CV.')
    } finally {
      setDeleting(false)
    }
  }

  // Work experience helpers
  const addWorkRole = () => {
    setWorkExperience([
      ...workExperience,
      { company: '', title: '', start_date: '', end_date: '', description: '' },
    ])
  }

  const removeWorkRole = (index: number) => {
    setWorkExperience(workExperience.filter((_, i) => i !== index))
  }

  const updateWorkRole = (index: number, field: keyof WorkExperience, val: string) => {
    const next = [...workExperience]
    next[index] = { ...next[index], [field]: val }
    setWorkExperience(next)
  }

  // Education helpers
  const addEducation = () => {
    setEducation([
      ...education,
      { institution: '', degree: '', graduation_year: '' },
    ])
  }

  const removeEducation = (index: number) => {
    setEducation(education.filter((_, i) => i !== index))
  }

  const updateEducation = (index: number, field: keyof Education, val: string) => {
    const next = [...education]
    next[index] = { ...next[index], [field]: val }
    setEducation(next)
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  return (
    <>
      <Navbar />
      <Container className="pb-5" style={{ maxWidth: 880 }}>
        <div className="mb-4">
          <h2 style={{ fontWeight: 700, color: 'var(--color-dark)' }}>CV & Resume Management</h2>
          <p className="text-muted">
            Upload your master CV document. The system will extract your skills, experience, and education for automated applications.
          </p>
        </div>

        {error && <Alert variant="danger" onClose={() => setError('')} dismissible>{error}</Alert>}
        {success && <Alert variant="success" onClose={() => setSuccess('')} dismissible>{success}</Alert>}

        {loading ? (
          <div className="text-center py-5">
            <Spinner animation="border" role="status" />
            <p className="mt-3 text-muted">Loading CV status...</p>
          </div>
        ) : !cv ? (
          /* State 1: No active CV uploaded */
          <Card className="shadow-sm border-0 p-4 text-center">
            <div style={{ fontSize: 54 }} className="mb-2">📄</div>
            <h4 className="mb-2">No Active CV Uploaded</h4>
            <p className="text-muted mb-4">
              Upload your CV in PDF or DOCX format (maximum 5 MB).
            </p>
            <Form onSubmit={handleUploadOrReplace} className="mx-auto" style={{ maxWidth: 450 }}>
              <Form.Group controlId="cvFileInput" className="mb-3">
                <Form.Control
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={handleFileChange}
                />
              </Form.Group>
              <Button
                type="submit"
                disabled={uploading || !selectedFile}
                style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                className="w-100"
              >
                {uploading ? 'Uploading & Parsing...' : 'Upload CV'}
              </Button>
            </Form>
          </Card>
        ) : (
          /* State 2: Active CV with Parsed Data Review & Editor */
          <>
            {/* File Details Card */}
            <Card className="shadow-sm border-0 mb-4">
              <Card.Body className="p-4">
                <div className="d-flex flex-wrap justify-content-between align-items-center mb-3">
                  <div>
                    <h5 className="mb-1 fw-bold text-primary">Active CV File</h5>
                    <div className="d-flex gap-2 align-items-center">
                      <span className="fw-semibold">{cv.file_name}</span>
                      <Badge bg={cv.file_type === 'pdf' ? 'danger' : 'primary'}>
                        {cv.file_type.toUpperCase()}
                      </Badge>
                      <span className="text-muted small">({formatFileSize(cv.file_size)})</span>
                    </div>
                  </div>
                  <div className="d-flex gap-2 mt-2 mt-sm-0">
                    <Button
                      variant="outline-danger"
                      size="sm"
                      onClick={() => setShowDeleteModal(true)}
                    >
                      Delete CV
                    </Button>
                  </div>
                </div>

                <hr />

                {/* Safe Replacement Form */}
                <h6 className="fw-semibold mb-2">Replace CV Document</h6>
                <p className="text-muted small mb-2">
                  Select a new PDF or DOCX file to replace your current CV. The existing CV will remain safe until the replacement succeeds.
                </p>
                <Form onSubmit={handleUploadOrReplace} className="d-flex flex-wrap gap-2 align-items-center">
                  <Form.Control
                    type="file"
                    size="sm"
                    style={{ maxWidth: 350 }}
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    onChange={handleFileChange}
                  />
                  <Button
                    type="submit"
                    variant="outline-primary"
                    size="sm"
                    disabled={uploading || !selectedFile}
                  >
                    {uploading ? 'Processing Replacement...' : 'Upload & Replace'}
                  </Button>
                </Form>
              </Card.Body>
            </Card>

            {/* Parsed Data Review & Manual Corrections Form */}
            <Form onSubmit={handleSaveCorrections}>
              {/* Section 1: Contact Information */}
              <Card className="shadow-sm border-0 mb-4">
                <Card.Body className="p-4">
                  <h5 className="mb-3 text-primary">1. Extracted Contact Information</h5>
                  <Row className="g-3">
                    <Col md={6}>
                      <Form.Group controlId="parsedName">
                        <Form.Label className="small text-muted mb-1">Full Name</Form.Label>
                        <Form.Control
                          type="text"
                          value={contactInfo.full_name || ''}
                          onChange={(e) => setContactInfo({ ...contactInfo, full_name: e.target.value })}
                        />
                      </Form.Group>
                    </Col>
                    <Col md={6}>
                      <Form.Group controlId="parsedEmail">
                        <Form.Label className="small text-muted mb-1">Email</Form.Label>
                        <Form.Control
                          type="email"
                          value={contactInfo.email || ''}
                          onChange={(e) => setContactInfo({ ...contactInfo, email: e.target.value })}
                        />
                      </Form.Group>
                    </Col>
                    <Col md={6}>
                      <Form.Group controlId="parsedPhone">
                        <Form.Label className="small text-muted mb-1">Phone Number</Form.Label>
                        <Form.Control
                          type="tel"
                          value={contactInfo.phone || ''}
                          onChange={(e) => setContactInfo({ ...contactInfo, phone: e.target.value })}
                        />
                      </Form.Group>
                    </Col>
                    <Col md={6}>
                      <Form.Group controlId="parsedLocation">
                        <Form.Label className="small text-muted mb-1">Location</Form.Label>
                        <Form.Control
                          type="text"
                          value={contactInfo.location || ''}
                          onChange={(e) => setContactInfo({ ...contactInfo, location: e.target.value })}
                        />
                      </Form.Group>
                    </Col>
                  </Row>
                </Card.Body>
              </Card>

              {/* Section 2: Skills */}
              <Card className="shadow-sm border-0 mb-4">
                <Card.Body className="p-4">
                  <h5 className="mb-2 text-primary">2. Extracted Skills</h5>
                  <p className="text-muted small mb-3">
                    Enter skills separated by commas. These will be matched against job requirements and referenced in applications.
                  </p>
                  <Form.Group controlId="parsedSkills">
                    <Form.Control
                      as="textarea"
                      rows={3}
                      value={skillsText}
                      onChange={(e) => setSkillsText(e.target.value)}
                      placeholder="e.g. Python, FastAPI, React, Docker, SQL"
                    />
                  </Form.Group>
                </Card.Body>
              </Card>

              {/* Section 3: Work Experience */}
              <Card className="shadow-sm border-0 mb-4">
                <Card.Body className="p-4">
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <h5 className="mb-0 text-primary">3. Work Experience</h5>
                    <Button variant="outline-primary" size="sm" onClick={addWorkRole}>
                      + Add Role
                    </Button>
                  </div>

                  {workExperience.length === 0 ? (
                    <p className="text-muted small">No work experience roles detected. Click "+ Add Role" to add one.</p>
                  ) : (
                    workExperience.map((role, idx) => (
                      <Card key={idx} className="bg-light border-0 p-3 mb-3">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                          <strong className="text-dark">Role #{idx + 1}</strong>
                          <Button
                            variant="outline-danger"
                            size="sm"
                            style={{ fontSize: 12, padding: '2px 8px' }}
                            onClick={() => removeWorkRole(idx)}
                          >
                            Remove
                          </Button>
                        </div>
                        <Row className="g-2 mb-2">
                          <Col md={6}>
                            <Form.Control
                              type="text"
                              placeholder="Company"
                              value={role.company || ''}
                              onChange={(e) => updateWorkRole(idx, 'company', e.target.value)}
                            />
                          </Col>
                          <Col md={6}>
                            <Form.Control
                              type="text"
                              placeholder="Job Title"
                              value={role.title || ''}
                              onChange={(e) => updateWorkRole(idx, 'title', e.target.value)}
                            />
                          </Col>
                          <Col md={6}>
                            <Form.Control
                              type="text"
                              placeholder="Start Date (e.g. 2021)"
                              value={role.start_date || ''}
                              onChange={(e) => updateWorkRole(idx, 'start_date', e.target.value)}
                            />
                          </Col>
                          <Col md={6}>
                            <Form.Control
                              type="text"
                              placeholder="End Date (e.g. Present)"
                              value={role.end_date || ''}
                              onChange={(e) => updateWorkRole(idx, 'end_date', e.target.value)}
                            />
                          </Col>
                        </Row>
                        <Form.Control
                          as="textarea"
                          rows={2}
                          placeholder="Description of responsibilities and achievements..."
                          value={role.description || ''}
                          onChange={(e) => updateWorkRole(idx, 'description', e.target.value)}
                        />
                      </Card>
                    ))
                  )}
                </Card.Body>
              </Card>

              {/* Section 4: Education */}
              <Card className="shadow-sm border-0 mb-4">
                <Card.Body className="p-4">
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <h5 className="mb-0 text-primary">4. Education</h5>
                    <Button variant="outline-primary" size="sm" onClick={addEducation}>
                      + Add Education
                    </Button>
                  </div>

                  {education.length === 0 ? (
                    <p className="text-muted small">No education entries detected. Click "+ Add Education" to add one.</p>
                  ) : (
                    education.map((edu, idx) => (
                      <Card key={idx} className="bg-light border-0 p-3 mb-3">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                          <strong className="text-dark">Education #{idx + 1}</strong>
                          <Button
                            variant="outline-danger"
                            size="sm"
                            style={{ fontSize: 12, padding: '2px 8px' }}
                            onClick={() => removeEducation(idx)}
                          >
                            Remove
                          </Button>
                        </div>
                        <Row className="g-2">
                          <Col md={5}>
                            <Form.Control
                              type="text"
                              placeholder="Institution"
                              value={edu.institution || ''}
                              onChange={(e) => updateEducation(idx, 'institution', e.target.value)}
                            />
                          </Col>
                          <Col md={4}>
                            <Form.Control
                              type="text"
                              placeholder="Degree / Major"
                              value={edu.degree || ''}
                              onChange={(e) => updateEducation(idx, 'degree', e.target.value)}
                            />
                          </Col>
                          <Col md={3}>
                            <Form.Control
                              type="text"
                              placeholder="Graduation Year"
                              value={edu.graduation_year || ''}
                              onChange={(e) => updateEducation(idx, 'graduation_year', e.target.value)}
                            />
                          </Col>
                        </Row>
                      </Card>
                    ))
                  )}
                </Card.Body>
              </Card>

              {/* Submit Corrections */}
              <div className="d-flex justify-content-end">
                <Button
                  type="submit"
                  disabled={saving}
                  style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)', minWidth: 160 }}
                >
                  {saving ? 'Saving...' : 'Save Corrections'}
                </Button>
              </div>
            </Form>
          </>
        )}

        {/* Delete Confirmation Modal */}
        <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)} centered>
          <Modal.Header closeButton>
            <Modal.Title className="text-danger">Delete Active CV</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            Are you sure you want to delete <strong>{cv?.file_name}</strong>?
            <br />
            <br />
            <span className="text-muted small">
              This will remove the file from storage and clear your parsed skills, experience, and education. You will need to upload a new CV to enable automated applications.
            </span>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDeleteCV} disabled={deleting}>
              {deleting ? 'Deleting...' : 'Permanently Delete'}
            </Button>
          </Modal.Footer>
        </Modal>
      </Container>
    </>
  )
}
