'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { PlatformShell } from '@/components/PlatformShell';

/**
 * AI Portal Layout Shell
 *
 * Provides the navigation structure and routing for all AI modules.
 * Migrated to PlatformShell for unified navigation experience.
 *
 * AI Portal uses purple/magenta branding for intelligent platform features:
 * - Visibility: Operational intelligence and access control
 * - ROI Engine: Live value modeling and operational inputs
 * - System Registry: AI-assisted surfaces architecture
 * - Command Health: Service posture and readiness tracking
 */
export default function AILayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const links = [
    { href: '/ai', label: 'Overview' },
    { href: '/founder/ai/policies', label: 'Policies' },
    { href: '/founder/ai/prompt-editor', label: 'Prompt Editor' },
    { href: '/founder/ai/review-queue', label: 'Review Queue' },
    { href: '/founder/ai/thresholds', label: 'Thresholds' },
  ];

  // Extract current module from pathname for breadcrumbs
  const pathSegments = pathname.split('/').filter(Boolean);
  const currentModule = pathSegments[1] || 'overview';

  // Module display names for breadcrumbs
  const moduleNames: Record<string, string> = {
    overview: 'Overview',
    visibility: 'Visibility',
    roi: 'ROI Engine',
    systems: 'System Registry',
    'command-center': 'Command Health',
  };

  // Build breadcrumbs component with AI branding
  const breadcrumbs = (
    <div className="space-y-3">
      {/* AI Portal Branding */}
      <div className="flex items-center gap-3">
        <div
          className="flex h-10 w-10 items-center justify-center chamfer-8"
          style={{
            background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.18), rgba(236, 72, 153, 0.12))',
            border: '1px solid rgba(168, 85, 247, 0.3)',
          }}
        >
          <span className="text-xl">🤖</span>
        </div>
        <div>
          <h1
            className="label-caps"
            style={{
              fontSize: 'var(--text-h3)',
              color: 'var(--color-ai-magenta)',
            }}
          >
            AI Intelligence
          </h1>
          <p className="micro-caps">Intelligent platform features and insights</p>
        </div>

        {/* Breadcrumbs */}
        {pathSegments.length > 1 && (
          <div className="hidden items-center gap-2 md:flex">
            <span className="text-[var(--color-text-muted)]">/</span>
            <span className="label-caps text-[var(--color-text-secondary)]">
              {moduleNames[currentModule] || currentModule}
            </span>
            {pathSegments.length > 2 && (
              <>
                <span className="text-[var(--color-text-muted)]">/</span>
                <span className="label-caps text-[var(--color-text-secondary)]">
                  {pathSegments[2] === 'new' ? 'New' : pathSegments[2]}
                </span>
              </>
            )}
          </div>
        )}
      </div>

      {/* AI Navigation */}
      <div className="flex flex-wrap items-center gap-3">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="command-panel"
            style={{
              padding: '0.55rem 0.9rem',
              textDecoration: pathname === link.href ? 'underline' : 'none',
            }}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </div>
  );

  return (
    <PlatformShell breadcrumbs={breadcrumbs}>
      {children}
    </PlatformShell>
  );
}
