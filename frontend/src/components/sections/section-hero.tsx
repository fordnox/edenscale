import { ArrowRight, Sparkles, Zap, Shield, Code } from "lucide-react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button.tsx"
import { Badge } from "@/components/ui/badge.tsx"
import { config } from "@/lib/config.ts"

export function SectionHero() {
  return (
    <section className="relative min-h-[calc(100vh-3.5rem)] flex items-center justify-center overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-background to-background" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-transparent to-transparent" />

      {/* Grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(var(--foreground) 1px, transparent 1px), linear-gradient(90deg, var(--foreground) 1px, transparent 1px)`,
          backgroundSize: "64px 64px",
        }}
      />

      {/* Floating accent dots */}
      <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-primary/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl animate-pulse delay-1000" />

      <div className="container relative z-10 mx-auto px-4 md:px-6 py-24 md:py-32">
        <div className="flex flex-col items-center text-center max-w-4xl mx-auto space-y-8">
          {/* Badge */}
          <Badge variant="outline" className="px-4 py-1.5 text-sm font-medium gap-2 border-primary/20 bg-primary/5">
            <Sparkles className="size-3.5 text-primary" />
            {config.VITE_APP_SLOGAN}
          </Badge>

          {/* Heading */}
          <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.1]">
            Build smarter with{" "}
            <span className="bg-gradient-to-r from-primary via-primary/80 to-primary/60 bg-clip-text text-transparent">
              {config.VITE_APP_TITLE}
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl leading-relaxed">
            The modern full-stack template that helps you ship faster.
            Built with best practices, so you can focus on what matters.
          </p>

          {/* CTA buttons */}
          <div className="flex flex-col sm:flex-row gap-4 pt-4">
            <Button size="lg" className="text-base px-8 h-12 gap-2" asChild>
              <Link to="/login">
                Get Started
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" className="text-base px-8 h-12" asChild>
              <a href={config.VITE_GITHUB_URL} target="_blank" rel="noopener noreferrer">
                View on GitHub
              </a>
            </Button>
          </div>

          {/* Feature pills */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-12 w-full max-w-2xl">
            <div className="flex items-center gap-3 rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm px-4 py-3">
              <div className="flex items-center justify-center size-9 rounded-lg bg-primary/10">
                <Zap className="size-4 text-primary" />
              </div>
              <div className="text-left">
                <p className="text-sm font-medium">Lightning Fast</p>
                <p className="text-xs text-muted-foreground">Optimized performance</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm px-4 py-3">
              <div className="flex items-center justify-center size-9 rounded-lg bg-primary/10">
                <Shield className="size-4 text-primary" />
              </div>
              <div className="text-left">
                <p className="text-sm font-medium">Secure by Default</p>
                <p className="text-xs text-muted-foreground">Built-in auth & safety</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm px-4 py-3">
              <div className="flex items-center justify-center size-9 rounded-lg bg-primary/10">
                <Code className="size-4 text-primary" />
              </div>
              <div className="text-left">
                <p className="text-sm font-medium">Developer First</p>
                <p className="text-xs text-muted-foreground">Clean, typed codebase</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default SectionHero
