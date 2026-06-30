import { Button, Heading, Hr, Section, Text } from 'react-email';
import { NewTavenEmailLayout, styles } from './_components/newtaven-layout';

interface NewTavenWelcomeEmailProps {
  firstName?: string;
  organizationName?: string;
  dashboardUrl?: string;
  recipientEmail?: string;
}

export const NewTavenWelcomeEmail = ({
  firstName,
  organizationName,
  dashboardUrl,
  recipientEmail,
}: NewTavenWelcomeEmailProps) => {
  const previewText = organizationName
    ? `Your NewTaven account for ${organizationName} is ready`
    : 'Your NewTaven account is ready';

  return (
    <NewTavenEmailLayout previewText={previewText} eyebrowLabel="Welcome">
      <Heading style={styles.heading}>
        Welcome to NewTaven{firstName ? `, ${firstName}` : ''}.
      </Heading>

      <Text style={styles.paragraph}>
        Your account is ready
        {organizationName ? (
          <>
            {' '}
            for <strong>{organizationName}</strong>
          </>
        ) : null}
        . You can sign in and pick up where you left off whenever you're
        ready.
      </Text>

      <Section style={styles.buttonWrap}>
        <Button style={styles.button} href={dashboardUrl}>
          Go to dashboard
        </Button>
      </Section>

      <Hr style={styles.hr} />

      <Text style={styles.footer}>
        This email was sent to{' '}
        <span style={styles.footerEmphasis}>{recipientEmail}</span> because a
        NewTaven account was created with this address.
      </Text>
    </NewTavenEmailLayout>
  );
};

NewTavenWelcomeEmail.PreviewProps = {
  firstName: 'Alex',
  organizationName: 'Marlowe Capital Partners',
  dashboardUrl: 'https://app.newtaven.com/',
  recipientEmail: 'alex.rivera@example.com',
} as NewTavenWelcomeEmailProps;

export default NewTavenWelcomeEmail;
