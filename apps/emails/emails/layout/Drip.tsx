import { Hr, Section, Text } from "@react-email/components";
import * as React from "react";
import { BRAND, kicker } from "./Shell";

// Shared furniture for the 7-day investor onboarding drip (emails/drip/*).
//
// This lives under layout/ deliberately: scripts/push-templates.mts walks every
// .tsx under emails/ and pushes it to Resend as a template, excluding only
// paths containing "/layout/". A helper module placed in emails/drip/ would be
// picked up and pushed as if it were a real template.

/**
 * A labelled feature list — the "what you'll see" block in each drip email.
 * Rendered as stacked rows with hairline rules rather than bullets: the brand
 * leans on the hairline rule instead of dingbats, and `list-style` support is
 * inconsistent across email clients anyway.
 */
export function Bullets({
  items,
}: {
  items: { label: string; body: string }[];
}) {
  return (
    <>
      {items.map((item, i) => (
        <div key={item.label}>
          {i > 0 && (
            <Hr
              style={{ borderColor: BRAND.border, borderTopWidth: 1, margin: "14px 0" }}
            />
          )}
          <Text
            style={{
              fontFamily: BRAND.body,
              fontWeight: 600,
              fontSize: "14px",
              color: BRAND.ink,
              margin: 0,
            }}
          >
            {item.label}
          </Text>
          <Text
            style={{
              fontFamily: BRAND.body,
              fontSize: "14px",
              lineHeight: 1.5,
              color: BRAND.muted,
              margin: "3px 0 0",
            }}
          >
            {item.body}
          </Text>
        </div>
      ))}
    </>
  );
}

/**
 * A quiet aside — used for the caveats that matter to an LP reading figures
 * (e.g. "amounts are your share of each fund").
 */
export function Note({ children }: { children: React.ReactNode }) {
  return (
    <Section
      style={{
        borderLeft: `2px solid ${BRAND.brassSoft}`,
        padding: "2px 0 2px 14px",
        margin: "0 0 22px",
      }}
    >
      <Text
        style={{
          fontFamily: BRAND.body,
          fontSize: "13px",
          lineHeight: 1.5,
          color: BRAND.muted,
          margin: 0,
        }}
      >
        {children}
      </Text>
    </Section>
  );
}

/**
 * Series position, closing each email. Tells the reader where they are in the
 * seven days and what lands next, so the sequence reads as one piece.
 */
export function SeriesFooter({ day, next }: { day: number; next?: string }) {
  return (
    <>
      <Hr style={{ borderColor: BRAND.border, margin: "28px 0 14px" }} />
      <Text style={{ ...kicker, margin: 0 }}>
        {`Day ${day} of 7`}
      </Text>
      <Text
        style={{
          fontFamily: BRAND.body,
          fontSize: "13px",
          color: BRAND.muted,
          margin: "6px 0 0",
        }}
      >
        {next ?? "That is the tour. The portal is yours from here."}
      </Text>
    </>
  );
}
