import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ChatPage from './pages/ChatPage'
import ReportsPage from './pages/ReportsPage'
import ReportDetailPage from './pages/ReportDetailPage'
import ProgressionPage from './pages/ProgressionPage'
import SpeedPage from './pages/SpeedPage'
import LeaderboardPage from './pages/LeaderboardPage'
import RosterPage from './pages/RosterPage'
import ComparePage from './pages/ComparePage'
import CharacterReportsPage from './pages/CharacterReportsPage'
import CharacterReportDetailPage from './pages/CharacterReportDetailPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:code" element={<ReportDetailPage />} />
          <Route path="/character-reports" element={<CharacterReportsPage />} />
          <Route path="/character-reports/:name/:code" element={<CharacterReportDetailPage />} />
          <Route path="/progression" element={<ProgressionPage />} />
          <Route path="/speed" element={<SpeedPage />} />
          <Route path="/leaderboard" element={<LeaderboardPage />} />
          <Route path="/roster" element={<RosterPage />} />
          <Route path="/compare" element={<ComparePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
