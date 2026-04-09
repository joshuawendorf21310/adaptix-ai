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

interface AuditSummary {
  total_prompts?: number;
  active_prompts?: number;
  guardrails_enabled?: boolean;
  pii_masking_enabled?: boolean;
  rate_limit_per_minute?: number;
  prompts?: Array<{
    id: string;
    name?: string;
    use_case?: string;
    is_active?: boolean;
    version?: number;
    created_at?: string;
  }>;
}

export default function PoliciesPage() {
  const { data: audit, loading, error } = useApi<AuditSummary>('/ai/prompts/audit');

  return (
    <div className="space-y-6 md:space-y-7">
      <CommandPageHeader
        eyebrow="AI Governance"
        title="AI Policies"
        description="Guardrails, PII masking, rate limits, and active prompt policy configuration."
        status={
          <StatusPill
            label={loading ? 'Loading…' : error ? 'Error' : 'Live'}
            tone={loading ? 'neutral' : error ? 'critical' : 'info'}
          />
        }
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <AdaptixCardSkeleton key={i} />)}
        </div>
      ) : error ? (
        <p className="text-sm text-red-400">Error loading AI policies: {error}</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile label="Active prompts" value={String(audit?.active_prompts ?? '—')} tone="info" />
            <MetricTile label="Total prompts" value={String(audit?.total_prompts ?? '—')} tone="accent" />
            <MetricTile
              label="Guardrails"
              value={audit?.guardrails_enabled != null ? (audit.guardrails_enabled ? 'Enabled' : 'Disabled') : '—'}
              tone={audit?.guardrails_enabled ? 'success' : 'warning'}
            />
            <MetricTile
              label="Rate limit"
              value={audit?.rate_limit_per_minute ? `${audit.rate_limit_per_minute}/min` : '—'}
              tone="neutral"
            />
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <CommandPanel eyebrow="Security" title="Policy controls" description="Active AI security and compliance controls.">
              <DataRow
                label="Guardrails"
                value={audit?.guardrails_enabled != null ? (audit.guardrails_enabled ? 'Enabled' : 'Disabled') : '—'}
                tone={audit?.guardrails_enabled ? 'success' : 'warning'}
              />
              <DataRow
                label="PII masking"
                value={audit?.pii_masking_enabled != null ? (audit.pii_masking_enabled ? 'Enabled' : 'Disabled') : '—'}
                tone={audit?.pii_masking_enabled ? 'success' : 'warning'}
              />
              <DataRow
                label="Rate limit"
                value={audit?.rate_limit_per_minute ? `${audit.rate_limit_per_minute} req/min` : '—'}
                tone="neutral"
              />
            </CommandPanel>

            <CommandPanel eyebrow="Prompts" title="Active system prompts" description="Currently active prompts across use cases.">
              {audit?.prompts && audit.prompts.length > 0 ? (
                audit.prompts
                  .filter((p) => p.is_active)
                  .map((p) => (
                    <DataRow
                      key={p.id}
                      label={p.name ?? p.use_case ?? p.id}
                      value={`v${p.version ?? 1}`}
                      tone="success"
                      detail={p.use_case}
                    />
                  ))
              ) : (
                <DataRow label="No active prompts" value="—" tone="neutral" />
              )}
            </CommandPanel>
          </div>
        </>
      )}
    </div>
  );
}
