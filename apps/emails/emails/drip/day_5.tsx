import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker } from "@/layout/Shell";
import { Bullets, Note, SeriesFooter } from "@/layout/Drip";

// Day 5 of the investor onboarding drip — Reports.
// Variables: recipient_name, app_url, organization_name, organization_website

export const subject = () => "Your quarterly and annual reports";

export default function DripDay5() {
  return (
    <Shell
      preview="The latest report per fund, and the history behind it"
      kickerText="Reports · 5 of 7"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>Your reports.</Text>
      <Text style={p}>
        {"{{{recipient_name}}}"} — reporting is the part of the relationship you
        will return to most, so it has a page of its own rather than being
        buried in a folder tree.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>How it is organised</Text>
        <Bullets
          items={[
            {
              label: "Grouped by fund",
              body:
                "Each fund you hold gets its own section. Reports that apply to the whole firm are grouped as Firm-wide.",
            },
            {
              label: "The latest is surfaced first",
              body:
                "The most recent report for each fund sits at the top with its publication date, ready to view or download.",
            },
            {
              label: "The history sits beneath it",
              body:
                "Every earlier report stays available, newest first. Nothing is retired when a new quarter is published.",
            },
          ]}
        />
      </Section>

      <Note>
        Reports are also filed in Documents alongside everything else shared with
        you. This page is the reading view; Documents is the record.
      </Note>

      <Section style={{ textAlign: "center", margin: "18px 0 4px" }}>
        <Button href="{{{app_url}}}" style={button}>
          Read your latest report
        </Button>
      </Section>

      <SeriesFooter day={5} next="Next: the data room." />
    </Shell>
  );
}
