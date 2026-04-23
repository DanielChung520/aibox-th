/**
 * @file        avatarUtils.ts
 * @description 頭像解析工具，根據名稱解析 avatar 圖片路徑
 */

const avatarModules = import.meta.glob<{ default: string }>(
  '../assets/avatar/*.png',
  { eager: true }
);

export function resolveAvatarSrc(name: string | undefined): string | undefined {
  if (!name) return undefined;
  const entry = Object.entries(avatarModules).find(([path]) => {
    const filename = path.split('/').pop() || '';
    return filename.replace(/\.png$/i, '') === name;
  });
  return entry ? (entry[1] as { default: string }).default : undefined;
}

export function isAvatarName(name: string | undefined): boolean {
  if (!name) return false;
  return resolveAvatarSrc(name) !== undefined;
}

export function resolveChannelIconSrc(icon: string | undefined): string | undefined {
  if (!icon) return undefined;
  const avatarSrc = resolveAvatarSrc(icon);
  if (avatarSrc) return avatarSrc;
  if (icon.startsWith('http') || icon.startsWith('/') || icon.startsWith('data:')) {
    return icon;
  }
  return undefined;
}
