import type { ReactNode } from 'react';
import { Body, Container, Head, Html, Preview, Section, Text } from 'react-email';

export const fontSans =
  '"Inter Tight", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif';
export const fontDisplay =
  '"Cormorant Garamond", Georgia, "Times New Roman", Times, serif';

export const colors = {
  conifer700: '#1F3D2E',
  brass700: '#8A6A3F',
  parchment50: '#FBF9F4',
  parchment100: '#F5F1E8',
  ink900: '#1A1A18',
  ink700: '#3A3A36',
  ink500: '#6F6E68',
  borderHairline: 'rgba(26, 26, 24, 0.10)',
};

export const styles = {
  main: {
    backgroundColor: colors.parchment50,
    fontFamily: fontSans,
    padding: '40px 0',
  },

  container: {
    margin: '0 auto',
    maxWidth: '560px',
    padding: '0 24px',
  },

  card: {
    backgroundColor: '#FFFFFF',
    border: `1px solid ${colors.borderHairline}`,
    borderRadius: '0px',
    padding: '40px',
  },

  wordmark: {
    fontFamily: fontSans,
    fontSize: '20px',
    fontWeight: 600,
    letterSpacing: '-0.02em',
    color: colors.conifer700,
    margin: '0 0 32px',
  },

  eyebrow: {
    fontFamily: fontSans,
    fontSize: '11px',
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.16em',
    color: colors.brass700,
    margin: '0 0 12px',
  },

  heading: {
    fontFamily: fontDisplay,
    fontWeight: 500,
    fontSize: '28px',
    lineHeight: '1.2',
    letterSpacing: '-0.015em',
    color: colors.ink900,
    margin: '0 0 24px',
  },

  paragraph: {
    fontFamily: fontSans,
    fontSize: '15px',
    lineHeight: '1.55',
    color: colors.ink700,
    margin: '0 0 16px',
  },

  sectionTitle: {
    fontFamily: fontSans,
    fontSize: '13px',
    fontWeight: 600,
    color: colors.ink900,
    margin: '0 0 12px',
  },

  buttonWrap: {
    margin: '0 0 8px',
  },

  button: {
    backgroundColor: colors.conifer700,
    borderRadius: '2px',
    color: colors.parchment50,
    fontFamily: fontSans,
    fontSize: '14px',
    fontWeight: 600,
    textDecoration: 'none',
    textAlign: 'center' as const,
    padding: '12px 28px',
  },

  link: {
    color: colors.conifer700,
    textDecoration: 'underline',
    wordBreak: 'break-all' as const,
  },

  hr: {
    border: 'none',
    borderTop: `1px solid ${colors.borderHairline}`,
    margin: '32px 0 24px',
  },

  footer: {
    fontFamily: fontSans,
    fontSize: '12px',
    lineHeight: '1.55',
    color: colors.ink500,
    margin: 0,
  },

  footerEmphasis: {
    color: colors.ink900,
  },

  dataCard: {
    backgroundColor: colors.parchment100,
    borderRadius: '0px',
    padding: '4px 20px',
    margin: '8px 0 24px',
  },
};

const fieldRow = {
  borderTop: `1px solid ${colors.borderHairline}`,
};

const fieldLabel = {
  fontFamily: fontSans,
  fontSize: '13px',
  color: colors.ink500,
  padding: '12px 0',
  textAlign: 'left' as const,
};

const fieldValue = {
  fontFamily: fontSans,
  fontSize: '13px',
  fontWeight: 600,
  color: colors.ink900,
  padding: '12px 0',
  textAlign: 'right' as const,
};

/** A label/value row with a hairline top rule. Renders nothing if `value` is falsy. */
export const Field = ({ label, value }: { label: string; value?: string }) => {
  if (!value) return null;
  return (
    <table width="100%" cellPadding="0" cellSpacing="0" role="presentation" style={fieldRow}>
      <tbody>
        <tr>
          <td style={fieldLabel}>{label}</td>
          <td style={fieldValue}>{value}</td>
        </tr>
      </tbody>
    </table>
  );
};

const FONT_LINK_HREF =
  'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500&family=Inter+Tight:wght@400;500;600&display=swap';

/**
 * Shared page chrome for NewTaven emails: font loading, parchment page
 * background, white hairline-bordered card, and the wordmark/eyebrow header.
 * Templates supply their own Heading/body content as children.
 */
export const NewTavenEmailLayout = ({
  previewText,
  eyebrowLabel,
  children,
}: {
  previewText: string;
  eyebrowLabel?: ReactNode;
  children: ReactNode;
}) => (
  <Html>
    <Head>
      <link href={FONT_LINK_HREF} rel="stylesheet" />
    </Head>
    <Preview>{previewText}</Preview>
    <Body style={styles.main}>
      <Container style={styles.container}>
        <Section style={styles.card}>
          <Text style={styles.wordmark}>NewTaven</Text>
          {eyebrowLabel ? <Text style={styles.eyebrow}>{eyebrowLabel}</Text> : null}
          {children}
        </Section>
      </Container>
    </Body>
  </Html>
);
