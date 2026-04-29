function PortfolioStrip() {
  const holdings = [
    { name: "Linnér Forestry",       sector: "Real Assets",     since: "2019", region: "Sweden" },
    { name: "Aurelia Industrial",    sector: "Private Equity",  since: "2017", region: "Germany" },
    { name: "Meridian Infrastructure", sector: "Real Assets",   since: "2020", region: "Spain" },
    { name: "Calder Credit Fund",    sector: "Credit",          since: "2022", region: "United Kingdom" },
    { name: "Arvada Holdings",       sector: "Private Equity",  since: "2014", region: "United States" },
    { name: "Vasari Editions",       sector: "Private Equity",  since: "2021", region: "Italy" },
  ];
  return (
    <section style={portfolioStyles.section}>
      <div style={portfolioStyles.inner}>
        <div style={portfolioStyles.head}>
          <div>
            <div style={portfolioStyles.eyebrow}>Portfolio</div>
            <h2 style={portfolioStyles.title}>A small list, deliberately.</h2>
          </div>
          <a href="#" style={portfolioStyles.viewAll}>View all positions →</a>
        </div>
        <table style={portfolioStyles.table}>
          <thead>
            <tr>
              <th style={portfolioStyles.th}>Holding</th>
              <th style={portfolioStyles.th}>Sector</th>
              <th style={portfolioStyles.th}>Region</th>
              <th style={{...portfolioStyles.th, textAlign: "right"}}>Held since</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map(h => (
              <tr key={h.name} style={portfolioStyles.tr}>
                <td style={portfolioStyles.tdName}>{h.name}</td>
                <td style={portfolioStyles.td}>{h.sector}</td>
                <td style={portfolioStyles.td}>{h.region}</td>
                <td style={{...portfolioStyles.td, textAlign: "right", fontFeatureSettings:"'tnum' 1,'lnum' 1"}}>{h.since}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const portfolioStyles = {
  section: { background: "var(--bg-raised)", padding: "128px 0" },
  inner: { maxWidth: "var(--container-wide)", margin: "0 auto", padding: "0 48px" },
  head: { display: "flex", justifyContent: "space-between", alignItems: "end", marginBottom: 56 },
  eyebrow: {
    fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.16em",
    color: "var(--brass-700)", marginBottom: 16,
  },
  title: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 48, lineHeight: 1.05, letterSpacing: "-0.04em",
    margin: 0, color: "var(--ink-900)",
  },
  viewAll: {
    fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500,
    color: "var(--fg-primary)", textDecoration: "none",
    borderBottom: "1px solid var(--brass-500)", paddingBottom: 3,
  },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.08em",
    color: "var(--fg-tertiary)", textAlign: "left",
    padding: "16px 0", borderBottom: "1px solid var(--border-default)",
  },
  tr: { borderBottom: "1px solid var(--border-hairline)" },
  td: {
    padding: "22px 0", fontFamily: "var(--font-sans)", fontSize: 14,
    color: "var(--fg-secondary)",
  },
  tdName: {
    padding: "22px 0", fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 18, letterSpacing: "-0.02em", color: "var(--ink-900)",
  },
};

window.PortfolioStrip = PortfolioStrip;
