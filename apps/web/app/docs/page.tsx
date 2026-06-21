import Link from "next/link";

export const metadata = {
  title: "Docs — WhatsAgent AI",
  description: "How WhatsAgent works, how to onboard, and what the API does.",
};

const SECTIONS = [
  {
    id: "overview",
    title: "Overview",
    body: (
      <>
        <p>
          WhatsAgent is an AI agent platform for WhatsApp. You connect your WhatsApp
          Business API number, train an agent on your FAQ + offer, and the agent
          handles inbound conversations 24/7 — qualifying, booking, and routing
          escalations to your team.
        </p>
        <p>Three things every business gets day-one:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>An always-on AI agent on your WhatsApp number</li>
          <li>A lead inbox with full conversation history and tagging</li>
          <li>Analytics on volume, qualified-lead rate, and response time</li>
        </ul>
      </>
    ),
  },
  {
    id: "onboarding",
    title: "Onboarding (48-hour go-live)",
    body: (
      <>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            <strong>Sign up</strong> at <Link className="underline" href="/signup">/signup</Link>.
            One business per account; you can invite teammates after.
          </li>
          <li>
            <strong>Run through the 6-step wizard</strong> at <code>/onboarding</code> —
            business details, agent persona, knowledge base, WhatsApp connect, test
            conversation, go-live toggle.
          </li>
          <li>
            <strong>Connect WhatsApp Business API</strong> — provide your WABA ID +
            phone-number ID + permanent access token. If you don't have a WABA yet,
            email <a className="underline" href="mailto:hello@influnexus.com">hello@influnexus.com</a> and
            we'll handle Meta verification for you.
          </li>
          <li>
            <strong>Upload knowledge</strong> — PDFs, FAQ, product pricing, refund
            policy. The agent grounds replies on this corpus.
          </li>
          <li>
            <strong>Test</strong> in the inbox with the built-in simulator before
            flipping live.
          </li>
        </ol>
      </>
    ),
  },
  {
    id: "agents",
    title: "Agent types",
    body: (
      <ul className="list-disc space-y-1 pl-5">
        <li>
          <strong>Sales agent</strong> — qualifies inbound, asks budget/timeline
          questions, books calls, hands off hot leads
        </li>
        <li>
          <strong>Support agent</strong> — resolves FAQ + order-status queries,
          escalates anything ambiguous
        </li>
        <li>
          <strong>Follow-up agent</strong> — nudges cold leads on day 2/5/14 based
          on last message
        </li>
      </ul>
    ),
  },
  {
    id: "api",
    title: "API",
    body: (
      <>
        <p>
          Base URL: <code>https://api.whatsagent.ai/api/v1</code>. Auth is cookie-based
          via <code>POST /auth/login</code>. Every business-scoped route follows the
          pattern <code>/{`{resource}`}/{`{business_id}`}/{`{action}`}</code>.
        </p>
        <table className="w-full text-sm">
          <thead className="border-b text-left text-slate-600">
            <tr>
              <th className="py-1 pr-4">Endpoint</th>
              <th className="py-1">Purpose</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <tr>
              <td className="py-1 pr-4 font-mono text-xs">POST /auth/signup</td>
              <td className="py-1">Create user + business in one call</td>
            </tr>
            <tr>
              <td className="py-1 pr-4 font-mono text-xs">GET /agents/{`{business_id}`}</td>
              <td className="py-1">List agents</td>
            </tr>
            <tr>
              <td className="py-1 pr-4 font-mono text-xs">POST /agents/{`{business_id}`}/{`{agent_id}`}/test</td>
              <td className="py-1">Dry-run prompt against agent</td>
            </tr>
            <tr>
              <td className="py-1 pr-4 font-mono text-xs">GET /analytics/{`{business_id}`}/overview</td>
              <td className="py-1">Volume + qualified-lead breakdown</td>
            </tr>
            <tr>
              <td className="py-1 pr-4 font-mono text-xs">GET /billing/{`{business_id}`}/plans</td>
              <td className="py-1">List plans + current subscription</td>
            </tr>
            <tr>
              <td className="py-1 pr-4 font-mono text-xs">POST /webhooks/whatsapp</td>
              <td className="py-1">Meta WhatsApp delivery webhook (signed)</td>
            </tr>
          </tbody>
        </table>
      </>
    ),
  },
  {
    id: "security",
    title: "Security",
    body: (
      <ul className="list-disc space-y-1 pl-5">
        <li>Row-level security on every business-owned row in Postgres</li>
        <li>Webhook signature verification (Meta, Stripe, Razorpay)</li>
        <li>Rate-limit on auth + webhook endpoints</li>
        <li>Structured logs + Sentry; PII is never logged in webhook bodies</li>
        <li>
          Daily WhatsApp token-health probe; alerts on
          <code className="ml-1">level=ERROR</code> CloudWatch metric
        </li>
      </ul>
    ),
  },
  {
    id: "limits",
    title: "Plan limits",
    body: (
      <table className="w-full text-sm">
        <thead className="border-b text-left text-slate-600">
          <tr>
            <th className="py-1 pr-4">Plan</th>
            <th className="py-1 pr-4">Conversations / mo</th>
            <th className="py-1">Agents</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <tr>
            <td className="py-1 pr-4">Free (pilot)</td>
            <td className="py-1 pr-4">100</td>
            <td className="py-1">1</td>
          </tr>
          <tr>
            <td className="py-1 pr-4">Sales Agent</td>
            <td className="py-1 pr-4">1,000</td>
            <td className="py-1">1</td>
          </tr>
          <tr>
            <td className="py-1 pr-4">Growth Bundle</td>
            <td className="py-1 pr-4">5,000</td>
            <td className="py-1">3</td>
          </tr>
          <tr>
            <td className="py-1 pr-4">Agency</td>
            <td className="py-1 pr-4">Unlimited</td>
            <td className="py-1">Unlimited</td>
          </tr>
        </tbody>
      </table>
    ),
  },
  {
    id: "support",
    title: "Support",
    body: (
      <p>
        Email <a className="underline" href="mailto:hello@influnexus.com">hello@influnexus.com</a>.
        Pilot customers get a shared Slack channel for sub-2-hour responses during
        IST business hours.
      </p>
    ),
  },
];

