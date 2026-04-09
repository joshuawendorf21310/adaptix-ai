'use client';
import Link from 'next/link';
import { motion } from 'motion/react';

const LINKS = [
  { href: '/founder/ai/policies', label: 'AI Policies', desc: 'Configure AI behavior rules, guardrails, and output constraints', color: 'var(--color-system-compliance)' },
  { href: '/founder/ai/prompt-editor', label: 'Prompt Editor', desc: 'Edit and version system prompts for each AI use case', color: 'var(--color-system-compliance)' },
  { href: '/founder/ai/thresholds', label: 'Confidence Thresholds', desc: 'Set minimum confidence scores for AI auto-actions', color: 'var(--color-system-compliance)' },
  { href: '/founder/ai/review-queue', label: 'AI Review Queue', desc: 'Human-in-the-loop review for low-confidence AI decisions', color: 'var(--color-system-compliance)' },
];

export default function AIPage() {
  return (
    <div className="p-5 space-y-6">
      <div>
        <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-orange-dim mb-1">DOMAIN 3 · AI GOVERNANCE</div>
        <h1 className="text-xl font-black uppercase tracking-wider text-text-primary">AI Governance</h1>
        <p className="text-xs text-text-muted mt-0.5">Policies · prompt editor · confidence thresholds · review queue</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {LINKS.map((l, i) => (
          <motion.div key={l.href} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
            <Link href={l.href} className="block bg-bg-panel border border-border-DEFAULT p-5 hover:border-[rgba(255,255,255,0.18)] transition-colors" style={{ clipPath: 'polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 0 100%)' }}>
              <div className="text-sm font-bold mb-1" style={{ color: l.color }}>{l.label}</div>
              <div className="text-xs text-[rgba(255,255,255,0.45)]">{l.desc}</div>
            </Link>
          </motion.div>
        ))}
      </div>
      <Link href="/founder" className="text-xs text-orange-dim hover:text-orange">← Back to Platform Command</Link>
    </div>
  );
}

