import { type FormEvent, useCallback, useState } from 'react'
import { CheckCircle2, Download, Loader2 } from 'lucide-react'
import { ingestReport, type IngestResponse } from '../../lib/api'

interface IngestFormProps {
  onIngested?: () => void
}

export default function IngestForm({ onIngested }: IngestFormProps) {
  const [code, setCode] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<IngestResponse | null>(null)

  const handleIngest = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    const trimmed = code.trim()
    if (!trimmed) return
    setIngesting(true)
    setError(null)
    setResult(null)
    try {
      const res = await ingestReport(trimmed)
      setResult(res)
      setCode('')
      onIngested?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ingestion failed')
    } finally {
      setIngesting(false)
    }
  }, [code, onIngested])

  return (
    <div>
      <form onSubmit={handleIngest} className="flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <label className="mb-1 block text-xs font-medium text-zinc-400">
            Pull a report from Warcraft Logs
          </label>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Paste WCL report code (e.g. Aqm8xMvbfFYPwG9X)"
            disabled={ingesting}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none disabled:opacity-50"
          />
        </div>
        <button
          type="submit"
          disabled={ingesting || !code.trim()}
          className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {ingesting ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> Pulling...</>
          ) : (
            <><Download className="h-4 w-4" /> Pull Report</>
          )}
        </button>
      </form>

      {error && (
        <div className="mt-3 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-4 text-sm text-emerald-400">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          Ingested <span className="font-mono">{result.report_code}</span>: {result.fights} fights, {result.performances} player performances
        </div>
      )}
    </div>
  )
}
