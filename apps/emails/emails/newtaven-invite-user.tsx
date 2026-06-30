import { Button, Heading, Hr, Link, Section, Text } from 'react-email';
import { NewTavenEmailLayout, styles } from './_components/newtaven-layout';

interface NewTavenInviteUserEmailProps {
  inviteeEmail?: string;
  organizationName?: string;
  inviterName?: string;
  role?: 'superadmin' | 'admin' | 'fund_manager' | 'lp';
  acceptUrl?: string;
  expiresAt?: string;
}

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Superadmin',
  admin: 'Admin',
  fund_manager: 'Fund Manager',
  lp: 'Limited Partner',
};

export const NewTavenInviteUserEmail = ({
  inviteeEmail,
  organizationName,
  inviterName,
  role,
  acceptUrl,
  expiresAt,
}: NewTavenInviteUserEmailProps) => {
  const roleLabel = role ? ROLE_LABELS[role] : undefined;
  const previewText = `Join ${organizationName} on NewTaven`;

  return (
    <NewTavenEmailLayout previewText={previewText} eyebrowLabel="Invitation">
      <Heading style={styles.heading}>
        Join <strong>{organizationName}</strong> on NewTaven
      </Heading>

      <Text style={styles.paragraph}>
        {inviterName ? (
          <>
            <strong>{inviterName}</strong> has invited you to join{' '}
            <strong>{organizationName}</strong>
            {roleLabel ? <> as {roleLabel}</> : null} on NewTaven.
          </>
        ) : (
          <>
            You have been invited to join <strong>{organizationName}</strong>
            {roleLabel ? <> as {roleLabel}</> : null} on NewTaven.
          </>
        )}
      </Text>

      <Section style={styles.buttonWrap}>
        <Button style={styles.button} href={acceptUrl}>
          Accept invitation
        </Button>
      </Section>

      <Text style={styles.paragraph}>
        Or copy and paste this link into your browser:{' '}
        <Link href={acceptUrl} style={styles.link}>
          {acceptUrl}
        </Link>
      </Text>

      <Hr style={styles.hr} />

      <Text style={styles.footer}>
        This invitation was sent to{' '}
        <span style={styles.footerEmphasis}>{inviteeEmail}</span>
        {expiresAt ? (
          <>
            {' '}
            and expires on{' '}
            <span style={styles.footerEmphasis}>{expiresAt}</span>
          </>
        ) : null}
        . If you were not expecting this invitation, you can ignore this
        email.
      </Text>
    </NewTavenEmailLayout>
  );
};

NewTavenInviteUserEmail.PreviewProps = {
  inviteeEmail: 'alex.rivera@example.com',
  organizationName: 'Marlowe Capital Partners',
  inviterName: 'Eleanor Vance',
  role: 'fund_manager',
  acceptUrl: 'https://app.newtaven.com/invitations/accept?token=8f3c1b2a',
  expiresAt: 'July 15, 2026',
} as NewTavenInviteUserEmailProps;

export default NewTavenInviteUserEmail;
