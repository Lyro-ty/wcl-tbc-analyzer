import {
  BarChart3,
  GitCompareArrows,
  MessageSquare,
  ScrollText,
  Swords,
  TrendingUp,
  Trophy,
  Users,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Chat', icon: MessageSquare },
  { to: '/reports', label: 'Reports', icon: ScrollText },
  { to: '/progression', label: 'Progression', icon: TrendingUp },
  { to: '/speed', label: 'Speed', icon: Swords },
  { to: '/leaderboard', label: 'Leaderboard', icon: Trophy },
  { to: '/roster', label: 'Roster', icon: Users },
] as const

export default function Sidebar({ collapsed }: { collapsed: boolean }) {
  return (
    <aside
      className={`flex flex-col border-r border-zinc-800 bg-zinc-900 transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      <div className="flex h-14 items-center gap-2 border-b border-zinc-800 px-4">
        <BarChart3 className="h-6 w-6 shrink-0 text-red-500" />
        {!collapsed && (
          <span className="truncate font-bold text-zinc-100">Shukketsu</span>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-2">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-zinc-800 text-zinc-100'
                  : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
              }`
            }
          >
            <Icon className="h-5 w-5 shrink-0" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-zinc-800 p-3">
        <NavLink
          to="/compare"
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-zinc-800 text-zinc-100'
                : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
            }`
          }
        >
          <GitCompareArrows className="h-5 w-5 shrink-0" />
          {!collapsed && <span>Compare</span>}
        </NavLink>
      </div>
    </aside>
  )
}
