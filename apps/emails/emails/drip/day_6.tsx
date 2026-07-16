import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker } from "@/layout/Shell";
import { Bullets, Note, SeriesFooter } from "@/layout/Drip";

// Day 6 of the investor onboarding drip — Documents / data room.
// Variables: recipient_name, app_url, organization_name, organization_website

export const subject = () => "The data room";

export default function DripDay6() {
  return (
    <Shell
      preview="Every document shared with you, and how access is handled"
      kickerText="Documents · 6 of 7"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>Your documents.</Text>
      <Text style={p}>
        {"{{{recipient_name}}}"} — reports, notices, statements and legal
        paperwork shared with you sit in one list, with the fund they belong to
        and the date they were filed.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>What each row tells you</Text>
        <Bullets
          items={[
            {
              label: "The document, and the file",
              body:
                "The title, plus the underlying file name and size — so you know what you are opening before you open it.",
            },
            {
              label: "Fund and type",
              body:
                "Which programme it belongs to, and whether it is legal, KYC / AML, financial, a report or a notice. Firm-wide papers show no fund.",
            },
            {
              label: "Download",
              body: "One action per row. The file opens in a new tab.",
            },
          ]}
        />
      </Section>

      <Note>
        Download links are private and time-limited. They are generated for you
        when the page loads, which is why a copied link will not work later or
        for someone else — and why forwarding one does not share the document.
      </Note>

      <Text style={p}>
        If the list grows long, press ⌘K — or Ctrl+K — anywhere in the portal to
        search your funds and documents, and to jump to any page.
      </Text>

      <Section style={{ textAlign: "center", margin: "18px 0 4px" }}>
        <Button href="{{{app_url}}}" style={button}>
          Open the data room
        </Button>
      </Section>

      <SeriesFooter day={6} next="Next: letters, and staying current." />
    </Shell>
  );
}
