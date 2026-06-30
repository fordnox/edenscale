import { Button, Heading, Hr, Section, Text } from 'react-email';
import {
  colors,
  fontSans,
  NewTavenEmailLayout,
  styles,
} from './_components/newtaven-layout';

interface NewTavenCapitalCallEmailProps {
  recipientName?: string;
  organizationName?: string;
  investorName?: string;
  fundName?: string;
  callTitle?: string;
  description?: string;
  currencyCode?: string;
  amountDue?: string;
  dueDate?: string;
  callDate?: string;
  committedAmount?: string;
  calledToDateAmount?: string;
  unfundedAmount?: string;
  viewUrl?: string;
}

const Stat = ({
  label,
  value,
  borderRight,
  borderTop,
}: {
  label: string;
  value?: string;
  borderRight?: boolean;
  borderTop?: boolean;
}) => (
  <td
    style={{
      ...statCell,
      ...(borderRight ? { borderRight: `1px solid ${colors.borderHairline}` } : null),
      ...(borderTop ? { borderTop: `1px solid ${colors.borderHairline}` } : null),
    }}
  >
    <Text style={statLabel}>{label}</Text>
    <Text style={statValue}>{value || '—'}</Text>
  </td>
);

const LedgerRow = ({
  label,
  value,
  total,
}: {
  label: string;
  value?: string;
  total?: boolean;
}) => {
  if (!value) return null;
  return (
    <table width="100%" cellPadding="0" cellSpacing="0" role="presentation">
      <tbody>
        <tr style={total ? ledgerRowTotal : ledgerRow}>
          <td style={total ? ledgerLabelTotal : ledgerLabel}>{label}</td>
          <td style={total ? ledgerValueTotal : ledgerValue}>{value}</td>
        </tr>
      </tbody>
    </table>
  );
};

export const NewTavenCapitalCallEmail = ({
  recipientName,
  organizationName,
  investorName,
  fundName,
  callTitle,
  description,
  currencyCode = 'USD',
  amountDue,
  dueDate,
  callDate,
  committedAmount,
  calledToDateAmount,
  unfundedAmount,
  viewUrl,
}: NewTavenCapitalCallEmailProps) => {
  const previewText = `Capital call for ${fundName}: ${amountDue} due ${dueDate}`;

  return (
    <NewTavenEmailLayout previewText={previewText} eyebrowLabel="Capital Call">
      <Heading style={styles.heading}>
        {callTitle || `${fundName} capital call`}
      </Heading>

      <Text style={styles.paragraph}>
        {recipientName ? `Dear ${recipientName},` : 'Dear investor,'}
      </Text>
      <Text style={styles.paragraph}>
        <strong>{organizationName}</strong> has issued a capital call for{' '}
        <strong>{fundName}</strong>. Please arrange for payment of the amount
        below by the due date. Wiring instructions are available in the
        investor portal — we never send banking details by email.
      </Text>

      <table width="100%" cellPadding="0" cellSpacing="0" role="presentation" style={statTable}>
        <tbody>
          <tr>
            <Stat label="Investor" value={investorName} borderRight />
            <Stat label="Amount due" value={amountDue} />
          </tr>
          <tr>
            <Stat label="Fund" value={fundName} borderRight borderTop />
            <Stat label="Due date" value={dueDate} borderTop />
          </tr>
        </tbody>
      </table>

      <Section style={styles.buttonWrap}>
        <Button style={styles.button} href={viewUrl}>
          View in investor portal
        </Button>
      </Section>

      <Hr style={styles.hr} />

      <Text style={styles.sectionTitle}>
        Notice summary {currencyCode ? `(${currencyCode})` : ''}
      </Text>
      <Section style={styles.dataCard}>
        <LedgerRow label="This capital call" value={amountDue} />
        {callDate ? <LedgerRow label="Notice date" value={callDate} /> : null}
        <LedgerRow label="Total commitment" value={committedAmount} />
        <LedgerRow
          label="Called to date (including this call)"
          value={calledToDateAmount}
        />
        <LedgerRow label="Remaining commitment" value={unfundedAmount} total />
      </Section>

      {description ? (
        <>
          <Text style={styles.sectionTitle}>Reason for this capital call</Text>
          <Text style={styles.paragraph}>{description}</Text>
        </>
      ) : null}

      <Text style={styles.paragraph}>
        Kind regards,
        <br />
        {organizationName}
      </Text>

      <Hr style={styles.hr} />

      <Text style={securityTitle}>A note on payment security</Text>
      <Text style={styles.footer}>
        {organizationName} will never request banking details or wiring
        instructions by email. Always verify payment instructions inside the
        investor portal before sending funds, and contact {organizationName}{' '}
        directly if a request looks unfamiliar.
      </Text>
    </NewTavenEmailLayout>
  );
};

NewTavenCapitalCallEmail.PreviewProps = {
  recipientName: 'Priya Anand',
  organizationName: 'Marlowe Capital Partners',
  investorName: 'Anand Family Office, LLC',
  fundName: 'Marlowe Capital Partners III',
  callTitle: 'Capital Call No. 4',
  description: 'Proceeds will fund the acquisition of a follow-on position.',
  currencyCode: 'USD',
  amountDue: '$250,000.00',
  dueDate: 'July 22, 2026',
  callDate: 'July 1, 2026',
  committedAmount: '$5,000,000.00',
  calledToDateAmount: '$3,250,000.00',
  unfundedAmount: '$1,750,000.00',
  viewUrl: 'https://app.newtaven.com/calls',
} as NewTavenCapitalCallEmailProps;

export default NewTavenCapitalCallEmail;

const statTable = {
  border: `1px solid ${colors.borderHairline}`,
  margin: '24px 0 24px',
};

const statCell = {
  width: '50%',
  padding: '16px 20px',
  verticalAlign: 'top' as const,
};

const statLabel = {
  fontFamily: fontSans,
  fontSize: '11px',
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.1em',
  color: colors.ink500,
  margin: '0 0 4px',
};

const statValue = {
  fontFamily: fontSans,
  fontSize: '18px',
  fontWeight: 600,
  color: colors.ink900,
  margin: 0,
  fontVariantNumeric: 'tabular-nums' as const,
};

const ledgerRow = {
  borderTop: `1px solid ${colors.borderHairline}`,
};

const ledgerRowTotal = {
  borderTop: `1px solid ${colors.ink900}`,
};

const ledgerLabel = {
  fontFamily: fontSans,
  fontSize: '13px',
  color: colors.ink500,
  padding: '12px 0',
  textAlign: 'left' as const,
};

const ledgerValue = {
  fontFamily: fontSans,
  fontSize: '13px',
  fontWeight: 600,
  color: colors.ink900,
  padding: '12px 0',
  textAlign: 'right' as const,
  fontVariantNumeric: 'tabular-nums' as const,
};

const ledgerLabelTotal = {
  ...ledgerLabel,
  fontWeight: 600,
  color: colors.ink900,
};

const ledgerValueTotal = {
  ...ledgerValue,
  fontSize: '14px',
};

const securityTitle = {
  fontFamily: fontSans,
  fontSize: '12px',
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.08em',
  color: colors.ink500,
  margin: '0 0 8px',
};
