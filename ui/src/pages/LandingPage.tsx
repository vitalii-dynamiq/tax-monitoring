import { Link } from "react-router-dom";
import {
  RiGitBranchLine,
  RiShieldCheckLine,
  RiRefreshLine,
  RiGlobalLine,
  RiExchangeDollarLine,
  RiFileSearchLine,
  RiArrowRightLine,
  RiFileCopyLine,
  RiCheckLine,
} from "react-icons/ri";
import { useState, type ComponentType } from "react";

/* ─── Data ─── */

const STATS = [
  { value: "235", label: "Countries & territories" },
  { value: "916", label: "Jurisdictions tracked" },
  { value: "1,017", label: "Active tax rates" },
  { value: "235", label: "Rules & exemptions" },
];

const FEATURES: { icon: ComponentType<{ className?: string }>; title: string; description: string }[] = [
  {
    icon: RiGitBranchLine,
    title: "Hierarchical tax chains",
    description: "Country, state, and city taxes resolved in one call. Cascading rates, overlapping jurisdictions, and local surcharges handled automatically.",
  },
  {
    icon: RiShieldCheckLine,
    title: "Rules engine included",
    description: "Exemptions for long stays, child guests, star ratings, property types, and seasonal variations. All encoded and version-controlled.",
  },
  {
    icon: RiRefreshLine,
    title: "Always current",
    description: "Monitoring agents scan regulatory sources daily. Changes are detected, flagged for review, and applied with full audit trail.",
  },
  {
    icon: RiGlobalLine,
    title: "One API, every jurisdiction",
    description: "From NYC hotel tax to Bali's regional levies. Same request format, same response shape, every jurisdiction worldwide.",
  },
  {
    icon: RiExchangeDollarLine,
    title: "Collection model clarity",
    description: "Know exactly who collects: the property, the platform, or the guest. Taxable base rules included per rate.",
  },
  {
    icon: RiFileSearchLine,
    title: "Audit-ready",
    description: "Every rate change tracked with legal references, effective dates, and authority attribution. Export-ready for compliance reviews.",
  },
];

const INTEGRATIONS = [
  "Booking platforms",
  "Property management systems",
  "Channel managers",
  "Payment processors",
  "ERP systems",
  "Tax filing software",
];

/* ─── Syntax-highlighted code ─── */

function SyntaxRequest() {
  return (
    <>
      <span className="text-emerald-400">curl</span>{" "}
      <span className="text-white/60">https://api.taxlens.io/v1/tax/calculate</span>{" "}
      <span className="text-white/30">\</span>{"\n"}
      {"  "}<span className="text-amber-400">-H</span>{" "}
      <span className="text-sky-300">"X-API-Key: txl_your_key"</span>{" "}
      <span className="text-white/30">\</span>{"\n"}
      {"  "}<span className="text-amber-400">-d</span>{" "}
      <span className="text-sky-300">{"'"}</span>
      <span className="text-white/50">{"{"}</span>{"\n"}
      {"    "}<span className="text-sky-300">"jurisdiction_code"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"US-NY-NYC"</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"stay_date"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"2026-06-15"</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"nightly_rate"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">200</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"currency"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"USD"</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"nights"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">3</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"property_type"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"hotel"</span>{"\n"}
      {"  "}<span className="text-white/50">{"}"}</span>
      <span className="text-sky-300">{"'"}</span>
    </>
  );
}

