import { type FormEvent, useCallback, useState } from 'react'
import { Loader2, Plus, X } from 'lucide-react'
import { getCharacters, getEncounters, getProgression, registerCharacter } from '../lib/api'
import type { ProgressionPoint } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import ProgressionLineChart from '../components/charts/ProgressionLineChart'
import IngestForm from '../components/ui/IngestForm'
import QuickAction from '../components/ui/QuickAction'

const WOW_CLASSES = [
  'Warrior', 'Paladin', 'Hunter', 'Rogue', 'Priest',
  'Shaman', 'Mage', 'Warlock', 'Druid',
]

const SPECS: Record<string, string[]> = {
  Warrior: ['Arms', 'Fury', 'Protection'],
  Paladin: ['Holy', 'Protection', 'Retribution'],
  Hunter: ['Beast Mastery', 'Marksmanship', 'Survival'],
  Rogue: ['Assassination', 'Combat', 'Subtlety'],
  Priest: ['Discipline', 'Holy', 'Shadow'],
  Shaman: ['Elemental', 'Enhancement', 'Restoration'],
  Mage: ['Arcane', 'Fire', 'Frost'],
  Warlock: ['Affliction', 'Demonology', 'Destruction'],
  Druid: ['Balance', 'Feral', 'Restoration'],
}

export default function ProgressionPage() {
  const { data: encounters, refetch: refetchEnc } = useApiQuery(() => getEncounters(), [])
  const { data: characters, refetch: refetchChars } = useApiQuery(() => getCharacters(), [])
  const [selectedChar, setSelectedChar] = useState('')
  const [selectedEnc, setSelectedEnc] = useState('')
  const [progression, setProgression] = useState<ProgressionPoint[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Registration form state
  const [showRegForm, setShowRegForm] = useState(false)
  const [regName, setRegName] = useState('')
  const [regServer, setRegServer] = useState('')
  const [regRegion, setRegRegion] = useState('US')
  const [regClass, setRegClass] = useState('')
  const [regSpec, setRegSpec] = useState('')
  const [regLoading, setRegLoading] = useState(false)
  const [regError, setRegError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!selectedChar || !selectedEnc) return
    setLoading(true)
    setError(null)
    try {
      const data = await getProgression(selectedChar, selectedEnc)
      setProgression(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [selectedChar, selectedEnc])

  const handleRegister = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    if (!regName || !regServer || !regClass || !regSpec) return
    setRegLoading(true)
    setRegError(null)
    try {
      await registerCharacter({
        name: regName,
        server_slug: regServer.toLowerCase().replace(/\s+/g, '-'),
        server_region: regRegion,
        character_class: regClass,
        spec: regSpec,
      })
      refetchChars()
      setShowRegForm(false)
      setRegName('')
      setRegServer('')
      setRegClass('')
      setRegSpec('')
      setSelectedChar(regName)
    } catch (err) {
      setRegError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setRegLoading(false)
    }
  }, [regName, regServer, regRegion, regClass, regSpec, refetchChars])

  const stats = progression && progression.length > 0 ? {
    bestParse: Math.max(...progression.map((p) => p.best_parse ?? 0)),
    medianDps: progression[progression.length - 1]?.median_dps ?? 0,
    totalKills: progression[progression.length - 1]?.kill_count ?? 0,
    avgDeaths: progression[progression.length - 1]?.avg_deaths ?? 0,
  } : null

  const hasCharacters = characters && characters.length > 0
  const hasEncounters = encounters && encounters.length > 0

  // Auto-show registration form when no characters exist
  const showReg = showRegForm || (characters !== undefined && !hasCharacters)

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Personal Progression</h1>

      {/* Ingest form — always available */}
      <div className="mb-6">
        <IngestForm onIngested={refetchEnc} />
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <select
          value={selectedChar}
          onChange={(e) => setSelectedChar(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">{hasCharacters ? 'Select character...' : 'No characters registered'}</option>
          {characters?.map((c) => (
            <option key={c.id} value={c.name}>{c.name} ({c.spec} {c.character_class})</option>
          ))}
        </select>

        <button
          onClick={() => setShowRegForm(!showRegForm)}
          className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-300 hover:border-zinc-600 hover:bg-zinc-700"
        >
          {showRegForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showRegForm ? 'Cancel' : 'Register Character'}
        </button>

        <select
          value={selectedEnc}
          onChange={(e) => setSelectedEnc(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">{hasEncounters ? 'Select encounter...' : 'No encounters (ingest a report first)'}</option>
          {encounters?.map((e) => (
            <option key={e.id} value={e.name}>{e.name} ({e.zone_name})</option>
          ))}
        </select>

        <button
          onClick={load}
          disabled={!selectedChar || !selectedEnc || loading}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Load'}
        </button>
      </div>

      {/* Character registration form */}
      {showReg && (
        <form onSubmit={handleRegister} className="mb-6 rounded-lg border border-zinc-700 bg-zinc-900/50 p-4">
          <h3 className="mb-3 text-sm font-semibold text-zinc-200">Register Character</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <input
              value={regName}
              onChange={(e) => setRegName(e.target.value)}
              placeholder="Name"
              required
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
            />
            <input
              value={regServer}
              onChange={(e) => setRegServer(e.target.value)}
              placeholder="Server"
              required
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
            />
            <select
              value={regRegion}
              onChange={(e) => setRegRegion(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            >
              <option value="US">US</option>
              <option value="EU">EU</option>
              <option value="KR">KR</option>
              <option value="TW">TW</option>
            </select>
            <select
              value={regClass}
              onChange={(e) => { setRegClass(e.target.value); setRegSpec('') }}
              required
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            >
              <option value="">Class...</option>
              {WOW_CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select
              value={regSpec}
              onChange={(e) => setRegSpec(e.target.value)}
              required
              disabled={!regClass}
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 disabled:opacity-50"
            >
              <option value="">Spec...</option>
              {regClass && SPECS[regClass]?.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          {regError && (
            <p className="mt-2 text-sm text-red-400">{regError}</p>
          )}
          <button
            type="submit"
            disabled={regLoading}
            className="mt-3 rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {regLoading ? <Loader2 className="inline h-4 w-4 animate-spin" /> : 'Register Character'}
          </button>
        </form>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-sm text-zinc-500">Best Parse</p>
            <p className="text-2xl font-bold text-orange-400">{stats.bestParse}%</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-sm text-zinc-500">Median DPS</p>
            <p className="text-2xl font-bold text-blue-400">{stats.medianDps?.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-sm text-zinc-500">Total Kills</p>
            <p className="text-2xl font-bold text-emerald-400">{stats.totalKills}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-sm text-zinc-500">Avg Deaths</p>
            <p className="text-2xl font-bold text-red-400">{stats.avgDeaths?.toFixed(1)}</p>
          </div>
        </div>
      )}

      {progression && progression.length > 0 && (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-200">Trend</h2>
            <QuickAction question={`How can I improve on ${selectedEnc}?`} />
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
            <ProgressionLineChart data={progression} />
          </div>
        </div>
      )}

      {progression?.length === 0 && (
        <div className="rounded-lg border border-zinc-800 p-8 text-center text-sm text-zinc-500">
          No progression data found. Run <code className="rounded bg-zinc-800 px-2 py-0.5">snapshot-progression</code> first.
        </div>
      )}
    </div>
  )
}
