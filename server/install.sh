#!/usr/bin/env bash
set -e

BASE_URL="http://192.168.1.116:6000"
APP_NAME="ABC管理系统"
VERSION="1.0.0"

detect_platform() {
  OS="$(uname -s)"
  ARCH="$(uname -m)"

  case "$OS" in
    Darwin)
      case "$ARCH" in
        arm64)  PLATFORM="macos_aarch64" ;;
        x86_64) PLATFORM="macos_x86_64" ;;
        *)      echo "Unsupported architecture: $ARCH"; exit 1 ;;
      esac
      ;;
    Linux)
      case "$ARCH" in
        x86_64)  PLATFORM="linux_x86_64" ;;
        aarch64) PLATFORM="linux_aarch64" ;;
        *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
      esac
      ;;
    MINGW*|MSYS*|CYGWIN*)
      PLATFORM="windows_x86_64"
      ;;
    *)
      echo "Unsupported OS: $OS"; exit 1 ;;
  esac
}

install_macos() {
  # Always download Intel version for testing
  DMG_FILE="abc-desktop-intel.dmg"

  DOWNLOAD_URL="${BASE_URL}/${DMG_FILE}?v=$(date +%s)"
  TMP_DMG="/tmp/abc-install-$(date +%s).$$.dmg"
  rm -f "$TMP_DMG"

  echo "→ Downloading Intel version..."
  curl -fsSL --progress-bar "$DOWNLOAD_URL" -o "$TMP_DMG"

  echo "→ Mounting DMG..."
  MOUNT_POINT="/tmp/abc-mount-$(date +%s).$$"
  rm -rf "$MOUNT_POINT"
  mkdir -p "$MOUNT_POINT"
  hdiutil attach "$TMP_DMG" -mountpoint "$MOUNT_POINT" -nobrowse -quiet

  echo "→ Installing to /Applications..."
  rm -rf "/Applications/${APP_NAME}.app" 2>/dev/null || true
  cp -R "${MOUNT_POINT}/${APP_NAME}.app" /Applications/

  echo "→ Cleaning up..."
  hdiutil detach "$MOUNT_POINT" -quiet
  rm -f "$TMP_DMG"
  rmdir "$MOUNT_POINT" 2>/dev/null || true
  xattr -dr com.apple.quarantine "/Applications/${APP_NAME}.app" 2>/dev/null || true

  echo ""
  echo "✅ ${APP_NAME} installed to /Applications/${APP_NAME}.app"
  echo ""
  echo "⚠️  First launch: right-click the app → Open → click 'Open' in the dialog"
  echo "   (Only required once, because the app is not notarized)"
}

install_linux() {
  echo "Linux installer coming soon."
  echo "For now, download manually from: ${BASE_URL}/"
  exit 1
}

install_windows() {
  echo "Windows installer coming soon."
  echo "For now, download manually from: ${BASE_URL}/"
  exit 1
}

echo "ABC管理系统 Installer"
echo "─────────────────────"

detect_platform

case "$PLATFORM" in
  macos_*)   install_macos ;;
  linux_*)   install_linux ;;
  windows_*) install_windows ;;
esac
