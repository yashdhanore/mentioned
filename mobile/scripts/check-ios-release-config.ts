import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

type JsonObject = Record<string, unknown>;

const mobileRoot = process.cwd();
const expectedProjectId = '2ca4c235-717e-48a1-aee8-173bf247f1b0';
const expectedAppGroup = 'group.com.yashd18.mentioned';
const expectedShareExtension = {
  targetName: 'MentionedShareExtension',
  bundleIdentifier: 'com.yashd18.mentioned.ShareExtension',
};

function readJson(relativePath: string): JsonObject {
  const absolutePath = path.join(mobileRoot, relativePath);
  return JSON.parse(readFileSync(absolutePath, 'utf8')) as JsonObject;
}

function objectAt(value: unknown, label: string): JsonObject {
  assert.equal(typeof value, 'object', `${label} must be an object.`);
  assert.notEqual(value, null, `${label} must be an object.`);
  return value as JsonObject;
}

function arrayAt(value: unknown, label: string): unknown[] {
  assert.equal(Array.isArray(value), true, `${label} must be an array.`);
  return value as unknown[];
}

function assertAssetExists(relativePath: unknown, label: string): void {
  if (typeof relativePath !== 'string') {
    assert.fail(`${label} must be configured.`);
  }
  const assetPath = path.resolve(mobileRoot, relativePath);
  assert.equal(existsSync(assetPath), true, `${label} does not exist at ${relativePath}.`);
}

function readResolvedExpoConfig(): JsonObject {
  const output = execFileSync('npx', ['expo', 'config', '--json'], {
    cwd: mobileRoot,
    encoding: 'utf8',
  });
  return JSON.parse(output) as JsonObject;
}

const appConfig = readJson('app.json');
const expo = objectAt(appConfig.expo, 'app.json expo');
const ios = objectAt(expo.ios, 'app.json expo.ios');
const infoPlist = objectAt(ios.infoPlist, 'app.json expo.ios.infoPlist');
const splash = objectAt(expo.splash, 'app.json expo.splash');
const extra = objectAt(expo.extra, 'app.json expo.extra');
const easExtra = objectAt(extra.eas, 'app.json expo.extra.eas');

assert.equal(expo.name, 'Mentioned');
assert.equal(expo.slug, 'mentioned');
assert.equal(expo.scheme, 'mentioned');
assert.equal(expo.version, '1.0.0');
assert.equal(expo.owner, 'yashd18');
assert.equal(ios.bundleIdentifier, 'com.yashd18.mentioned');
assert.equal(ios.supportsTablet, false);
assert.equal(infoPlist.ITSAppUsesNonExemptEncryption, false);
assert.equal(easExtra.projectId, expectedProjectId);
assertAssetExists(expo.icon, 'app icon');
assertAssetExists(splash.image, 'splash image');

const easConfig = readJson('eas.json');
const cli = objectAt(easConfig.cli, 'eas.json cli');
const build = objectAt(easConfig.build, 'eas.json build');
const developmentBuild = objectAt(build.development, 'eas.json build.development');
const previewBuild = objectAt(build.preview, 'eas.json build.preview');
const previewEnv = objectAt(previewBuild.env, 'eas.json build.preview.env');
const productionBuild = objectAt(build.production, 'eas.json build.production');
const productionEnv = objectAt(productionBuild.env, 'eas.json build.production.env');
const productionIos = objectAt(productionBuild.ios, 'eas.json build.production.ios');

assert.equal(cli.version, '>= 16.0.1');
assert.equal(cli.appVersionSource, 'remote');
assert.equal(developmentBuild.developmentClient, true);
assert.equal(developmentBuild.distribution, 'internal');
assert.equal(previewEnv.EXPO_PUBLIC_APP_ENV, 'production');
assert.equal(productionEnv.EXPO_PUBLIC_APP_ENV, 'production');
assert.equal(productionBuild.autoIncrement, true);
assert.equal(productionIos.resourceClass, 'm-medium');

const resolvedConfig = readResolvedExpoConfig();
const resolvedExtra = objectAt(resolvedConfig.extra, 'resolved Expo extra');
const resolvedEas = objectAt(resolvedExtra.eas, 'resolved Expo extra.eas');
const resolvedBuild = objectAt(resolvedEas.build, 'resolved Expo extra.eas.build');
const experimental = objectAt(resolvedBuild.experimental, 'resolved Expo extra.eas.build.experimental');
const resolvedIos = objectAt(experimental.ios, 'resolved Expo extra.eas.build.experimental.ios');
const appExtensions = arrayAt(
  resolvedIos.appExtensions,
  'resolved Expo extra.eas.build.experimental.ios.appExtensions',
).map((extension, index) =>
  objectAt(extension, `resolved Expo extra.eas.build.experimental.ios.appExtensions[${index}]`),
);
const shareExtension = appExtensions.find(
  (extension) => extension.targetName === expectedShareExtension.targetName,
);

assert.ok(shareExtension, 'Resolved Expo config must include the iOS share extension target.');
assert.equal(shareExtension.bundleIdentifier, expectedShareExtension.bundleIdentifier);
const entitlements = objectAt(shareExtension.entitlements, 'resolved share extension entitlements');
assert.deepEqual(
  entitlements['com.apple.security.application-groups'],
  [expectedAppGroup],
);
assert.equal(resolvedExtra.appleApplicationGroup, expectedAppGroup);

console.log('iOS release config check passed');
