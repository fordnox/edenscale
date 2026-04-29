import { useEffect } from "react"
import { useNavigate, Link } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import { register } from "@teamhanko/hanko-elements"
import { ArrowLeft, Sparkles, Zap, Shield, Code } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/useAuth"
import { config } from "@/lib/config"
import { hanko } from "@/lib/hanko"

export default function LoginPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    register(config.VITE_HANKO_API_URL).catch(console.error)
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/")
    }
  }, [isAuthenticated, navigate])

  useEffect(() => {
    const unsub = hanko.onSessionCreated(() => {
      navigate("/")
    })
    return () => {
      unsub()
    }
  }, [navigate])

  return (
    <>
      <Helmet>
        <title>{`Login | ${config.VITE_APP_TITLE}`}</title>
        <meta name="description" content="Sign in to your account." />
        <link rel="canonical" href={`${config.VITE_APP_URL}/login`} />
        <meta property="og:title" content={`Login | ${config.VITE_APP_TITLE}`} />
        <meta property="og:description" content="Sign in to your account." />
        <meta property="og:url" content={`${config.VITE_APP_URL}/login`} />
        <meta property="og:type" content="website" />
        <meta name="twitter:title" content={`Login | ${config.VITE_APP_TITLE}`} />
        <meta name="twitter:description" content="Sign in to your account." />
      </Helmet>

      <div className="min-h-screen grid lg:grid-cols-2">
        {/* Left panel — branding */}
        <div className="hidden lg:flex relative flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground">
          {/* Background decoration */}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_var(--tw-gradient-stops))] from-primary-foreground/10 via-transparent to-transparent" />
          <div className="absolute top-1/3 -right-24 w-96 h-96 rounded-full bg-primary-foreground/5 blur-3xl" />
          <div className="absolute -bottom-12 -left-12 w-72 h-72 rounded-full bg-primary-foreground/5 blur-3xl" />

          {/* Grid pattern */}
          <div
            className="absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage: `linear-gradient(hsl(var(--primary-foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--primary-foreground)) 1px, transparent 1px)`,
              backgroundSize: "48px 48px",
            }}
          />

          {/* Top — logo */}
          <div className="relative z-10">
            <Link to="/" className="flex items-center gap-2 group">
              <ArrowLeft className="size-4 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
              <span className="text-lg font-bold">{config.VITE_APP_TITLE}</span>
            </Link>
          </div>

          {/* Center — value props */}
          <div className="relative z-10 space-y-8">
            <div className="space-y-2">
              <h2 className="text-3xl font-bold tracking-tight">Start building today</h2>
              <p className="text-primary-foreground/70 text-lg max-w-sm">
                Sign in to access your dashboard and start shipping faster.
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center size-10 rounded-lg bg-primary-foreground/10 backdrop-blur-sm">
                  <Zap className="size-5" />
                </div>
                <div>
                  <p className="font-medium">Lightning Fast</p>
                  <p className="text-sm text-primary-foreground/60">Optimized for performance</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center size-10 rounded-lg bg-primary-foreground/10 backdrop-blur-sm">
                  <Shield className="size-5" />
                </div>
                <div>
                  <p className="font-medium">Secure by Default</p>
                  <p className="text-sm text-primary-foreground/60">Built-in auth and safety</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center size-10 rounded-lg bg-primary-foreground/10 backdrop-blur-sm">
                  <Code className="size-5" />
                </div>
                <div>
                  <p className="font-medium">Developer First</p>
                  <p className="text-sm text-primary-foreground/60">Clean, typed codebase</p>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom — quote */}
          <div className="relative z-10">
            <blockquote className="border-l-2 border-primary-foreground/20 pl-4">
              <p className="text-sm text-primary-foreground/70 italic">
                "The best developer experience I've encountered. Everything just works."
              </p>
              <footer className="mt-2 text-sm text-primary-foreground/50">
                — Happy Developer
              </footer>
            </blockquote>
          </div>
        </div>

        {/* Right panel — login form */}
        <div className="flex flex-col relative overflow-hidden">
          {/* Background */}
          <div className="absolute inset-0 bg-gradient-to-b from-muted/30 via-background to-background" />
          <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />

          {/* Mobile back link */}
          <div className="relative z-10 p-6 lg:hidden">
            <Button variant="ghost" size="sm" asChild>
              <Link to="/">
                <ArrowLeft className="size-4 mr-2" />
                Back
              </Link>
            </Button>
          </div>

          {/* Form centered */}
          <div className="flex-1 flex items-center justify-center p-6 relative z-10">
            <div className="w-full max-w-sm space-y-8">
              {/* Mobile branding */}
              <div className="text-center lg:hidden space-y-2">
                <div className="inline-flex items-center gap-2 text-primary mb-2">
                  <Sparkles className="size-5" />
                </div>
                <h1 className="text-2xl font-bold">{config.VITE_APP_TITLE}</h1>
                <p className="text-sm text-muted-foreground">{config.VITE_APP_SLOGAN}</p>
              </div>

              {/* Desktop heading */}
              <div className="hidden lg:block space-y-2 text-center">
                <h1 className="text-2xl font-bold tracking-tight">Welcome back</h1>
                <p className="text-muted-foreground">Sign in to your account to continue</p>
              </div>

              {/* Login card */}
              <Card className="border-border/50 shadow-lg">
                <CardContent className="pt-6">
                  <hanko-auth />
                </CardContent>
              </Card>

              {/* Footer */}
              <p className="text-center text-xs text-muted-foreground">
                By continuing, you agree to our terms of service and privacy policy.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
