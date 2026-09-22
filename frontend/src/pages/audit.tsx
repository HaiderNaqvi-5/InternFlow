import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api } from '@/lib/api'
import { relativeTime } from '@/lib/format'
import type { AuditEntry } from '@/lib/types'

interface AuditResponse {
  items: AuditEntry[]
  total: number
  page: number
  page_size: number
}

export default function AuditPage() {
  const [page, setPage] = useState(1)

  const audit = useQuery({
    queryKey: ['audit', page],
    queryFn: () => api.get<AuditResponse>(`/api/v1/audit?page=${page}&page_size=20`),
  })

  const items = audit.data?.items ?? []
  const total = audit.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / 20))

  return (
    <div>
      <PageHeader title="Audit Log" description="A record of actions across the system" />

      {audit.isLoading ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : items.length === 0 ? (
        <EmptyState title="No audit entries" description="Actions will be logged here as they happen." />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <Table>
            <THead>
              <TR>
                <TH>When</TH>
                <TH>Actor</TH>
                <TH>Action</TH>
                <TH>Entity</TH>
                <TH>Details</TH>
              </TR>
            </THead>
            <TBody>
              {items.map((e) => (
                <TR key={e.id}>
                  <TD className="whitespace-nowrap text-muted-foreground">{relativeTime(e.created_at)}</TD>
                  <TD className="font-medium">{e.actor_name ?? 'System'}</TD>
                  <TD>
                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{e.action}</code>
                  </TD>
                  <TD className="text-muted-foreground">
                    {e.entity_type ? `${e.entity_type}${e.entity_id != null ? ` #${e.entity_id}` : ''}` : '—'}
                  </TD>
                  <TD className="max-w-[16rem] truncate text-xs text-muted-foreground">
                    {e.metadata ? JSON.stringify(e.metadata) : '—'}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}

      <div className="mt-4 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {audit.data?.page ?? 1} of {totalPages} · {total} entries
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            <ChevronLeft className="size-4" /> Prev
          </Button>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
