"use client";

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { loginDev } from '@/services/auth';

export default function AccessPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState('00000000-0000-0000-0000-000000000001');
  const [userId, setUserId] = useState('00000000-0000-0000-0000-000000000401');
  const [role, setRole] = useState('founder');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true); setError('');
    try { await loginDev({ tenant_id: tenantId, user_id: userId, role }); router.push('/founder/ai/policies'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to sign in'); }
    finally { setSubmitting(false); }
  }

  return <main className="platform-shell"><div className="platform-shell__inner"><form className="plate-card" onSubmit={onSubmit} style={{ maxWidth: 640, margin: '2rem auto', display: 'grid', gap: '1rem' }}><h1>Developer Access</h1><label>Tenant ID<input value={tenantId} onChange={(e) => setTenantId(e.target.value)} style={{ width: '100%' }} /></label><label>User ID<input value={userId} onChange={(e) => setUserId(e.target.value)} style={{ width: '100%' }} /></label><label>Role<select value={role} onChange={(e) => setRole(e.target.value)}><option value="founder">founder</option><option value="admin">admin</option><option value="viewer">viewer</option></select></label>{error ? <div style={{ color: '#fca5a5' }}>{error}</div> : null}<button type="submit" disabled={submitting}>{submitting ? 'Signing in…' : 'Create session'}</button></form></div></main>;
}
