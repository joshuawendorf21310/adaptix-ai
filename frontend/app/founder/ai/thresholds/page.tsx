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

interface SystemHealth {
  active_alerts?: number;
  p95_latency_ms?: number;
  healthy?: number;
  degraded?: number;
  down?: number;
}

interface FounderSystem {
  ai_healthy?: boolean;
  bedrock_latency_p95?: number;
  daily_token_budget?: number;
  tokens_used_today?: number;
  error_rate?: number;
}

export default function ThresholdsPage() {
  const systemHealthState = useApi<SystemHealth>('/api/v1/system-health/dashboard');
  const founderSystemState = useApi<FounderSystem>('/api/founder/system');

  const loading = systemHealthState.loading || founderSystemState.loading;
  const health = systemHealthState.data;
  const sys = founderSystemState.data;

  const tokenPct =
    sys && sys.daily_token_budget && sys.tokens_used_today != null
      ? ((sys.tokens_used_today / sys.daily_token_budget) * 100).toFixed(1)
      : null;

  return (
    <div className="space-y-6 md:space-y-7">
      <CommandPageHeader
        eyebrow="AI Governance"
        title="AI Thresholds"
        description="Token budgets, latency thresholds, error rate limits, and alert configuration."
        status={
          <StatusPill
            label={loading ? 'Loading…' : sys?.ai_healthy === false ? 'AI degraded' : 'Healthy'}
            tone={loading ? 'neutral' : sys?.ai_healthy === false ? 'critical' : 'success'}
          />
        }
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <AdaptixCardSkeleton key={i} />)}
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="AI health"
              value={sys?.ai_healthy != null ? (sys.ai_healthy ? 'Healthy' : 'Degraded') : '—'}
              tone={sys?.ai_healthy ? 'success' : 'critical'}
            />
            <MetricTile
              label="P95 latency"
              value={sys?.bedrock_latency_p95 ? `${sys.bedrock_latency_p95}ms` : (health?.p95_latency_ms ? `${health.p95_latency_ms}ms` : '—')}
              tone={(sys?.bedrock_latency_p95 ?? health?.p95_latency_ms ?? 0) > 3000 ? 'warning' : 'success'}
            />
            <MetricTile
              label="Token usage"
              value={tokenPct ? `${tokenPct}%` : sys?.tokens_used_today != null ? String(sys.tokens_used_today) : '—'}
              detail={sys?.daily_token_budget ? `of ${sys.daily_token_budget.toLocaleString()} budget` : undefined}
              tone={tokenPct && parseFloat(tokenPct) > 80 ? 'warning' : 'success'}
            />
            <MetricTile
              label="Error rate"
              value={sys?.error_rate != null ? `${(sys.error_rate * 100).toFixed(2)}%` : '—'}
              tone={(sys?.error_rate ?? 0) > 0.05 ? 'critical' : 'success'}
            />
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <CommandPanel eyebrow="Threshold config" title="Operational thresholds" description="Configured limits and alerting thresholds for AI workloads.">
              <DataRow label="P95 latency limit" value="3,000ms" tone="neutral" detail="Alerts if exceeded" />
              <DataRow label="Error rate limit" value="5%" tone="neutral" detail="Alerts above this rate" />
              <DataRow
                label="Daily token budget"
                value={sys?.daily_token_budget ? sys.daily_token_budget.toLocaleString() : '—'}
                tone="accent"
              />
              <DataRow
                label="Tokens used today"
                value={sys?.tokens_used_today != null ? sys.tokens_used_today.toLocaleString() : '—'}
                tone={tokenPct && parseFloat(tokenPct) > 80 ? 'warning' : 'success'}
              />
            </CommandPanel>

            <CommandPanel eyebrow="Platform health" title="Service alerts" description="Active system health alerts impacting AI services.">
              <DataRow
                label="Active alerts"
                value={String(health?.active_alerts ?? '—')}
                tone={(health?.active_alerts ?? 0) > 0 ? 'critical' : 'success'}
              />
              <DataRow
                label="Healthy services"
                value={String(health?.healthy ?? '—')}
                tone="success"
              />
              <DataRow
                label="Degraded"
                value={String(health?.degraded ?? '—')}
                tone={(health?.degraded ?? 0) > 0 ? 'warning' : 'success'}
              />
              <DataRow
                label="Down"
                value={String(health?.down ?? '—')}
                tone={(health?.down ?? 0) > 0 ? 'critical' : 'success'}
              />
            </CommandPanel>
          </div>
        </>
      )}
    </div>
  );
}
