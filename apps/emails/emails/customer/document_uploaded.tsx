import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker, MetaRow, MetaDivider } from "@/layout/Shell";

// Variables (mirror notify_document_uploaded in backend/app/services/notifications.py):
//   recipient_name, document_title, document_type_label, fund_name, uploaded_at,
//   view_url, organization_name, organization_website

export const subject = () => "New document: {{{document_title}}}";

export default function CustomerDocumentUploaded() {
  return (
    <Shell
      preview="A new document is available in {{{organization_name}}}"
      kickerText="Document"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>A new document is available.</Text>
      <Text style={p}>
        Dear {"{{{recipient_name}}}"}, a new document has been shared with you.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Document</Text>
        <MetaRow label="Title" value="{{{document_title}}}" valueSize="16px" accent />
        <MetaDivider />
        <MetaRow label="Type" value="{{{document_type_label}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Fund" value="{{{fund_name}}}" valueSize="16px" />
        <MetaDivider />
        <MetaRow label="Uploaded" value="{{{uploaded_at}}}" valueSize="16px" />
      </Section>

      <Section style={{ textAlign: "center", margin: "8px 0 4px" }}>
        <Button href="{{{view_url}}}" style={button}>
          View document
        </Button>
      </Section>
    </Shell>
  );
}
