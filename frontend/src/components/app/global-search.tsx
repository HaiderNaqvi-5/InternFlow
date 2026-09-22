import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '@/lib/api'
import type { SearchResults } from '@/lib/types'
import { cn } from '@/lib/utils'

export function GlobalSearch() {
  const [q, setQ] = useState('')
  const [focused, setFocused] = useState(false)
  const navigate = useNavigate()
  const enabled = q.trim().length >= 2 && focused

  const { data } = useQuery({
    queryKey: ['search', q],
    queryFn: () => api.get<SearchResults>(`/api/v1/search?q=${encodeURIComponent(q)}`),
    enabled,
    placeholderData: (prev) => prev,
  })

  return (
    <div className="relative w-full max-w-md">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && data?.results?.[0]) navigate(data.results[0].link)
        }}
        placeholder="Search tasks, people, announcements…"
        className="h-9 w-full rounded-lg border border-border bg-muted/40 pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-ring focus:bg-card focus:outline-none"
      />
      {focused && data && data.results.length > 0 && (
        <div className="absolute left-0 right-0 top-10 z-40 rounded-lg border border-border bg-popover p-1 shadow-lg">
          {data.results.slice(0, 8).map((r) => (
            <button
              key={`${r.type}-${r.id}`}
              onMouseDown={() => navigate(r.link)}
              className={cn(
                'flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent',
              )}
            >
              <span className="truncate">{r.label}</span>
              <span className="shrink-0 rounded-full bg-muted px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                {r.type}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}