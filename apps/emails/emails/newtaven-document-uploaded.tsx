import { Button, Heading, Hr, Section, Text } from 'react-email';
import { Field, NewTavenEmailLayout, styles } from './_components/newtaven-layout';

interface NewTavenDocumentUploadedEmailProps {
  recipientName?: string;
  organizationName?: string;
  fundName?: string;
  documentTitle?: string;
  documentType?: 'legal' | 'kyc_aml' | 'financial' | 'report' | 'notice' | 'other';
  uploadedAt?: string;
  viewUrl?: string;
}

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  legal: 'Legal Document',
  kyc_aml: 'KYC/AML Document',
  financial: 'Financial Document',
  report: 'Fund Report',
  notice: 'Notice',
  other: 'Document',
};

export const NewTavenDocumentUploadedEmail = ({
  recipientName,
  organizationName,
  fundName,
  documentTitle,
  documentType = 'other',
  uploadedAt,
  viewUrl,
}: NewTavenDocumentUploadedEmailProps) => {
  const typeLabel = DOCUMENT_TYPE_LABELS[documentType] ?? DOCUMENT_TYPE_LABELS.other;
  const previewText = `${organizationName} has uploaded a new document: ${documentTitle}`;

  return (
    <NewTavenEmailLayout previewText={previewText} eyebrowLabel={typeLabel}>
      <Heading style={styles.heading}>{documentTitle}</Heading>

      <Text style={styles.paragraph}>
        {recipientName ? `Dear ${recipientName},` : 'Dear investor,'}
      </Text>
      <Text style={styles.paragraph}>
        <strong>{organizationName}</strong> has uploaded a new document
        {fundName ? (
          <>
            {' '}
            for <strong>{fundName}</strong>
          </>
        ) : null}
        . Select the button below to view it in the investor portal.
      </Text>

      <Section style={styles.dataCard}>
        <Field label="Fund" value={fundName} />
        <Field label="Uploaded" value={uploadedAt} />
      </Section>

      <Section style={styles.buttonWrap}>
        <Button style={styles.button} href={viewUrl}>
          View document
        </Button>
      </Section>

      <Text style={styles.paragraph}>
        Kind regards,
        <br />
        {organizationName}
      </Text>

      <Hr style={styles.hr} />

      <Text style={styles.footer}>
        {organizationName} documents are only available through the investor
        portal. If this notice looks unfamiliar, contact {organizationName}{' '}
        directly before opening any attachment.
      </Text>
    </NewTavenEmailLayout>
  );
};

NewTavenDocumentUploadedEmail.PreviewProps = {
  recipientName: 'Priya Anand',
  organizationName: 'Marlowe Capital Partners',
  fundName: 'Marlowe Capital Partners III',
  documentTitle: 'Q2 2026 Fund Report',
  documentType: 'report',
  uploadedAt: 'July 1, 2026',
  viewUrl: 'https://app.newtaven.com/documents',
} as NewTavenDocumentUploadedEmailProps;

export default NewTavenDocumentUploadedEmail;
