import { useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import { register } from "@teamhanko/hanko-elements"
import { config } from "@/lib/config.ts"
import { useAuth } from "@/hooks/useAuth"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { User, LogOut, Loader2 } from "lucide-react"

export default function UserProfilePage() {
  const { user, isLoading, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    register(config.VITE_HANKO_API_URL).catch(console.error)
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate("/")
  }

  if (isLoading) {
    return (
      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </main>
    )
  }

  if (!isAuthenticated || !user) {
    return (
      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="max-w-md mx-auto text-center py-16">
          <User className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
          <h1 className="text-2xl font-bold text-foreground mb-2">Not Logged In</h1>
          <p className="text-muted-foreground mb-6">
            Please log in to view your profile.
          </p>
          <Button onClick={() => navigate("/login")}>
            Go to Login
          </Button>
        </div>
      </main>
    )
  }

  return (
    <>
      <Helmet>
        <title>{`Profile | ${config.VITE_APP_TITLE}`}</title>
        <meta name="description" content="View and manage your profile settings." />
        <link rel="canonical" href={`${config.VITE_APP_URL}/profile`} />
        <meta property="og:title" content={`Profile | ${config.VITE_APP_TITLE}`} />
        <meta property="og:description" content="View and manage your profile settings." />
        <meta property="og:url" content={`${config.VITE_APP_URL}/profile`} />
        <meta property="og:type" content="website" />
        <meta name="twitter:title" content={`Profile | ${config.VITE_APP_TITLE}`} />
        <meta name="twitter:description" content="View and manage your profile settings." />
      </Helmet>
      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-3xl font-bold text-foreground mb-8">Profile</h1>

          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Account</CardTitle>
            </CardHeader>
            <CardContent>
              <hanko-profile />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <Button
                variant="outline"
                className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
                onClick={handleLogout}
              >
                <LogOut className="w-4 h-4 mr-2" />
                Log Out
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    </>
  )
}
