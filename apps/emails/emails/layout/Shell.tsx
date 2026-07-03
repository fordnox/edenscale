import {
  Body,
  Container,
  Head,
  Hr,
  Html,
  Link,
  Preview,
  Section,
  Text,
} from "@react-email/components";
import * as React from "react";

type CSSProperties = React.CSSProperties;

// NewTaven brand tokens — mirrors the app's design system (see the frontend
// index.css: conifer / brass / parchment / ink).
export const BRAND = {
  conifer: "#1f3d2e",
  coniferSoft: "#2a4736",
  brass: "#8a6a3f",
  brassSoft: "#b8915c",
  paper: "#fbf9f4",
  raised: "#f5f1e8",
  card: "#ffffff",
  border: "rgba(26,26,24,0.10)",
  ink: "#1a1a18",
  inkSoft: "#3a3a36",
  muted: "#6f6e68",
  display: '"Cormorant Garamond", "Times New Roman", Times, serif',
  body: 'Inter, "Inter Tight", -apple-system, Helvetica, Arial, sans-serif',
  mono: '"JetBrains Mono", ui-monospace, Menlo, monospace',
} as const;

export const fonts = {
  href: "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Inter:wght@400;500;600&display=swap",
};

export const main = {
  backgroundColor: BRAND.paper,
  fontFamily: BRAND.body,
  margin: 0,
  padding: "32px 0",
} as const;

export const container = {
  width: "560px",
  maxWidth: "100%",
  margin: "0 auto",
  backgroundColor: BRAND.card,
  border: `1px solid ${BRAND.border}`,
  borderTop: `3px solid ${BRAND.conifer}`,
} as const;

export const header = {
  padding: "22px 32px 0",
  display: "flex" as const,
  justifyContent: "space-between" as const,
  alignItems: "baseline" as const,
};

export const wordmark = {
  fontFamily: BRAND.display,
  fontWeight: 600,
  fontSize: "22px",
  letterSpacing: "-0.01em",
  color: BRAND.conifer,
  margin: 0,
};

export const kicker = {
  fontFamily: BRAND.body,
  fontSize: "10px",
  fontWeight: 600,
  letterSpacing: "0.18em",
  textTransform: "uppercase" as const,
  color: BRAND.brass,
  margin: 0,
};

export const h1 = {
  fontFamily: BRAND.display,
  fontWeight: 600,
  fontSize: "30px",
  lineHeight: 1.05,
  letterSpacing: "-0.015em",
  color: BRAND.ink,
  margin: "14px 0 18px",
} as const;

export const p = {
  fontFamily: BRAND.body,
  fontSize: "15px",
  lineHeight: 1.55,
  color: BRAND.inkSoft,
  margin: "0 0 14px",
} as const;

export const meta = {
  fontFamily: BRAND.mono,
  fontSize: "12px",
  color: BRAND.muted,
  margin: 0,
} as const;

export const button = {
  display: "inline-block",
  backgroundColor: BRAND.conifer,
  color: "#ffffff",
  textDecoration: "none",
  padding: "12px 22px",
  borderRadius: "2px",
  fontFamily: BRAND.body,
  fontWeight: 600,
  fontSize: "14px",
} as const;

export const panel = {
  border: `1px solid ${BRAND.border}`,
  padding: "18px",
  margin: "8px 0 22px",
  backgroundColor: BRAND.paper,
} as const;

export function Shell({
  preview,
  kickerText,
  organizationName = "NewTaven",
  organizationWebsite = "",
  children,
}: {
  preview: string;
  kickerText: string;
  organizationName?: string;
  organizationWebsite?: string;
  children: React.ReactNode;
}) {
  return (
    <Html>
      <Head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="stylesheet" href={fonts.href} />
      </Head>
      <Preview>{preview}</Preview>
      <Body style={main}>
        <Container style={container}>
          <Section style={header}>
            <Text style={wordmark}>{organizationName}</Text>
            <Text style={kicker}>{kickerText}</Text>
          </Section>
          <Section style={{ padding: "8px 32px 32px" }}>{children}</Section>
          <Hr style={{ borderColor: BRAND.border, margin: 0 }} />
          <Section style={{ padding: "20px 32px", backgroundColor: BRAND.conifer }}>
            <Text style={{ ...meta, color: "rgba(251,249,244,0.72)" }}>
              {organizationName}
            </Text>
            <Text style={{ ...meta, color: "rgba(251,249,244,0.5)", marginTop: 6 }}>
              {organizationWebsite ? `${organizationWebsite} · ` : ""}
              Delivered by NewTaven
            </Text>
          </Section>
        </Container>
      </Body>
    </Html>
  );
}

export function MetaRow({
  label,
  value,
  accent = false,
  valueSize = "18px",
  valueStyle,
}: {
  label: string;
  value: string;
  accent?: boolean;
  valueSize?: string;
  valueStyle?: CSSProperties;
}) {
  return (
    <div>
      <Text style={kicker}>{label}</Text>
      <Text
        style={{
          fontFamily: BRAND.mono,
          fontWeight: 600,
          fontSize: valueSize,
          color: accent ? BRAND.brass : BRAND.ink,
          margin: "4px 0 0",
          ...valueStyle,
        }}
      >
        {value}
      </Text>
    </div>
  );
}

export function MetaDivider() {
  return (
    <Hr style={{ borderColor: BRAND.border, borderTopWidth: 1, margin: "14px 0" }} />
  );
}
