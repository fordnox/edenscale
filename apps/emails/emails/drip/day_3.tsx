import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker } from "@/layout/Shell";
import { Bullets, Note, SeriesFooter } from "@/layout/Drip";

// Day 3 of the investor onboarding drip — Capital calls.
// Variables: recipient_name, app_url, organization_name, organization_website

export const subject = () => "What has been called";

export default function DripDay3() {
  return (
    <Shell
      preview="Drawdown notices, funding status, and your own allocation"
      kickerText="Capital Calls · 3 of 7"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>What has been called.</Text>
      <Text style={p}>
        {"{{{recipient_name}}}"} — when a fund draws down capital, the notice
        appears here and you receive an email. The Capital Calls tab is the
        record of every drawdown against your commitments.
      </Text>
      <Text style={p}>
        Three figures sit at the top: what is outstanding right now, and how
        much has been called and paid over the life of your commitments.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Reading the table</Text>
        <Bullets
          items={[
            {
              label: "Your amount",
              body:
                "The call is shown at your share, not the fund’s. No arithmetic required.",
            },
            {
              label: "Paid",
              body:
                "A percentage against each call, so a partial payment is visible as a partial payment. Overdue calls are marked in brass.",
            },
            {
              label: "Status",
              body:
                "Scheduled, sent, partially paid, paid, or overdue — the state of the notice, not a reminder to act.",
            },
          ]}
        />
      </Section>

      <Text style={p}>
        Open any row for the full notice: the due date, the call date, the
        manager’s description, and your allocation line by line with the date
        each part was paid.
      </Text>

      <Note>
        You only ever see your own allocation. Other investors’ positions in the
        same call are never exposed to you, and yours is never exposed to them.
      </Note>

      <Section style={{ textAlign: "center", margin: "18px 0 4px" }}>
        <Button href="{{{app_url}}}" style={button}>
          View capital calls
        </Button>
      </Section>

      <SeriesFooter day={3} next="Next: distributions — what has come back." />
    </Shell>
  );
}
