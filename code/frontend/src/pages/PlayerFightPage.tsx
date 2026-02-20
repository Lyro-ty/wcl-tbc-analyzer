import { useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Swords, Heart, HeartCrack, Shield, Sparkles, Skull, Activity, Timer, ClipboardCheck, Ban, ListOrdered, Gauge, Layers, RotateCcw, Target, Gem } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  fetchCancelledCasts,
  fetchCastMetrics,
  fetchCastTimeline,
  fetchConsumableCheck,
  fetchCooldownUsage,
  fetchDotRefreshes,
  fetchFightDeaths,
  fetchRotationScore,
  fetchOverhealAnalysis,
  fetchPhaseMetrics,
  fetchPlayerAbilities,
  fetchPlayerBuffs,
  fetchResourceUsage,
  fetchTrinketProcs,
  getFightDetails,
} from '../lib/api'
import type { AbilityMetric, FightPlayer } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import AbilityBarChart from '../components/charts/AbilityBarChart'
import UptimeBarChart from '../components/charts/UptimeBarChart'
import ActivityGauge from '../components/charts/ActivityGauge'
import CooldownChart from '../components/charts/CooldownChart'
import DotRefreshChart from '../components/charts/DotRefreshChart'
import RotationScoreComponent from '../components/RotationScore'
import PhaseBreakdown from '../components/charts/PhaseBreakdown'
import ResourceChart from '../components/charts/ResourceChart'
import CancelledCasts from '../components/CancelledCasts'
import CastTimeline from '../components/charts/CastTimeline'
import ConsumableCheck from '../components/ConsumableCheck'
import DeathRecap from '../components/DeathRecap'
import OverhealChart from '../components/charts/OverhealChart'
import TrinketChart from '../components/charts/TrinketChart'
import DataTable, { type Column } from '../components/ui/DataTable'
import ErrorBoundary from '../components/ui/ErrorBoundary'
import QuickAction from '../components/ui/QuickAction'
import { classColor, formatDuration, formatNumber, parseColor } from '../lib/wow-classes'

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
    () => fetchPlayerAbilities(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load buff uptimes
  const { data: buffs, loading: loadingBuffs, error: buffsError } = useApiQuery(
    () => fetchPlayerBuffs(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load death recap (event data)
  const { data: deaths } = useApiQuery(
    () => fetchFightDeaths(code!, fightIdNum),
    [code, fightId],
  )

  // Load cast metrics (event data)
  const { data: castMetrics } = useApiQuery(
    () => fetchCastMetrics(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load cooldown usage (event data)
  const { data: cooldowns } = useApiQuery(
    () => fetchCooldownUsage(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load consumable check
  const { data: consumables } = useApiQuery(
    () => fetchConsumableCheck(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load overhealing analysis
  const { data: overheal } = useApiQuery(
    () => fetchOverhealAnalysis(code!, fightIdNum, player!).catch(() => null),
    [code, fightId, player],
  )

  // Load cancelled casts
  const { data: cancelledCasts } = useApiQuery(
    () => fetchCancelledCasts(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load cast timeline (event data)
  const { data: castTimeline } = useApiQuery(
    () => fetchCastTimeline(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load resource usage (event data)
  const { data: resources } = useApiQuery(
    () => fetchResourceUsage(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load phase metrics (event data)
  const { data: phases } = useApiQuery(
    () => fetchPhaseMetrics(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load DoT refresh data (event data)
  const { data: dotRefreshes } = useApiQuery(
    () => fetchDotRefreshes(code!, fightIdNum, player!),
    [code, fightId, player],
  )

  // Load rotation score (event data)
  const { data: rotationScore } = useApiQuery(
    () => fetchRotationScore(code!, fightIdNum, player!).catch(() => null),
    [code, fightId, player],
  )

  // Load trinket proc data
  const { data: trinketProcs } = useApiQuery(
    () => fetchTrinketProcs(code!, fightIdNum, player!).catch(() => []),
    [code, fightId, player],
  )

  const playerDeaths = deaths?.filter((d) => d.player_name === player) ?? []

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

      {/* Ability error */}
      {abilitiesError && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          Failed to load abilities: {abilitiesError}
        </div>
      )}

      {/* Buff error */}
      {buffsError && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          Failed to load buffs: {buffsError}
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
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <AbilityBarChart data={damageAbilities} />
            </div>
          </ErrorBoundary>
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
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <AbilityBarChart data={healingAbilities} accentColor="#22c55e" />
            </div>
          </ErrorBoundary>
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

      {/* Overhealing Analysis */}
      {overheal && overheal.abilities.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <HeartCrack className="h-5 w-5 text-red-400" />
            Overhealing Analysis
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <OverhealChart data={overheal} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Buff uptimes */}
      {buffData.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Shield className="h-5 w-5 text-blue-400" />
            Buff Uptimes
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <UptimeBarChart data={buffData} label="Buffs" />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Debuff uptimes */}
      {debuffData.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Sparkles className="h-5 w-5 text-purple-400" />
            Debuff Uptimes
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <UptimeBarChart data={debuffData} label="Debuffs" />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* No buff data note */}
      {!loadingBuffs && hasAbilityData && !hasBuffData && !buffsError && (
        <div className="mb-8 rounded-lg border border-zinc-800/50 bg-zinc-900/20 p-4 text-center text-xs text-zinc-500">
          No buff/debuff uptime data available for this fight.
        </div>
      )}

      {/* Death Recap (event data) */}
      {playerDeaths.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Skull className="h-5 w-5 text-red-400" />
            Death Recap
          </h2>
          <ErrorBoundary>
            <DeathRecap deaths={playerDeaths} />
          </ErrorBoundary>
        </div>
      )}

      {/* Cast Activity / GCD Uptime (event data) */}
      {castMetrics && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Activity className="h-5 w-5 text-cyan-400" />
            Cast Activity
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-5">
              <ActivityGauge data={castMetrics} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Rotation Score (event data) */}
      {rotationScore && rotationScore.rules_checked > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Target className="h-5 w-5 text-rose-400" />
            Rotation Score
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <RotationScoreComponent data={rotationScore} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Cast Timeline (event data) */}
      {castTimeline && castTimeline.length > 0 && playerInfo && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <ListOrdered className="h-5 w-5 text-violet-400" />
            Cast Timeline
          </h2>
          <ErrorBoundary>
            <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <CastTimeline data={castTimeline} fightDurationMs={playerInfo.duration_ms} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Cancelled Casts (event data) */}
      {cancelledCasts && cancelledCasts.cancel_count > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Ban className="h-5 w-5 text-orange-400" />
            Cancelled Casts
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <CancelledCasts data={cancelledCasts} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* DoT Refresh Analysis (event data) */}
      {dotRefreshes && dotRefreshes.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <RotateCcw className="h-5 w-5 text-purple-400" />
            DoT Refresh Analysis
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <DotRefreshChart data={dotRefreshes} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Cooldown Efficiency (event data) */}
      {cooldowns && cooldowns.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Timer className="h-5 w-5 text-amber-400" />
            Cooldown Efficiency
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <CooldownChart data={cooldowns} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Resource Usage (event data) */}
      {resources && resources.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Gauge className="h-5 w-5 text-blue-400" />
            Resource Usage
          </h2>
          <ErrorBoundary>
            <div className="space-y-4">
              {resources.map((r) => (
                <div
                  key={r.resource_type}
                  className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4"
                >
                  <ResourceChart data={r} />
                </div>
              ))}
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Phase Breakdown (event data) */}
      {phases && phases.length > 0 && playerInfo && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Layers className="h-5 w-5 text-indigo-400" />
            Boss Phase Breakdown
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <PhaseBreakdown data={phases} fightDurationMs={playerInfo.duration_ms} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Consumable Check */}
      {consumables && (consumables.consumables.length > 0 || consumables.missing.length > 0) && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <ClipboardCheck className="h-5 w-5 text-teal-400" />
            Consumable Check
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <ConsumableCheck data={consumables} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Trinket Procs */}
      {trinketProcs && trinketProcs.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
            <Gem className="h-5 w-5 text-emerald-400" />
            Trinket Performance
          </h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <TrinketChart data={trinketProcs} />
            </div>
          </ErrorBoundary>
        </div>
      )}
    </div>
  )
}
