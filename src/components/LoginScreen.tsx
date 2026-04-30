import { type FormEvent, useState } from 'react';
import { Eye, EyeOff, LogIn, Moon, Sun } from 'lucide-react';
import { authApi, setAuthToken, setSessionUser, type AuthUser } from '../lib/api';
import logoWordmark from '../assets/dinamica-wordmark.svg';
import logoWordmarkDark from '../assets/dinamica-wordmark-dark.svg';
import { cn } from '../lib/utils';

type LoginScreenProps = {
  onLogin: (user: AuthUser, token: string) => void;
  themeMode: 'light' | 'dark';
  onToggleTheme: () => void;
};

export function LoginScreen({ onLogin, themeMode, onToggleTheme }: LoginScreenProps) {
  const isDark = themeMode === 'dark';
  const [email, setEmail] = useState('admin@dinamica.com');
  const [password, setPassword] = useState('admin');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');

    try {
      const response = await authApi.post('/login', { email, password });
      const user = response.data?.user as AuthUser | undefined;
      const token = response.data?.access_token as string | undefined;
      if (!user || !token) {
        throw new Error('Resposta de login inválida.');
      }
      setAuthToken(token);
      const enrichedUser: AuthUser = { ...user, name: (user as any).full_name || (user as any).name };
      setSessionUser(enrichedUser);
      onLogin(enrichedUser, token);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Não foi possível entrar.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={cn("min-h-screen overflow-hidden", isDark ? "bg-[#0F1115] text-slate-100" : "bg-[#EEF2F5] text-[#102A40]")}>
      <button
        onClick={onToggleTheme}
        className={cn(
          "fixed right-4 top-4 z-[80] rounded-full border px-3 py-2 text-xs font-bold shadow-lg backdrop-blur transition-all",
          isDark ? "border-slate-700 bg-slate-900/80 text-slate-100 hover:bg-slate-800" : "border-slate-200 bg-white/90 text-slate-700 hover:bg-slate-100"
        )}
        title={isDark ? "Ativar modo claro" : "Ativar modo escuro"}
      >
        <span className="inline-flex items-center gap-2">
          {isDark ? <Sun size={14} /> : <Moon size={14} />}
          {isDark ? 'Dia' : 'Noite'}
        </span>
      </button>
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[440px_minmax(0,1fr)]">
        <section className={cn(
          "relative flex flex-col justify-between border-r px-8 py-10 lg:px-14",
          isDark ? "border-slate-800 bg-[#11141A]" : "border-slate-200 bg-white"
        )}>
          <div className="inline-flex items-center gap-3">
            <img
              src={isDark ? logoWordmarkDark : logoWordmark}
              alt="Dinâmica Empreendimentos"
              className={cn("w-auto", isDark ? "h-12" : "h-14")}
            />
          </div>

          <div className="max-w-sm">
            <p className="mb-4 text-sm font-bold uppercase tracking-[0.24em] text-[#4CB232]">Acesso Seguro</p>
            <h1 className={cn("text-5xl font-black tracking-tight", isDark ? "text-slate-100" : "text-[#102A40]")}>Login</h1>
            <p className={cn("mt-5 text-sm leading-6", isDark ? "text-slate-400" : "text-slate-500")}>
              Entre com seu usuário administrativo para acessar o painel web restaurado e integrado ao FastAPI.
            </p>

            <form onSubmit={handleSubmit} className="mt-12 space-y-7">
              <label className="block">
                <span className="mb-3 block text-sm font-black text-[#4CB232]">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className={cn(
                    "w-full border-0 border-b bg-transparent px-0 py-3 text-lg outline-none transition focus:border-[#4CB232]",
                    isDark ? "border-slate-700 text-slate-100 placeholder:text-slate-500" : "border-slate-300 text-[#102A40] placeholder:text-slate-400"
                  )}
                  placeholder="admin@dinamica.com"
                  autoComplete="username"
                />
              </label>

              <label className="block">
                <span className="mb-3 block text-sm font-black text-[#4CB232]">Senha</span>
                <div className={cn("flex items-center gap-3 border-b", isDark ? "border-slate-700" : "border-slate-300")}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className={cn(
                      "w-full border-0 bg-transparent px-0 py-3 text-lg outline-none",
                      isDark ? "text-slate-100 placeholder:text-slate-500" : "text-[#102A40] placeholder:text-slate-400"
                    )}
                    placeholder="admin"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    className={cn("pb-1 text-slate-400 transition", isDark ? "hover:text-slate-100" : "hover:text-[#102A40]")}
                    aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </label>

              {error ? <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div> : null}

              <button
                type="submit"
                disabled={submitting}
                className="inline-flex w-full items-center justify-center gap-3 rounded-2xl bg-gradient-to-r from-[#3FAE2A] to-[#62BC3B] px-5 py-4 text-sm font-black uppercase tracking-[0.24em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
              >
                <LogIn size={16} />
                {submitting ? 'Entrando...' : 'Entrar'}
              </button>
            </form>
          </div>

          <div className={cn("text-xs", isDark ? "text-slate-400" : "text-slate-500")}>
            Usuário padrão semeado no banco:
            <span className={cn("ml-2 font-bold", isDark ? "text-slate-200" : "text-slate-700")}>admin@dinamica.com</span>
          </div>
        </section>

        <section className={cn(
          "relative hidden overflow-hidden lg:block",
          isDark
            ? "bg-[radial-gradient(circle_at_top,#173027,transparent_55%),linear-gradient(90deg,#121820_0%,#17202A_55%,#151b24_100%)]"
            : "bg-[radial-gradient(circle_at_top,#cde7d2,transparent_55%),linear-gradient(90deg,#f7fafc_0%,#edf3f7_55%,#e6edf3_100%)]"
        )}>
          <div className="absolute left-10 top-10 h-28 w-28 rounded-full border-8 border-[#4CB232]/90 bg-white shadow-[0_0_80px_rgba(76,178,50,0.18)]" />
          <div className="absolute right-36 top-20 h-12 w-12 rounded-full bg-gradient-to-br from-[#7DCA5D] to-[#4CB232] shadow-[0_0_40px_rgba(76,178,50,0.35)]" />
          <div className="absolute inset-x-20 top-24 h-[420px] rounded-[50%] border-[28px] border-[#E5F3E1] border-r-[#4CB232] border-b-transparent blur-[1px]" />
          <div className="absolute inset-x-24 top-40 h-[260px] rounded-[42px] border border-[#4CB232]/30 bg-white/90 shadow-[0_30px_80px_rgba(16,42,64,0.18)]">
            <div className="flex h-full">
              <div className="flex w-24 flex-col justify-center gap-4 border-r border-[#4CB232]/20 px-5">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="h-7 w-7 rounded-full bg-gradient-to-br from-[#7DCA5D] to-[#4CB232] shadow-inner shadow-white/20" />
                ))}
              </div>
              <div className="flex-1 p-9">
                <div className="mb-8 flex items-start justify-between">
                  <div className="space-y-3">
                    <div className="h-3 w-28 rounded-full bg-[#4CB232]" />
                    <div className="h-3 w-32 rounded-full bg-[#4CB232]" />
                    <div className="h-3 w-20 rounded-full bg-[#4CB232]" />
                  </div>
                  <div className="h-32 w-32 rounded-full border-8 border-[#4CB232] bg-[#4CB232]/15" />
                </div>
                <div className="space-y-5">
                  {[62, 74, 58].map((width, index) => (
                    <div key={width} className="flex items-center gap-3">
                      <div className="h-5 w-5 rounded-full bg-[#4CB232]" />
                      <div className="h-5 rounded-full bg-[#4CB232]" style={{ width: `${width}%` }} />
                      <div className="h-5 rounded-full bg-[#98D07E]/90" style={{ width: `${20 - index * 4}%` }} />
                    </div>
                  ))}
                </div>
                <div className="mt-10 grid grid-cols-3 gap-4">
                  {Array.from({ length: 3 }).map((_, index) => (
                    <div key={index} className="rounded-2xl border border-[#4CB232]/20 bg-[#F3F7FA] p-4">
                      <div className="h-4 w-4 rounded-full bg-[#4CB232]" />
                      <div className="mt-4 h-2 w-16 rounded-full bg-[#4CB232]" />
                      <div className="mt-2 h-2 w-12 rounded-full bg-[#98D07E]/80" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="absolute bottom-12 left-24 h-28 w-24 rounded-t-[30px] bg-gradient-to-b from-[#7DCA5D] to-[#4CB232] shadow-[0_14px_30px_rgba(76,178,50,0.2)]" />
          <div className="absolute bottom-12 left-40 h-20 w-16 rounded-t-[20px] bg-gradient-to-b from-[#B8E2A6] to-[#4CB232]" />
          <div className="absolute bottom-20 right-20 h-44 w-16 rounded-full bg-gradient-to-b from-[#4CB232] to-[#3C9828]" />
          <div className="absolute bottom-24 left-10 right-10 h-px bg-[#4CB232]/30" />
        </section>
      </div>
    </div>
  );
}
