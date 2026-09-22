import { useState, useEffect } from 'react'
import { Navbar as BsNavbar, Nav, Container, Button, Badge, NavDropdown } from 'react-bootstrap'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api/client'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (!user) return
    const fetchUnread = () => {
      api<{ unread_count: number }>('/api/notifications/unread-count')
        .then((res) => setUnreadCount(res.unread_count))
        .catch(() => {})
    }
    fetchUnread()
    const interval = setInterval(fetchUnread, 30000)
    return () => clearInterval(interval)
  }, [user, location.pathname])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <BsNavbar bg="white" expand="lg" className="border-bottom shadow-sm mb-4">
      <Container>
        <BsNavbar.Brand
          as={Link}
          to="/"
          style={{ color: 'var(--color-primary)', fontWeight: 700, fontSize: '1.25rem' }}
        >
          AutoApply
        </BsNavbar.Brand>
        <BsNavbar.Toggle aria-controls="main-navbar" />
        <BsNavbar.Collapse id="main-navbar">
          <Nav className="me-auto">
            <Nav.Link
              as={Link}
              to="/"
              active={location.pathname === '/'}
              className="fw-medium"
            >
              Dashboard
            </Nav.Link>
            <Nav.Link
              as={Link}
              to="/profile"
              active={location.pathname === '/profile'}
              className="fw-medium"
            >
              Profile
            </Nav.Link>
            <Nav.Link
              as={Link}
              to="/cv"
              active={location.pathname === '/cv'}
              className="fw-medium"
            >
              CV / Resume
            </Nav.Link>
            <Nav.Link
              as={Link}
              to="/jobs"
              active={location.pathname.startsWith('/jobs')}
              className="fw-medium"
            >
              Jobs
            </Nav.Link>
            <Nav.Link
              as={Link}
              to="/applications"
              active={location.pathname.startsWith('/applications') || location.pathname.startsWith('/apply')}
              className="fw-medium"
            >
              Applications
            </Nav.Link>
            {user?.role === 'admin' && (
              <NavDropdown
                title="Admin ⚙️"
                id="admin-nav-dropdown"
                active={location.pathname.startsWith('/admin')}
                className="fw-semibold text-danger"
              >
                <NavDropdown.Item as={Link} to="/admin">
                  📊 Dashboard & Metrics
                </NavDropdown.Item>
                <NavDropdown.Item as={Link} to="/admin/users">
                  👥 User Management
                </NavDropdown.Item>
                <NavDropdown.Item as={Link} to="/admin/settings">
                  ⚙️ System Settings & Audit Logs
                </NavDropdown.Item>
              </NavDropdown>
            )}
          </Nav>
          <div className="d-flex align-items-center gap-3">
            {/* Notification Bell Badge */}
            <Link
              to="/notifications"
              className="position-relative text-decoration-none text-secondary p-1"
              title="Notifications"
            >
              <span style={{ fontSize: '1.25rem' }}>🔔</span>
              {unreadCount > 0 && (
                <Badge
                  pill
                  bg="danger"
                  className="position-absolute top-0 start-100 translate-middle"
                  style={{ fontSize: '0.65rem' }}
                >
                  {unreadCount > 99 ? '99+' : unreadCount}
                </Badge>
              )}
            </Link>

            <div className="text-end d-none d-sm-block">
              <div className="small fw-semibold">{user?.name}</div>
              <Badge bg={user?.role === 'admin' ? 'danger' : 'primary'} style={{ fontSize: 10 }}>
                {user?.role}
              </Badge>
            </div>
            <Button variant="outline-secondary" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </BsNavbar.Collapse>
      </Container>
    </BsNavbar>
  )
}
