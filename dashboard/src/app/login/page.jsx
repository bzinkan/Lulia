'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiFetch, setAuthToken } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null); setBusy(true);
    try {
      const path = mode === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register';
      const body = mode === 'login'
        ? { email: email.trim(), password }
        : { email: email.trim(), password, name: name.trim() };
      const res = await apiFetch(path, { method: 'POST', body: JSON.stringify(body) });
      if (!res?.access_token) throw new Error('No token in response');
      setAuthToken(res.access_token);
      router.push('/');
    } catch (err) {
      const msg = String(err?.message || 'Authentication failed');
      // Pull a friendlier message out of the FastAPI error body when we can.
      const m = msg.match(/"detail":"([^"]+)"/);
      setError(m ? m[1] : msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4"
      style={{ background: 'var(--warm-bg, #F5EDE0)' }}>
      <div className="w-full max-w-sm rounded-card p-8"
        style={{ background: 'var(--warm-card, white)', border: '1px solid var(--border, #E7E5E4)',
                 boxShadow: '0 8px 32px rgba(0,0,0,0.08)' }}>
        <h1 className="font-serif text-3xl mb-2" style={{ color: 'var(--coral, #D86C52)' }}>
          Lulia Lesson Lab
        </h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-mid, #78716C)' }}>
          {mode === 'login' ? 'Sign in to continue.' : 'Create your teacher account.'}
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {mode === 'register' && (
            <Field label="Your name">
              <input className="auth-input" type="text" required minLength={1} maxLength={120}
                value={name} onChange={e => setName(e.target.value)}
                placeholder="e.g. Sarah Johnson" autoComplete="name" />
            </Field>
          )}
          <Field label="Email">
            <input className="auth-input" type="email" required
              value={email} onChange={e => setEmail(e.target.value)}
              placeholder="you@school.edu" autoComplete="email" />
          </Field>
          <Field label="Password">
            <input className="auth-input" type="password" required minLength={mode === 'register' ? 8 : 1} maxLength={72}
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder={mode === 'register' ? 'At least 8 characters' : 'Your password'}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
          </Field>

          {error && (
            <div className="text-sm rounded-md p-2" style={{ background: '#FEF2F2', color: '#B91C1C' }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={busy}
            className="rounded-lg py-2.5 mt-2 font-semibold text-white"
            style={{ background: 'var(--coral, #D86C52)', opacity: busy ? 0.6 : 1, cursor: busy ? 'not-allowed' : 'pointer' }}>
            {busy ? '…' : (mode === 'login' ? 'Sign in' : 'Create account')}
          </button>
        </form>

        <div className="mt-5 text-center text-sm" style={{ color: 'var(--text-mid, #78716C)' }}>
          {mode === 'login' ? (
            <>New to Lulia?{' '}
              <button onClick={() => { setMode('register'); setError(null); }}
                className="font-semibold underline" style={{ color: 'var(--coral, #D86C52)' }}>
                Create an account
              </button>
            </>
          ) : (
            <>Already have an account?{' '}
              <button onClick={() => { setMode('login'); setError(null); }}
                className="font-semibold underline" style={{ color: 'var(--coral, #D86C52)' }}>
                Sign in
              </button>
            </>
          )}
        </div>

        <style jsx>{`
          .auth-input {
            width: 100%;
            border: 1px solid var(--border, #E7E5E4);
            background: white;
            border-radius: 10px;
            padding: 10px 12px;
            font-size: 14px;
            outline: none;
            font-family: inherit;
            color: var(--text-dark, #1C1917);
          }
          .auth-input:focus {
            border-color: var(--coral, #D86C52);
            box-shadow: 0 0 0 3px rgba(216,108,82,0.12);
          }
        `}</style>
      </div>
    </div>
  );
}


function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-bold uppercase tracking-wider"
        style={{ color: 'var(--text-mid, #78716C)' }}>
        {label}
      </span>
      {children}
    </label>
  );
}
