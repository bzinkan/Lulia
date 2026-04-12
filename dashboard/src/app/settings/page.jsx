'use client';
import { useEffect, useState, Suspense } from 'react';
import { Settings, Link2, CheckCircle, XCircle, ExternalLink, Calendar, Palette } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function SettingsWrapper() {
  return <Suspense fallback={<div className="animate-pulse h-96 bg-gray-200 rounded-[14px]" />}><SettingsPage /></Suspense>;
}

function SettingsPage() {
  const [googleConnected, setGoogleConnected] = useState(false);
  const [canvaConnected, setCanvaConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [justConnected, setJustConnected] = useState(false);
  const [justConnectedCanva, setJustConnectedCanva] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = window.location.search;
      if (params.includes('google=connected')) setJustConnected(true);
      if (params.includes('canva=connected')) setJustConnectedCanva(true);
    }
    checkStatus();
  }, []);

  async function checkStatus() {
    try {
      const [gData, cData] = await Promise.all([
        apiFetch('/api/v1/classroom/status'),
        apiFetch('/api/v1/canva/status'),
      ]);
      setGoogleConnected(gData.connected);
      setCanvaConnected(cData.connected);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function handleConnect() {
    window.location.href = 'http://localhost:8000/api/v1/classroom/auth/start';
  }

  async function handleDisconnect() {
    await apiFetch('/api/v1/classroom/disconnect', { method: 'POST' });
    setGoogleConnected(false);
  }

  async function handleCanvaConnect() {
    window.location.href = 'http://127.0.0.1:8000/api/v1/canva/auth/start';
  }

  async function handleCanvaDisconnect() {
    await apiFetch('/api/v1/canva/disconnect', { method: 'POST' });
    setCanvaConnected(false);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Manage your account and integrations</p>
      </div>

      {justConnected && (
        <div className="bg-green-50 border border-green-200 rounded-[14px] p-4 mb-6">
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle className="w-5 h-5" />
            <span className="font-medium">Google account connected successfully!</span>
          </div>
        </div>
      )}

      {justConnectedCanva && (
        <div className="bg-green-50 border border-green-200 rounded-[14px] p-4 mb-6">
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle className="w-5 h-5" />
            <span className="font-medium">Canva account connected successfully!</span>
          </div>
        </div>
      )}

      {/* Google Integration */}
      <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-orange-50 rounded-xl flex items-center justify-center">
            <Link2 className="w-5 h-5 text-orange-500" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Google Integration</h2>
            <p className="text-sm text-gray-500">Connect to Classroom, Drive, Calendar, Slides, and Forms</p>
          </div>
        </div>

        {loading ? (
          <div className="animate-pulse h-10 bg-gray-200 rounded-xl w-40" />
        ) : googleConnected ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span className="text-sm font-medium text-green-700">Connected</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Google Classroom', desc: 'Push assignments to students' },
                { label: 'Google Drive', desc: 'Store lesson plans and files' },
                { label: 'Google Calendar', desc: 'Sync lesson schedule' },
                { label: 'Google Slides', desc: 'Generate presentations' },
              ].map(s => (
                <div key={s.label} className="flex items-center gap-2 text-sm text-gray-600">
                  <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                  <span>{s.label}</span>
                </div>
              ))}
            </div>

            <button
              onClick={handleDisconnect}
              className="bg-white hover:bg-red-50 text-red-600 border border-red-200 px-4 py-2 rounded-xl font-medium text-sm transition-colors"
            >
              Disconnect Google Account
            </button>
          </div>
        ) : (
          <button
            onClick={handleConnect}
            className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-medium text-sm transition-colors flex items-center gap-2"
          >
            <ExternalLink className="w-4 h-4" />
            Connect Google Account
          </button>
        )}
      </div>

      {/* Canva Integration */}
      <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-purple-50 rounded-xl flex items-center justify-center">
            <Palette className="w-5 h-5 text-purple-500" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Canva Integration</h2>
            <p className="text-sm text-gray-500">Create professional designs, worksheets, and presentations</p>
          </div>
        </div>

        {loading ? (
          <div className="animate-pulse h-10 bg-gray-200 rounded-xl w-40" />
        ) : canvaConnected ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span className="text-sm font-medium text-green-700">Connected</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Create Designs', desc: 'Generate documents and posters' },
                { label: 'Presentations', desc: 'Build slide decks' },
                { label: 'Export to PDF', desc: 'Download finished materials' },
              ].map(s => (
                <div key={s.label} className="flex items-center gap-2 text-sm text-gray-600">
                  <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                  <span>{s.label}</span>
                </div>
              ))}
            </div>

            <button
              onClick={handleCanvaDisconnect}
              className="bg-white hover:bg-red-50 text-red-600 border border-red-200 px-4 py-2 rounded-xl font-medium text-sm transition-colors"
            >
              Disconnect Canva Account
            </button>
          </div>
        ) : (
          <button
            onClick={handleCanvaConnect}
            className="bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded-xl font-medium text-sm transition-colors flex items-center gap-2"
          >
            <ExternalLink className="w-4 h-4" />
            Connect Canva Account
          </button>
        )}
      </div>

      {/* Preferences */}
      <div className="bg-white rounded-[14px] p-6" style={{ border: '1px solid #E7E5E4' }}>
        <h2 className="text-lg font-semibold text-gray-900 mb-4" style={{ fontFamily: "'DM Serif Display', serif" }}>Preferences</h2>
        <div className="space-y-4">
          <label className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-gray-700">Auto-sync to Google Calendar</span>
              <p className="text-xs text-gray-400">Automatically push approved plans to your calendar</p>
            </div>
            <input type="checkbox" className="accent-orange-500 w-5 h-5" />
          </label>
          <label className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-gray-700">Auto-push to Classroom</span>
              <p className="text-xs text-gray-400">Automatically publish approved materials to Classroom</p>
            </div>
            <input type="checkbox" className="accent-orange-500 w-5 h-5" />
          </label>
        </div>
      </div>
    </div>
  );
}
