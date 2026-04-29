function Hero() {
  return (
    <section style={heroStyles.section}>
      <div style={heroStyles.bg}>
        {/* Photographic placeholder: warm gradient field acts as a stand-in
            for a hero photograph. Replace with a real image when supplied. */}
        <div style={heroStyles.placeholder}>
          <div style={heroStyles.placeholderLabel}>Photograph placeholder · warm interior, golden-hour</div>
        </div>
        <div style={heroStyles.protection} />
      </div>
      <div style={heroStyles.content}>
        <div style={heroStyles.eyebrow}>Est. 2009 · Vilnius &middot; Stockholm &middot; London</div>
        <h1 style={heroStyles.title}>
          Patient capital,<br/>
          <span style={heroStyles.titleAlt}>deployed deliberately.</span>
        </h1>
        
        <p style={heroStyles.lede}>
          EdenScale is a private investment group. We hold fewer companies, on longer
          horizons, with the people who built them.
        </p>
        <div style={heroStyles.actions}>
          <a href="#" style={heroStyles.primary}>Read the latest letter</a>
          <a href="#" style={heroStyles.secondary}>Our approach →</a>
        </div>
      </div>
    </section>
  );
}

const heroStyles = {
  section: {
    position: "relative",
    minHeight: 620,
    display: "flex", alignItems: "flex-end",
    overflow: "hidden",
  },
  bg: { position: "absolute", inset: 0, zIndex: 0 },
  placeholder: {
    position: "absolute", inset: 0,
    background: `
      radial-gradient(ellipse at 20% 30%, rgba(184, 145, 92, 0.45), transparent 55%),
      radial-gradient(ellipse at 80% 70%, rgba(31, 61, 46, 0.65), transparent 60%),
      linear-gradient(180deg, #3A3A36 0%, #1A1A18 100%)`,
    display: "flex", alignItems: "center", justifyContent: "center",
  },
  placeholderLabel: {
    fontFamily: "var(--font-sans)", fontSize: 11,
    color: "rgba(251, 249, 244, 0.45)",
    textTransform: "uppercase", letterSpacing: "0.16em",
  },
  protection: {
    position: "absolute", inset: 0,
    background: "linear-gradient(180deg, transparent 30%, rgba(14, 27, 20, 0.78) 100%)",
  },
  content: {
    position: "relative", zIndex: 1,
    maxWidth: "var(--container-wide)", width: "100%",
    margin: "0 auto", padding: "0 48px 96px",
    color: "var(--parchment-50)",
  },
  eyebrow: {
    fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.16em",
    color: "var(--brass-300)", marginBottom: 24,
  },
  title: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: "clamp(56px, 7vw, 96px)",
    lineHeight: 1.0, letterSpacing: "-0.045em",
    margin: 0, maxWidth: 980, textWrap: "balance",
  },
  titleAlt: {
    fontWeight: 500,
    color: "var(--brass-300)",
  },
  lede: {
    fontFamily: "var(--font-sans)", fontSize: 19, fontWeight: 400,
    lineHeight: 1.5, color: "rgba(251, 249, 244, 0.82)",
    margin: "28px 0 36px", maxWidth: 560, textWrap: "pretty",
  },
  actions: { display: "flex", gap: 16, alignItems: "center" },
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

window.Hero = Hero;
