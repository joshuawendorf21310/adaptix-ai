"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { PlatformShell } from '@/components/PlatformShell';

const LINKS = [
  { href: '/ai', label: 'AI Home' },
  { href: '/founder/ai/policies', label: 'Policies' },
  { href: '/founder/ai/prompt-editor', label: 'Prompt Editor' },
  { href: '/founder/ai/review-queue', label: 'Review Queue' },
  { href: '/founder/ai/thresholds', label: 'Thresholds' },
];

export default function FounderLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const breadcrumbs = <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center' }}><div><div style={{ color: 'var(--color-brand-orange)', fontSize: '.75rem', textTransform: 'uppercase' }}>Adaptix AI</div><h1 style={{ margin: '.35rem 0' }}>Founder AI Governance</h1></div><nav style={{ display: 'flex', gap: '.75rem', flexWrap: 'wrap' }}>{LINKS.map((link) => <Link key={link.href} href={link.href} style={{ textDecoration: pathname.startsWith(link.href) ? 'underline' : 'none' }}>{link.label}</Link>)}</nav></div>;
  return <PlatformShell breadcrumbs={breadcrumbs}>{children}</PlatformShell>;
}
