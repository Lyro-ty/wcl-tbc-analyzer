import { User } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getCharacters } from '../lib/api'
import { useApiQuery } from '../hooks/useApiQuery'
import { classColor } from '../lib/wow-classes'

export default function CharactersListPage() {
  const { data: characters, loading, error } = useApiQuery(() => getCharacters(), [])

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-lg bg-zinc-800/50" />
        ))}
      </div>
    )
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Characters</h1>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {characters && characters.length === 0 && (
        <div className="flex flex-col items-center gap-4 py-20 text-zinc-500">
          <User className="h-12 w-12" />
          <p className="text-lg font-medium">No characters registered</p>
          <p className="text-sm">
            Register a character on the{' '}
            <Link to="/progression" className="text-red-400 hover:text-red-300">
              Progression page
            </Link>{' '}
            to start tracking.
          </p>
        </div>
      )}

      {characters && characters.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {characters.map((c) => (
            <Link
              key={c.id}
              to={`/characters/${encodeURIComponent(c.name)}`}
              className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5 transition-colors hover:border-zinc-700 hover:bg-zinc-900"
            >
              <p
                className="text-lg font-semibold"
                style={{ color: classColor(c.character_class) }}
              >
                {c.name}
              </p>
              <p className="mt-1 text-sm text-zinc-400">
                {c.spec} {c.character_class}
              </p>
              <p className="mt-0.5 text-xs text-zinc-500">
                {c.server_slug}-{c.server_region}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