function SyntaxResponse() {
  return (
    <>
      <span className="text-white/50">{"{"}</span>{"\n"}
      {"  "}<span className="text-sky-300">"jurisdiction"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-white/50">{"{"}</span>{"\n"}
      {"    "}<span className="text-sky-300">"code"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"US-NY-NYC"</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"name"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"New York City"</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"path"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"US &gt; US-NY &gt; US-NY-NYC"</span>{"\n"}
      {"  "}<span className="text-white/50">{"}"}</span>
      <span className="text-white/30">,</span>{"\n"}
      {"  "}<span className="text-sky-300">"tax_breakdown"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-white/50">{"{"}</span>{"\n"}
      {"    "}<span className="text-sky-300">"total_tax"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">96.75</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"effective_rate"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">0.1613</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"currency"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"USD"</span>
      <span className="text-white/30">,</span>{"\n"}
      {"    "}<span className="text-sky-300">"components"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-white/50">{"["}</span>{"\n"}
      {"      "}<span className="text-white/50">{"{"}</span>{" "}
      <span className="text-sky-300">"name"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"NY State Sales Tax"</span>
      <span className="text-white/30">,</span>{" "}
      <span className="text-sky-300">"tax_amount"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">24.00</span>{" "}
      <span className="text-white/50">{"}"}</span>
      <span className="text-white/30">,</span>{"\n"}
      {"      "}<span className="text-white/50">{"{"}</span>{" "}
      <span className="text-sky-300">"name"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"NYC Hotel Tax"</span>
      <span className="text-white/30">,</span>{" "}
      <span className="text-sky-300">"tax_amount"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">35.40</span>{" "}
      <span className="text-white/50">{"}"}</span>
      <span className="text-white/30">,</span>{"\n"}
      {"      "}<span className="text-white/50">{"{"}</span>{" "}
      <span className="text-sky-300">"name"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"NYC Convention Tax"</span>
      <span className="text-white/30">,</span>{" "}
      <span className="text-sky-300">"tax_amount"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">10.50</span>{" "}
      <span className="text-white/50">{"}"}</span>
      <span className="text-white/30">,</span>{"\n"}
      {"      "}<span className="text-white/50">{"{"}</span>{" "}
      <span className="text-sky-300">"name"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"Javits Center Fee"</span>
      <span className="text-white/30">,</span>{" "}
      <span className="text-sky-300">"tax_amount"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">4.50</span>{" "}
      <span className="text-white/50">{"}"}</span>
      <span className="text-white/30">,</span>{"\n"}
      {"      "}<span className="text-white/50">{"{"}</span>{" "}
      <span className="text-sky-300">"name"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-emerald-300">"NYC Unit Fee"</span>
      <span className="text-white/30">,</span>{" "}
      <span className="text-sky-300">"tax_amount"</span>
      <span className="text-white/30">:</span>{" "}
      <span className="text-amber-300">22.35</span>{" "}
      <span className="text-white/50">{"}"}</span>{"\n"}
      {"    "}<span className="text-white/50">{"]"}</span>{"\n"}
      {"  "}<span className="text-white/50">{"}"}</span>{"\n"}
      <span className="text-white/50">{"}"}</span>
    </>
  );
}

function CodeBlock({ label, children }: { label: string; children: React.ReactNode }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const el = document.querySelector(`[data-code="${label}"]`);
    if (el) navigator.clipboard.writeText(el.textContent || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#0c0c0f] overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06] bg-white/[0.015]">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-white/[0.06]" />
          <span className="w-2.5 h-2.5 rounded-full bg-white/[0.06]" />
          <span className="w-2.5 h-2.5 rounded-full bg-white/[0.06]" />
          <span className="text-[13px] font-medium text-white/30 ml-2">{label}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[12px] text-white/25 hover:text-white/50 transition-colors"
        >
          {copied ? <RiCheckLine className="w-3.5 h-3.5" /> : <RiFileCopyLine className="w-3.5 h-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        data-code={label}
        className="p-5 overflow-x-auto text-[13px] leading-[1.7] font-mono flex-1 scrollbar-hide"
      >
        <code>{children}</code>
      </pre>
    </div>
  );
}

/* ─── Page ─── */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#09090b] text-white antialiased selection:bg-white/10">
      {/* ─── Nav ─── */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/[0.06] bg-[#09090b]/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <img src="/logo.svg" alt="TaxLens" className="w-8 h-8" />
            <span className="text-[16px] font-semibold tracking-tight">TaxLens</span>
          </div>
          <div className="hidden sm:flex items-center gap-8 text-[14px] text-white/50">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#api" className="hover:text-white transition-colors">API</a>
            <a href="#coverage" className="hover:text-white transition-colors">Coverage</a>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="h-9 px-4 rounded-lg bg-white text-[#09090b] text-[14px] font-medium flex items-center hover:bg-white/90 transition-colors"
            >
              Sign in
            </Link>
          </div>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <section className="pt-36 sm:pt-48 pb-20 sm:pb-28 px-5 sm:px-8">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-[2.5rem] sm:text-5xl lg:text-[3.5rem] font-semibold tracking-tight leading-[1.08] mb-6">
            Accommodation tax
            <br />
            <span className="text-white/40">for platforms that scale</span>
          </h1>

          <p className="text-lg sm:text-xl text-white/40 leading-relaxed max-w-xl mx-auto mb-10">
            One API to calculate, track, and stay compliant with accommodation taxes in every jurisdiction worldwide.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              to="/login"
              className="h-12 px-7 rounded-lg bg-white text-[#09090b] text-[15px] font-semibold flex items-center gap-2 hover:bg-white/90 transition-all"
            >
              Get API access <RiArrowRightLine className="w-4 h-4" />
            </Link>
            <a
              href="#api"
              className="h-12 px-7 rounded-lg border border-white/[0.1] text-[15px] font-medium text-white/60 flex items-center hover:text-white hover:border-white/20 transition-all"
            >
              See how it works
            </a>
          </div>
        </div>
      </section>

      {/* ─── Stats bar ─── */}
      <section className="border-y border-white/[0.06]">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 grid grid-cols-2 lg:grid-cols-4">
          {STATS.map((stat, i) => (
            <div
              key={stat.label}
              className={[
                "py-8 sm:py-10 text-center",
                i < 3 ? "lg:border-r lg:border-white/[0.06]" : "",
                i === 0 ? "border-r border-white/[0.06] max-lg:border-r" : "",
                i === 2 ? "border-r border-white/[0.06] max-lg:border-r max-lg:border-t max-lg:border-white/[0.06]" : "",
                i === 1 ? "max-lg:border-r-0" : "",
                i === 3 ? "max-lg:border-t border-white/[0.06]" : "",
              ].filter(Boolean).join(" ")}
            >
              <div className="text-3xl sm:text-4xl font-bold tabular-nums tracking-tight">{stat.value}</div>
              <div className="text-[13px] text-white/35 mt-1.5">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── API Demo ─── */}
      <section id="api" className="py-20 sm:py-28 px-5 sm:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="max-w-2xl mb-14">
            <p className="text-[13px] font-semibold uppercase tracking-widest text-white/25 mb-4">API</p>
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-tight mb-4">
              One request. Full tax breakdown.
            </h2>
            <p className="text-base text-white/40 leading-relaxed">
              Send a jurisdiction, dates, and nightly rate. Get back every tax component, the effective rate, applicable rules, and legal references.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CodeBlock label="Request">
              <SyntaxRequest />
            </CodeBlock>
            <CodeBlock label="Response">
              <SyntaxResponse />
            </CodeBlock>
          </div>
        </div>
      </section>

      {/* ─── Features ─── */}
      <section id="features" className="py-20 sm:py-28 px-5 sm:px-8 border-t border-white/[0.06]">
        <div className="max-w-6xl mx-auto">
          <div className="max-w-2xl mb-14">
            <p className="text-[13px] font-semibold uppercase tracking-widest text-white/25 mb-4">Capabilities</p>
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-tight mb-4">
              Everything tax compliance needs
            </h2>
            <p className="text-base text-white/40 leading-relaxed">
              Built by talking to tax teams at OTAs. Every edge case you've hit — long-stay exemptions, star-rating tiers, seasonal surcharges, platform collection obligations — is handled.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-white/[0.06] rounded-xl overflow-hidden border border-white/[0.06]">
            {FEATURES.map(({ icon: Icon, title, description }) => (
              <div key={title} className="bg-[#09090b] p-7 sm:p-8">
                <div className="w-9 h-9 rounded-lg bg-white/[0.05] flex items-center justify-center mb-4">
                  <Icon className="w-[18px] h-[18px] text-white/50" />
                </div>
                <h3 className="text-[15px] font-semibold mb-2">{title}</h3>
                <p className="text-[14px] text-white/35 leading-relaxed">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Coverage ─── */}
      <section id="coverage" className="py-20 sm:py-28 px-5 sm:px-8 border-t border-white/[0.06]">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
            <div>
              <p className="text-[13px] font-semibold uppercase tracking-widest text-white/25 mb-4">Coverage</p>
              <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-tight mb-4">
                100% of global OTA markets
              </h2>
              <p className="text-base text-white/40 leading-relaxed mb-8">
                Every country where Airbnb, Booking.com, and Expedia operate. From major cities with complex multi-layered taxes to small island nations with flat tourist levies.
              </p>

              <div className="space-y-4">
                {[
                  { region: "Europe", detail: "EU VAT + city tourist taxes + platform obligations" },
                  { region: "Americas", detail: "US state/county/city taxes + LATAM IVA + Caribbean levies" },
                  { region: "Asia-Pacific", detail: "Japan accommodation tax + GST variants + ASEAN levies" },
                  { region: "Middle East & Africa", detail: "GCC tourism fees + municipality taxes + VAT" },
                ].map((r) => (
                  <div key={r.region} className="flex gap-3 items-start">
                    <span className="w-1 h-1 rounded-full bg-white/20 mt-2.5 flex-shrink-0" />
                    <div>
                      <span className="text-[14px] font-medium">{r.region}</span>
                      <span className="text-[14px] text-white/30 ml-2">{r.detail}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 sm:p-8">
                <div className="text-[13px] font-semibold uppercase tracking-widest text-white/25 mb-5">How it works</div>
                <div className="space-y-5">
                  {[
                    { step: "1", title: "Send booking details", desc: "Jurisdiction, dates, rate, property type, guest info." },
                    { step: "2", title: "Get full tax breakdown", desc: "Every component, rate, amount, legal reference, and collection info." },
                    { step: "3", title: "Stay current automatically", desc: "Monitoring agents scan regulatory changes. You get notified before rates change." },
                  ].map((s) => (
                    <div key={s.step} className="flex gap-4">
                      <div className="w-7 h-7 rounded-md bg-white/[0.06] flex items-center justify-center text-[13px] font-semibold text-white/40 flex-shrink-0">
                        {s.step}
                      </div>
                      <div>
                        <div className="text-[14px] font-medium mb-0.5">{s.title}</div>
                        <div className="text-[13px] text-white/30 leading-relaxed">{s.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 sm:p-8">
                <div className="text-[13px] font-semibold uppercase tracking-widest text-white/25 mb-4">Integrates with</div>
                <div className="flex flex-wrap gap-2">
                  {INTEGRATIONS.map((name) => (
                    <span
                      key={name}
                      className="px-3 py-1.5 rounded-md border border-white/[0.06] bg-white/[0.02] text-[13px] text-white/40"
                    >
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Enterprise CTA ─── */}
      <section className="py-20 sm:py-28 px-5 sm:px-8 border-t border-white/[0.06]">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-tight mb-4">
            Stop maintaining spreadsheets.
            <br />
            <span className="text-white/40">Start querying an API.</span>
          </h2>
          <p className="text-base text-white/40 leading-relaxed mb-10 max-w-lg mx-auto">
            TaxLens replaces your team's manual tax rate tracking with a single source of truth. Auditable, versioned, and always up to date.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              to="/login"
              className="h-12 px-7 rounded-lg bg-white text-[#09090b] text-[15px] font-semibold flex items-center gap-2 hover:bg-white/90 transition-all"
            >
              Get API access <RiArrowRightLine className="w-4 h-4" />
            </Link>
            <a
              href="mailto:hello@getdynamiq.ai"
              className="h-12 px-7 rounded-lg border border-white/[0.1] text-[15px] font-medium text-white/60 flex items-center hover:text-white hover:border-white/20 transition-all"
            >
              Talk to founders
            </a>
          </div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="border-t border-white/[0.06] py-10 px-5 sm:px-8">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <img src="/logo.svg" alt="TaxLens" className="w-5 h-5 opacity-40" />
            <span className="text-[13px] text-white/25">&copy; {new Date().getFullYear()} Dynamiq Technologies, Inc.</span>
          </div>
          <div className="flex items-center flex-wrap justify-center gap-6 text-[13px] text-white/25">
            <Link to="/app" className="hover:text-white/50 transition-colors">Dashboard</Link>
            <Link to="/app/docs" className="hover:text-white/50 transition-colors">API Docs</Link>
            <a href="https://getdynamiq.ai/privacy" target="_blank" rel="noopener noreferrer" className="hover:text-white/50 transition-colors">Privacy Policy</a>
            <a href="https://getdynamiq.ai/terms" target="_blank" rel="noopener noreferrer" className="hover:text-white/50 transition-colors">Terms of Service</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
