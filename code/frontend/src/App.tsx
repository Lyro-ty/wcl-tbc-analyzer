import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ChatPage from './pages/ChatPage'
import ReportsPage from './pages/ReportsPage'
import ReportDetailPage from './pages/ReportDetailPage'
import ProgressionPage from './pages/ProgressionPage'
import SpeedPage from './pages/SpeedPage'
import LeaderboardPage from './pages/LeaderboardPage'
import RosterPage from './pages/RosterPage'
import CharactersListPage from './pages/CharactersListPage'
import CharacterProfilePage from './pages/CharacterProfilePage'
import CharacterReportsPage from './pages/CharacterReportsPage'
import CharacterReportDetailPage from './pages/CharacterReportDetailPage'
import PlayerFightPage from './pages/PlayerFightPage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:code" element={<ReportDetailPage />} />
          <Route path="/reports/:code/fights/:fightId/player/:player" element={<PlayerFightPage />} />
          <Route path="/characters" element={<CharactersListPage />} />
          <Route path="/characters/:name" element={<CharacterProfilePage />} />
          <Route path="/character-reports" element={<CharacterReportsPage />} />
          <Route path="/character-reports/:name/:code" element={<CharacterReportDetailPage />} />
          <Route path="/progression" element={<ProgressionPage />} />
          <Route path="/speed" element={<SpeedPage />} />
          <Route path="/leaderboard" element={<LeaderboardPage />} />
          <Route path="/roster" element={<RosterPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
