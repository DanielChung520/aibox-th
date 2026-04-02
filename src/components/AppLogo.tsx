/**
 * @file        應用 Logo 元件
 * @description Sider 頂部的 Logo 圖片，長條形 banner (992×227px, 4.37:1)
 * @lastUpdate  2026-04-02 13:00:00
 * @author      Daniel Chung
 * @version     1.2.0
 */

import { useNavigate } from 'react-router-dom';

interface AppLogoProps {
  logo: string;
  collapsed: boolean;
  textColor: string;
  borderColor: string;
}

// Logo 原圖尺寸: 992×227px，寬高比 ≈ 4.37:1
const LOGO_WIDTH = 992;
const LOGO_HEIGHT = 227;
const LOGO_ASPECT = LOGO_WIDTH / LOGO_HEIGHT; // ≈ 4.37

// 容器: Sider 200px 寬，Logo 區域 65px 高，圖片左右留 8px padding
// 計算: 圖片可用寬度 200-16=184px → 高 = 184/4.37 ≈ 42px
// 圖片寬度固定 180px → 高 = 180/4.37 ≈ 41px（左右各 10px padding）
const LOGO_DISPLAY_WIDTH = 180; // px
const LOGO_DISPLAY_HEIGHT = Math.round(LOGO_DISPLAY_WIDTH / LOGO_ASPECT); // ≈ 41px

export default function AppLogo({ logo }: AppLogoProps) {
  const navigate = useNavigate();
  // appLogo 為空時也顯示 EDGE-logo (不 fallback 到舊 logo.png)
  const src = (logo && logo.length > 0) ? logo : undefined;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        height: '100%',
        cursor: 'pointer',
      }}
      onClick={() => navigate('/app/home')}
    >
      <img
        src={src ?? '../assets/EDGE-logo-light.png'}
        alt="EDGE logo"
        style={{
          width: LOGO_DISPLAY_WIDTH,
          height: LOGO_DISPLAY_HEIGHT,
          objectFit: 'contain',
          display: 'block',
        }}
      />
    </div>
  );
}
