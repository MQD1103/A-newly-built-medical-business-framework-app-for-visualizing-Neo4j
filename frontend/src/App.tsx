import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import AdminUser from './pages/AdminUser'
import AiCheck from './pages/AiCheck'
import Community from './pages/Community'
import Courses from './pages/Courses'
import Friends from './pages/Friends'
import Home from './pages/Home'
import Hospital from './pages/Hospital'
import LinkedInfo from './pages/LinkedInfo'
import Login from './pages/Login'
import Mall from './pages/Mall'
import Manage from './pages/Manage'
import Materials from './pages/Materials'
import Me from './pages/Me'
import NoticeDetail from './pages/NoticeDetail'
import Notices from './pages/Notices'
import Notifications from './pages/Notifications'
import Orders from './pages/Orders'
import ProfileEdit from './pages/ProfileEdit'
import Reminders from './pages/Reminders'
import Schedule from './pages/Schedule'
import Scores from './pages/Scores'
import ServiceShop from './pages/ServiceShop'
import Services from './pages/Services'
import Supervision from './pages/Supervision'
import SymptomDiary from './pages/SymptomDiary'

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="phone-stage">
        <div className="app-frame">
          <p className="center-msg muted">加载中…</p>
        </div>
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Home />} />
        <Route path="notices" element={<Notices />} />
        <Route path="notices/:id" element={<NoticeDetail />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="reminders" element={<Reminders />} />
        <Route path="community" element={<Community />} />
        <Route path="friends" element={<Friends />} />
        <Route path="mall" element={<Mall />} />
        <Route path="orders" element={<Orders />} />
        <Route path="services" element={<Services />} />
        <Route path="hospital" element={<Hospital />} />
        <Route path="ai-check" element={<AiCheck />} />
        <Route path="symptom-diary" element={<SymptomDiary />} />
        <Route path="courses" element={<Courses />} />
        <Route path="service-shop" element={<ServiceShop />} />
        <Route path="supervision" element={<Supervision />} />
        <Route path="materials" element={<Materials />} />
        <Route path="scores" element={<Scores />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="manage" element={<Manage />} />
        <Route path="admin-user" element={<AdminUser />} />
        <Route path="profile" element={<ProfileEdit />} />
        <Route path="linked" element={<LinkedInfo />} />
        <Route path="me" element={<Me />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
