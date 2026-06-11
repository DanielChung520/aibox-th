/**
 * @file        登錄頁面
 * @description 用戶登錄頁面
 * @lastUpdate  2026-03-22 19:56:42
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Checkbox, Typography, App } from 'antd';
import type { InputRef } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { authApi } from '../services/api';
import { authStore } from '../stores/auth';
import { useEffectiveTheme, useContentTokens } from '../contexts/AppThemeProvider';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';
import logoDark from '../assets/EDGE-logo-icon.png';
import logoLight from '../assets/EDGE-logo-dark.png';
import heroBg from '../assets/hero-bg.jpg';

const { Title, Text } = Typography;

export default function Login() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();

  const effectiveTheme = useEffectiveTheme();
  const isDark = effectiveTheme === 'dark';
  const logoSrc = isDark ? logoDark : logoLight;
  const contentTokens = useContentTokens();
  const cardBg = isDark ? contentTokens.chatInputBg : contentTokens.colorBgBase;
  const textColor = contentTokens.colorTextBase;
  const secondaryColor = contentTokens.textSecondary;

  const passwordRef = useRef<InputRef>(null);

  const savedUsername = localStorage.getItem('remembered_username') || '';
  const [initialUsername] = useState(savedUsername);

  useEntityPerception({ defaultEntityType: 'login', defaultAction: 'view' });

  useEffect(() => {
    pageContextManager.report({ component: 'Login', entityType: 'login', action: 'view' });
  }, []);

  const onFinish = async (values: { username: string; password: string; remember: boolean }) => {
    setLoading(true);
    try {
      if (values.remember) {
        localStorage.setItem('remembered_username', values.username);
      } else {
        localStorage.removeItem('remembered_username');
      }
      const response = await authApi.login(values);
      if (response.data.code === 200) {
        const { user, token } = response.data.data;
        authStore.login(user, token);
        message.success('登錄成功');
        try {
          const win = getCurrentWindow();
          await win.maximize();
        } catch (_) {
          // non-Tauri environment - ignore
        }
        navigate('/app');
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '用戶名或密碼錯誤');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'relative',
      height: '100vh',
      width: '100%',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      overflow: 'hidden',
      background: `linear-gradient(135deg, ${isDark ? 'rgba(15,23,42,0.92)' : 'rgba(248,250,252,0.90)'} 0%, ${isDark ? 'rgba(30,58,95,0.85)' : 'rgba(59,130,246,0.08)'} 100%), url(${heroBg}) center center / cover no-repeat`,
      transition: 'background 0.3s',
    }}>
      <div style={{
        position: 'absolute',
        inset: 0,
        zIndex: 0,
        backgroundImage: `radial-gradient(circle, ${contentTokens.colorPrimary}18 1px, transparent 1px)`,
        backgroundSize: '36px 36px',
        maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 70%)',
        WebkitMaskImage: 'radial-gradient(ellipse at center, black 30%, transparent 70%)',
        animation: 'loginGridPulse 4s ease-in-out infinite',
      }} />

      <div style={{
        position: 'absolute',
        borderRadius: '50%',
        zIndex: 0,
        pointerEvents: 'none',
        width: 500,
        height: 500,
        background: `radial-gradient(circle at 40% 50%, ${contentTokens.colorPrimary}20 0%, transparent 60%)`,
        top: '-15%',
        right: '-8%',
        animation: 'loginOrbFloat 10s ease-in-out infinite',
      }} />

      <div style={{
        position: 'relative',
        zIndex: 2,
        width: 360,
        padding: '40px',
        background: cardBg,
        borderRadius: '10px',
        boxShadow: isDark ? contentTokens.cardShadow : contentTokens.boxShadowSecondary,
        backdropFilter: isDark ? 'blur(4px)' : 'none',
        transition: 'all 0.3s',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          {logoSrc && (
            <img
              src={logoSrc}
              alt="logo"
              style={{
                width: 200,
                height: 50,
                objectFit: 'contain',
                marginBottom: 16,
                borderRadius: 8,
              }}
            />
          )}
          <Title level={3} style={{ margin: 0, color: textColor }}>登錄</Title>
          <Text type="secondary" style={{ color: secondaryColor }}>ABC 管理系統</Text>
        </div>

        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '請輸入用戶名' }]}
            initialValue={initialUsername}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用戶名"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  passwordRef.current?.input?.focus();
                }
              }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '請輸入密碼' },
              { min: 6, message: '密碼至少6位' }
            ]}
          >
            <Input.Password
              ref={passwordRef}
              prefix={<LockOutlined />}
              placeholder="密碼"
            />
          </Form.Item>

          <Form.Item name="remember" valuePropName="checked" initialValue={!!savedUsername}>
            <Checkbox>記住帳戶</Checkbox>
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{
                background: `linear-gradient(135deg, ${contentTokens.colorPrimary} 0%, ${contentTokens.colorInfo} 100%)`,
                border: 'none',
              }}
            >
              登錄
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center', color: secondaryColor, fontSize: '12px' }}>
          默認帳號: admin / admin123
        </div>
      </div>

      <style>{`
        @keyframes loginGridPulse {
          0%, 100% { opacity: 0.5; }
          50%       { opacity: 1; }
        }

        @keyframes loginOrbFloat {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%      { transform: translate(30px, -30px) scale(1.1); }
          66%      { transform: translate(-20px, 20px) scale(0.9); }
        }
      `}</style>
    </div>
  );
}
