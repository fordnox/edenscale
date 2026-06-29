import { createFileRoute } from '@tanstack/react-router';
import { AccountView } from '@neondatabase/auth-ui';

export const Route = createFileRoute('/account/$pathname')({
  component: Account,
});

function Account() {
  const { pathname } = Route.useParams();
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
      }}
    >
      <AccountView pathname={pathname} />
    </div>
  );
}