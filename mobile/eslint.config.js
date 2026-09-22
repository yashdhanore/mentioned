const expoConfig = require('eslint-config-expo/flat');
const { defineConfig, globalIgnores } = require('eslint/config');

module.exports = defineConfig([
  globalIgnores(['ios', 'android', '.expo', 'dist', 'web-build', 'node_modules']),
  expoConfig,
]);
