import React, { useRef, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { ChevronRight, LogOut, User } from 'lucide-react';
import { Camera, Loader2, Lock, Save, X } from 'lucide-react';
import { resolveUrl } from '../../services/api';
import type { AuthUser } from '../../services/auth-api';
import { changePassword, updateProfile, uploadAvatar } from '../../services/auth-api';

interface HeaderProps {
  breadcrumbs?: string[];
  activeTab: string;
  onNavigate: (tab: string) => void;
  onClearSearch: () => void;
  showTabs?: boolean;
  user?: AuthUser | null;
  onLogout?: () => void;
  onUserUpdated?: (user: AuthUser) => void;
}

type AccountSettingsProps = {
  user: AuthUser;
  onClose: () => void;
  onUserUpdated?: (user: AuthUser) => void;
};

const friendlyError = (error: unknown) => {
  if (!(error instanceof Error)) return 'Something went wrong';
  try {
    const parsed = JSON.parse(error.message) as { detail?: string | { msg?: string }[] };
    if (typeof parsed.detail === 'string') return parsed.detail;
    if (Array.isArray(parsed.detail) && parsed.detail[0]?.msg) return parsed.detail[0].msg;
  } catch {
    return error.message;
  }
  return error.message;
};

function AccountSettings({ user, onClose, onUserUpdated }: AccountSettingsProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(user.name);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [busy, setBusy] = useState<'avatar' | 'profile' | 'password' | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const initials =
    user.name
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'U';

  const run = async (
    kind: 'avatar' | 'profile' | 'password',
    action: () => Promise<AuthUser>,
    okMessage: string,
  ) => {
    setBusy(kind);
    setError('');
    setMessage('');
    try {
      const updated = await action();
      onUserUpdated?.(updated);
      setMessage(okMessage);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(null);
    }
  };

  const handleAvatar = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    void run('avatar', () => uploadAvatar(file), 'Profile photo updated');
    event.target.value = '';
  };

  const saveProfile = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run('profile', () => updateProfile(name.trim()), 'Profile saved');
  };

  const savePassword = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run(
      'password',
      async () => {
        const updated = await changePassword(currentPassword, newPassword);
        setCurrentPassword('');
        setNewPassword('');
        return updated;
      },
      'Password changed',
    );
  };

  return (
    <div className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
      <section className="w-full max-w-lg rounded-2xl border border-white/10 bg-navy-mid/95 p-5 shadow-[0_30px_80px_rgba(0,0,0,0.65)]">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[2px] text-secondary">Account</p>
            <h2 className="font-serif text-3xl font-black tracking-tighter text-white">Profile Settings</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 text-on-surface-variant transition-colors hover:bg-white/10 hover:text-white" aria-label="Close account settings">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && <div className="mb-4 rounded-xl border border-red-500/25 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</div>}
        {message && <div className="mb-4 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{message}</div>}

        <div className="mb-5 flex items-center gap-4 rounded-xl border border-white/10 bg-black/25 p-3">
          <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-black/50">
            {user.avatar_url ? (
              <img src={resolveUrl(user.avatar_url)} alt={user.name} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center font-mono text-xl font-bold text-secondary">{initials}</div>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-[11px] uppercase tracking-[1.5px] text-on-surface-variant">{user.email}</p>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={handleAvatar} />
            <button type="button" onClick={() => fileRef.current?.click()} disabled={busy === 'avatar'} className="mt-2 inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-on-surface transition-colors hover:bg-white/10 disabled:opacity-60">
              {busy === 'avatar' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Camera className="h-3.5 w-3.5" />}
              Upload Photo
            </button>
          </div>
        </div>

        <form onSubmit={saveProfile} className="space-y-3">
          <label className="flex items-center gap-3 rounded-xl border border-white/5 bg-black/40 p-3.5">
            <User className="h-5 w-5 shrink-0 text-orange-glow" />
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" minLength={2} maxLength={120} required className="w-full border-none bg-transparent text-md font-light text-on-surface placeholder:text-outline-variant focus:outline-none focus:ring-0" />
          </label>
          <button type="submit" disabled={busy === 'profile'} className="flex w-full items-center justify-center gap-2 rounded-xl bg-orange-glow py-3 font-mono text-[11px] font-black uppercase tracking-widest text-white transition-all hover:bg-[#E0784C] disabled:opacity-60">
            {busy === 'profile' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save Profile
          </button>
        </form>

        <form onSubmit={savePassword} className="mt-5 space-y-3 border-t border-white/10 pt-5">
          <label className="flex items-center gap-3 rounded-xl border border-white/5 bg-black/40 p-3.5">
            <Lock className="h-5 w-5 shrink-0 text-orange-glow" />
            <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} placeholder="Current password" minLength={1} maxLength={128} required className="w-full border-none bg-transparent text-md font-light text-on-surface placeholder:text-outline-variant focus:outline-none focus:ring-0" />
          </label>
          <label className="flex items-center gap-3 rounded-xl border border-white/5 bg-black/40 p-3.5">
            <Lock className="h-5 w-5 shrink-0 text-orange-glow" />
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="New password" minLength={8} maxLength={128} required className="w-full border-none bg-transparent text-md font-light text-on-surface placeholder:text-outline-variant focus:outline-none focus:ring-0" />
          </label>
          <button type="submit" disabled={busy === 'password'} className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 py-3 font-mono text-[11px] font-black uppercase tracking-widest text-on-surface transition-all hover:bg-white/10 disabled:opacity-60">
            {busy === 'password' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />}
            Change Password
          </button>
        </form>
      </section>
    </div>
  );
}

export default function Header({
  breadcrumbs,
  activeTab,
  onNavigate,
  onClearSearch,
  showTabs = true,
  user,
  onLogout,
  onUserUpdated,
}: HeaderProps) {
  const [showAccountSettings, setShowAccountSettings] = useState(false);
  const initials =
    user?.name
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'U';

  return (
    <>
      <header className="fixed top-0 left-0 w-full z-[1000] bg-navy-mid/75 backdrop-blur-[20px] shadow-[0_40px_80px_rgba(0,0,0,0.4)] border-b border-white/5">
        <div className="flex justify-between items-center h-20 px-8 md:px-16 w-full max-w-[1920px] mx-auto">
          <div className="flex items-center gap-8">
            <div onClick={onClearSearch} className="flex items-center gap-3 cursor-pointer group">
              <span className="font-serif text-2xl font-black tracking-tighter">
                <span className="text-white group-hover:text-primary transition-colors">Drill</span>
                <span className="text-[#ff6b35] group-hover:text-secondary transition-colors">Down</span>
              </span>
            </div>

            {breadcrumbs && breadcrumbs.length > 0 && (
              <nav className="hidden md:flex items-center gap-2 text-on-surface-variant font-mono text-xs tracking-wider">
                {breadcrumbs.map((crumb, idx) => (
                  <React.Fragment key={idx}>
                    {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-outline/50" />}
                    <span
                      className={`${
                        idx === breadcrumbs.length - 1
                          ? 'text-secondary font-bold font-mono'
                          : 'hover:text-primary cursor-pointer transition-colors'
                      }`}
                    >
                      {crumb}
                    </span>
                  </React.Fragment>
                ))}
              </nav>
            )}
          </div>

          {showTabs && (
            <nav className="hidden md:flex items-center gap-6">
              {[
                { id: 'explore', label: 'Explore' },
                { id: 'history', label: 'History' },
              ].map((link) => (
                <button
                  key={link.id}
                  onClick={() => onNavigate(link.id)}
                  className={`font-mono text-xs uppercase tracking-[2px] transition-all py-1.5 px-3 rounded-md cursor-pointer ${
                    activeTab === link.id
                      ? 'text-secondary border-b-2 border-secondary font-bold'
                      : 'text-on-surface-variant hover:text-primary hover:bg-white/5'
                  }`}
                >
                  {link.label}
                </button>
              ))}
            </nav>
          )}

          <div className="flex items-center gap-4 text-primary">
            {user && (
              <span className="hidden sm:inline font-mono text-[10px] uppercase tracking-[1.5px] text-on-surface-variant max-w-[160px] truncate">
                {user.name}
              </span>
            )}
            <button
              type="button"
              onClick={() => user && setShowAccountSettings(true)}
              className="hover:bg-white/5 p-1.5 rounded-full cursor-pointer transition-colors text-on-surface-variant hover:text-primary"
              title="Account settings"
              aria-label="Account settings"
            >
              {user?.avatar_url ? (
                <img
                  src={resolveUrl(user.avatar_url)}
                  alt={user.name}
                  className="h-8 w-8 rounded-full border border-white/10 object-cover"
                />
              ) : user ? (
                <span className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-black/40 font-mono text-[11px] font-bold text-secondary">
                  {initials}
                </span>
              ) : (
                <User className="w-5 h-5" />
              )}
            </button>
            {onLogout && (
              <button
                onClick={onLogout}
                className="hover:bg-white/5 p-2 rounded-full cursor-pointer transition-colors text-on-surface-variant hover:text-secondary"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      </header>

      {user && showAccountSettings && (
        <AccountSettings
          user={user}
          onClose={() => setShowAccountSettings(false)}
          onUserUpdated={(updatedUser) => {
            onUserUpdated?.(updatedUser);
          }}
        />
      )}
    </>
  );
}
