import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button } from "@/layout/Shell";

// Variables (mirror notify_welcome in backend/app/services/notifications.py):
//   recipient_name, app_url, organization_name, organization_website

export const subject = () => "Welcome to {{{organization_name}}}";

export default function CustomerWelcome() {
  return (
    <Shell
      preview="Your {{{organization_name}}} account is ready"
      kickerText="Welcome"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>Your account is ready.</Text>
      <Text style={p}>
        Hi {"{{{recipient_name}}}"} — your access to{" "}
        <b>{"{{{organization_name}}}"}</b> on NewTaven is live. You can review
        capital calls, distributions, documents and reporting in one place.
      </Text>
      <Section style={{ textAlign: "center", margin: "18px 0 4px" }}>
        <Button href="{{{app_url}}}" style={button}>
          Open NewTaven
        </Button>
      </Section>
    </Shell>
  );
}
