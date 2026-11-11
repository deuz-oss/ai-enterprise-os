// ESLint (audit 2026-11-11 Phase 1, C8). Sebelumnya tidak ada linter sama
// sekali -- padahal sudah ada 5 komentar `eslint-disable react-hooks/...` di
// kode. Sengaja sempit: hanya aturan hooks, karena `tsc --strict` sudah
// menangani tipe. Tambah aturan lain satu per satu, jangan preset besar.
//
// - rules-of-hooks: error (hook dipanggil kondisional = bug nyata).
// - exhaustive-deps: warn dulu; `npm run lint` hanya gagal untuk error.
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default [
  { ignores: ["dist/**", "node_modules/**"] },
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { "react-hooks": reactHooks },
    linterOptions: { reportUnusedDisableDirectives: "warn" },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
];
