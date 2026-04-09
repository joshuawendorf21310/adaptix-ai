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
  use_case?: string;
  model_id?: string;
  input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  cost_usd?: number;
  status?: string;
  created_at?: string;
}

const STATUS_TONE: Record<string, 'success' | 'warning' | 'critical' | 'neutral'> = {
  success: 'success',
  completed: 'success',
  error: 'critical',
  failed: 'critical',
  pending: 'warning',
  processing: 'warning',
};

export default function ReviewQueuePage() {
  const { data: log, loading, error } = useApi<PromptLogEntry[]>('/api/v1/ai/prompt-log?limit=50');

  const pendingEntries = log?.filter((e) => ['pending', 'processing'].includes(e.status ?? '')) ?? [];
  const errorEntries = log?.filter((e) => ['error', 'failed'].includes(e.status ?? '')) ?? [];
  const totalCost = log?.reduce((s, e) => s + (e.cost_usd ?? 0), 0) ?? 0;

  return (
    <div className="space-y-6 md:space-y-7">
      <CommandPageHeader
        eyebrow="AI Governance"
        title="Review Queue"
        description="Monitor and triage AI prompt calls — pending, failed, and completed."
        status={
          <StatusPill
            label={loading ? 'Loading…' : error ? 'Error' : errorEntries.length > 0 ? 'Errors detected' : 'Healthy'}
            tone={loading ? 'neutral' : error ? 'critical' : errorEntries.length > 0 ? 'warning' : 'success'}
          />
        }
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <AdaptixCardSkeleton key={i} />)}
        </div>
      ) : error ? (
        <p className="text-sm text-red-400">Error loading prompt log: {error}</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile label="Total calls" value={String(log?.length ?? 0)} tone="info" />
            <MetricTile label="Pending" value={String(pendingEntries.length)} tone={pendingEntries.length > 0 ? 'warning' : 'success'} />
            <MetricTile label="Errors" value={String(errorEntries.length)} tone={errorEntries.length > 0 ? 'critical' : 'success'} />
            <MetricTile label="Total cost" value={`$${totalCost.toFixed(4)}`} tone="accent" />
          </div>

          {errorEntries.length > 0 && (
            <CommandPanel eyebrow="Errors" title="Failed calls" description="Prompt calls that resulted in errors — review and retry as needed.">
              {errorEntries.map((e) => (
                <DataRow
                  key={e.id}
                  label={e.use_case ?? 'unknown'}
                  value={e.status ?? 'error'}
                  tone="critical"
                  detail={e.created_at ? new Date(e.created_at).toLocaleString() : undefined}
                />
              ))}
            </CommandPanel>
          )}

          <CommandPanel eyebrow="All calls" title="Prompt log" description="Complete AI call log for the current period.">
            {log && log.length > 0 ? (
              log.map((entry) => (
                <DataRow
                  key={entry.id}
                  label={entry.use_case ?? 'unknown'}
                  value={<StatusPill label={entry.status ?? 'ok'} tone={STATUS_TONE[entry.status ?? ''] ?? 'neutral'} />}
                  tone={STATUS_TONE[entry.status ?? ''] ?? 'neutral'}
                  detail={[
                    entry.latency_ms ? `${entry.latency_ms}ms` : null,
                    entry.model_id?.split('.').slice(-1)[0] ?? null,
                  ].filter(Boolean).join(' · ') || undefined}
                />
              ))
            ) : (
              <DataRow label="No calls in log" value="—" tone="neutral" />
            )}
          </CommandPanel>
        </>
      )}
    </div>
  );
}
