import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker, MetaRow, MetaDivider } from "@/layout/Shell";

// Variables (mirror notify_letter_drafted in backend/app/services/notifications.py):
//   recipient_name, document_title, subject, view_url,
//   organization_name, organization_website

export const subject = () => "Your letter draft is ready";

export default function CustomerLetterDrafted() {
  return (
    <Shell
      preview="A draft letter based on {{{document_title}}} is ready to review"
      kickerText="Letter"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>Your letter draft is ready.</Text>
      <Text style={p}>
        Hi {"{{{recipient_name}}}"} — we drafted a letter from {"{{{document_title}}}"}.
        It's saved to your Letters as an unsent draft for you to review and edit.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Draft</Text>
        <MetaRow label="Subject" value="{{{subject}}}" valueSize="16px" accent />
        <MetaDivider />
        <MetaRow label="Source" value="{{{document_title}}}" valueSize="16px" />
      </Section>

      <Section style={{ textAlign: "center", margin: "8px 0 4px" }}>
        <Button href="{{{view_url}}}" style={button}>
          Review in NewTaven
        </Button>
      </Section>
    </Shell>
  );
}
