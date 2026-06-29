function ApproachSection() {
  const principles = [
    {
      n: "01",
      title: "We invest patiently.",
      body: "Most of our holdings are over a decade old. Time, more than leverage, has been our principal source of return.",
    },
    {
      n: "02",
      title: "We hold fewer things.",
      body: "Our portfolio rarely exceeds twenty positions. Concentration forces us to know each one well enough to defend it.",
    },
    {
      n: "03",
      title: "We back operators.",
      body: "We invest with people who have already built something. We are the second call, not the first.",
    },
  ];
  return (
    <section style={approachStyles.section}>
      <div style={approachStyles.inner}>
        <div style={approachStyles.head}>
          <div style={approachStyles.eyebrow}>Approach</div>
          <h2 style={approachStyles.title}>
            Three rules we have not changed since 2009.
          </h2>
        </div>
        <div style={approachStyles.grid}>
          {principles.map(p => (
            <article key={p.n} style={approachStyles.card}>
              <div style={approachStyles.numeral}>{p.n}</div>
              <h3 style={approachStyles.cardTitle}>{p.title}</h3>
              <p style={approachStyles.body}>{p.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

const approachStyles = {
  section: { background: "var(--bg-page)", padding: "128px 0" },
  inner: {
    maxWidth: "var(--container-wide)", margin: "0 auto",
    padding: "0 48px",
  },
  head: {
    display: "grid", gridTemplateColumns: "5fr 7fr", gap: 48,
    marginBottom: 80, alignItems: "end",
  },
  eyebrow: {
    fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.16em",
    color: "var(--brass-700)",
  },
  title: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 52, lineHeight: 1.05, letterSpacing: "-0.04em",
    margin: 0, color: "var(--ink-900)", textWrap: "balance",
  },
  grid: {
    display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0,
    borderTop: "1px solid var(--border-default)",
  },
  card: {
    padding: "40px 32px 0 0", borderRight: "1px solid var(--border-hairline)",
    minHeight: 260,
  },
  numeral: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 14, letterSpacing: "0.08em", textTransform: "uppercase",
    color: "var(--brass-700)", marginBottom: 24,
    fontFeatureSettings: "'tnum' 1",
  },
  cardTitle: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 26, lineHeight: 1.15, letterSpacing: "-0.03em",
    margin: "0 0 16px", color: "var(--ink-900)",
  },
  body: {
    fontFamily: "var(--font-sans)", fontSize: 15, lineHeight: 1.6,
    color: "var(--fg-secondary)", margin: 0, maxWidth: 320,
  },
};

window.ApproachSection = ApproachSection;
