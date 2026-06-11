/**
 * @file        首頁 / Home 畫面
 * @description 全幅 Hero Banner，包含底圖動畫、品牌展示與「開始使用」CTA
 * @lastUpdate  2026-05-10 12:29:41
 * @author      Daniel Chung
 * @version     2.0.1
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Typography } from 'antd';
import { useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';
import logoDark from '../assets/EDGE-logo-dark.png';
import logoLight from '../assets/EDGE-logo-light.png';
import heroBg from '../assets/hero-bg.jpg';

const { Title, Text } = Typography;

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function Home() {
  const navigate = useNavigate();
  const contentTokens = useContentTokens();
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'dashboard', defaultAction: 'list' });
  void dispatchEntity; // Reserved for future event handler use

  useEffect(() => {
    pageContextManager.report({ component: 'Home', entityType: 'dashboard', action: 'list' });
    return () => { pageContextManager.report({ component: undefined, entityType: undefined, action: undefined }); };
  }, []);
  const effectiveTheme = useEffectiveTheme();
  const isDark = effectiveTheme === 'dark';
  const logoSrc = isDark ? logoDark : logoLight;
  const primaryColor = contentTokens.colorPrimary;
  const infoColor = contentTokens.colorInfo;
  const textBaseColor = contentTokens.colorTextBase;
  const textSecondaryColor = contentTokens.textSecondary;

  return (
    <div style={{
      position: 'relative',
      height: '100%',
      width: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      background: `linear-gradient(135deg, ${isDark ? 'rgba(15,23,42,0.93)' : 'rgba(248,250,252,0.92)'} 0%, ${isDark ? 'rgba(30,58,95,0.88)' : 'rgba(59,130,246,0.10)'} 100%), url(${heroBg}) center center / cover no-repeat`,
    }}>
      <div style={{
        position: 'absolute',
        inset: 0,
        zIndex: 0,
        backgroundImage: `radial-gradient(circle, ${hexToRgba(primaryColor, 0.08)} 1.5px, transparent 1.5px)`,
        backgroundSize: '36px 36px',
        maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 70%)',
        WebkitMaskImage: 'radial-gradient(ellipse at center, black 30%, transparent 70%)',
        animation: 'homeGridPulse 4s ease-in-out infinite',
      }} />

      <div style={{
        position: 'absolute',
        borderRadius: '50%',
        zIndex: 0,
        pointerEvents: 'none',
        width: 640,
        height: 640,
        background: `radial-gradient(circle at 40% 50%, ${hexToRgba(primaryColor, 0.25)} 0%, ${hexToRgba(primaryColor, 0.08)} 35%, transparent 70%)`,
        top: '-25%',
        right: '-10%',
        animation: 'homeOrbFloat1 12s ease-in-out infinite',
      }} />

      <div style={{
        position: 'absolute',
        borderRadius: '50%',
        zIndex: 0,
        pointerEvents: 'none',
        width: 560,
        height: 560,
        background: `radial-gradient(circle at 60% 50%, ${hexToRgba(infoColor, 0.2)} 0%, ${hexToRgba(infoColor, 0.06)} 35%, transparent 70%)`,
        bottom: '-20%',
        left: '-8%',
        animation: 'homeOrbFloat2 14s ease-in-out infinite',
      }} />

      <div style={{
        position: 'absolute',
        zIndex: 0,
        pointerEvents: 'none',
        width: '60%',
        height: 1,
        background: `linear-gradient(90deg, transparent 0%, ${hexToRgba(primaryColor, 0.15)} 50%, transparent 100%)`,
        top: '50%',
        left: '20%',
        transform: 'translateY(-50%)',
        animation: 'homeBeamPulse 6s ease-in-out infinite',
      }} />

      <div style={{
        position: 'relative',
        zIndex: 2,
        textAlign: 'center',
        padding: '40px',
        maxWidth: 700,
      }}>
        {logoSrc && (
          <img
            src={logoSrc}
            alt="EDGE"
            style={{
              height: 48,
              width: 'auto',
              objectFit: 'contain',
              marginBottom: 32,
              opacity: 0,
              animation: 'homeFadeSlideUp 0.8s ease-out 0.2s forwards',
            }}
          />
        )}

        <Title
          level={1}
          style={{
            color: textBaseColor,
            fontSize: 48,
            fontWeight: 700,
            margin: 0,
            marginBottom: 16,
            opacity: 0,
            animation: 'homeFadeSlideUp 0.8s ease-out 0.4s forwards',
          }}
        >
          AI 智能平台
        </Title>

        <Text
          style={{
            color: textSecondaryColor,
            fontSize: 18,
            display: 'block',
            marginBottom: 40,
            opacity: 0,
            animation: 'homeFadeSlideUp 0.8s ease-out 0.6s forwards',
          }}
        >
          探索智能體與工具，打造您的 AI 工作流程
        </Text>

        <div style={{
          opacity: 0,
          animation: 'homeFadeSlideUp 0.8s ease-out 0.8s forwards',
        }}>
          <Button
            type="primary"
            size="large"
            onClick={() => navigate('/app/browse-agent')}
            style={{
              height: 52,
              padding: '0 40px',
              fontSize: 18,
              borderRadius: 26,
              background: `linear-gradient(135deg, ${primaryColor} 0%, ${infoColor} 100%)`,
              border: 'none',
              boxShadow: `0 8px 32px ${hexToRgba(primaryColor, 0.35)}`,
              cursor: 'pointer',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)';
              (e.currentTarget as HTMLElement).style.boxShadow = `0 12px 40px ${hexToRgba(primaryColor, 0.5)}`;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
              (e.currentTarget as HTMLElement).style.boxShadow = `0 8px 32px ${hexToRgba(primaryColor, 0.35)}`;
            }}
          >
            開始使用
          </Button>
        </div>
      </div>

      <style>{`
        @keyframes homeFadeSlideUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        @keyframes homeGridPulse {
          0%, 100% { opacity: 0.5; }
          50%       { opacity: 1; }
        }

        @keyframes homeOrbFloat1 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%      { transform: translate(40px, -40px) scale(1.08); }
          66%      { transform: translate(-20px, 30px) scale(0.95); }
        }

        @keyframes homeOrbFloat2 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%      { transform: translate(-40px, -30px) scale(1.1); }
          66%      { transform: translate(30px, 40px) scale(0.9); }
        }

        @keyframes homeBeamPulse {
          0%, 100% { opacity: 0.3; }
          50%       { opacity: 0.8; }
        }
      `}</style>
    </div>
  );
}
