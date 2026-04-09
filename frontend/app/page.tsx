import Link from 'next/link';

export default function HomePage() {
  return <main className="platform-shell"><div className="platform-shell__inner plate-card"><h1>Adaptix AI</h1><p>Standalone AI governance shell for prompts, policies, review queue, and thresholds.</p><div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}><Link href="/access">Developer Access</Link><Link href="/founder/ai/policies">AI Policies</Link></div></div></main>;
}