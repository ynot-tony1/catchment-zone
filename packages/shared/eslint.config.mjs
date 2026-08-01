// ESLint flat config for the shared package. Kept intentionally small: this
// package has no framework-specific rules to apply, just TypeScript
// recommendations shared with the web app's stricter config.
import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ignores: ["node_modules/**", "dist/**"],
  },
);
