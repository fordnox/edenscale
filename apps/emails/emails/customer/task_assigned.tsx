import { Button, Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, button, panel, kicker, MetaRow, MetaDivider } from "@/layout/Shell";

// Variables (mirror notify_task_assigned in backend/app/services/notifications.py):
//   recipient_name, task_title, task_description, due_date, view_url,
//   organization_name, organization_website

export const subject = () => "Task assigned: {{{task_title}}}";

export default function CustomerTaskAssigned() {
  return (
    <Shell
      preview="A task was assigned to you: {{{task_title}}}"
      kickerText="Task"
      organizationName="{{{organization_name}}}"
      organizationWebsite="{{{organization_website}}}"
    >
      <Text style={h1}>A task was assigned to you.</Text>
      <Text style={p}>
        Hi {"{{{recipient_name}}}"} — {"{{{task_title}}}"} is now assigned to you.
      </Text>

      <Section style={panel}>
        <Text style={{ ...kicker, marginBottom: 14 }}>Task</Text>
        <MetaRow label="Title" value="{{{task_title}}}" valueSize="16px" accent />
        <MetaDivider />
        <MetaRow label="Due" value="{{{due_date}}}" valueSize="16px" />
      </Section>

      <Text style={{ ...p, color: "#6f6e68", fontSize: "13px" }}>
        {"{{{task_description}}}"}
      </Text>

      <Section style={{ textAlign: "center", margin: "8px 0 4px" }}>
        <Button href="{{{view_url}}}" style={button}>
          Open in NewTaven
        </Button>
      </Section>
    </Shell>
  );
}
