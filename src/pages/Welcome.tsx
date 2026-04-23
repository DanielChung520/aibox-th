/**
 * @file        歡迎頁面
 * @description 應用啟動後的歡迎頁，展示 logo、應用名稱，並自動跳轉至登錄頁
 * @lastUpdate  2026-04-23 09:13:04
 * @author      Daniel Chung
 * @version     1.0.1
 * @history
 * - 2026-03-17 23:27:55 | Daniel Chung | 1.0.0 | 初始版本，新增 logo 動畫效果
 */

import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Typography, theme } from 'antd';
import { useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';
import { authStore } from '../stores/auth';
import logoDark from '../assets/EDGE-logo-icon.png';
import logoLight from '../assets/EDGE-logo-dark.png';

const { Title, Text } = Typography;

export default function Welcome() {
  const navigate = useNavigate();
  const [countdown, setCountdown] = useState(3);
  const [appName] = useState('管理系统');
  const navigatedRef = useRef(false);
  const contentTokens = useContentTokens();
  const effectiveTheme = useEffectiveTheme();
  const { token } = theme.useToken();
  const logoSrc = effectiveTheme === 'dark' ? logoDark : logoLight;

  useEffect(() => {
    if (authStore.getState().isAuthenticated && !navigatedRef.current) {
      navigatedRef.current = true;
      navigate('/app/home', { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (countdown === 0 && !navigatedRef.current) {
      navigatedRef.current = true;
      navigate('/login', { replace: true });
    }
  }, [countdown, navigate]);

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      background: `linear-gradient(135deg, ${contentTokens.colorBgBase} 0%, ${contentTokens.colorPrimary}33 50%, ${contentTokens.colorBgBase} 100%)`,
    }}>
      <div style={{
        textAlign: 'center',
        padding: '40px',
        background: `${token.colorBgElevated}cc`,
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        borderRadius: '16px',
        border: `1px solid ${token.colorBorderSecondary}`,
        boxShadow: contentTokens.cardShadow,
        minWidth: '320px',
      }}>
        {logoSrc ? (
          <img
            src={logoSrc} 
            alt="logo" 
            style={{ 
              width: 200, 
              height: 50, 
              objectFit: 'contain',
              margin: '0 auto 24px',
              animation: 'logoScale 1.2s ease-out forwards',
            }} 
          />
        ) : (
          <div style={{
            width: 128,
            height: 128,
            background: `linear-gradient(135deg, ${contentTokens.colorPrimary} 0%, ${contentTokens.colorInfo} 100%)`,
            borderRadius: '16px',
            margin: '0 auto 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '48px',
            color: contentTokens.btnText,
            fontWeight: 'bold',
            animation: 'logoScale 3.6s ease-out forwards',
          }}>
            ABC
          </div>
        )}
        
        <Title level={2} style={{ margin: 0, color: contentTokens.colorTextBase }}>
          {appName}
        </Title>
        
        <Text type="secondary" style={{ color: contentTokens.textSecondary }}>版本 1.0.0</Text>
        
        <div style={{ marginTop: '32px' }}>
          <Button 
            type="primary" 
            size="large"
            onClick={() => {
              navigatedRef.current = true;
               navigate('/login', { replace: true });
            }}
            style={{ 
              background: `linear-gradient(135deg, ${contentTokens.colorPrimary} 0%, ${contentTokens.colorInfo} 100%)`,
              border: 'none',
            }}
          >
            进入登录
          </Button>
        </div>
        
        <div style={{ marginTop: '24px', color: contentTokens.textSecondary, fontSize: '12px' }}>
          <Text type="secondary" style={{ color: contentTokens.textSecondary }}>
            {countdown} 秒后自动跳转...
          </Text>
        </div>
        
        <div style={{ marginTop: '48px', color: contentTokens.textSecondary, fontSize: '12px' }}>
          © 2026 版权所有
        </div>
      </div>
      <style>{`
        @keyframes logoScale {
          0% { transform: scale(2.2); opacity: 0; }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