export default function DocsPage() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-lg font-semibold">
            WhatsAgent AI
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <Link href="/" className="text-slate-600 hover:text-slate-900">
              Home
            </Link>
            <Link href="/login" className="text-slate-600 hover:text-slate-900">
              Sign in
            </Link>
            <Link
              href="/signup"
              className="rounded bg-brand-600 px-3 py-1.5 font-medium text-white hover:bg-brand-700"
            >
              Start free
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto grid max-w-5xl gap-10 px-6 py-12 lg:grid-cols-[200px_1fr]">
        <aside className="hidden lg:block">
          <nav className="sticky top-8 space-y-1 text-sm">
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="block rounded px-2 py-1 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              >
                {s.title}
              </a>
            ))}
          </nav>
        </aside>

        <article className="space-y-12">
          <div>
            <h1 className="text-3xl font-bold">Documentation</h1>
            <p className="mt-2 text-slate-600">
              Everything you need to onboard, configure, and operate WhatsAgent.
            </p>
          </div>
          {SECTIONS.map((s) => (
            <section key={s.id} id={s.id} className="space-y-3 scroll-mt-20">
              <h2 className="text-xl font-semibold">{s.title}</h2>
              <div className="space-y-3 text-sm leading-relaxed text-slate-700">
                {s.body}
              </div>
            </section>
          ))}
        </article>
      </div>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-2 px-6 py-6 text-xs text-slate-500 sm:flex-row">
          <p>© {new Date().getFullYear()} Influnexus — WhatsAgent AI</p>
          <p>
            <a href="mailto:hello@influnexus.com" className="hover:text-slate-700">
              hello@influnexus.com
            </a>
          </p>
        </div>
      </footer>
    </main>
  );
}
