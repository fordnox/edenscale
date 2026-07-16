import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker } from "@/layout/Shell";
import { Bullets, Note, SeriesFooter } from "@/layout/Drip";

// Day 7 of the investor onboarding drip — Letters, notifications, archive.
// Closes the series.
// Variables: recipient_name, app_url, organization_name, organization_website

export const subject = () => "Letters, and staying current";

export default function DripDay7() {
  return (
    <Shell
      preview="Correspondence, your inbox, and the full history"
      kickerText="Letters · 7 of 7"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>Letters to you.</Text>
      <Text style={p}>
        {"{{{recipient_name}}}"} — announcements and notices from your fund
        managers are kept as letters, not as email you have to find again.
        Unread subjects are set in bold; opening a letter marks it read.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Three ways to stay current</Text>
        <Bullets
          items={[
            {
              label: "Letters",
              body:
                "The full text of every piece of correspondence, with the date it was sent and whether you have read it.",
            },
            {
              label: "Notifications",
              body:
                "Your inbox — capital activity, document releases and correspondence, grouped by today, yesterday, this week and earlier. Mark them read, or archive them once handled.",
            },
            {
              label: "Archive",
              body:
                "Everything, in order: every capital notice, distribution and letter for your account, newest first. Reachable from the Overview feed.",
            },
          ]}
        />
      </Section>

      <Note>
        Correspondence runs one way. If you need to reach your fund manager,
        reply to them directly — the portal is your record, not a mailbox.
      </Note>

      <Text style={p}>
        Two last things. Your details live under Profile, in the account menu —
        name, phone and title are yours to edit, while access is set by your
        fund manager. And if you invest through more than one firm, the switcher
        at the top left moves between them.
      </Text>

      <Section style={{ textAlign: "center", margin: "18px 0 4px" }}>
        <Button href="{{{app_url}}}" style={button}>
          Open the portal
        </Button>
      </Section>

      <SeriesFooter day={7} />
    </Shell>
  );
}
