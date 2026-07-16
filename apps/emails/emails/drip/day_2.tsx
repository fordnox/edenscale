import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker } from "@/layout/Shell";
import { Bullets, Note, SeriesFooter } from "@/layout/Drip";

// Day 2 of the investor onboarding drip — Funds and fund detail.
// Variables: recipient_name, app_url, organization_name, organization_website

export const subject = () => "The funds you hold";

export default function DripDay2() {
  return (
    <Shell
      preview="Your commitment, your position, and fund-level performance"
      kickerText="Funds · 2 of 7"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>Funds you hold.</Text>
      <Text style={p}>
        {"{{{recipient_name}}}"} — the Funds tab lists every fund you are
        committed to: the fund name, its vintage year, your commitment, and
        whether it is active, closed or liquidating.
      </Text>
      <Text style={p}>
        Open a fund and you get two views side by side — your position, and the
        fund’s own performance. The distinction matters, so we keep them apart
        rather than blending them into one number.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Your position</Text>
        <Bullets
          items={[
            {
              label: "Committed, called, distributed",
              body:
                "What you signed up for, what has been drawn down so far — shown as a percentage of your commitment — and what has come back.",
            },
            {
              label: "Your value",
              body:
                "Your pro-rata share of the fund’s fair value, with your TVPI alongside it.",
            },
          ]}
        />
      </Section>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Fund performance</Text>
        <Bullets
          items={[
            {
              label: "Net IRR, DPI, TVPI",
              body:
                "The fund-wide figures, so you can read your position against the whole.",
            },
            {
              label: "Fund NAV",
              body:
                "The latest mark. Until a fund is marked, we show DPI — cash actually returned — rather than a valuation we cannot yet stand behind.",
            },
          ]}
        />
      </Section>

      <Note>
        Each fund page also carries its own capital calls and distributions, so
        you can review a single programme end to end without leaving it.
      </Note>

      <Section style={{ textAlign: "center", margin: "18px 0 4px" }}>
        <Button href="{{{app_url}}}" style={button}>
          Review your funds
        </Button>
      </Section>

      <SeriesFooter day={2} next="Next: capital calls, and how to read what has been called." />
    </Shell>
  );
}
