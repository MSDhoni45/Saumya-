import Link from "next/link";

export const metadata = {
  title: "WhatsAgent AI — Your WhatsApp Sales Team, On Autopilot",
  description:
    "AI agents that qualify leads, book meetings, and answer support on WhatsApp 24/7. Built for SMBs and agencies.",
};

const TIERS = [
  {
    name: "Sales Agent",
    price: "₹15,000",
    cadence: "/mo",
    blurb: "One AI agent that qualifies inbound leads and books calls.",
    features: ["1 agent", "1,000 conversations / month", "Telegram + Slack alerts", "1 WhatsApp number"],
    cta: "Start pilot",
    highlight: false,
  },
  {
    name: "Growth Bundle",
    price: "₹35,000",
    cadence: "/mo",
    blurb: "Sales + support + follow-up agents working in tandem.",
    features: ["3 agents", "5,000 conversations / month", "Priority routing", "Up to 3 WhatsApp numbers", "Weekly performance review"],
    cta: "Most popular",
    highlight: true,
  },
  {
    name: "Agency",
    price: "₹75,000+",
    cadence: "/mo",
    blurb: "White-label, multi-business, manager seat. Built for resellers.",
    features: ["Unlimited agents", "Unlimited conversations", "White-label branding", "Multi-business console", "Dedicated success manager"],
    cta: "Talk to sales",
    highlight: false,
  },
];

