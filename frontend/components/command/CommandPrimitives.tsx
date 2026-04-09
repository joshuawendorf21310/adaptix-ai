import * as React from 'react';
import clsx from 'clsx';

type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'critical' | 'info';

function toneStyles(tone: Tone) {
  switch (tone) {
    case 'accent': return { color: 'var(--color-brand-orange)', border: 'rgba(255,106,0,0.26)', background: 'rgba(255,106,0,0.10)' };
    case 'success': return { color: 'var(--color-status-active)', border: 'rgba(34,197,94,0.24)', background: 'rgba(34,197,94,0.10)' };
    case 'warning': return { color: 'var(--color-status-warning)', border: 'rgba(245,158,11,0.24)', background: 'rgba(245,158,11,0.10)' };
    case 'critical': return { color: 'var(--color-brand-red)', border: 'rgba(255,45,45,0.24)', background: 'rgba(255,45,45,0.10)' };
    case 'info': return { color: 'var(--color-status-info)', border: 'rgba(56,189,248,0.24)', background: 'rgba(56,189,248,0.10)' };
    default: return { color: 'var(--color-text-secondary)', border: 'var(--color-border-default)', background: 'rgba(255,255,255,0.03)' };
  }
}

export function StatusPill({ label, tone = 'neutral', className }: { label: string; tone?: Tone; className?: string }) { const styles = toneStyles(tone); return <span className={clsx('inline-flex items-center gap-2 border px-3 py-1.5', className)} style={{ color: styles.color, borderColor: styles.border, background: styles.background, borderRadius: 999 }}><span className="h-1.5 w-1.5 rounded-full" style={{ background: styles.color, display: 'inline-block' }} />{label}</span>; }
export function CommandPageHeader({ eyebrow, title, description, status }: { eyebrow: string; title: string; description: string; status?: React.ReactNode }) { return <section className="plate-card"><div style={{ display: 'grid', gap: '.75rem' }}><div style={{ textTransform: 'uppercase', letterSpacing: '.12em', fontSize: '.72rem', color: 'var(--color-brand-orange)', fontWeight: 700 }}>{eyebrow}</div><div style={{ display: 'flex', gap: '.75rem', flexWrap: 'wrap', alignItems: 'center' }}><h1 style={{ margin: 0 }}>{title}</h1>{status}</div><p className="text-text-secondary">{description}</p></div></section>; }
export function CommandPanel({ eyebrow, title, description, children }: { eyebrow?: string; title: string; description?: string; children: React.ReactNode }) { return <section className="plate-card"><div style={{ marginBottom: '1rem' }}>{eyebrow ? <div style={{ textTransform: 'uppercase', letterSpacing: '.12em', fontSize: '.72rem', color: 'var(--color-text-muted)', fontWeight: 700 }}>{eyebrow}</div> : null}<h2 style={{ margin: '.35rem 0' }}>{title}</h2>{description ? <p className="text-text-secondary">{description}</p> : null}</div>{children}</section>; }
export function MetricTile({ label, value, detail, tone = 'neutral' }: { label: string; value: string; detail?: string; tone?: Tone }) { const styles = toneStyles(tone); return <div className="plate-card"><div style={{ textTransform: 'uppercase', letterSpacing: '.12em', fontSize: '.72rem', color: 'var(--color-text-muted)', fontWeight: 700 }}>{label}</div><div style={{ marginTop: '.5rem', fontSize: '1.75rem', fontWeight: 800, color: styles.color }}>{value}</div>{detail ? <div className="text-text-muted" style={{ marginTop: '.35rem', fontSize: '.85rem' }}>{detail}</div> : null}</div>; }
export function DataRow({ label, value, tone = 'neutral', detail }: { label: string; value: React.ReactNode; tone?: Tone; detail?: string }) { const styles = toneStyles(tone); return <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', padding: '.75rem 0', borderBottom: '1px solid rgba(255,255,255,.06)' }}><div><div>{label}</div>{detail ? <div className="text-text-muted" style={{ fontSize: '.85rem', marginTop: '.25rem' }}>{detail}</div> : null}</div><div style={{ color: styles.color, fontWeight: 700 }}>{value}</div></div>; }
