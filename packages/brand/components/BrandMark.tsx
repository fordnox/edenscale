import { MARK_PATH, MARK_TRANSFORM, MARK_VIEWBOX } from "./markPath.ts"

interface BrandMarkProps {
  className?: string
  /** Set when the mark is the only content of its link/button. */
  title?: string
}

/**
 * NewTaven raven mark, for the React apps.
 *
 * Fills with `currentColor` so it inherits whatever the slot sets — the app
 * tints (`text-conifer-700`, `text-brass-700`, `text-parchment-50` on the dark
 * login panels) all work without a per-app asset. Use this rather than the
 * standalone `assets/mark-*.svg` files anywhere the colour comes from CSS; an
 * `<img>` cannot inherit it.
 *
 * Sized by className (`size-5`, `size-6`, …), matching the lucide icons it sits
 * alongside. Geometry lives in ./markPath.ts.
 */
export function BrandMark({ className, title }: BrandMarkProps) {
  return (
    <svg
      viewBox={MARK_VIEWBOX}
      className={className}
      fill="currentColor"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {title ? <title>{title}</title> : null}
      <g transform={MARK_TRANSFORM}>
        <path fillRule="evenodd" d={MARK_PATH} />
      </g>
    </svg>
  )
}
