import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker, MetaRow, MetaDivider } from "@/layout/Shell";

// Variables (mirror notify_distribution in backend/app/services/notifications.py):
//   recipient_name, distribution_title, investor_name, fund_name, currency_code,
//   amount_receivable, payment_date, committed_amount, distributed_to_date,
//   view_url, description, organization_name, organization_website

export const subject = () =>
  "Distribution notice: {{{distribution_title}}} — {{{fund_name}}}";

export default function CustomerDistribution() {
  return (
    <Shell
      preview="Distribution from {{{fund_name}}} · paid {{{payment_date}}}"
      kickerText="Distribution"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>{"{{{distribution_title}}}"}</Text>
      <Text style={p}>
        Dear {"{{{recipient_name}}}"}, a distribution has been issued for{" "}
        <b>{"{{{investor_name}}}"}</b> in {"{{{fund_name}}}"}.
      </Text>

      <Section style={panel}>
        <MetaRow label="Amount receivable" value="{{{amount_receivable}}}" valueSize="26px" accent />
        <MetaDivider />
        <MetaRow label="Payment date" value="{{{payment_date}}}" valueSize="16px" />
      </Section>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Commitment</Text>
        <MetaRow label="Committed" value="{{{committed_amount}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Distributed to date" value="{{{distributed_to_date}}}" valueSize="16px" />
      </Section>

      <Text style={{ ...p, color: "#6f6e68", fontSize: "13px" }}>
        {"{{{description}}}"}
      </Text>

      <Section style={{ textAlign: "center", margin: "8px 0 4px" }}>
        <Button href="{{{view_url}}}" style={button}>
          View distribution
        </Button>
      </Section>
    </Shell>
  );
}
