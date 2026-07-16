import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker } from "@/layout/Shell";
import { Bullets, Note, SeriesFooter } from "@/layout/Drip";

// Day 1 of the investor onboarding drip — Overview.
//
// Static template: the copy is fixed and describes the portal itself, so the
// only variables are the recipient and the sending organization. Nothing here
// is derived from the LP's own figures.
//
// Variables: recipient_name, app_url, organization_name, organization_website

export const subject = () => "Your portfolio, in one place";

export default function DripDay1() {
  return (
    <Shell
      preview="A short series on what you can do in the investor portal"
      kickerText="Overview · 1 of 7"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>Your portfolio, in one place.</Text>
      <Text style={p}>
        {"{{{recipient_name}}}"} — over the next seven days we will walk you
        through the investor portal, one part at a time. Each note takes about a
        minute to read.
      </Text>
      <Text style={p}>
        Start with the Overview. It is the page you land on, and it answers the
        question most limited partners open the portal to ask: where does my
        position stand today.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>What you will see</Text>
        <Bullets
          items={[
            {
              label: "A consolidated position table",
              body:
                "One row per fund — commitment, paid-in, distributed, unfunded, fair value, TVPI and net IRR — with a total across the funds you hold.",
            },
            {
              label: "Quick figures",
              body:
                "Committed capital, outstanding calls awaiting funding, distributions year to date, and unread notifications.",
            },
            {
              label: "Recent updates",
              body:
                "Capital notices, distributions and letters in one timeline, newest first. The full history lives in the archive.",
            },
          ]}
        />
      </Section>

      <Note>
        Every figure in the portal is your share of each fund, not the fund
        total. Where a fund has not been marked yet, fair value and TVPI show a
        dash rather than an estimate.
      </Note>

      <Section style={{ textAlign: "center", margin: "18px 0 4px" }}>
        <Button href="{{{app_url}}}" style={button}>
          Open the portal
        </Button>
      </Section>

      <SeriesFooter day={1} next="Next: the funds you hold, and how each one is performing." />
    </Shell>
  );
}
