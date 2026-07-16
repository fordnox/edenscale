import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker } from "@/layout/Shell";
import { Bullets, Note, SeriesFooter } from "@/layout/Drip";

// Day 4 of the investor onboarding drip — Distributions.
// Variables: recipient_name, app_url, organization_name, organization_website

export const subject = () => "What has been returned";

export default function DripDay4() {
  return (
    <Shell
      preview="Distribution notices, payment dates, and your allocation"
      kickerText="Distributions · 4 of 7"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>What has been returned.</Text>
      <Text style={p}>
        {"{{{recipient_name}}}"} — the mirror of yesterday’s note. When a fund
        realises a position and returns capital, the distribution notice lands
        here, at your share.
      </Text>
      <Text style={p}>
        Two figures head the page: lifetime distributed, and what you have
        received to date. The gap between them is money announced but not yet
        settled.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Reading the table</Text>
        <Bullets
          items={[
            {
              label: "Your amount",
              body: "Your share of each distribution, per fund, with the date it was declared.",
            },
            {
              label: "Received",
              body:
                "A percentage against each notice, so a distribution paid in tranches reads correctly.",
            },
            {
              label: "The detail view",
              body:
                "Open a row for the payment date, the record date, the manager’s note, and your allocation with the date each part was received.",
            },
          ]}
        />
      </Section>

      <Note>
        Distributions appear in the Overview table under Distributed and feed
        your TVPI. If you are reconciling a payment against your own records,
        this page and the archive are the two places to look.
      </Note>

      <Section style={{ textAlign: "center", margin: "18px 0 4px" }}>
        <Button href="{{{app_url}}}" style={button}>
          View distributions
        </Button>
      </Section>

      <SeriesFooter day={4} next="Next: your quarterly and annual reports." />
    </Shell>
  );
}
