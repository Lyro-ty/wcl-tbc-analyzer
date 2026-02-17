import { type ReactNode, useCallback, useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'

export interface Column<T> {
  key: string
  label: string
  render: (row: T, index: number) => ReactNode
  sortValue?: (row: T) => number | string
  className?: string
}

interface Props<T> {
  columns: Column<T>[]
  data: T[]
  rowKey: (row: T) => string
  rowClassName?: (row: T) => string
  emptyMessage?: string
}

export default function DataTable<T>({
  columns,
  data,
  rowKey,
  rowClassName,
  emptyMessage = 'No data',
}: Props<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setSortKey(key)
        setSortDir('desc')
      }
    },
    [sortKey],
  )

  const sorted = useMemo(() => {
    if (!sortKey) return data
    const col = columns.find((c) => c.key === sortKey)
    if (!col?.sortValue) return data
    const fn = col.sortValue
    return [...data].sort((a, b) => {
      const va = fn(a)
      const vb = fn(b)
      const cmp = va < vb ? -1 : va > vb ? 1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir, columns])

  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 p-8 text-center text-sm text-zinc-500">
        {emptyMessage}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/50">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left font-medium text-zinc-400 ${
                  col.sortValue ? 'cursor-pointer select-none hover:text-zinc-200' : ''
                } ${col.className ?? ''}`}
                onClick={col.sortValue ? () => handleSort(col.key) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortValue &&
                    (sortKey === col.key ? (
                      sortDir === 'asc' ? (
                        <ArrowUp className="h-3.5 w-3.5" />
                      ) : (
                        <ArrowDown className="h-3.5 w-3.5" />
                      )
                    ) : (
                      <ArrowUpDown className="h-3.5 w-3.5 opacity-30" />
                    ))}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, rowIndex) => (
            <tr
              key={rowKey(row)}
              className={`border-b border-zinc-800/50 transition-colors hover:bg-zinc-900/30 ${
                rowClassName?.(row) ?? ''
              }`}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-4 py-2.5 ${col.className ?? ''}`}>
                  {col.render(row, rowIndex)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
