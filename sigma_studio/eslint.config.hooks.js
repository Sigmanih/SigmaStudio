import reactHooks from 'eslint-plugin-react-hooks';

export default [{
  files: ['src/**/*.{js,jsx}'],
  languageOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
  plugins: { 'react-hooks': reactHooks },
  rules: { 'react-hooks/rules-of-hooks': 'error' },
}];
