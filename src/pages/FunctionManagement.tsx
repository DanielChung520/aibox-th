import React, { useState, useEffect } from 'react';
import { Table, Button, Space, Modal, Form, Input, Select, Popconfirm, Tag, App } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SettingOutlined, DragOutlined } from '@ant-design/icons';
import { functionApi, roleApi, Function, Role, FunctionRoleAuth } from '../services/api';
import { iconMap } from '../utils/icons';
import IconPicker from '../components/IconPicker';
import { useContentTokens } from '../contexts/AppThemeProvider';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

interface SortableRowProps {
  id: string;
  children: React.ReactNode;
  onDoubleClick?: () => void;
}

function SortableRow({ id, children, onDoubleClick }: SortableRowProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    cursor: 'grab',
  };

  return (
    <tr ref={setNodeRef} style={style} {...attributes} {...listeners} onDoubleClick={onDoubleClick}>
      {children}
    </tr>
  );
}

export default function FunctionManagement() {
  const [functions, setFunctions] = useState<Function[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [authModalVisible, setAuthModalVisible] = useState(false);
  const [editingFunction, setEditingFunction] = useState<Function | null>(null);
  const [authFunction, setAuthFunction] = useState<Function | null>(null);
  const [authData, setAuthData] = useState<FunctionRoleAuth | null>(null);
  const [iconPickerVisible, setIconPickerVisible] = useState(false);
  const { message } = App.useApp();
  const contentTokens = useContentTokens();
  const [form] = Form.useForm();
  const [authForm] = Form.useForm();
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const [flatGroups, setFlatGroups] = useState<Function[]>([]);
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'function', defaultAction: 'list' });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const functionTypeOptions = [
    { value: 'group', label: '群組' },
    { value: 'sub_function', label: '子功能' },
    { value: 'tab', label: 'Tab功能' },
  ];

  const fetchFunctions = async () => {
    setLoading(true);
    try {
      const response = await functionApi.list();
      const data = response.data.data || [];
      setFunctions(data);
      const groups = data.filter((f: Function) => f.function_type === 'group')
        .sort((a: Function, b: Function) => {
          const oa = typeof a.sort_order === 'number' ? a.sort_order : parseInt(String(a.sort_order || '0'), 10);
          const ob = typeof b.sort_order === 'number' ? b.sort_order : parseInt(String(b.sort_order || '0'), 10);
          return oa - ob;
        });
      setFlatGroups(groups);
    } catch (error) {
      console.error('Failed to fetch functions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFunctions();
    fetchRoles();
  }, []);

  useEffect(() => {
    pageContextManager.report({ component: 'FunctionManagement', entityType: 'function', action: 'list' });
    return () => {
      pageContextManager.report({ component: 'FunctionManagement', entityType: 'function', action: undefined });
    };
  }, []);

  const fetchRoles = async () => {
    try {
      const response = await roleApi.list();
      setRoles(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch roles');
    }
  };

  const handleAddGroup = () => {
    setEditingFunction(null);
    form.resetFields();
    form.setFieldsValue({ function_type: 'group', parent_key: null });
    setModalVisible(true);
  };

  const handleEdit = (record: Function) => {
    dispatchEntity(record._key, 'edit');
    setEditingFunction(record);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleDelete = async (key: string) => {
    dispatchEntity(key, 'delete');
    try {
      await functionApi.delete(key);
      fetchFunctions();
      message.success('刪除成功');
    } catch (error) {
      message.error('刪除失敗');
    }
  };

  const handleAuth = async (record: Function) => {
    dispatchEntity(record._key, 'edit');
    setAuthFunction(record);
    try {
      const response = await functionApi.getRoles(record._key);
      setAuthData(response.data.data);
      authForm.setFieldsValue({
        role_keys: response.data.data?.role_keys || [],
      });
      setAuthModalVisible(true);
    } catch (error) {
      message.error('獲取授權失敗');
    }
  };

  const handleAuthSubmit = async () => {
    if (!authFunction?._key) return;
    try {
      const values = await authForm.validateFields();
      await functionApi.setRoles(
        authFunction._key,
        values.role_keys || [],
        authData?.inherited_role_keys || []
      );
      message.success('授權更新成功');
      setAuthModalVisible(false);
    } catch (error) {
      message.error('授權更新失敗');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingFunction) {
        await functionApi.update(editingFunction._key, values);
      } else {
        await functionApi.create(values);
      }
      setModalVisible(false);
      fetchFunctions();
    } catch (error) {
      console.error('Failed to save');
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = flatGroups.findIndex(g => g._key === active.id);
    const newIndex = flatGroups.findIndex(g => g._key === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const reordered = arrayMove(flatGroups, oldIndex, newIndex);
    setFlatGroups(reordered);

    for (let i = 0; i < reordered.length; i++) {
      try {
        await functionApi.update(reordered[i]._key, { sort_order: i });
      } catch (error) {
        message.error(`更新 ${reordered[i].name} 順序失敗`);
        fetchFunctions();
        return;
      }
    }
    message.success('排序已更新');
  };

  const handleRowDoubleClick = (record: Function) => {
    if (record.function_type !== 'group') return;
    setExpandedKeys(prev => {
      const next = new Set(prev);
      if (next.has(record._key)) {
        next.delete(record._key);
      } else {
        next.add(record._key);
      }
      return next;
    });
  };

  const columns = [
    {
      title: '',
      key: 'drag',
      width: 32,
      render: (_: any) => (
        <DragOutlined style={{ color: contentTokens.textSecondary, cursor: 'grab', fontSize: 14 }} />
      ),
    },
    {
      title: '名稱',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '類型',
      dataIndex: 'function_type',
      key: 'function_type',
      render: (type: string) => {
        const map: Record<string, string> = {
          group: '群組',
          sub_function: '子功能',
          tab: 'Tab功能',
        };
        return <Tag>{map[type] || type}</Tag>;
      },
    },
    {
      title: '圖標',
      dataIndex: 'icon',
      key: 'icon',
      render: (icon: string) => {
        const IconComp = iconMap[icon];
        return IconComp ? <IconComp /> : null;
      },
    },
    {
      title: '路徑',
      dataIndex: 'path',
      key: 'path',
    },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'enabled' ? 'green' : 'red'}>
          {status === 'enabled' ? '啟用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: any, record: Function) => (
        <Space>
          <Button type="link" icon={<SettingOutlined />} onClick={() => handleAuth(record)} size="small">
            授權
          </Button>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)} size="small" />
          <Popconfirm title="確認刪除？" onConfirm={() => handleDelete(record._key)}>
            <Button type="link" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>功能維護 <small style={{ color: contentTokens.textSecondary, fontWeight: 'normal' }}>（雙擊群組展開/收攏 · 拖曳調整順序）</small></h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddGroup}>
          新增功能組
        </Button>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={flatGroups.map(g => g._key)}
          strategy={verticalListSortingStrategy}
        >
          <Table
            columns={columns}
            dataSource={flatGroups}
            loading={loading}
            rowKey="_key"
            pagination={false}
            expandable={{
              expandedRowKeys: Array.from(expandedKeys),
              onExpandedRowsChange: (keys) => setExpandedKeys(new Set(keys as string[])),
              expandedRowRender: (record: Function) => {
                const subs = functions.filter(
                  (f: Function) => f.function_type === 'sub_function' && f.parent_key === record.code
                );
                return (
                  <Table
                    columns={columns}
                    dataSource={subs}
                    rowKey="_key"
                    pagination={false}
                    size="small"
                    style={{ background: contentTokens.tableExpandedRowBg }}
                  />
                );
              },
            }}
            components={{
              body: {
                wrapper: ({ children }: { children: React.ReactNode }) => (
                  <tbody>{children}</tbody>
                ),
                row: (props: any) => {
                  const record = flatGroups.find(g => g._key === props['data-row-key']);
                  return (
                    <SortableRow
                      id={props['data-row-key'] as string}
                      onDoubleClick={() => record && handleRowDoubleClick(record)}
                    >
                      {props.children}
                    </SortableRow>
                  );
                },
              },
            }}
            onRow={(record) => ({
              onDoubleClick: () => handleRowDoubleClick(record),
            })}
          />
        </SortableContext>
      </DndContext>

      <Modal
        title={editingFunction ? '編輯功能' : '新增功能'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        width={600}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名稱" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="代碼" rules={[{ required: true }]}>
            <Input disabled={!!editingFunction} />
          </Form.Item>
          <Form.Item name="function_type" label="類型">
            <Select options={functionTypeOptions} />
          </Form.Item>
          <Form.Item name="parent_key" label="父功能">
            <Select
              options={flatGroups.map(g => ({ value: g.code, label: g.name }))}
              allowClear
            />
          </Form.Item>
          <Form.Item label="圖標">
            <Space>
              <Button onClick={() => setIconPickerVisible(true)}>
                {form.getFieldValue('icon') && iconMap[form.getFieldValue('icon')]
                  ? React.createElement(iconMap[form.getFieldValue('icon')], { style: { fontSize: 16, marginRight: 8 } })
                  : null}
                選擇圖標
              </Button>
              <span>{form.getFieldValue('icon')}</span>
            </Space>
          </Form.Item>
          <Form.Item name="path" label="路徑">
            <Input placeholder="/app/xxx" />
          </Form.Item>
          <Form.Item name="status" label="狀態" initialValue="enabled">
            <Select
              options={[
                { value: 'enabled', label: '啟用' },
                { value: 'disabled', label: '停用' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <IconPicker
        open={iconPickerVisible}
        onCancel={() => setIconPickerVisible(false)}
        onSelect={(icon) => {
          form.setFieldValue('icon', icon);
          setIconPickerVisible(false);
        }}
      />

      <Modal
        title={`授權管理 - ${authFunction?.name || ''}`}
        open={authModalVisible}
        onCancel={() => setAuthModalVisible(false)}
        onOk={handleAuthSubmit}
        width={500}
        forceRender
      >
        <Form form={authForm} layout="vertical">
          {authData?.inherited_role_keys && authData.inherited_role_keys.length > 0 && (
            <Form.Item label="繼承自父功能">
              <div>
                {authData.inherited_role_keys.map(key => {
                  const role = roles.find(r => r._key === key);
                  return <Tag key={key} color="blue">{role?.name || key}</Tag>;
                })}
              </div>
            </Form.Item>
          )}
          <Form.Item
            name="role_keys"
            label={authData?.inherited_role_keys?.length ? '額外授權角色' : '授權角色'}
          >
            <Select mode="multiple" placeholder="選擇角色" options={roles.map(role => ({ value: role._key, label: role.name }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
