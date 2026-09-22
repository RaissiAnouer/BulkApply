import { HashRouter, Routes, Route, Navigate, Link } from 'react-router-dom'
import { Container, Card, Button, Badge } from 'react-bootstrap'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import Navbar from './components/Navbar'
import Login from './pages/Login'
import Register from './pages/Register'
import VerifyEmail from './pages/VerifyEmail'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import Profile from './pages/Profile'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminUsers from './pages/admin/AdminUsers'
import AdminUserDetail from './pages/admin/AdminUserDetail'
import AdminSettings from './pages/admin/AdminSettings'
import CV from './pages/CV'
import Jobs from './pages/Jobs'
import AddJob from './pages/AddJob'
import JobDetail from './pages/JobDetail'
import Applications from './pages/Applications'
import ApplicationDetail from './pages/ApplicationDetail'
import Apply from './pages/Apply'
import Notifications from './pages/Notifications'
import './App.css'

function DashboardStub() {
  const { user } = useAuth()

  return (
    <>
      <Navbar />
      <Container className="py-4" style={{ maxWidth: 650 }}>
        <Card className="shadow-sm border-0 p-4 rounded-3">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h3 className="mb-0" style={{ color: 'var(--color-dark)', fontWeight: 700 }}>
              Welcome, {user?.name}! 👋
            </h3>
            <Badge bg={user?.role === 'admin' ? 'danger' : 'primary'} style={{ fontSize: 13 }}>
              {user?.role === 'admin' ? 'Administrator' : 'Job Seeker'}
            </Badge>
          </div>

          <div className="bg-light p-3 rounded mb-4">
            <div className="mb-2">
              <strong>Email:</strong> {user?.email}
            </div>
            <div className="mb-2">
              <strong>Verification:</strong>{' '}
              <Badge bg={user?.is_verified ? 'success' : 'warning'}>
                {user?.is_verified ? 'Verified' : 'Unverified'}
              </Badge>
            </div>
            <div>
              <strong>Account Status:</strong>{' '}
              <Badge bg={user?.is_active ? 'success' : 'secondary'}>
                {user?.is_active ? 'Active' : 'Suspended'}
              </Badge>
            </div>
          </div>

          <div className="d-flex flex-wrap gap-2 mb-4">
            <Link to="/profile">
              <Button style={{ backgroundColor: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}>
                Candidate Profile
              </Button>
            </Link>
            <Link to="/cv">
              <Button variant="outline-primary">
                CV & Resume
              </Button>
            </Link>
            <Link to="/jobs">
              <Button variant="outline-success">
                Saved Jobs
              </Button>
            </Link>
            <Link to="/applications">
              <Button variant="outline-info">
                Applications & Letters
              </Button>
            </Link>
            <Link to="/notifications">
              <Button variant="outline-warning">
                Notifications 🔔
              </Button>
            </Link>
            {user?.role === 'admin' && (
              <Link to="/admin">
                <Button variant="outline-danger">
                  Admin Dashboard 📊
                </Button>
              </Link>
            )}
          </div>

          <p className="text-muted small mb-0 text-center">
            AutoApply MVP Active — Auto-Apply with Playwright, Gemini Cover Letters, Notifications & Admin Management.
          </p>
        </Card>
      </Container>
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <HashRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cv"
            element={
              <ProtectedRoute>
                <CV />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs"
            element={
              <ProtectedRoute>
                <Jobs />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs/add"
            element={
              <ProtectedRoute>
                <AddJob />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs/new"
            element={
              <ProtectedRoute>
                <AddJob />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs/:id"
            element={
              <ProtectedRoute>
                <JobDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications"
            element={
              <ProtectedRoute>
                <Applications />
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/:id"
            element={
              <ProtectedRoute>
                <ApplicationDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/apply"
            element={
              <ProtectedRoute>
                <Apply />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs/:id/apply"
            element={
              <ProtectedRoute>
                <Apply />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <Notifications />
              </ProtectedRoute>
            }
          />
          {/* Admin Routes */}
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminDashboard />
              </AdminRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <AdminRoute>
                <AdminUsers />
              </AdminRoute>
            }
          />
          <Route
            path="/admin/users/:id"
            element={
              <AdminRoute>
                <AdminUserDetail />
              </AdminRoute>
            }
          />
          <Route
            path="/admin/settings"
            element={
              <AdminRoute>
                <AdminSettings />
              </AdminRoute>
            }
          />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardStub />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </HashRouter>
    </AuthProvider>
  )
}
