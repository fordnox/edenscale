function Header() {
  const links = ["Approach", "Portfolio", "Letters", "About"];
  return (
    <header style={headerStyles.bar}>
      <div style={headerStyles.inner}>
        <a href="#" style={headerStyles.brand} aria-label="EdenScale home">
          <svg width="26" height="26" viewBox="0 0 64 64" fill="none" style={{flexShrink:0}}>
            <path fill="currentColor" fillRule="evenodd" clipRule="evenodd"
              d="M32 4 C 18 12, 10 24, 10 36 C 10 49, 20 60, 32 60 C 44 60, 54 49, 54 36 C 54 24, 46 12, 32 4 Z M32 50 L 32 30 L 26 30 L 32 22 L 38 30 L 32 30 L 32 50 Z"/>
          </svg>
          <span style={headerStyles.wordmark}>EdenScale</span>
        </a>
        <nav style={headerStyles.nav}>
          {links.map(l => <a key={l} href="#" style={headerStyles.link}>{l}</a>)}
        </nav>
        <a href="#" style={headerStyles.lpBtn}>Limited partner login →</a>
      </div>
    </header>
  );
}

const headerStyles = {
  bar: {
    position: "sticky", top: 0, zIndex: 10,
    background: "rgba(251, 249, 244, 0.92)",
    backdropFilter: "blur(8px)",
    borderBottom: "1px solid var(--border-hairline)",
  },
  inner: {
    maxWidth: "var(--container-wide)", margin: "0 auto",
    padding: "20px 48px",
    display: "flex", alignItems: "center", gap: 48,
  },
  brand: {
    display: "flex", alignItems: "center", gap: 12,
    color: "var(--conifer-700)", textDecoration: "none",
  },
  wordmark: {
    fontFamily: "var(--font-sans)", fontWeight: 600,
    fontSize: 22, letterSpacing: "-0.04em",
    color: "var(--ink-900)",
  },
  nav: { display: "flex", gap: 32, marginLeft: 24 },
  link: {
    fontFamily: "var(--font-sans)", fontSize: 14, fontWeight: 500,
    color: "var(--fg-secondary)", textDecoration: "none",
    letterSpacing: "0.005em",
  },
  lpBtn: {
    marginLeft: "auto",
    fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500,
    color: "var(--fg-primary)", textDecoration: "none",
    padding: "8px 14px", borderRadius: 2,
    border: "1px solid var(--border-default)",
  },
};

window.Header = Header;
