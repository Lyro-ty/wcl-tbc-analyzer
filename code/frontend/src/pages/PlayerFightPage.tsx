import { useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Swords, Heart, Shield, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  fetchPlayerAbilities,
  fetchPlayerBuffs,
  getFightDetails,
} from '../lib/api'
import type { AbilityMetric, BuffUptime, FightPlayer } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import AbilityBarChart from '../components/charts/AbilityBarChart'
import UptimeBarChart from '../components/charts/UptimeBarChart'
import DataTable, { type Column } from '../components/ui/DataTable'
import QuickAction from '../components/ui/QuickAction'
import { classColor, formatDuration, formatNumber } from '../lib/wow-classes'

function parseColor(parse: number | null): string {
  if (parse == null) return 'text-zinc-500'
  if (parse >= 99) return 'text-orange-300'
  if (parse >= 95) return 'text-orange-400'
  if (parse >= 75) return 'text-purple-400'
  if (parse >= 50) return 'text-blue-400'
  if (parse >= 25) return 'text-green-400'
  return 'text-zinc-400'
}

export default function PlayerFightPage() {
  const { code, fightId, player } = useParams<{
    code: string
    fightId: string
    player: string
  }>()

  const fightIdNum = Number(fightId)

  // Load player info from fight details
  const { data: fightPlayers, loading: loadingFight } = useApiQuery(
    () => getFightDetails(code!, fightIdNum),
    [code, fightId],
  )

  // Load ability breakdown
  const { data: abilities, loading: loadingAbilities, error: abilitiesError } = useApiQuery(
    () => fetchPlayerAbilities(code!, fightIdNum, player!).catch(() => [] as AbilityMetric[]),
    [code, fightId, player],
  )

  // Load buff uptimes
  const { data: buffs, loading: loadingBuffs } = useApiQuery(
    () => fetchPlayerBuffs(code!, fightIdNum, player!).catch(() => [] as BuffUptime[]),
    [code, fightId, player],
  )

  const playerInfo: FightPlayer | undefined = fightPlayers?.find(
    (p) => p.player_name === player,
  )

  const damageAbilities = abilities?.filter((a) => a.metric_type === 'damage') ?? []
  const healingAbilities = abilities?.filter((a) => a.metric_type === 'healing') ?? []
  const buffData = buffs?.filter((b) => b.metric_type === 'buff') ?? []
  const debuffData = buffs?.filter((b) => b.metric_type === 'debuff') ?? []

  const hasAbilityData = (abilities?.length ?? 0) > 0
  const hasBuffData = (buffs?.length ?? 0) > 0

  const abilityColumns: Column<AbilityMetric>[] = [
    {
      key: 'name',
      label: 'Ability',
      render: (r) => <span className="font-medium text-zinc-200">{r.ability_name}</span>,
    },
    {
      key: 'pct',
      label: '% Total',
      sortValue: (r) => r.pct_of_total,
      render: (r) => (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-amber-500/80 to-orange-500/80"
              style={{ width: `${Math.min(r.pct_of_total, 100)}%` }}
            />
          </div>
          <span className="font-mono text-xs">{r.pct_of_total.toFixed(1)}%</span>
        </div>
      ),
    },
    {
      key: 'total',
      label: 'Total',
      sortValue: (r) => r.total,
      render: (r) => <span className="font-mono">{r.total.toLocaleString()}</span>,
    },
    {
      key: 'hits',
      label: 'Hits',
      sortValue: (r) => r.hit_count,
      render: (r) => <span className="font-mono">{r.hit_count.toLocaleString()}</span>,
    },
    {
      key: 'crit',
      label: 'Crit %',
      sortValue: (r) => r.crit_pct,
      render: (r) => (
        <span className={`font-mono ${r.crit_pct >= 50 ? 'text-amber-400' : ''}`}>
          {r.crit_pct.toFixed(1)}%
        </span>
      ),
    },
  ]

  if (loadingFight) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <Link
          to={`/reports/${code}`}
          className="text-zinc-400 hover:text-zinc-200"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">
            <span style={{ color: classColor(playerInfo?.player_class ?? '') }}>
              {player}
            </span>
          </h1>
          {playerInfo && (
            <p className="text-sm text-zinc-400">
              {playerInfo.player_spec} {playerInfo.player_class}
              <span className="mx-2 text-zinc-600">|</span>
              {playerInfo.encounter_name}
              <span className="mx-2 text-zinc-600">|</span>
              {playerInfo.kill ? 'Kill' : 'Wipe'} in {formatDuration(playerInfo.duration_ms)}
            </p>
          )}
        </div>
        <QuickAction
          question={`Analyze ${player}'s performance on ${playerInfo?.encounter_name ?? 'this boss'} in report ${code}, fight ${fightId}. Look at abilities and buffs.`}
        />
      </div>

      {/* Stats bar */}
      {playerInfo && (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">DPS</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">
              {formatNumber(playerInfo.dps)}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Parse</p>
            <p className={`mt-1 text-lg font-bold ${parseColor(playerInfo.parse_percentile)}`}>
              {playerInfo.parse_percentile != null
                ? `${playerInfo.parse_percentile}%`
                : '—'}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">HPS</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">
              {formatNumber(playerInfo.hps)}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Deaths</p>
            <p
              className={`mt-1 text-lg font-bold ${
                playerInfo.deaths > 0 ? 'text-red-400' : 'text-zinc-300'
              }`}
            >
              {playerInfo.deaths}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">iLvl</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">
              {playerInfo.item_level != null
                ? playerInfo.item_level.toFixed(0)
                : '—'}
            </p>
          </div>
        </div>
      )}

      {/* Loading state for ability data */}
      {(loadingAbilities || loadingBuffs) && (
        <div className="flex items-center gap-2 py-8 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading ability data...
        </div>
      )}

      {/* No data CTA */}
      {!loadingAbilities && !hasAbilityData && !abilitiesError && (
        <div className="mb-8 rounded-lg border border-zinc-800 bg-zinc-900/30 p-6 text-center">
          <Sparkles className="mx-auto mb-3 h-8 w-8 text-zinc-600" />
          <p className="mb-1 text-sm font-medium text-zinc-300">
            Detailed ability data not available
          </p>
          <p className="text-xs text-zinc-500">
            Re-ingest this report with table data enabled to see ability breakdowns
            and buff uptimes.
          </p>
        </div>
      )}

      {/* Damage breakdown */}
      {damageAbilities.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Swords className="h-5 w-5 text-red-400" />
            Damage Breakdown
          </h2>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
            <AbilityBarChart data={damageAbilities} />
          </div>
          <div className="mt-3">
            <DataTable
              columns={abilityColumns}
              data={damageAbilities}
              rowKey={(r) => `${r.spell_id}-${r.ability_name}`}
              emptyMessage="No damage data"
            />
          </div>
        </div>
      )}

      {/* Healing breakdown */}
      {healingAbilities.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Heart className="h-5 w-5 text-emerald-400" />
            Healing Breakdown
          </h2>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
            <AbilityBarChart data={healingAbilities} accentColor="#22c55e" />
          </div>
          <div className="mt-3">
            <DataTable
              columns={abilityColumns}
              data={healingAbilities}
              rowKey={(r) => `${r.spell_id}-${r.ability_name}`}
              emptyMessage="No healing data"
            />
          </div>
        </div>
      )}

      {/* Buff uptimes */}
      {buffData.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Shield className="h-5 w-5 text-blue-400" />
            Buff Uptimes
          </h2>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
            <UptimeBarChart data={buffData} label="Buffs" />
          </div>
        </div>
      )}

      {/* Debuff uptimes */}
      {debuffData.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Sparkles className="h-5 w-5 text-purple-400" />
            Debuff Uptimes
          </h2>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
            <UptimeBarChart data={debuffData} label="Debuffs" />
          </div>
        </div>
      )}

      {/* No buff data note */}
      {!loadingBuffs && hasAbilityData && !hasBuffData && (
        <div className="mb-8 rounded-lg border border-zinc-800/50 bg-zinc-900/20 p-4 text-center text-xs text-zinc-500">
          No buff/debuff uptime data available for this fight.
        </div>
      )}
    </div>
  )
}
