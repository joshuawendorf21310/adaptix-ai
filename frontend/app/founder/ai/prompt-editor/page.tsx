'use client';

import { useApi } from '@/hooks/useApi';
import {
  CommandPageHeader,
  CommandPanel,
  DataRow,
  MetricTile,
  StatusPill,
} from '@/components/command/CommandPrimitives';
import { AdaptixCardSkeleton } from '@/components/ui';

interface PromptLogEntry {
  id: string;
  prompt_id?: string;
  use_case?: string;
  model_id?: string;
  input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  cost_usd?: number;
  created_at?: string;
}

interface AuditSummary {
  total_prompts?: number;
  active_prompts?: number;
  total_calls_today?: number;
  avg_latency_ms?: number;
}

export default function PromptEditorPage() {
  const logState = useApi<PromptLogEntry[]>('/ai/prompt-log?limit=20');
  const auditState = useApi<AuditSummary>('/ai/prompts/audit');

  const loading = logState.loading || auditState.loading;
  const log = logState.data;
  const audit = auditState.data;

  const useCaseCounts = log
    ? log.reduce<Record<string, number>>((acc, e) => {
        const uc = e.use_case ?? 'unknown';
        acc[uc] = (acc[uc] ?? 0) + 1;
        return acc;
      }, {})
    : null;

  const avgLatency =
    log && log.length > 0
      ? (log.reduce((s, e) => s + (e.latency_ms ?? 0), 0) / log.length).toFixed(0)
      : null;

  return (
    <div className="space-y-6 md:space-y-7">
      <CommandPageHeader
        eyebrow="AI Governance"
        title="Prompt Editor"
        description="System prompt audit log and usage statistics."
        status={<StatusPill label={loading ? 'Loading…' : 'Live'} tone={loading ? 'neutral' : 'info'} />}
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <AdaptixCardSkeleton key={i} />)}
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile label="Active prompts" value={String(audit?.active_prompts ?? '—')} tone="info" />
            <MetricTile label="Total prompts" value={String(audit?.total_prompts ?? '—')} tone="accent" />
            <MetricTile label="Calls today" value={String(audit?.total_calls_today ?? '—')} tone="neutral" />
            <MetricTile
              label="Avg latency"
              value={avgLatency ? `${avgLatency}ms` : String(audit?.avg_latency_ms ? `${audit.avg_latency_ms.toFixed(0)}ms` : '—')}
              tone={avgLatency && parseInt(avgLatency) > 2000 ? 'warning' : 'success'}
            />
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <CommandPanel eyebrow="Recent calls" title="Prompt call log" description="Most recent AI prompt calls across all use cases.">
              {log && log.length > 0 ? (
                log.map((entry) => (
                  <DataRow
                    key={entry.id}
                    label={entry.use_case ?? 'unknown'}
                    value={entry.model_id?.split('.').slice(-1)[0] ?? '—'}
                    tone="neutral"
                    detail={[
                      entry.latency_ms ? `${entry.latency_ms}ms` : null,
                      entry.cost_usd ? `$${entry.cost_usd.toFixed(4)}` : null,
                    ].filter(Boolean).join(' · ') || undefined}
                  />
                ))
              ) : (
                <DataRow label="No prompt calls recorded" value="—" tone="neutral" />
              )}
            </CommandPanel>

            <CommandPanel eyebrow="Distribution" title="Calls by use case" description="AI call volume grouped by use case.">
              {useCaseCounts && Object.keys(useCaseCounts).length > 0 ? (
                Object.entries(useCaseCounts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([uc, count]) => (
                    <DataRow key={uc} label={uc} value={String(count)} tone="accent" />
                  ))
              ) : (
                <DataRow label="No usage data" value="—" tone="neutral" />
              )}
            </CommandPanel>
          </div>
        </>
      )}
    </div>
  );
}
