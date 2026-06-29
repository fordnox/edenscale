function LetterStrip() {
  const letters = [
    { vol: "Vol. xii · No. 3", date: "15 October 2025", title: "On the discipline of holding cash when the room is loud.", read: "8 min" },
    { vol: "Vol. xii · No. 2", date: "15 July 2025",    title: "Forestry, fifty years on: notes from the Linnér holding.",   read: "12 min" },
    { vol: "Vol. xii · No. 1", date: "15 April 2025",   title: "Why we said no to twenty-eight things this quarter.",         read: "6 min" },
  ];
  return (
    <section style={letterStyles.section}>
      <div style={letterStyles.inner}>
        <div style={letterStyles.head}>
          <div style={letterStyles.eyebrow}>Quarterly Letters</div>
          <h2 style={letterStyles.title}>What we are thinking, written down.</h2>
        </div>
        <div style={letterStyles.grid}>
          {letters.map(l => (
            <article key={l.vol} style={letterStyles.card}>
              <div style={letterStyles.vol}>{l.vol}</div>
              <h3 style={letterStyles.cardTitle}>{l.title}</h3>
              <div style={letterStyles.meta}>
                <span>{l.date}</span>
                <span style={letterStyles.dot} />
                <span>{l.read} read</span>
              </div>
              <a href="#" style={letterStyles.cardLink}>Read →</a>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

const letterStyles = {
  section: { background: "var(--bg-page)", padding: "128px 0", borderTop: "1px solid var(--border-hairline)" },
  inner: { maxWidth: "var(--container-wide)", margin: "0 auto", padding: "0 48px" },
  head: { marginBottom: 56 },
  eyebrow: {
    fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.16em",
    color: "var(--brass-700)", marginBottom: 16,
  },
  title: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 48, lineHeight: 1.05, letterSpacing: "-0.04em",
    margin: 0, color: "var(--ink-900)", maxWidth: 720,
  },
  grid: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24 },
  card: {
    background: "var(--bg-surface)", border: "1px solid var(--border-hairline)",
    padding: 32, display: "flex", flexDirection: "column", gap: 20,
    minHeight: 320,
  },
  vol: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase",
    color: "var(--brass-700)",
    fontFeatureSettings: "'tnum' 1",
  },
  cardTitle: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 22, lineHeight: 1.2, letterSpacing: "-0.03em",
    color: "var(--ink-900)", margin: 0, flex: 1, textWrap: "balance",
  },
  meta: {
    display: "flex", alignItems: "center", gap: 8,
    fontSize: 12, color: "var(--fg-tertiary)",
    fontFamily: "var(--font-sans)",
  },
  dot: { width: 3, height: 3, borderRadius: 999, background: "var(--ink-300)" },
  cardLink: {
    fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500,
    color: "var(--fg-primary)", textDecoration: "none",
    borderBottom: "1px solid var(--brass-500)", paddingBottom: 3,
    alignSelf: "start",
  },
};

window.LetterStrip = LetterStrip;
