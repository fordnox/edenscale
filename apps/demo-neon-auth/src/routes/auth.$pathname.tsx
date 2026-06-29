import { createFileRoute } from '@tanstack/react-router';
import { AuthView } from '@neondatabase/auth-ui';

export const Route = createFileRoute('/auth/$pathname')({
  component: Auth,
});

function Auth() {
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
      <AuthView pathname={pathname} />
    </div>
  );
}