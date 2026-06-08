export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center">
          <span className="text-xl font-semibold tracking-tight text-slate-900">WhatsAgent AI</span>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">{children}</div>
      </div>
    </div>
  );
}
