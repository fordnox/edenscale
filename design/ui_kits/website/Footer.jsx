function Footer() {
  const cols = [
    { h: "Firm",       links: ["Approach", "Partners", "Offices", "Careers"] },
    { h: "Investments", links: ["Portfolio", "Sectors", "Co-investments", "Realized"] },
    { h: "Investors",  links: ["LP login", "Subscription documents", "Tax & reporting", "Contact"] },
  ];
  return (
    <footer style={footerStyles.section}>
      <div style={footerStyles.inner}>
        <div style={footerStyles.top}>
          <div style={footerStyles.brandCol}>
            <div style={footerStyles.brand}>
              <svg width="22" height="22" viewBox="0 0 64 64" fill="none">
                <path fill="currentColor" fillRule="evenodd" clipRule="evenodd"
                  d="M32 4 C 18 12, 10 24, 10 36 C 10 49, 20 60, 32 60 C 44 60, 54 49, 54 36 C 54 24, 46 12, 32 4 Z M32 50 L 32 30 L 26 30 L 32 22 L 38 30 L 32 30 L 32 50 Z"/>
              </svg>
              <span style={footerStyles.wordmark}>EdenScale</span>
            </div>
            <p style={footerStyles.address}>
              Gediminas pr. 24<br/>
              LT-01103 Vilnius, Lithuania
            </p>
          </div>
          {cols.map(c => (
            <div key={c.h} style={footerStyles.col}>
              <div style={footerStyles.colHead}>{c.h}</div>
              <ul style={footerStyles.list}>
                {c.links.map(l => <li key={l}><a href="#" style={footerStyles.link}>{l}</a></li>)}
              </ul>
            </div>
          ))}
        </div>
        <hr style={footerStyles.rule}/>
        <div style={footerStyles.bottom}>
          <div style={footerStyles.disclosure}>
            EdenScale Partners SCA, SICAV-RAIF is a Luxembourg-domiciled investment vehicle.
            This material is provided for informational purposes only and does not constitute
            an offer to sell or a solicitation to buy any security. Past performance is not
            indicative of future results.
          </div>
          <div style={footerStyles.copy}>
            © 2009–2025 EdenScale Partners
          </div>
        </div>
      </div>
    </footer>
  );
}

const footerStyles = {
  section: { background: "var(--bg-page)", borderTop: "1px solid var(--border-default)", padding: "80px 0 48px" },
  inner: { maxWidth: "var(--container-wide)", margin: "0 auto", padding: "0 48px" },
  top: { display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 48 },
  brandCol: { display: "flex", flexDirection: "column", gap: 16 },
  brand: { display: "flex", alignItems: "center", gap: 10, color: "var(--conifer-700)" },
  wordmark: {
    fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 20,
    color: "var(--ink-900)", letterSpacing: "-0.04em",
  },
  address: {
    fontFamily: "var(--font-sans)", fontSize: 13, lineHeight: 1.55,
    color: "var(--fg-tertiary)", margin: 0,
  },
  col: {},
  colHead: {
    fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.12em",
    color: "var(--fg-tertiary)", marginBottom: 16,
  },
  list: { listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 },
  link: {
    fontFamily: "var(--font-sans)", fontSize: 14, color: "var(--fg-primary)",
    textDecoration: "none",
  },
  rule: { border: 0, borderTop: "1px solid var(--border-hairline)", margin: "56px 0 24px" },
  bottom: { display: "flex", justifyContent: "space-between", gap: 48, alignItems: "flex-start" },
  disclosure: {
    fontFamily: "var(--font-sans)", fontSize: 11, lineHeight: 1.6,
    color: "var(--fg-tertiary)", maxWidth: 640,
  },
  copy: {
    fontFamily: "var(--font-sans)", fontSize: 11, color: "var(--fg-tertiary)",
    whiteSpace: "nowrap",
  },
};

window.Footer = Footer;
