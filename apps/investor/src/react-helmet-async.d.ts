declare module "react-helmet-async" {
  import type { ComponentType, ReactNode } from "react"

  export const HelmetProvider: ComponentType<{ children?: ReactNode }>
  export const Helmet: ComponentType<{ children?: ReactNode }>
}
