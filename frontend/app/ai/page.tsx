import Link from "next/link";

const AI_SURFACES = [
  {
    href: "/visibility",
    label: "Visibility",
    description: "Operational intelligence, access control, and truth-based system visibility.",
    accent: "var(--color-ai-cyan)",
  },
  {
    href: "/roi",
    label: "ROI engine",
    description: "Live value modeling grounded in platform pricing and operational inputs.",
    accent: "var(--color-brand-orange)",
  },
  {
    href: "/systems",
    label: "System registry",
    description: "See where AI-assisted surfaces fit into the broader platform architecture.",
    accent: "var(--color-status-active)",
  },
  {
    href: "/command-center",
    label: "Command health",
    description: "Track service posture and readiness before claiming confidence.",
    accent: "var(--color-status-warning)",
  },
];

/**
 * AI Portal Overview Page
 *
 * Provides access to all AI-powered intelligence surfaces in the platform.
 * Migrated to PlatformShell layout for unified navigation experience.
 */
export default function AIPage() {
  return (
    <div className="space-y-6">
      <div className="platform-page-header border-b border-[var(--color-border-default)] pb-5">
        <div className="platform-kicker text-[var(--color-ai-magenta)]">AI surfaces</div>
        <h1 style={{ fontSize: "clamp(1.8rem, 3vw, 2.8rem)", lineHeight: 1.02, fontWeight: 800, letterSpacing: "-0.04em" }}>
          Intelligence that stays inside the operating system.
        </h1>
        <p style={{ maxWidth: 760, color: "var(--color-text-secondary)", lineHeight: 1.8 }}>
          AI in Adaptix should reinforce routing clarity, billing accuracy, compliance readiness, and operational truth. These are the primary intelligence surfaces available today.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {AI_SURFACES.map((surface) => (
          <Link
            key={surface.href}
            href={surface.href}
            className="command-panel p-5 transition-all hover:border-[rgba(168,85,247,0.25)] hover:shadow-elevation-2"
            style={{ borderLeftWidth: 2, borderLeftColor: surface.accent }}
          >
            <div className="eyebrow" style={{ color: surface.accent }}>
              AI
            </div>
            <div style={{ marginTop: 10, fontSize: "1.05rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
              {surface.label}
            </div>
            <p style={{ marginTop: 10, color: "var(--color-text-secondary)", lineHeight: 1.75, fontSize: "0.92rem" }}>
              {surface.description}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
