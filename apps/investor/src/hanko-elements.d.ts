import type * as React from "react"

declare global {
  namespace React.JSX {
    interface IntrinsicElements {
      "hanko-auth": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>
      "hanko-profile": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>
    }
  }

  namespace JSX {
    interface IntrinsicElements {
      "hanko-auth": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>
      "hanko-profile": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>
    }
  }
}

export {}
