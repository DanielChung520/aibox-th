/**
 * @file        用戶管理頁面
 * @description 用戶 CRUD 操作，包含用戶列表、新增、編輯、刪除、密碼重置
 * @lastUpdate  2026-03-17 23:27:55
 * @author      Daniel Chung
 * @version     1.0.0
 * @history
 * - 2026-03-17 23:27:55 | Daniel Chung | 1.0.0 | 初始版本
 */

import { useState, useEffect, useCallback } from 'react';
import { Table, Button, Space, Modal, Form, Input, Select, Popconfirm, Switch, App } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';
import { PlusOutlined, EditOutlined, DeleteOutlined, KeyOutlined } from '@ant-design/icons';
import { userApi, roleApi, User, Role } from '../services/api';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';
import { resolvePageContext } from '../components/FloatingAssistant/types';

function StatusSwitch({ userKey, status, onStatusChange, message }: { userKey: string; status: string; onStatusChange: (key: string, newStatus: string) => void; message: MessageInstance }) {
  const handleChange = async (checked: boolean) => {
    const newStatus = checked ? 'enabled' : 'disabled';
    try {
      await userApi.update(userKey, { status: newStatus });
      message.success(`用戶已${checked ? '啟用' : '禁用'}`);
      onStatusChange(userKey, newStatus);
    } catch (err) {
      message.error('操作失敗');
    }
  };
  return (
    <Switch
      checked={status === 'enabled'}
      checkedChildren="啟用"
      unCheckedChildren="禁用"
      onChange={handleChange}
    />
  );
}

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [passwordModalVisible, setPasswordModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form] = Form.useForm();
  const [passwordForm] = Form.useForm();
  const { message } = App.useApp();
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'user', defaultAction: 'list' });
  const pageInfo = resolvePageContext('/app/users');

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await userApi.list();
      setUsers(response.data.data || []);
    } catch (error) {
      message.error('獲取用戶列表失敗');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleStatusChange = useCallback((key: string, newStatus: string) => {
    setUsers(prevUsers => prevUsers.map(user => 
      user._key === key ? { ...user, status: newStatus } : user
    ));
  }, []);

  const fetchRoles = async () => {
    try {
      const response = await roleApi.list();
      setRoles(response.data.data || []);
    } catch (error) {
      message.error('獲取角色列表失敗');
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchRoles();
  }, []);

  useEffect(() => {
    const enabledUsers = users.filter((user) => user.status === 'enabled').length;
    const disabledUsers = users.length - enabledUsers;
    const component = modalVisible
      ? 'UserFormModal'
      : passwordModalVisible
        ? 'PasswordResetModal'
        : 'UserTable';
    const componentName = modalVisible
      ? editingUser?.username || '新增用戶'
      : passwordModalVisible
        ? editingUser?.username || '重設密碼'
        : '用戶列表';
    const action = modalVisible
      ? (editingUser ? 'edit' : 'create')
      : passwordModalVisible
        ? 'edit'
        : 'list';

    pageContextManager.report({
      page: '/app/users',
      pageName: pageInfo.name,
      component,
      componentName,
      entity: editingUser?.username,
      entityType: editingUser ? 'user' : undefined,
      action,
      data: {
        total_users: users.length,
        enabled_users: enabledUsers,
        disabled_users: disabledUsers,
        role_count: roles.length,
        loading,
        editing_user: editingUser
          ? {
              username: editingUser.username,
              name: editingUser.name,
              status: editingUser.status,
              tier: editingUser.tier || 'general',
              role_keys: editingUser.role_keys,
            }
          : undefined,
      },
    });

    return () => {
      pageContextManager.report({
        page: '/app/users',
        pageName: pageInfo.name,
        component: undefined,
        componentName: undefined,
        entity: undefined,
        entityType: undefined,
        action: undefined,
        data: undefined,
      });
    };
  }, [users, roles, loading, modalVisible, passwordModalVisible, editingUser, pageInfo.name]);

  const handleAdd = () => {
    setEditingUser(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: User) => {
    setEditingUser(record);
    form.setFieldsValue({
      username: record.username,
      name: record.name,
      role_keys: record.role_keys,
      status: record.status,
      tier: record.tier || 'general',
    });
    setModalVisible(true);
  };

  const handleDelete = async (key: string) => {
    try {
      await userApi.delete(key);
      message.success('刪除成功');
      fetchUsers();
    } catch (error) {
      message.error('刪除失敗');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingUser) {
        await userApi.update(editingUser._key, values);
        message.success('更新成功');
      } else {
        await userApi.create({
          ...values,
          password_hash: values.password,
          status: values.status || 'enabled',
        });
        message.success('創建成功');
      }
      setModalVisible(false);
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.message || '操作失敗');
    }
  };

  const handleResetPassword = (record: User) => {
    setEditingUser(record);
    passwordForm.resetFields();
    setPasswordModalVisible(true);
  };

  const handlePasswordSubmit = async () => {
    try {
      const values = await passwordForm.validateFields();
      await userApi.resetPassword(editingUser!._key, values.password);
      message.success('密碼重置成功');
      setPasswordModalVisible(false);
    } catch (error) {
      message.error('密碼重置失敗');
    }
  };

  const columns = [
    {
      title: '用戶名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '角色',
      dataIndex: 'role_keys',
      key: 'role_keys',
      render: (roleKeys: string[]) => {
        return roleKeys.map(key => {
          const role = roles.find(r => r._key === key);
          return role?.name || key;
        }).join(', ');
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string, record: User) => (
        <StatusSwitch userKey={record._key} status={status} onStatusChange={handleStatusChange} message={message} />
      ),
    },
    {
      title: '会员等级',
      dataIndex: 'tier',
      key: 'tier',
      render: (tier: string) => {
        const text = tier === 'vip' ? 'VIP' : '一般';
        return <span style={{ color: tier === 'vip' ? '#faad14' : undefined, fontWeight: 500 }}>{text}</span>;
      },
    },
    {
      title: '創建時間',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: User) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />} 
            onClick={() => handleEdit(record)}
          >
            編輯
          </Button>
          <Button 
            type="link" 
            icon={<KeyOutlined />}
            onClick={() => handleResetPassword(record)}
          >
            重置密碼
          </Button>
          {record.username !== 'admin' && (
            <Popconfirm
              title="確定刪除此用戶嗎？"
              onConfirm={() => handleDelete(record._key)}
              okText="確定"
              cancelText="取消"
            >
              <Button type="link" danger icon={<DeleteOutlined />}>
                刪除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增用戶
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={users}
        rowKey="_key"
        loading={loading}
        pagination={{ pageSize: 10 }}
        onRow={(record) => ({
          onClick: () => dispatchEntity(record._key, 'view', { username: record.username, name: record.name }),
        })}
      />

      <Modal
         title={editingUser ? '編輯用戶' : '新增用戶'}
         open={modalVisible}
         onOk={handleSubmit}
         onCancel={() => setModalVisible(false)}
         width={500}
         destroyOnHidden
         forceRender
       >
         <Form form={form} layout="vertical">
          <Form.Item
            name="username"
            label="用戶名"
            rules={[{ required: true, message: '請輸入用戶名' }]}
          >
            <Input disabled={!!editingUser} />
          </Form.Item>
          
          {!editingUser && (
            <Form.Item
              name="password"
              label="密碼"
              rules={[
                { required: true, message: '請輸入密碼' },
                { min: 6, message: '密碼至少6位' }
              ]}
            >
              <Input.Password />
            </Form.Item>
          )}
          
          <Form.Item
            name="name"
            label="姓名"
            rules={[{ required: true, message: '請輸入姓名' }]}
          >
            <Input />
          </Form.Item>
          
          <Form.Item
            name="role_keys"
            label="角色"
            rules={[{ required: true, message: '請選擇角色' }]}
          >
            <Select mode="multiple" placeholder="請選擇角色">
              {roles.map(role => (
                <Select.Option key={role._key} value={role._key}>
                  {role.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item name="status" label="狀態" initialValue="enabled">
            <Select>
              <Select.Option value="enabled">啟用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="tier" label="会员等级" initialValue="general">
            <Select>
              <Select.Option value="general">一般用戶</Select.Option>
              <Select.Option value="vip">VIP</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

       <Modal
         title="重置密碼"
         open={passwordModalVisible}
         onOk={handlePasswordSubmit}
         onCancel={() => setPasswordModalVisible(false)}
         destroyOnHidden
         forceRender
       >
         <Form form={passwordForm} layout="vertical">
          <Form.Item
            name="password"
            label="新密碼"
            rules={[
              { required: true, message: '請輸入新密碼' },
              { min: 6, message: '密碼至少6位' }
            ]}
          >
            <Input.Password />
          </Form.Item>
          
          <Form.Item
            name="confirmPassword"
            label="確認密碼"
            dependencies={['password']}
            rules={[
              { required: true, message: '請確認密碼' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('兩次輸入密碼不一致'));
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
