import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const eslintConfig = [
  ...nextCoreWebVitals,
  ...nextTypescript,
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
          message:
            "Do not use an em dash; use a period, comma, or parentheses instead.",
        },
      ],
    },
  },
];

export default eslintConfig;
