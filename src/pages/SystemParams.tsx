/**
 * @file        系統參數頁面
 * @description 系統參數配置，包含基本資訊、主題、窗口、備份等參數管理
 * @lastUpdate  2026-04-24 12:40:27
 * @author      Daniel Chung
 * @version     1.2.0
 */

import { useState, useEffect, useMemo } from 'react';
import { App, Card, Form, Input, Button, Switch, InputNumber, Tabs, Space, Upload, Image, theme, type TabsProps, Select, Avatar, Row, Col, Typography } from 'antd';
import { SaveOutlined, ReloadOutlined, UploadOutlined, CheckCircleFilled } from '@ant-design/icons';
import { paramsApi, SystemParam } from '../services/api';
import SystemParamsModels from './SystemParamsModels';
import ThemeTemplateManagement from './ThemeTemplateManagement';
import SystemParamsBasicTools from './SystemParamsBasicTools';
import SystemParamsIntent from './SystemParamsIntent';
import DatabaseBackupPanel from './backup/DatabaseBackupPanel';
import FloatingAssistantSettings from './FloatingAssistantSettings';
import SystemParamsDataAgent from './SystemParamsDataAgent';
import { MODULE_OPTIONS, normalizeGraphModuleSelection } from './data-agent/schemaGraphUtils';

const avatarModules = import.meta.glob<{ default: string }>(
  '../assets/avatar/*.png',
  { eager: true }
);

interface AvatarEntry {
  name: string;
  src: string;
}

const avatarList: AvatarEntry[] = Object.entries(avatarModules)
  .map(([path, mod]) => {
    const filename = path.split('/').pop() || '';
    const name = filename.replace(/\.png$/i, '');
    return { name, src: mod.default };
  })
  .sort((a, b) => a.name.localeCompare(b.name, 'zh-Hant'));

interface ParamFormValues {
  [key: string]: any;
}

