import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center py-32">
      <AlertTriangle className="mb-4 h-16 w-16 text-zinc-600" />
      <h1 className="mb-2 text-2xl font-bold text-zinc-200">Page not found</h1>
      <p className="mb-6 text-sm text-zinc-500">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        className="rounded-lg bg-red-600 px-5 py-2 text-sm font-medium text-white hover:bg-red-700"
      >
        Go to Dashboard
      </Link>
    </div>
  )
}
