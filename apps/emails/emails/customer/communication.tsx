import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel } from "@/layout/Shell";

// Variables (mirror notify_communication in backend/app/services/notifications.py):
//   communication_type_label, subject, body_preview, view_url,
//   organization_name, organization_website

export const subject = () => "{{{communication_type_label}}}: {{{subject}}}";

export default function CustomerCommunication() {
  return (
    <Shell
      preview="{{{communication_type_label}}} from {{{organization_name}}}"
      kickerText="{{{communication_type_label}}}"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>{"{{{subject}}}"}</Text>
      <Section style={panel}>
        <Text style={{ ...p, margin: 0 }}>{"{{{body_preview}}}"}</Text>
      </Section>
      <Section style={{ textAlign: "center", margin: "8px 0 4px" }}>
        <Button href="{{{view_url}}}" style={button}>
          Read in NewTaven
        </Button>
      </Section>
    </Shell>
  );
}
