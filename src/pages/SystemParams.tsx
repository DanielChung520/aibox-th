/**
 * @file        系統參數頁面
 * @description 系統參數配置，包含基本資訊、主題、窗口、備份等參數管理
 * @lastUpdate  2026-03-27 11:55:55
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { App, Card, Form, Input, Button, Switch, InputNumber, Tabs, Space, Upload, Image, theme, type TabsProps, Select } from 'antd';
import { SaveOutlined, ReloadOutlined, UploadOutlined } from '@ant-design/icons';
import { paramsApi, SystemParam } from '../services/api';
import SystemParamsModels from './SystemParamsModels';
import ThemeTemplateManagement from './ThemeTemplateManagement';
import SystemParamsBasicTools from './SystemParamsBasicTools';
import DatabaseBackupPanel from './backup/DatabaseBackupPanel';

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
        }
        values[param.param_key] = value;
      });
      form.setFieldsValue(values);

      const logoParam = response.data.data?.find((p: SystemParam) => p.param_key === 'app.logo');
      if (logoParam?.param_value) {
        setLogoBase64(logoParam.param_value);
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

  const groupedParams = params.reduce((acc, param) => {
    if (param.category === 'web_search') return acc;
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

    switch (param.param_type) {
      case 'boolean':
        return <Switch {...commonProps} />;
      case 'number':
        return <InputNumber {...commonProps} style={{ width: '100%' }} />;
      default:
        return <Input {...commonProps} />;
    }
  };

  const buildCategoryTab = (category: string, categoryParams: SystemParam[]) => {
    if (category === 'basic') {
      return {
        key: category,
        label: categoryLabels[category] || category,
        children: (
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
