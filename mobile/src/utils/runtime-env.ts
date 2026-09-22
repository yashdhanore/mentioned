export function isProductionBuild(
  appEnv: string | undefined = process.env.EXPO_PUBLIC_APP_ENV,
): boolean {
  return appEnv?.trim().toLowerCase() === 'production';
}

export function isLocalHost(hostname: string): boolean {
  return ['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(hostname);
}
