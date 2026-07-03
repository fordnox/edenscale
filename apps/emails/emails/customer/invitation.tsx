import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker, MetaRow, MetaDivider } from "@/layout/Shell";

// Variables (mirror notify_invitation in backend/app/services/notifications.py):
//   inviter_name, role_label, accept_url, invitee_email, expires_at,
//   organization_name, organization_website

export const subject = () =>
  "You're invited to join {{{organization_name}}} on NewTaven";

export default function CustomerInvitation() {
  return (
    <Shell
      preview="{{{inviter_name}}} invited you to {{{organization_name}}}"
      kickerText="Invitation"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>You've been invited.</Text>
      <Text style={p}>
        {"{{{inviter_name}}}"} has invited you to join{" "}
        <b>{"{{{organization_name}}}"}</b> on NewTaven as{" "}
        {"{{{role_label}}}"}.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Invitation</Text>
        <MetaRow label="Email" value="{{{invitee_email}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Role" value="{{{role_label}}}" valueSize="16px" accent />
        <MetaDivider />
        <MetaRow label="Expires" value="{{{expires_at}}}" valueSize="16px" />
      </Section>

      <Section style={{ textAlign: "center", margin: "8px 0 4px" }}>
        <Button href="{{{accept_url}}}" style={button}>
          Accept invitation
        </Button>
      </Section>
    </Shell>
  );
}
