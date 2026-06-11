/**
 * @file        Header 右側控制區元件
 * @description Header 右側的控制項：服務狀態列、主題切換、使用者頭像下拉
 * @lastUpdate  2026-04-14 21:39:58
 * @author      Daniel Chung
 * @version     1.2.0
 */

import { useState } from 'react';
import { Button, Avatar, Dropdown, Modal, Form, Input, Descriptions, App } from 'antd';
import type { MenuProps } from 'antd';
import {
  UserOutlined, LogoutOutlined, SunOutlined, MoonOutlined,
  KeyOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import ServiceStatusBar from './ServiceStatusBar';
import JobMonitor from './JobMonitor';
import type { LoginResponse } from '../services/api';
import { userApi } from '../services/api';
import { useAvatar } from '../services/avatarCache';

interface HeaderControlsProps {
  user: LoginResponse['user'] | null;
  isDark: boolean;
  primaryColor: string;
  textColor: string;
  onLogout: () => void;
  onToggleTheme: () => void;
}

export default function HeaderControls({
  user,
  isDark,
  primaryColor,
  textColor,
  onLogout,
  onToggleTheme,
}: HeaderControlsProps) {
  const avatarSrc = useAvatar();
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordForm] = Form.useForm();
  const { message } = App.useApp();

  const menuItems: MenuProps['items'] = [
    { key: 'account', icon: <InfoCircleOutlined />, label: '我的帳戶信息', onClick: () => setAccountModalOpen(true) },
    { key: 'password', icon: <KeyOutlined />, label: '變更密碼', onClick: () => { passwordForm.resetFields(); setPasswordModalOpen(true); } },
    { type: 'divider' as const },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登錄', onClick: onLogout },
  ];

  const handlePasswordChange = async () => {
    try {
      const values = await passwordForm.validateFields();
      setPasswordLoading(true);
      await userApi.resetPassword(user?._key || '', values.newPassword);
      message.success('密碼變更成功');
      setPasswordModalOpen(false);
      passwordForm.resetFields();
    } catch (err: any) {
      if (err?.errorFields) return; // validation error
      message.error(err?.response?.data?.message || '密碼變更失敗');
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <ServiceStatusBar />
      <JobMonitor isDark={isDark} primaryColor={primaryColor} textColor={textColor} />
      <Button
        type="text"
        icon={isDark ? <SunOutlined /> : <MoonOutlined />}
        onClick={onToggleTheme}
        style={{ color: textColor }}
      />
      <span style={{ color: textColor }}>{user?.name || user?.username}</span>
      <Dropdown menu={{ items: menuItems }} placement="bottomRight">
        <Avatar
          style={{ cursor: 'pointer', background: avatarSrc ? 'transparent' : primaryColor }}
          src={avatarSrc}
          icon={!avatarSrc ? <UserOutlined /> : undefined}
        />
      </Dropdown>

      <Modal
        title="我的帳戶信息"
        open={accountModalOpen}
        onCancel={() => setAccountModalOpen(false)}
        footer={<Button onClick={() => setAccountModalOpen(false)}>關閉</Button>}
      >
        <Descriptions column={1} size="small" style={{ marginTop: 16 }}>
          <Descriptions.Item label="用戶名">{user?.username || '-'}</Descriptions.Item>
          <Descriptions.Item label="姓名">{user?.name || '-'}</Descriptions.Item>
          <Descriptions.Item label="角色">{user?.role_name || '-'}</Descriptions.Item>
        </Descriptions>
      </Modal>

      <Modal
        title="變更密碼"
        open={passwordModalOpen}
        onCancel={() => { setPasswordModalOpen(false); passwordForm.resetFields(); }}
        onOk={handlePasswordChange}
        confirmLoading={passwordLoading}
        okText="確認變更"
        cancelText="取消"
      >
        <Form form={passwordForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="newPassword"
            label="新密碼"
            rules={[
              { required: true, message: '請輸入新密碼' },
              { min: 6, message: '密碼至少6位' },
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="confirmPassword"
            label="確認新密碼"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: '請確認新密碼' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('newPassword') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('兩次輸入的密碼不一致'));
                },
              }),
            ]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
