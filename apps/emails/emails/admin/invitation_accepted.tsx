import { Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, panel, kicker, MetaRow, MetaDivider } from "@/layout/Shell";

// Variables (mirror notify_invitation_accepted in backend/app/services/notifications.py):
//   accepted_name, accepted_email, role_label, organization_name,
//   organization_website

export const subject = () => "Invitation accepted — {{{accepted_name}}}";

export default function AdminInvitationAccepted() {
  return (
    <Shell
      preview="{{{accepted_name}}} joined {{{organization_name}}}"
      kickerText="Membership"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>An invitation was accepted.</Text>
      <Text style={p}>
        {"{{{accepted_name}}}"} has accepted their invitation and joined{" "}
        <b>{"{{{organization_name}}}"}</b>.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>New member</Text>
        <MetaRow label="Name" value="{{{accepted_name}}}" valueSize="16px" accent />
        <MetaDivider />
        <MetaRow label="Email" value="{{{accepted_email}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Role" value="{{{role_label}}}" valueSize="16px" />
      </Section>
    </Shell>
  );
}
