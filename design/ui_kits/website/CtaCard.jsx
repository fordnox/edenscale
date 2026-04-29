function CtaCard() {
  return (
    <section style={ctaStyles.section}>
      <div style={ctaStyles.inner}>
        <div style={ctaStyles.eyebrow}>Limited Partnership</div>
        <h2 style={ctaStyles.title}>
          A small number of subscriptions open each year.
        </h2>
        <p style={ctaStyles.body}>
          EdenScale admits new limited partners by referral, and only when an existing
          allocation closes. If your circumstances are aligned, we would welcome the
          conversation.
        </p>
        <div style={ctaStyles.actions}>
          <a href="#" style={ctaStyles.primary}>Request the prospectus</a>
          <a href="#" style={ctaStyles.secondary}>Email the partnership office →</a>
        </div>
      </div>
    </section>
  );
}

const ctaStyles = {
  section: {
    background: "var(--conifer-700)", color: "var(--parchment-50)",
    padding: "128px 0",
  },
  inner: {
    maxWidth: 880, margin: "0 auto", padding: "0 48px",
    textAlign: "left",
  },
  eyebrow: {
    fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.16em",
    color: "var(--brass-300)", marginBottom: 24,
  },
  title: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 56, lineHeight: 1.05, letterSpacing: "-0.045em",
    margin: 0, color: "var(--parchment-50)", textWrap: "balance",
  },
  body: {
    fontFamily: "var(--font-sans)", fontSize: 18, lineHeight: 1.55,
    color: "rgba(251, 249, 244, 0.78)",
    margin: "28px 0 40px", maxWidth: 580,
  },
  actions: { display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" },
  primary: {
    fontFamily: "var(--font-sans)", fontSize: 14, fontWeight: 500,
    color: "var(--ink-900)", background: "var(--parchment-50)",
    padding: "14px 24px", borderRadius: 2, textDecoration: "none",
  },
  secondary: {
    fontFamily: "var(--font-sans)", fontSize: 14, fontWeight: 500,
    color: "var(--parchment-50)", textDecoration: "none",
    borderBottom: "1px solid var(--brass-500)", paddingBottom: 4,
  },
};

window.CtaCard = CtaCard;