const USE_CASES = [
  {
    title: "Qualify inbound leads in <30 seconds",
    body: "Your agent answers the moment a lead messages your WhatsApp Business number. Asks the right qualifying questions, books a meeting, and hands the lead off to a human only when it matters.",
  },
  {
    title: "Cut support load by 60%",
    body: "Trained on your FAQ, refund policy, and order data. Resolves the easy 60% on its own. Routes the rest to your team with full context — no copy-pasting transcripts.",
  },
  {
    title: "Follow up without forgetting",
    body: "Auto-nudges cold leads on day 2, 5, 14 based on their last message. Never lets a hot lead go quiet because a rep was on PTO.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-lg font-semibold">
            WhatsAgent AI
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <a href="#use-cases" className="text-slate-600 hover:text-slate-900">
              How it works
            </a>
            <a href="#pricing" className="text-slate-600 hover:text-slate-900">
              Pricing
            </a>
            <Link href="/docs" className="text-slate-600 hover:text-slate-900">
              Docs
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

      <section className="mx-auto max-w-6xl px-6 py-20 sm:py-28">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div className="space-y-6">
            <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">
              For SMBs and agencies in India + SEA
            </p>
            <h1 className="text-4xl font-bold leading-tight text-slate-900 sm:text-5xl">
              Your WhatsApp sales team,
              <br />
              <span className="text-brand-600">on autopilot.</span>
            </h1>
            <p className="text-lg text-slate-600">
              AI agents that qualify leads, book meetings, and resolve support tickets on
              WhatsApp 24/7. Launch in 48 hours. White-glove onboarding for the first 100 customers.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <Link
                href="/signup"
                className="rounded-lg bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-700"
              >
                Start 7-day pilot
              </Link>
              <a
                href="mailto:hello@influnexus.com?subject=WhatsAgent%20demo"
                className="rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-50"
              >
                Book a 15-min demo
              </a>
            </div>
            <p className="pt-2 text-xs text-slate-500">
              No credit card required · Cancel anytime · Built on official WhatsApp Business API
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="space-y-4 text-sm">
              <div className="flex gap-3">
                <div className="h-8 w-8 shrink-0 rounded-full bg-emerald-100 text-center text-base leading-8">
                  👤
                </div>
                <div className="rounded-lg rounded-tl-none bg-slate-100 px-4 py-2">
                  Hey, do you guys do bulk orders for offices?
                </div>
              </div>
              <div className="flex flex-row-reverse gap-3">
                <div className="h-8 w-8 shrink-0 rounded-full bg-brand-100 text-center text-base leading-8">
                  🤖
                </div>
                <div className="rounded-lg rounded-tr-none bg-brand-600 px-4 py-2 text-white">
                  Yes! Roughly how many seats and which city? I can send a quote in ~2 minutes.
                </div>
              </div>
              <div className="flex gap-3">
                <div className="h-8 w-8 shrink-0 rounded-full bg-emerald-100 text-center text-base leading-8">
                  👤
                </div>
                <div className="rounded-lg rounded-tl-none bg-slate-100 px-4 py-2">
                  ~40 seats, Bangalore. When can someone call?
                </div>
              </div>
              <div className="flex flex-row-reverse gap-3">
                <div className="h-8 w-8 shrink-0 rounded-full bg-brand-100 text-center text-base leading-8">
                  🤖
                </div>
                <div className="rounded-lg rounded-tr-none bg-brand-600 px-4 py-2 text-white">
                  Booked you with Priya for tomorrow 3:00 PM IST. Confirmation on its way 📅
                </div>
              </div>
            </div>
            <div className="mt-4 border-t border-slate-100 pt-4 text-xs text-slate-500">
              Real conversation handled by a WhatsAgent. Average qualifying time: 47 seconds.
            </div>
          </div>
        </div>
      </section>

      <section id="use-cases" className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="text-3xl font-bold">Three jobs your agents do, day one.</h2>
          <div className="mt-10 grid gap-8 lg:grid-cols-3">
            {USE_CASES.map((u) => (
              <div key={u.title} className="space-y-3">
                <h3 className="text-lg font-semibold text-slate-900">{u.title}</h3>
                <p className="text-sm text-slate-600">{u.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-6xl px-6 py-20">
        <div className="space-y-2 text-center">
          <h2 className="text-3xl font-bold">Simple, flat pricing.</h2>
          <p className="text-slate-600">No per-message fees. No surprise overages.</p>
        </div>
        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {TIERS.map((t) => (
            <div
              key={t.name}
              className={`rounded-2xl border bg-white p-6 ${
                t.highlight
                  ? "border-brand-500 shadow-lg ring-2 ring-brand-500/20"
                  : "border-slate-200"
              }`}
            >
              {t.highlight && (
                <p className="mb-3 inline-block rounded-full bg-brand-100 px-3 py-0.5 text-xs font-semibold text-brand-700">
                  Most popular
                </p>
              )}
              <h3 className="text-xl font-bold">{t.name}</h3>
              <p className="mt-1 text-sm text-slate-600">{t.blurb}</p>
              <p className="mt-4">
                <span className="text-3xl font-bold">{t.price}</span>
                <span className="text-sm text-slate-500">{t.cadence}</span>
              </p>
              <ul className="mt-5 space-y-2 text-sm text-slate-700">
                {t.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-emerald-600">✓</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={t.highlight ? "/signup" : "mailto:hello@influnexus.com?subject=WhatsAgent%20demo"}
                className={`mt-6 block rounded-lg px-4 py-2.5 text-center text-sm font-semibold ${
                  t.highlight
                    ? "bg-brand-600 text-white hover:bg-brand-700"
                    : "border border-slate-300 text-slate-900 hover:bg-slate-50"
                }`}
              >
                {t.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-slate-200 bg-slate-900 text-white">
        <div className="mx-auto max-w-4xl px-6 py-16 text-center">
          <h2 className="text-3xl font-bold">Ready to never miss a WhatsApp lead again?</h2>
          <p className="mt-3 text-slate-300">
            Pilot program open for 10 design partners. Onboarding in 48 hours, refund anytime in the first 30 days.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              href="/signup"
              className="rounded-lg bg-brand-500 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-600"
            >
              Start free pilot
            </Link>
            <a
              href="mailto:hello@influnexus.com?subject=WhatsAgent%20demo"
              className="rounded-lg border border-slate-700 px-5 py-3 text-sm font-semibold hover:bg-slate-800"
            >
              Book demo
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-6 py-6 text-xs text-slate-500 sm:flex-row">
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
