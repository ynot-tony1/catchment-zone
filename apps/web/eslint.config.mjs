import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [
      ".next/**",
      "playwright-report/**",
      "test-results/**",
      "next-env.d.ts",
    ],
  },
  {
    rules: {
      // Em dashes are banned from prose in this codebase (comments, UI
      // copy); this rule catches the most common accidental slip, a
      // literal em dash character inside a string or template literal.
      "no-restricted-syntax": [
        "warn",
        {
          selector: "Literal[value=/\\u2014/]",
          message: "Do not use an em dash; use a period, comma, or parentheses instead.",
        },
      ],
    },
  },
];

export default eslintConfig;
