/**
 * @file        登錄頁面
 * @description 用戶登錄頁面
 * @lastUpdate  2026-03-22 19:56:42
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Checkbox, Typography, App } from 'antd';
import type { InputRef } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { authApi } from '../services/api';
import { authStore } from '../stores/auth';
import { useEffectiveTheme, useContentTokens } from '../contexts/AppThemeProvider';
import logoDark from '../assets/EDGE-logo-icon.png';
import logoLight from '../assets/EDGE-logo-dark.png';

const { Title, Text } = Typography;

export default function Login() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();

  const effectiveTheme = useEffectiveTheme();
  const isDark = effectiveTheme === 'dark';
  const logoSrc = isDark ? logoDark : logoLight;
  const contentTokens = useContentTokens();
  const pageBg = contentTokens.contentBg || contentTokens.colorBgBase;
  const cardBg = isDark ? contentTokens.chatInputBg : contentTokens.colorBgBase;
  const textColor = contentTokens.colorTextBase;
  const secondaryColor = contentTokens.textSecondary;

  const passwordRef = useRef<InputRef>(null);

  const savedUsername = localStorage.getItem('remembered_username') || '';
  const [initialUsername] = useState(savedUsername);

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
        message.success('登录成功');
        navigate('/app');
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '用户名或密码错误');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      background: pageBg,
      transition: 'background 0.3s',
    }}>
      <div style={{
        width: 360,
        padding: '40px',
        background: cardBg,
        borderRadius: '10px',
        boxShadow: isDark ? contentTokens.cardShadow : contentTokens.boxShadowSecondary,
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
          <Title level={3} style={{ margin: 0, color: textColor }}>登录</Title>
          <Text type="secondary" style={{ color: secondaryColor }}>ABC 管理系统</Text>
        </div>

        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
            initialValue={initialUsername}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
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
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6位' }
            ]}
          >
            <Input.Password
              ref={passwordRef}
              prefix={<LockOutlined />}
              placeholder="密码"
            />
          </Form.Item>

          <Form.Item name="remember" valuePropName="checked" initialValue={!!savedUsername}>
            <Checkbox>记住账户</Checkbox>
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
              登录
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center', color: secondaryColor, fontSize: '12px' }}>
          默认账号: admin / admin123
        </div>
      </div>
    </div>
  );
}
