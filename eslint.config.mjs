// Root flat ESLint config for the frontend workspace (apps/manager, apps/investor,
// apps/superadmin, packages/ui, packages/shared).
//
// Deliberately minimal: this is not a full "recommended" ruleset. Per plan 019, the
// two rules worth having here are the ones that catch real bugs in this codebase —
// `react-hooks/exhaustive-deps` (stale closures) and
// `@typescript-eslint/no-floating-promises` (unawaited mutations). Both are landed
// as warnings, not errors, so the gate is installable without a mass fix-up pass.
//
// `no-floating-promises` requires type-aware linting (a real TS program via
// `parserOptions.projectService`), which is why every matched file goes through
// the TypeScript parser with type information attached.
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default tseslint.config(
  {
    ignores: [
      "**/dist/**",
      "**/node_modules/**",
      "**/.astro/**",
      "**/build/**",
      "**/.turbo/**",
    ],
  },
  {
    files: [
      "apps/manager/src/**/*.{ts,tsx}",
      "apps/investor/src/**/*.{ts,tsx}",
      "apps/superadmin/src/**/*.{ts,tsx}",
      "packages/ui/src/**/*.{ts,tsx}",
      "packages/shared/src/**/*.{ts,tsx}",
    ],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "@typescript-eslint": tseslint.plugin,
      "react-hooks": reactHooks,
    },
    rules: {
      "@typescript-eslint/no-floating-promises": "warn",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
);