export default function SystemParams() {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const [params, setParams] = useState<SystemParam[]>([]);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [logoBase64, setLogoBase64] = useState<string>('');
  const [form] = Form.useForm();

  const [selectedAvatar, setSelectedAvatar] = useState<string>('');

  const fetchParams = async () => {
    try {
      const response = await paramsApi.list();
      setParams(response.data.data || []);

      const values: ParamFormValues = {};
      response.data.data?.forEach((param: SystemParam) => {
        let value: any = param.param_value;
        if (param.param_type === 'number') {
          value = parseInt(param.param_value, 10);
        } else if (param.param_type === 'boolean') {
          value = param.param_value === 'true';
        } else if (param.param_key === 'ragic.default_graph_modules') {
          value = normalizeGraphModuleSelection(param.param_value.split(','));
        }
        values[param.param_key] = value;
      });
      form.setFieldsValue(values);

      const logoParam = response.data.data?.find((p: SystemParam) => p.param_key === 'app.logo');
      if (logoParam?.param_value) {
        setLogoBase64(logoParam.param_value);
      }

      const avatarParam = response.data.data?.find((p: SystemParam) => p.param_key === 'basic.avatar');
      if (avatarParam?.param_value) {
        setSelectedAvatar(avatarParam.param_value);
      }

      const systemTypeParam = response.data.data?.find((p: SystemParam) => p.param_key === 'basic.system_type');
      if (systemTypeParam?.param_value) {
        localStorage.setItem('app.system_type', systemTypeParam.param_value);
      }
    } catch {
      message.error('获取参数失败');
    }
  };

  useEffect(() => {
    fetchParams();
  }, []);

  const handleSave = async (category?: string) => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const paramsToSave = category
        ? params.filter(p => p.category === category)
        : params;

      for (const param of paramsToSave) {
        let paramValue = values[param.param_key];

        if (param.param_type === 'boolean') {
          paramValue = paramValue ? 'true' : 'false';
        } else if (param.param_type === 'number') {
          paramValue = String(paramValue);
        } else if (param.param_key === 'ragic.default_graph_modules') {
          paramValue = normalizeGraphModuleSelection(Array.isArray(paramValue) ? paramValue : []).join(',');
        }

        await paramsApi.update(param.param_key, paramValue);

        if (param.param_key === 'basic.system_type') {
          localStorage.setItem('app.system_type', paramValue);
        }
      }

      message.success('保存成功');
      fetchParams();
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (file: File) => {
    try {
      setUploading(true);

      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      await paramsApi.update('app.logo', base64);
      setLogoBase64(base64);
      message.success('Logo 上传成功');
      fetchParams();
    } catch {
      message.error('Logo 上传失败');
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleAvatarSelect = async (avatarName: string) => {
    try {
      setSelectedAvatar(avatarName);
      await paramsApi.update('basic.avatar', avatarName);
      message.success('頭像已更新');
      window.dispatchEvent(new CustomEvent('avatar-changed', { detail: { name: avatarName } }));
    } catch {
      message.error('頭像更新失敗');
    }
  };

  const groupedParams = params.reduce((acc, param) => {
    if (param.category === 'web_search' || param.category === 'intent' || param.category === 'floating_assistant' || param.category === 'data_agent' || param.category === 'aiq') return acc;
    if (!acc[param.category]) {
      acc[param.category] = [];
    }
    acc[param.category].push(param);
    return acc;
  }, {} as Record<string, SystemParam[]>);

  const categoryLabels: Record<string, string> = {
    basic: '基本信息',
    theme: '主题设置',
    window: '窗口设置',
    behavior: '行为设置',
    update: '更新设置',
    backup: '备份设置',
    knowledge: '知識庫參數',
    task_chat: '任務聊天參數',
    ragic: 'Ragic 連線設定',
  };

  const ragicParamLabels: Record<string, string> = {
    'ragic.server_prefix': '伺服器前綴 (如 ap15)',
    'ragic.database': '資料庫名稱 (如 2025shianyong)',
    'ragic.service_account': '服務帳號',
    'ragic.api_key': 'API Key',
    'ragic.default_graph_modules': '圖譜預設模組',
  };

  const renderParamInput = (param: SystemParam) => {
    const commonProps = {
      disabled: param.param_key === 'app.version',
    };

    if (param.param_key === 'basic.system_type') {
      return (
        <Select {...commonProps} style={{ width: '100%' }}>
          <Select.Option value="sap">SAP</Select.Option>
          <Select.Option value="ragic">Ragic</Select.Option>
        </Select>
      );
    }

    if (param.param_key === 'ragic.api_key') {
      return <Input.Password {...commonProps} style={{ width: '100%' }} />;
    }

    if (param.param_key === 'ragic.default_graph_modules') {
      return (
        <Select
          {...commonProps}
          mode="multiple"
          style={{ width: '100%' }}
          options={MODULE_OPTIONS}
          placeholder="選擇圖譜預設模組"
          maxTagCount={3}
        />
      );
    }

    switch (param.param_type) {
      case 'boolean':
        return <Switch {...commonProps} />;
      case 'number':
        return <InputNumber {...commonProps} style={{ width: '100%' }} />;
      default:
        return <Input {...commonProps} />;
    }
  };

  const currentAvatarEntry = useMemo(
    () => avatarList.find(a => a.name === selectedAvatar),
    [selectedAvatar]
  );

  const buildCategoryTab = (category: string, categoryParams: SystemParam[]) => {
    if (category === 'basic') {
      return {
        key: category,
        label: categoryLabels[category] || category,
        children: (
          <Row gutter={24}>
            <Col xs={24} lg={14}>
              <Card>
                <div style={{ marginBottom: 24 }}>
                  <div style={{ fontWeight: 'bold', marginBottom: 12 }}>应用 Logo</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    {logoBase64 ? (
                      <Image
                        src={logoBase64}
                        alt="Logo"
                        width={80}
                        height={80}
                        style={{ objectFit: 'contain', border: `1px solid ${token.colorBorder}`, borderRadius: 8 }}
                        fallback="/vite.svg"
                      />
                    ) : (
                      <div style={{ width: 80, height: 80, border: `1px dashed ${token.colorBorder}`, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <UploadOutlined style={{ fontSize: 24, color: token.colorTextQuaternary }} />
                      </div>
                    )}
                    <div>
                      <Upload
                        accept="image/*"
                        showUploadList={false}
                        beforeUpload={handleLogoUpload}
                        disabled={uploading}
                      >
                        <Button loading={uploading} icon={<UploadOutlined />}>
                          上传 Logo
                        </Button>
                      </Upload>
                      <div style={{ fontSize: 12, color: token.colorTextQuaternary, marginTop: 4 }}>
                        推荐尺寸: 128x128，支持 PNG/JPG/SVG
                      </div>
                    </div>
                  </div>
                </div>
                <Form form={form} layout="vertical" style={{ maxWidth: 600 }}>
                  {categoryParams.map(param => (
                    <Form.Item
                      key={param.param_key}
                      name={param.param_key}
                      label={param.param_key.split('.')[1] || param.param_key}
                      tooltip={param.require_restart ? '需要重启生效' : undefined}
                    >
                      {renderParamInput(param)}
                    </Form.Item>
                  ))}
                  <Form.Item>
                    <Space>
                      <Button
                        type="primary"
                        icon={<SaveOutlined />}
                        onClick={() => handleSave(category)}
                        loading={saving}
                      >
                        保存
                      </Button>
                      <Button
                        icon={<ReloadOutlined />}
                        onClick={() => form.resetFields()}
                      >
                        重置
                      </Button>
                    </Space>
                  </Form.Item>
                </Form>
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card>
                <Typography.Title level={5} style={{ marginTop: 0, marginBottom: 16 }}>頭像設置</Typography.Title>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 24 }}>
                  <Avatar
                    size={96}
                    src={currentAvatarEntry?.src}
                    style={{
                      border: `3px solid ${token.colorPrimary}`,
                      boxShadow: `0 4px 12px ${token.colorPrimary}33`,
                    }}
                  />
                  <Typography.Text style={{ marginTop: 8, fontSize: 14 }}>
                    {selectedAvatar || '尚未選擇'}
                  </Typography.Text>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: 12,
                    maxHeight: 360,
                    overflowY: 'auto',
                    padding: 4,
                  }}
                >
                  {avatarList.map(avatar => (
                    <div
                      key={avatar.name}
                      onClick={() => handleAvatarSelect(avatar.name)}
                      style={{
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 4,
                        padding: 8,
                        borderRadius: 8,
                        border: `2px solid ${selectedAvatar === avatar.name ? token.colorPrimary : 'transparent'}`,
                        background: selectedAvatar === avatar.name ? `${token.colorPrimary}10` : 'transparent',
                        transition: 'all 0.2s',
                        position: 'relative',
                      }}
                    >
                      <Avatar size={56} src={avatar.src} />
                      <Typography.Text
                        style={{ fontSize: 11, textAlign: 'center' }}
                        ellipsis
                      >
                        {avatar.name}
                      </Typography.Text>
                      {selectedAvatar === avatar.name && (
                        <CheckCircleFilled
                          style={{
                            position: 'absolute',
                            top: 4,
                            right: 4,
                            fontSize: 16,
                            color: token.colorPrimary,
                          }}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            </Col>
          </Row>
        ),
      };
    }

    return {
      key: category,
      label: categoryLabels[category] || category,
      children: (
        <Card>
          <Form form={form} layout="vertical" style={{ maxWidth: 600 }}>
            {categoryParams.map(param => (
              <Form.Item
                key={param.param_key}
                name={param.param_key}
                label={ragicParamLabels[param.param_key] || param.param_key.split('.')[1] || param.param_key}
                tooltip={param.require_restart ? '需要重启生效' : undefined}
              >
                {renderParamInput(param)}
              </Form.Item>
            ))}
            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={() => handleSave(category)}
                  loading={saving}
                >
                  保存
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => form.resetFields()}
                >
                  重置
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      ),
    };
  };

  const tabItems: TabsProps['items'] = [
    {
      key: 'models',
      label: '模型',
      children: <SystemParamsModels />,
    },
    {
      key: 'theme-templates',
      label: '樣板維護',
      children: <ThemeTemplateManagement />,
    },
    {
      key: 'basic-tools',
      label: '基礎工具',
      children: <SystemParamsBasicTools />,
    },
    {
      key: 'floating-assistant',
      label: '艾企助手',
      children: <FloatingAssistantSettings />,
    },
    {
      key: 'data-agent',
      label: '資料代理',
      children: <SystemParamsDataAgent />,
    },
    {
      key: 'intent',
      label: '意圖分析',
      children: <SystemParamsIntent />,
    },
    {
      key: 'backup',
      label: '備份管理',
      children: <DatabaseBackupPanel />,
    },
    ...Object.entries(groupedParams).map(([category, categoryParams]) =>
      buildCategoryTab(category, categoryParams)
    ),
  ];

  return (
    <div>
      <Tabs items={tabItems} />
    </div>
  );
}
