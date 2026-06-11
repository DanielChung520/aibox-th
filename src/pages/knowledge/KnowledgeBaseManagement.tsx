/**
 * @file        知識庫管理頁面
 * @description 知識管理 - 知識庫的建立、設定與管理
 * @lastUpdate  2026-03-25 12:56:08
 * @author      Daniel Chung
 * @version     3.0.0
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Typography, Button, Input, Radio, Space, App, Modal, Form, Select, Switch, Tag } from 'antd';
import {
  AppstoreOutlined,
  BarsOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import {
  KnowledgeRoot, KnowledgeRoleAuth,
  knowledgeApi, ontologyApi, roleApi, Ontology, Role,
} from '../../services/api';
import { useEntityPerception } from '../../hooks/useEntityPerception';
import KBCardGrid from './components/KBCardGrid';
import KBTableList from './components/KBTableList';
import KBCreateModal from './components/KBCreateModal';

const { TextArea } = Input;
const { Title } = Typography;

const TAG_SEPARATORS = [' ', '，', ',', '/', '；', ';'];

export default function KnowledgeBaseManagement() {
  const contentTokens = useContentTokens();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'knowledge_base', defaultAction: 'list' });

  const [data, setData] = useState<KnowledgeRoot[]>([]);
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');
  const [searchText, setSearchText] = useState('');
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingKb, setEditingKb] = useState<KnowledgeRoot | null>(null);
  const [editForm] = Form.useForm();

  const [domainOptions, setDomainOptions] = useState<{ label: string; value: string }[]>([]);
  const [majorOptions, setMajorOptions] = useState<{ label: string; value: string }[]>([]);

  const [authModalVisible, setAuthModalVisible] = useState(false);
  const [authKb, setAuthKb] = useState<KnowledgeRoot | null>(null);
  const [authData, setAuthData] = useState<KnowledgeRoleAuth | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [authForm] = Form.useForm();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await knowledgeApi.listRoots();
      setData(res.data.data || []);
    } catch {
      message.error('載入知識庫列表失敗');
    } finally {
      setLoading(false);
    }
  }, [message]);

  const loadOntologyOptions = useCallback(async () => {
    try {
      const res = await ontologyApi.list();
      const all: Ontology[] = res.data.data || [];
      setDomainOptions(
        all.filter(o => o.type === 'domain').map(o => ({ label: o.name, value: o.name }))
      );
      setMajorOptions(
        all.filter(o => o.type === 'major').map(o => ({ label: o.name, value: o.name }))
      );
    } catch {
      // noop
    }
  }, []);

  const loadRoles = useCallback(async () => {
    try {
      const res = await roleApi.list();
      setRoles(res.data.data || []);
    } catch {
      // noop
    }
  }, []);

  useEffect(() => {
    loadData();
    loadOntologyOptions();
    loadRoles();
  }, [loadData, loadOntologyOptions, loadRoles]);

  const filteredData = useMemo(() => {
    let result = data;
    if (favoriteOnly) {
      result = result.filter((item) => item.is_favorite);
    }
    if (searchText) {
      const lowerSearch = searchText.toLowerCase();
      result = result.filter(
        (item) =>
          item.name.toLowerCase().includes(lowerSearch) ||
          (item.description && item.description.toLowerCase().includes(lowerSearch))
      );
    }
    return result;
  }, [data, searchText, favoriteOnly]);

  const handleCreate = () => {
    setCreateModalVisible(true);
  };

  const handleCreateSuccess = async (_id: string, values: Partial<KnowledgeRoot>) => {
    try {
      await knowledgeApi.createRoot(values);
      message.success('知識庫建立成功');
      setCreateModalVisible(false);
      loadData();
    } catch (error: any) {
      message.error(error.response?.data?.message || '建立失敗');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await knowledgeApi.deleteRoot(id);
      message.success('知識庫已刪除');
      dispatchEntity(id, 'delete');
      loadData();
    } catch (error: any) {
      message.error(error.response?.data?.message || '刪除失敗');
    }
  };

  const handleFavoriteToggle = async (id: string) => {
    try {
      const res = await knowledgeApi.toggleFavorite(id);
      setData((prev) =>
        prev.map((item) =>
          item._key === id ? { ...item, is_favorite: res.data.data.is_favorite } : item
        )
      );
    } catch {
      message.error('收藏切換失敗');
    }
  };

  const handleCopy = async (id: string) => {
    try {
      await knowledgeApi.copyRoot(id);
      message.success('知識庫複製成功');
      loadData();
    } catch (error: any) {
      message.error(error.response?.data?.message || '複製失敗');
    }
  };

  const handleEdit = (id: string) => {
    const kb = data.find((item) => item._key === id);
    dispatchEntity(id, 'view', { kb_name: kb?.name });
    navigate(`/app/knowledge/management/${id}`);
  };

  const handleEditMeta = useCallback((id: string) => {
    const kb = data.find((item) => item._key === id);
    if (!kb) return;
    setEditingKb(kb);
    editForm.setFieldsValue({
      name: kb.name,
      description: kb.description,
      tags: kb.tags || [],
      ontology_domain: kb.ontology_domain,
      ontology_majors: kb.ontology_majors,
    });
    setEditModalVisible(true);
    dispatchEntity(id, 'edit', { kb_name: kb.name });
  }, [data, editForm, dispatchEntity]);

  const handleEditMetaOk = useCallback(async () => {
    try {
      const values = await editForm.validateFields();
      if (!editingKb) return;
      await knowledgeApi.updateRoot(editingKb._key, values);
      message.success('知識庫資訊已更新');
      setEditModalVisible(false);
      setEditingKb(null);
      editForm.resetFields();
      loadData();
    } catch (error: any) {
      if (error.response?.data?.message) {
        message.error(error.response.data.message);
      }
    }
  }, [editingKb, editForm, message, loadData]);

  const handleEditMetaCancel = useCallback(() => {
    setEditModalVisible(false);
    setEditingKb(null);
    editForm.resetFields();
  }, [editForm]);

  const handleAuthorize = useCallback(async (id: string) => {
    const kb = data.find((item) => item._key === id);
    if (!kb) return;
    setAuthKb(kb);
    try {
      const res = await knowledgeApi.getRoles(id);
      setAuthData(res.data.data);
      authForm.setFieldsValue({
        role_keys: res.data.data?.role_keys || [],
      });
      setAuthModalVisible(true);
      dispatchEntity(id, 'edit', { kb_name: kb.name, action_type: 'authorize' });
    } catch {
      message.error('獲取授權資料失敗');
    }
  }, [data, authForm, message, dispatchEntity]);

  const handleAuthSubmit = useCallback(async () => {
    if (!authKb?._key) return;
    try {
      const values = await authForm.validateFields();
      await knowledgeApi.setRoles(
        authKb._key,
        values.role_keys || [],
        authData?.inherited_role_keys || []
      );
      message.success('授權更新成功');
      setAuthModalVisible(false);
    } catch {
      message.error('授權更新失敗');
    }
  }, [authKb, authForm, authData, message]);

  return (
    <div style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, color: contentTokens.colorPrimary }}>
          🗄️ 知識庫管理
        </Title>
        <Space size="middle">
          <Input
            placeholder="搜尋知識庫..."
            prefix={<SearchOutlined style={{ color: contentTokens.textSecondary }} />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Space size="small">
            <Switch
              checked={favoriteOnly}
              onChange={setFavoriteOnly}
              size="small"
            />
            <span style={{ color: contentTokens.textSecondary, fontSize: 13, whiteSpace: 'nowrap' }}>
              我的收藏
            </span>
          </Space>
          <Radio.Group
            value={viewMode}
            onChange={(e) => setViewMode(e.target.value)}
            optionType="button"
            buttonStyle="solid"
          >
            <Radio.Button value="grid">
              <AppstoreOutlined />
            </Radio.Button>
            <Radio.Button value="table">
              <BarsOutlined />
            </Radio.Button>
          </Radio.Group>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            建立知識庫
          </Button>
        </Space>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {viewMode === 'grid' ? (
          <KBCardGrid
            data={filteredData}
            loading={loading}
            onEdit={handleEdit}
            onEditMeta={handleEditMeta}
            onCopy={handleCopy}
            onDelete={handleDelete}
            onFavoriteToggle={handleFavoriteToggle}
            onAuthorize={handleAuthorize}
          />
        ) : (
          <KBTableList
            data={filteredData}
            loading={loading}
            onEdit={handleEdit}
            onEditMeta={handleEditMeta}
            onCopy={handleCopy}
            onDelete={handleDelete}
            onFavoriteToggle={handleFavoriteToggle}
            onAuthorize={handleAuthorize}
          />
        )}
      </div>

      <KBCreateModal
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        onSuccess={handleCreateSuccess}
        domains={domainOptions}
        majors={majorOptions}
      />

      <Modal
        title="編輯知識庫資訊"
        open={editModalVisible}
        onOk={handleEditMetaOk}
        onCancel={handleEditMetaCancel}
        okText="儲存"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical" name="kb_edit_form">
          <Form.Item
            name="name"
            label="知識庫名稱"
            rules={[{ required: true, message: '請輸入知識庫名稱!' }]}
          >
            <Input placeholder="例如: 產品文件庫" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} placeholder="簡單描述此知識庫的用途..." />
          </Form.Item>
          <Form.Item
            name="tags"
            label="標籤"
            tooltip="輸入標籤後按 Enter 確認，支援空格、逗號、斜線、分號作為分隔符號"
          >
            <Select
              mode="tags"
              tokenSeparators={TAG_SEPARATORS}
              placeholder="輸入標籤，例如: 財務 預算 庫存"
            />
          </Form.Item>
          <Form.Item
            name="ontology_domain"
            label="知識領域 (Domain)"
            rules={[{ required: true, message: '請選擇一個知識領域!' }]}
          >
            <Select placeholder="選擇領域" options={domainOptions} />
          </Form.Item>
          <Form.Item name="ontology_majors" label="專業主題 (Majors)">
            <Select
              mode="multiple"
              allowClear
              placeholder="選擇相關專業主題"
              options={majorOptions}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`授權管理 - ${authKb?.name || ''}`}
        open={authModalVisible}
        onCancel={() => setAuthModalVisible(false)}
        onOk={handleAuthSubmit}
        okText="儲存"
        cancelText="取消"
        width={500}
        destroyOnHidden
      >
        <Form form={authForm} layout="vertical">
          {authData?.inherited_role_keys && authData.inherited_role_keys.length > 0 && (
            <Form.Item label="繼承的角色">
              <div>
                {authData.inherited_role_keys.map((key) => {
                  const role = roles.find((r) => r._key === key);
                  return <Tag key={key} color="blue">{role?.name || key}</Tag>;
                })}
              </div>
            </Form.Item>
          )}
          <Form.Item
            name="role_keys"
            label={authData?.inherited_role_keys?.length ? '額外授權角色' : '授權角色'}
          >
            <Select
              mode="multiple"
              placeholder="選擇角色"
              options={roles.map((r) => ({ value: r._key, label: r.name }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
