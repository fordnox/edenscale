import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker, MetaRow, MetaDivider } from "@/layout/Shell";

// Variables (mirror notify_capital_call in backend/app/services/notifications.py):
//   recipient_name, call_title, investor_name, fund_name, currency_code,
//   amount_due, due_date, call_date, committed_amount, called_to_date,
//   unfunded_amount, view_url, description, organization_name, organization_website

export const subject = () =>
  "Capital call: {{{call_title}}} — {{{fund_name}}}";

export default function CustomerCapitalCall() {
  return (
    <Shell
      preview="Capital call for {{{fund_name}}} · due {{{due_date}}}"
      kickerText="Capital Call"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>{"{{{call_title}}}"}</Text>
      <Text style={p}>
        Dear {"{{{recipient_name}}}"}, a capital call has been issued for{" "}
        <b>{"{{{investor_name}}}"}</b> in {"{{{fund_name}}}"}.
      </Text>

      <Section style={panel}>
        <MetaRow label="Amount due" value="{{{amount_due}}}" valueSize="26px" accent />
        <MetaDivider />
        <MetaRow label="Due date" value="{{{due_date}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Call date" value="{{{call_date}}}" valueSize="16px" />
      </Section>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Commitment</Text>
        <MetaRow label="Committed" value="{{{committed_amount}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Called to date" value="{{{called_to_date}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Remaining unfunded" value="{{{unfunded_amount}}}" valueSize="16px" />
      </Section>

      <Text style={{ ...p, color: "#6f6e68", fontSize: "13px" }}>
        {"{{{description}}}"}
      </Text>

      <Section style={{ textAlign: "center", margin: "8px 0 4px" }}>
        <Button href="{{{view_url}}}" style={button}>
          View capital call
        </Button>
      </Section>
    </Shell>
  );
}
