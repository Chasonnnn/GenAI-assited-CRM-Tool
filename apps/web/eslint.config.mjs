import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';
import unusedImports from 'eslint-plugin-unused-imports';
import reactHooks from 'eslint-plugin-react-hooks';

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  // Registers the react-hooks plugin + its recommended rules, including the React Compiler
  // diagnostics (purity, immutability, set-state-in-render, preserve-manual-memoization, ...).
  // We override the compiler rules to 'warn' below so they surface bailouts without failing CI
  // during the React Compiler rollout.
  reactHooks.configs.flat.recommended,
  {
    ignores: ['.next/**', 'node_modules/**', 'dist/**'],
  },
  {
    plugins: {
      'unused-imports': unusedImports,
    },
    rules: {
      // Correctness rule stays hard — the compiler relies on it.
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // React Compiler diagnostics: warn-only first pass (surface bailouts, then tighten later).
      'react-hooks/static-components': 'warn',
      'react-hooks/use-memo': 'warn',
      'react-hooks/component-hook-factories': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/incompatible-library': 'warn',
      'react-hooks/immutability': 'warn',
      'react-hooks/globals': 'warn',
      'react-hooks/refs': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/error-boundaries': 'warn',
      'react-hooks/purity': 'warn',
      'react-hooks/set-state-in-render': 'warn',
      'react-hooks/unsupported-syntax': 'warn',
      'react-hooks/config': 'warn',
      'react-hooks/gating': 'warn',
      '@typescript-eslint/no-unused-vars': 'off',
      'unused-imports/no-unused-imports': 'error',
      'unused-imports/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'error',
    },
  }
);
