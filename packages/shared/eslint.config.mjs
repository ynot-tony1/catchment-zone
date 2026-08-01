// ESLint flat config for the shared package. Kept intentionally small: this
// package has no framework-specific rules to apply, just TypeScript
// recommendations shared with the web app's stricter config.
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ignores: ["node_modules/**", "dist/**"],
  },
  {
    // scripts/ runs directly under Node (via `node scripts/sync-config.mjs`
    // in the "prepare" lifecycle script), not bundled, so it needs Node's
    // globals rather than the browser/library defaults.
    files: ["scripts/**/*.mjs"],
    languageOptions: {
      globals: globals.node,
    },
  },
);
