import React, { useState } from 'react';
import { X, Building2, Lock, Mail, Sparkles, User as UserIcon } from 'lucide-react';
import { api, AuthResponse } from '../api/client';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (auth: AuthResponse) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgName, setOrgName] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      let res: AuthResponse;
      if (isRegister) {
        res = await api.register({
          org_name: orgName,
          org_slug: orgSlug,
          email,
          password,
          full_name: fullName,
        });
      } else {
        res = await api.login(email, password);
      }
      onSuccess(res);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemoAuth = async (slug: 'saas-alpha' | 'saas-beta') => {
    setLoading(true);
    setError(null);
    const demoEmail = slug === 'saas-alpha' ? 'cfo@alpha.io' : 'cfo@beta.io';
    const demoName = slug === 'saas-alpha' ? 'SaaS Alpha Technologies' : 'Beta Cloud Networks';
    const demoPass = 'DemoPassword123!';

    try {
      let res: AuthResponse;
      try {
        // Try logging in first
        res = await api.login(demoEmail, demoPass);
      } catch {
        // If account doesn't exist, auto-register
        res = await api.register({
          org_name: demoName,
          org_slug: slug,
          email: demoEmail,
          password: demoPass,
          full_name: `${slug === 'saas-alpha' ? 'Alpha' : 'Beta'} Finance Lead`,
        });
      }
      onSuccess(res);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Demo authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-5 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-4 h-4" />
        </button>

        <div>
          <h2 className="text-xl font-bold text-white flex items-center space-x-2">
            <Building2 className="w-5 h-5 text-emerald-400" />
            <span>{isRegister ? 'Register SaaS Organisation' : 'Sign in to Rekon'}</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            {isRegister
              ? 'Provision a new tenant account with scoped database isolation.'
              : 'Access your payment reconciliation workspaces.'}
          </p>
        </div>

        {/* Quick Demo Login Helpers */}
        <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
          <div className="text-[11px] font-medium text-slate-400 flex items-center space-x-1">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>One-Click Multi-Tenant Demo Sessions:</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleQuickDemoAuth('saas-alpha')}
              disabled={loading}
              className="px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-semibold transition text-left"
            >
              🏢 Tenant Alpha
              <span className="block text-[10px] text-slate-400 font-normal">cfo@alpha.io</span>
            </button>
            <button
              type="button"
              onClick={() => handleQuickDemoAuth('saas-beta')}
              disabled={loading}
              className="px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-lg text-xs font-semibold transition text-left"
            >
              🏢 Tenant Beta
              <span className="block text-[10px] text-slate-400 font-normal">cfo@beta.io</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {isRegister && (
            <>
              <div>
                <label className="block text-slate-300 font-medium mb-1">Company Name</label>
                <div className="relative">
                  <Building2 className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    required
                    value={orgName}
                    onChange={(e) => {
                      setOrgName(e.target.value);
                      if (!orgSlug) {
                        setOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '-'));
                      }
                    }}
                    placeholder="Acme SaaS Inc"
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Tenant Slug (unique URL handle)</label>
                <input
                  type="text"
                  required
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value.toLowerCase())}
                  placeholder="acme-saas"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Your Full Name</label>
                <div className="relative">
                  <UserIcon className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Rohan Sharma"
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-slate-300 font-medium mb-1">Email Address</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="finance@yourcompany.com"
                className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-1">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-emerald-500 hover:bg-emerald-600 font-semibold text-slate-950 rounded-lg transition disabled:opacity-50"
          >
            {loading ? 'Processing...' : isRegister ? 'Create Account & Organisation' : 'Sign In'}
          </button>
        </form>

        <div className="text-center pt-2 border-t border-slate-800 text-xs text-slate-400">
          {isRegister ? 'Already have an organisation?' : "Don't have an organisation yet?"}{' '}
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setError(null);
            }}
            className="text-emerald-400 hover:underline font-medium"
          >
            {isRegister ? 'Sign In' : 'Register New Organisation'}
          </button>
        </div>
      </div>
    </div>
  );
};
