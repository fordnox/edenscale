import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker, MetaRow, MetaDivider } from "@/layout/Shell";

// Variables (mirror notify_commitment_status in backend/app/services/notifications.py):
//   recipient_name, fund_name, status_label, committed_amount, view_url,
//   organization_name, organization_website

export const subject = () => "Commitment {{{status_label}}} — {{{fund_name}}}";

export default function CustomerCommitmentStatus() {
  return (
    <Shell
      preview="Your commitment to {{{fund_name}}} is now {{{status_label}}}"
      kickerText="Commitment"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>Commitment {"{{{status_label}}}"}.</Text>
      <Text style={p}>
        Dear {"{{{recipient_name}}}"}, your commitment to{" "}
        <b>{"{{{fund_name}}}"}</b> is now {"{{{status_label}}}"}.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Commitment</Text>
        <MetaRow label="Fund" value="{{{fund_name}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Status" value="{{{status_label}}}" valueSize="16px" accent />
        <MetaDivider />
        <MetaRow label="Committed" value="{{{committed_amount}}}" valueSize="16px" />
      </Section>

      <Section style={{ textAlign: "center", margin: "8px 0 4px" }}>
        <Button href="{{{view_url}}}" style={button}>
          View commitment
        </Button>
      </Section>
    </Shell>
  );
}
