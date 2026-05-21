/**
 * @file        技能管理頁面
 * @description 知識管理 - 技能上傳、編輯與授權管理
 * @lastUpdate  2026-05-09 04:30:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import { Typography, Button, Input, Space, App, Modal, Form, Select, Tag, Table, Tabs, Upload, Slider, InputNumber, Switch, Spin, Tooltip } from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  ReloadOutlined,
  InboxOutlined,
  EditOutlined,
  DeleteOutlined,
  UpOutlined,
  DownOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  ApartmentOutlined,
  CopyOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  WarningOutlined,
  HolderOutlined,
} from '@ant-design/icons';
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import mermaid from 'mermaid';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { ActionScript, actionApi, skillsRagApi, paramsApi, modelProviderApi, agentApi } from '../../services/api';
import api from '../../services/api';
import type { UploadFile } from 'antd/es/upload';
import type { RcFile } from 'antd/es/upload';
import { useEntityPerception } from '../../hooks/useEntityPerception';
import { pageContextManager } from '../../services/PageContextManager';

const { TextArea } = Input;
const { Title } = Typography;
const { Dragger } = Upload;

const TAG_SEPARATORS = [' ', '，', ',', '/', '；', ';'];

const BUSINESS_DOMAINS: { label: string; value: string }[] = [
  { label: '全部', value: '' },
  { label: '研發', value: 'rd' },
  { label: '行銷', value: 'market' },
  { label: '銷售', value: 'sales' },
  { label: '訂單', value: 'order' },
  { label: '庫存', value: 'inventory' },
  { label: '採購', value: 'purchase' },
  { label: '排程', value: 'planning' },
  { label: '人資', value: 'hr' },
  { label: '製造', value: 'mes' },
  { label: '財務', value: 'finance' },
  { label: '應收/應付', value: 'ap_ar' },
  { label: '會計', value: 'accounting' },
];

const STATUS_OPTIONS = [
  { label: '啟用', value: 'enabled' },
  { label: '停用', value: 'disabled' },
];

interface StepItem {
  title: string;
  description?: string;
  type: 'llm_prompt' | 'script' | 'manual' | 'agent' | 'tool';
  model?: string;
  temperature?: number;
  max_tokens?: number;
  prompt?: string;
  script_id?: string;
  parameters?: string;
  note?: string;
  require_human?: boolean;
  agent_name?: string;
  tool_name?: string;
  tool_params?: string;
}

export default function SkillsManagement() {
  const contentTokens = useContentTokens();
  const { message } = App.useApp();
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'skill', defaultAction: 'list' });
  void dispatchEntity; // Reserved for future event handler use

  useEffect(() => {
    pageContextManager.report({ component: 'SkillsManagement', entityType: 'skill', action: 'list' });
    return () => { pageContextManager.report({ component: undefined, entityType: undefined, action: undefined }); };
  }, []);

  const [data, setData] = useState<ActionScript[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [activeTab, setActiveTab] = useState('');

  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);

  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingSkill, setEditingSkill] = useState<ActionScript | null>(null);
  const [editForm] = Form.useForm();
  const [localSteps, setLocalSteps] = useState<StepItem[]>([]);
  const [stepModalVisible, setStepModalVisible] = useState(false);
  const [editingStepIndex, setEditingStepIndex] = useState<number | null>(null);
  const [stepType, setStepType] = useState<'llm_prompt' | 'script' | 'manual' | 'agent' | 'tool'>('llm_prompt');
  const [stepForm] = Form.useForm();

  const [syncing, setSyncing] = useState(false);
  const [checking, setChecking] = useState(false);
  const [settingsModalVisible, setSettingsModalVisible] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsForm] = Form.useForm();
  const [generatingSteps, setGeneratingSteps] = useState(false);
  const [clarifyModalVisible, setClarifyModalVisible] = useState(false);
  const [clarifyText, setClarifyText] = useState('');
  const [clarifyPendingValues, setClarifyPendingValues] = useState<Record<string, any> | null>(null);
  const [modelOptions, setModelOptions] = useState<{ label: string; value: string }[]>([]);
  const [agentOptions, setAgentOptions] = useState<{ label: string; value: string }[]>([]);
  const [warningData, setWarningData] = useState<any>(null);
  const [warningModalVisible, setWarningModalVisible] = useState(false);
  const [checkResultVisible, setCheckResultVisible] = useState(false);
  const [checkResultData, setCheckResultData] = useState<any>(null);
  const [mermaidModalVisible, setMermaidModalVisible] = useState(false);
  const [mermaidCode, setMermaidCode] = useState('');
  const [mermaidSvg, setMermaidSvg] = useState('');

  const formatRelativeTime = useCallback((isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return '剛剛';
    if (diffMin < 60) return `${diffMin} 分鐘前`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour} 小時前`;
    const diffDay = Math.floor(diffHour / 24);
    if (diffDay < 7) return `${diffDay} 天前`;
    return isoString.substring(0, 16).replace('T', ' ');
  }, []);

  const latestSyncTime = useMemo(() => {
    const times = data
      .map((s) => s.last_sync_at)
      .filter((t): t is string => !!t)
      .sort()
      .reverse();
    return times.length > 0 ? times[0] : null;
  }, [data]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await actionApi.list();
      setData(res.data.data || []);
    } catch {
      message.error('載入技能列表失敗');
    } finally {
      setLoading(false);
    }
  }, [message]);

  const loadModelOptions = useCallback(async () => {
    try {
      const res = await modelProviderApi.list();
      const providers = res.data?.data || [];
      const options: { label: string; value: string }[] = [];
      for (const p of providers) {
        if (p.status !== 'enabled') continue;
        const models = p.models || [];
        for (const m of models) {
          if (m.status === 'disabled') continue;
          options.push({
            label: `${p.name} / ${m.display_name || m.name || m.model_id}`,
            value: m.model_id,
          });
        }
      }
      if (options.length === 0) {
        options.push({ label: 'llama3.2:latest (本地)', value: 'llama3.2:latest' });
      }
      setModelOptions(options);
    } catch {
      setModelOptions([{ label: 'llama3.2:latest (本地)', value: 'llama3.2:latest' }]);
    }
  }, []);

  const loadAgentOptions = useCallback(async () => {
    try {
      const res = await agentApi.list();
      const agents: any[] = res.data?.data || [];
      setAgentOptions(agents.map((a) => ({ label: a.name, value: a.name })));
    } catch {
      setAgentOptions([]);
    }
  }, []);

  useEffect(() => {
    loadData();
    loadModelOptions();
    loadAgentOptions();
  }, [loadData, loadModelOptions, loadAgentOptions]);

  useEffect(() => {
    mermaid.initialize({ startOnLoad: false });
  }, []);

  useEffect(() => {
    if (mermaidModalVisible && mermaidCode) {
      mermaid.render('mermaid-flowchart', mermaidCode).then(({ svg }) => {
        setMermaidSvg(svg);
      }).catch(() => {
        message.error('流程圖渲染失敗');
      });
    }
  }, [mermaidModalVisible, mermaidCode, message]);

  const filteredData = useMemo(() => {
    let result = data;
    if (activeTab) {
      result = result.filter((item) => item.tags && item.tags.some((t) => t === activeTab));
    }
    if (searchText) {
      const lowerSearch = searchText.toLowerCase();
      result = result.filter(
        (item) =>
          item.name.toLowerCase().includes(lowerSearch) ||
          (item.description && item.description.toLowerCase().includes(lowerSearch)) ||
          (item.tags && item.tags.some((t) => t.toLowerCase().includes(lowerSearch)))
      );
    }
    return result;
  }, [data, searchText, activeTab]);

  const handleSync = useCallback(async () => {
    if (!editingSkill) return;
    setSyncing(true);
    try {
      await skillsRagApi.sync(editingSkill.skill_no);
      message.success('同步完成');
      const res = await actionApi.getByNo(editingSkill.skill_no);
      if (res.data.data) {
        setEditingSkill((prev) => prev ? { ...prev, last_sync_at: res.data.data.last_sync_at } : prev);
      }
      loadData();
    } catch (error: any) {
      message.error(error.response?.data?.message || '同步失敗');
    } finally {
      setSyncing(false);
    }
  }, [editingSkill, message, loadData]);

  const handleCheck = useCallback(async () => {
    if (!editingSkill) return;
    setChecking(true);
    try {
      await skillsRagApi.check(editingSkill.skill_no);
      message.success('檢查請求已送出');

      const skillNo = editingSkill.skill_no;
      let attempts = 0;
      const maxAttempts = 10;

      const poll = async (): Promise<void> => {
        const res = await actionApi.getByNo(skillNo);
        const data = res.data?.data;
        if (!data) return;

        const status = (data as any).check_status;
        const result = (data as any).check_result;

        if (status === 'checking' && attempts < maxAttempts) {
          attempts++;
          await new Promise((r) => setTimeout(r, 3000));
          return poll();
        }

        setEditingSkill((prev) => prev ? { ...prev, ...data } : prev);
        setCheckResultData(result || null);
        loadData();

        if (result) {
          setCheckResultVisible(true);
        }
      };

      await poll();
    } catch (error: any) {
      message.error(error.response?.data?.message || '檢查失敗');
    } finally {
      setChecking(false);
    }
  }, [editingSkill, message, loadData]);

  function generateMermaidCode(steps: StepItem[]): string {
    const typeColors: Record<string, { fill: string; stroke: string; color: string }> = {
      llm_prompt: { fill: '#e6f4ff', stroke: '#1677ff', color: '#135200' },
      script: { fill: '#fff7e6', stroke: '#fa8c16', color: '#873800' },
      manual: { fill: '#f6ffed', stroke: '#52c41a', color: '#135200' },
      agent: { fill: '#f9f0ff', stroke: '#722ed1', color: '#391063' },
      tool: { fill: '#fff0f6', stroke: '#eb2f96', color: '#9c0e5c' },
    };

    let code = 'flowchart TD\n';

    steps.forEach((step, i) => {
      const id = `step${i}`;
      const typeLabel = step.type === 'llm_prompt' ? 'LLM' : step.type === 'script' ? 'Script' : step.type === 'manual' ? 'Manual' : step.type === 'agent' ? 'Agent' : 'Tool';
      const label = `${i + 1}. ${step.title} (${typeLabel})`.replace(/"/g, '#quot;');
      code += `    ${id}["${label}"]\n`;
    });

    if (steps.length > 0) {
      for (let i = 0; i < steps.length - 1; i++) {
        code += `    step${i} --> step${i + 1}\n`;
      }
      code += `    step${steps.length - 1} --> done["✅ 完成"]\n`;
    }

    code += `    style done fill:#f6ffed,stroke:#52c41a,color:#135200\n`;

    steps.forEach((step, i) => {
      const colors = typeColors[step.type];
      if (colors) {
        code += `    style step${i} fill:${colors.fill},stroke:${colors.stroke},color:${colors.color}\n`;
      }
    });

    return code;
  }

  const handleGenerateMermaid = useCallback(() => {
    if (localSteps.length === 0) {
      message.warning('請先新增步驟');
      return;
    }
    const code = generateMermaidCode(localSteps);
    setMermaidCode(code);
    setMermaidSvg('');
    setMermaidModalVisible(true);
  }, [localSteps, message]);

  const handleCopyMermaid = useCallback(() => {
    navigator.clipboard.writeText(mermaidCode).then(() => {
      message.success('已複製 Mermaid 程式碼');
    }).catch(() => {
      message.error('複製失敗');
    });
  }, [mermaidCode, message]);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    try {
      const res = await paramsApi.list();
      const params = res.data.data || [];
      const getVal = (key: string) => {
        const p = params.find((p) => p.param_key === key);
        return p ? p.param_value : undefined;
      };
      settingsForm.setFieldsValue({
        llm_model: getVal('skills.llm_model') || undefined,
        temperature: getVal('skills.temperature') !== undefined ? Number(getVal('skills.temperature')) : 0.7,
        max_tokens: getVal('skills.max_tokens') !== undefined ? Number(getVal('skills.max_tokens')) : 4096,
      });
    } catch {
      message.error('載入設定失敗');
    } finally {
      setSettingsLoading(false);
    }
  }, [settingsForm, message]);

  const handleSaveSettings = async () => {
    try {
      const values = await settingsForm.validateFields();
      setSavingSettings(true);
      await Promise.all([
        paramsApi.update('skills.llm_model', values.llm_model),
        paramsApi.update('skills.temperature', String(values.temperature)),
        paramsApi.update('skills.max_tokens', String(values.max_tokens)),
      ]);
      message.success('設定已儲存');
      setSettingsModalVisible(false);
    } catch (error: any) {
      if (error.response?.data?.message) {
        message.error(error.response.data.message);
      }
    } finally {
      setSavingSettings(false);
    }
  };

  const hasEnoughContext = useCallback((values: Record<string, any>): boolean => {
    const desc = (values.description || '').trim();
    const goal = (values.goal || '').trim();
    const domain = (values.domain || '').trim();
    const tags = values.tags || [];
    const name = (values.name || '').trim();
    // Must have at least name + one of: description, goal, or domain
    if (!name) return false;
    const contextParts = [desc, goal, domain, ...tags].filter(Boolean);
    return contextParts.length >= 2;
  }, []);

  const doGenerateSteps = useCallback(async (supplement?: string, force?: boolean) => {
    try {
      const values = editForm.getFieldsValue(['name', 'description', 'goal', 'domain', 'tags']);
      setGeneratingSteps(true);
      const payload: Record<string, any> = {
        name: values.name || '',
        description: values.description || '',
        goal: values.goal || '',
        domain: values.domain || '',
        tags: values.tags || [],
      };
      if (force) payload.force = true;
      if (supplement) {
        payload.description = (payload.description || '') + '\n[補充說明] ' + supplement;
      }
      const res = await api.post('/api/v1/action-scripts/generate-steps', payload, { timeout: 120000 });
      const data = res.data?.data;

      if (data && typeof data === 'object' && !Array.isArray(data) && data._warning === true) {
        setWarningData(data);
        setWarningModalVisible(true);
        return;
      }

      const steps = Array.isArray(data) ? data : [];
      if (steps.length === 0) {
        message.warning('AI 無法產生步驟。請檢查技能名稱與完成目標是否一致，或按「忽略警告」強制生成');
        return;
      }
      const parsedSteps: StepItem[] = steps.map((s: any) => ({
        title: s.title || '',
        description: s.description || '',
        type: s.type || 'llm_prompt',
        prompt: s.prompt,
        tool_name: s.tool_name,
        agent_name: s.agent_name,
        note: s.note,
      }));
      setLocalSteps(parsedSteps);
      message.success(`已產生 ${parsedSteps.length} 個步驟`);
    } catch (error: any) {
      message.error(error.response?.data?.message || 'AI 生成步驟失敗');
    } finally {
      setGeneratingSteps(false);
      setClarifyModalVisible(false);
      setClarifyText('');
      setClarifyPendingValues(null);
    }
  }, [editForm, message]);

  const handleGenerateSteps = useCallback(async () => {
    try {
      const values = await editForm.validateFields(['name', 'description', 'goal', 'domain', 'tags']);
      if (!hasEnoughContext(values)) {
        setClarifyPendingValues(values);
        setClarifyText('');
        setClarifyModalVisible(true);
        return;
      }
      await doGenerateSteps();
    } catch {
      // validation failed — form fields missing required values
      message.warning('請至少填寫技能名稱');
    }
  }, [editForm, message, hasEnoughContext, doGenerateSteps]);

  const handleUpload = async () => {
    const file = uploadFileList[0] as RcFile | undefined;
    if (!file) {
      message.warning('請選擇一個檔案');
      return;
    }
    setUploading(true);
    try {
      await skillsRagApi.upload(file);
      message.success('技能檔案上傳成功');
      setUploadModalVisible(false);
      setUploadFileList([]);
      loadData();
    } catch (error: any) {
      message.error(error.response?.data?.message || '上傳失敗');
    } finally {
      setUploading(false);
    }
  };

  const handleUploadCancel = () => {
    setUploadModalVisible(false);
    setUploadFileList([]);
  };

  const handleCreate = () => {
    setEditingSkill(null);
    setLocalSteps([]);
    editForm.resetFields();
    editForm.setFieldsValue({ domain: activeTab || undefined });
    setEditModalVisible(true);
  };

  const handleEdit = (record: ActionScript) => {
    setEditingSkill(record);
    const matchedDomain = record.tags?.find((t) => BUSINESS_DOMAINS.some((d) => d.value === t)) || null;
    const parsedSteps: StepItem[] = (record.steps || []).map((s) => {
      try {
        return JSON.parse(s) as StepItem;
      } catch {
        return { title: s, type: 'manual' } as StepItem;
      }
    });
    setLocalSteps(parsedSteps);
    editForm.setFieldsValue({
      name: record.name,
      description: record.description,
      goal: (record as any).goal || '',
      domain: matchedDomain,
      tags: record.tags || [],
      linked_agents: record.linked_agents || [],
      guardrails: record.guardrails || [],
      status: record.status,
    });
    setCheckResultData((record as any).check_result || null);
    setEditModalVisible(true);
  };

  const handleEditOk = async () => {
    try {
      const values = await editForm.validateFields();
      const { domain: _domain, ...apiValues } = values;
      // Sync domain back into tags: remove old domain tag, add new one
      let updatedTags = [...(values.tags || [])];
      const oldDomainTag = BUSINESS_DOMAINS.find((d) => d.value && updatedTags.includes(d.value));
      if (oldDomainTag) {
        updatedTags = updatedTags.filter((t: string) => t !== oldDomainTag.value);
      }
      if (_domain) {
        updatedTags.push(_domain);
      }
      const stepsStr = localSteps.map((s) => JSON.stringify(s));
      if (editingSkill) {
        await actionApi.update(editingSkill._key, { ...apiValues, tags: updatedTags, steps: stepsStr });
        message.success('技能資訊已更新');
      } else {
        await actionApi.create({ ...apiValues, steps: stepsStr });
        message.success('技能已新增');
      }
      setEditModalVisible(false);
      setEditingSkill(null);
      setLocalSteps([]);
      editForm.resetFields();
      loadData();
    } catch (error: any) {
      if (error.response?.data?.message) {
        message.error(error.response.data.message);
      }
    }
  };

  const handleEditCancel = () => {
    setEditModalVisible(false);
    setEditingSkill(null);
    setLocalSteps([]);
    editForm.resetFields();
  };

  const handleDelete = async (id: string) => {
    try {
      await actionApi.delete(id);
      message.success('技能已刪除');
      loadData();
    } catch (error: any) {
      message.error(error.response?.data?.message || '刪除失敗');
    }
  };

  const confirmDelete = (id: string, name: string) => {
    Modal.confirm({
      title: '確認刪除',
      content: `確定要刪除技能「${name}」嗎？`,
      okText: '刪除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => handleDelete(id),
    });
  };

  const openAddStep = () => {
    setEditingStepIndex(null);
    setStepType('llm_prompt');
    stepForm.resetFields();
    setStepModalVisible(true);
  };

  const openEditStep = (index: number) => {
    setEditingStepIndex(index);
    const step = localSteps[index];
    setStepType(step.type);
    stepForm.setFieldsValue(step);
    setStepModalVisible(true);
  };

  const handleStepOk = async () => {
    try {
      const values = await stepForm.validateFields();
      const step: StepItem = { ...values, type: stepType };
      if (editingStepIndex !== null) {
        const updated = [...localSteps];
        updated[editingStepIndex] = step;
        setLocalSteps(updated);
      } else {
        setLocalSteps([...localSteps, step]);
      }
      setStepModalVisible(false);
      setEditingStepIndex(null);
      stepForm.resetFields();
    } catch {
      void 0;
    }
  };

  const handleStepCancel = () => {
    setStepModalVisible(false);
    setEditingStepIndex(null);
    stepForm.resetFields();
  };

  const removeStep = (index: number) => {
    setLocalSteps(localSteps.filter((_, i) => i !== index));
  };

  const moveStep = (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= localSteps.length) return;
    const updated = [...localSteps];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    setLocalSteps(updated);
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = Number(active.id);
    const newIndex = Number(over.id);
    setLocalSteps((prev) => {
      const updated = [...prev];
      const [moved] = updated.splice(oldIndex, 1);
      updated.splice(newIndex, 0, moved);
      return updated;
    });
  }, []);

  const columns = [
    {
      title: '名稱',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '綁定Agent',
      dataIndex: 'linked_agents',
      key: 'linked_agents',
      width: 200,
      render: (agents: string[] | undefined) => {
        if (!agents || agents.length === 0) {
          return <span style={{ color: contentTokens.textSecondary }}>-</span>;
        }
        return (
          <Space wrap size={[2, 2]}>
            {agents.map((a) => (
              <Tag key={a} color="blue" style={{ margin: 0 }}>{a}</Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: '領域',
      key: 'domain',
      width: 100,
      render: (_: unknown, record: ActionScript) => {
        if (!record.tags || record.tags.length === 0) return <span style={{ color: contentTokens.textSecondary }}>-</span>;
        const matched = BUSINESS_DOMAINS.find((d) => d.value && record.tags!.includes(d.value));
        return matched?.label || '-';
      },
    },
    {
      title: '步驟數',
      dataIndex: 'steps',
      key: 'steps',
      width: 80,
      align: 'center' as const,
      render: (steps: string[]) => steps?.length || 0,
    },
    {
      title: '檢查狀態',
      key: 'check_status',
      width: 100,
      render: (_: unknown, record: ActionScript) => {
        const { check_status, last_check_at } = record;
        if (check_status === 'checking') {
          return (
            <span>
              <Spin size="small" style={{ marginRight: 4 }} />
              評估中
            </span>
          );
        }
        if (check_status === 'passed') {
          return (
            <Tooltip title={last_check_at ? formatRelativeTime(last_check_at) : ''}>
              <Tag color="green">通過</Tag>
            </Tooltip>
          );
        }
        if (check_status === 'failed') {
          return <Tag color="red">失敗</Tag>;
        }
        if (check_status === 'warning') {
          return <Tag color="orange">警告</Tag>;
        }
        return <Tag>未檢查</Tag>;
      },
    },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => (
        <Tag color={status === 'enabled' ? 'green' : 'default'}>
          {status === 'enabled' ? '啟用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: ActionScript) => (
        <Space size="small">
          <Button type="link" size="small" onClick={() => handleEdit(record)}>
            編輯
          </Button>
          <Button type="link" size="small" danger onClick={() => confirmDelete(record._key, record.name)}>
            刪除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0, color: contentTokens.colorPrimary }}>
          技能管理
        </Title>
        <Space size="middle">
          <Input
            placeholder="搜尋技能..."
            prefix={<SearchOutlined style={{ color: contentTokens.textSecondary }} />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={loadData}>
            刷新
          </Button>
          <Button icon={<SettingOutlined />} onClick={() => { loadSettings(); setSettingsModalVisible(true); }}>
            設置
          </Button>
          {activeTab && (
            <Button icon={<PlusOutlined />} onClick={handleCreate}>
              新增技能
            </Button>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setUploadModalVisible(true)}>
            上傳 skill.md
          </Button>
        </Space>
      </div>

      <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginBottom: 8 }}>
        最後同步: {latestSyncTime ? formatRelativeTime(latestSyncTime) : '尚未同步'}
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={BUSINESS_DOMAINS.map((domain) => ({
          key: domain.value,
          label: domain.label,
        }))}
        style={{ marginBottom: 16 }}
      />

      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table
          dataSource={filteredData}
          columns={columns}
          rowKey="_key"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 筆` }}
          size="middle"
          onRow={(record) => ({
            onDoubleClick: () => handleEdit(record),
            style: { cursor: 'pointer' },
          })}
        />
      </div>

      <Modal
        title="上傳 skill.md"
        open={uploadModalVisible}
        onOk={handleUpload}
        onCancel={handleUploadCancel}
        okText="上傳"
        cancelText="取消"
        confirmLoading={uploading}
        okButtonProps={{ disabled: uploadFileList.length === 0 }}
        destroyOnClose
        width="60vw"
        style={{ top: 20 }}
        styles={{ body: { minHeight: '50vh' } }}
      >
        <Dragger
          multiple={false}
          accept=".md"
          fileList={uploadFileList}
          beforeUpload={(file) => {
            setUploadFileList([file]);
            return false;
          }}
          onRemove={() => setUploadFileList([])}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">點擊或拖拽 .md 檔案到此區域上傳</p>
          <p className="ant-upload-hint">僅支援 Markdown (.md) 格式的技能檔案</p>
        </Dragger>
      </Modal>

      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{editingSkill ? '編輯技能' : '新增技能'}</span>
            {editingSkill && (
              <Space size="small">
                <Button size="small" icon={<SyncOutlined />} onClick={handleSync} loading={syncing}>
                  同步到 Qdrant
                </Button>
                <Button size="small" icon={<CheckCircleOutlined />} onClick={handleCheck} loading={checking}>
                  完整性檢查
                </Button>
                <Button size="small" icon={<ApartmentOutlined />} onClick={handleGenerateMermaid}>
                  Mermaid
                </Button>
                {editingSkill.last_sync_at && (
                  <span style={{ fontSize: 12, color: '#888' }}>
                    已同步: {formatRelativeTime(editingSkill.last_sync_at)}
                  </span>
                )}
                {editingSkill.check_status === 'checking' && (
                  <span style={{ fontSize: 12 }}>
                    <Spin size="small" style={{ marginRight: 4 }} />
                    評估中
                  </span>
                )}
                {editingSkill.check_status && editingSkill.check_status !== 'checking' && (
                  <Tag color={editingSkill.check_status === 'passed' ? 'green' : editingSkill.check_status === 'failed' ? 'red' : editingSkill.check_status === 'warning' ? 'orange' : undefined}>
                    {editingSkill.check_status === 'passed' ? '通過' : editingSkill.check_status === 'failed' ? '失敗' : editingSkill.check_status === 'warning' ? '警告' : editingSkill.check_status}
                  </Tag>
                )}
                {editingSkill.check_status && editingSkill.check_status !== 'checking' && checkResultData && (
                  <Button size="small" onClick={() => setCheckResultVisible(true)}>
                    檢視報告
                  </Button>
                )}
              </Space>
            )}
          </div>
        }
        open={editModalVisible}
        onOk={handleEditOk}
        onCancel={handleEditCancel}
        okText="儲存"
        cancelText="取消"
        width="60vw"
        style={{ top: 20 }}
        styles={{ body: { minHeight: '50vh' } }}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" name="skill_edit_form">
          <Form.Item name="name" label="名稱" rules={[{ required: true, message: '請輸入名稱!' }]}>
            <Input placeholder="技能名稱" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="技能描述..." />
          </Form.Item>
          <Form.Item name="goal" label="完成目標">
            <TextArea rows={2} placeholder="例如：照片已上傳、ERP 已勾稽、回單已確認" />
          </Form.Item>
          <Form.Item name="domain" label="業務領域">
            <Select
              placeholder="選擇業務領域"
              allowClear
              options={BUSINESS_DOMAINS.filter((d) => d.value)}
            />
          </Form.Item>
          <Form.Item
            name="tags"
            label="標籤"
            tooltip="輸入標籤後按 Enter 確認"
          >
            <Select
              mode="tags"
              tokenSeparators={TAG_SEPARATORS}
              placeholder="輸入標籤"
            />
          </Form.Item>
          <Form.Item name="linked_agents" label="綁定 Agent">
            <Select mode="tags" tokenSeparators={TAG_SEPARATORS} placeholder="選擇或輸入 Agent 名稱" options={agentOptions} />
          </Form.Item>
          <Form.Item label="步驟">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Button
                icon={<ThunderboltOutlined />}
                onClick={handleGenerateSteps}
                loading={generatingSteps}
                type="dashed"
                block
                style={{ marginBottom: 8 }}
              >
                AI 生成建議步驟
              </Button>
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                <SortableContext items={localSteps.map((_, i) => String(i))} strategy={verticalListSortingStrategy}>
                  {localSteps.map((step, index) => (
                    <SortableStepItem
                      key={index}
                      step={step}
                      index={index}
                      total={localSteps.length}
                      onEdit={openEditStep}
                      onRemove={removeStep}
                      onMove={moveStep}
                    />
                  ))}
                </SortableContext>
              </DndContext>
              <Button type="dashed" block icon={<PlusOutlined />} onClick={openAddStep}>
                新增步驟
              </Button>
            </div>
          </Form.Item>
          <Form.Item name="guardrails" label="護欄 (Guardrails)">
            <Select mode="tags" tokenSeparators={TAG_SEPARATORS} placeholder="輸入護欄規則" />
          </Form.Item>
          <Form.Item name="status" label="狀態" rules={[{ required: true, message: '請選擇狀態!' }]}>
            <Select placeholder="選擇狀態" options={STATUS_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="技能流程圖"
        open={mermaidModalVisible}
        onCancel={() => setMermaidModalVisible(false)}
        footer={null}
        width="50vw"
        style={{ top: 20 }}
        destroyOnClose
      >
        <Spin spinning={!mermaidSvg && mermaidCode !== ''}>
          <div
            style={{
              background: '#fff',
              borderRadius: 8,
              padding: 24,
              marginBottom: 16,
              border: '1px solid #f0f0f0',
              overflow: 'auto',
            }}
          >
            <div dangerouslySetInnerHTML={{ __html: mermaidSvg }} />
          </div>
        </Spin>
        <div style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontWeight: 500 }}>Mermaid 程式碼</span>
            <Button size="small" icon={<CopyOutlined />} onClick={handleCopyMermaid}>
              複製
            </Button>
          </div>
          <Input.TextArea rows={8} value={mermaidCode} readOnly style={{ fontFamily: 'monospace', fontSize: 12 }} />
        </div>
      </Modal>

      <Modal
        title={editingStepIndex !== null ? '編輯步驟' : '新增步驟'}
        open={stepModalVisible}
        onOk={handleStepOk}
        onCancel={handleStepCancel}
        okText="確定"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={stepForm} layout="vertical" name="step_form">
          <Form.Item name="title" label="標題" rules={[{ required: true, message: '請輸入步驟標題!' }]}>
            <Input placeholder="步驟標題" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="步驟描述..." />
          </Form.Item>
          <Form.Item label="類型" required>
            <Select
              value={stepType}
              onChange={(v) => setStepType(v)}
              options={[
                { label: 'LLM Prompt', value: 'llm_prompt' },
                { label: 'Script', value: 'script' },
                { label: 'Manual', value: 'manual' },
                { label: 'Agent', value: 'agent' },
                { label: 'Tools', value: 'tool' },
              ]}
            />
          </Form.Item>
          {stepType === 'llm_prompt' && (
            <>
              <Form.Item name="model" label="Model">
                <Select placeholder="選擇模型" allowClear options={modelOptions} />
              </Form.Item>
              <Form.Item name="temperature" label="Temperature">
                <Slider min={0} max={2} step={0.1} />
              </Form.Item>
              <Form.Item name="max_tokens" label="Max Tokens">
                <InputNumber min={128} max={32000} step={128} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="prompt" label="Prompt">
                <TextArea rows={4} placeholder="輸入 prompt..." />
              </Form.Item>
            </>
          )}
          {stepType === 'script' && (
            <>
              <Form.Item name="script_id" label="Script ID/Name">
                <Input placeholder="輸入 Script ID 或名稱" />
              </Form.Item>
              <Form.Item name="parameters" label="Parameters">
                <TextArea rows={3} placeholder='{"key": "value"}' />
              </Form.Item>
            </>
          )}
          {stepType === 'manual' && (
            <>
              <Form.Item name="note" label="Note">
                <TextArea rows={3} placeholder="輸入備註..." />
              </Form.Item>
              <Form.Item name="require_human" label="Require Human" valuePropName="checked">
                <Switch />
              </Form.Item>
            </>
          )}
          {stepType === 'agent' && (
            <>
              <Form.Item name="agent_name" label="Agent 名稱" rules={[{ required: true, message: '請輸入 Agent 名稱!' }]}>
                <Input placeholder="輸入 Agent 名稱" />
              </Form.Item>
            </>
          )}
          {stepType === 'tool' && (
            <>
              <Form.Item name="tool_name" label="Tool 名稱" rules={[{ required: true, message: '請輸入 Tool 名稱!' }]}>
                <Input placeholder="輸入 Tool 名稱" />
              </Form.Item>
              <Form.Item name="tool_params" label="參數">
                <TextArea rows={3} placeholder='{"key": "value"}' />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      <Modal
        title="AI 助手設定"
        open={settingsModalVisible}
        onOk={handleSaveSettings}
        onCancel={() => setSettingsModalVisible(false)}
        okText="儲存"
        cancelText="取消"
        confirmLoading={savingSettings}
        destroyOnClose
      >
        <Spin spinning={settingsLoading}>
          <Form form={settingsForm} layout="vertical" name="settings_form">
            <Form.Item name="llm_model" label="LLM Model" rules={[{ required: true, message: '請選擇模型!' }]}>
              <Select
                placeholder="選擇 LLM 模型"
                options={modelOptions}
              />
            </Form.Item>
            <Form.Item name="temperature" label="Temperature" tooltip="數值越高，輸出越有創意（0~2）">
              <Slider min={0} max={2} step={0.1} />
            </Form.Item>
            <Form.Item name="max_tokens" label="Max Tokens">
              <InputNumber min={128} max={128000} step={128} style={{ width: '100%' }} />
            </Form.Item>
          </Form>
        </Spin>
      </Modal>

      <Modal
        title="補充資訊"
        open={clarifyModalVisible}
        onCancel={() => { setClarifyModalVisible(false); setClarifyPendingValues(null); }}
        footer={null}
        width={480}
        destroyOnClose
      >
        <div style={{ marginBottom: 12, color: '#666' }}>
          目前的資訊不足以讓 AI 充分理解技能需求。請補充描述或完成目標，讓 AI 能產生更準確的步驟建議：
        </div>
        <div style={{ marginBottom: 8, fontSize: 12, color: '#888' }}>
          當前填寫內容：
          <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
            {clarifyPendingValues?.name && <li>名稱：{clarifyPendingValues.name}</li>}
            {clarifyPendingValues?.description && <li>描述：{clarifyPendingValues.description}</li>}
            {clarifyPendingValues?.goal && <li>完成目標：{clarifyPendingValues.goal}</li>}
            {clarifyPendingValues?.domain && <li>業務領域：{clarifyPendingValues.domain}</li>}
          </ul>
        </div>
        <TextArea
          rows={4}
          placeholder="例如：這個技能需要先查詢 ERP 庫存，然後比對訂單，最後寫入 Ragic..."
          value={clarifyText}
          onChange={(e) => setClarifyText(e.target.value)}
          style={{ marginBottom: 16 }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={() => { setClarifyModalVisible(false); setClarifyPendingValues(null); }}>
            取消
          </Button>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={generatingSteps}
            onClick={() => doGenerateSteps(clarifyText)}
          >
            開始生成
          </Button>
        </div>
      </Modal>

      <Modal
        title={
          <span style={{ color: '#faad14' }}>
            <WarningOutlined style={{ marginRight: 8 }} />
            設計問題提醒
          </span>
        }
        open={warningModalVisible}
        onCancel={() => setWarningModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setWarningModalVisible(false)}>瞭解，我修改一下</Button>,
          <Button key="continue" type="primary" danger onClick={() => {
            setWarningModalVisible(false);
            doGenerateSteps(undefined, true);
          }}>忽略警告，繼續生成</Button>,
        ]}
        width={520}
        destroyOnClose
      >
        <div style={{ marginBottom: 12 }}>
          技能設計發現以下問題，建議先修改再生成步驟：
        </div>
        {warningData?.issues?.map((issue: any, i: number) => (
          <div
            key={i}
            style={{
              padding: '8px 12px',
              marginBottom: 8,
              borderRadius: 6,
              background: issue.severity === 'error' ? '#fff2f0' : '#fffbe6',
              border: `1px solid ${issue.severity === 'error' ? '#ffccc7' : '#ffe58f'}`,
            }}
          >
            <div style={{ fontWeight: 500, marginBottom: 2 }}>
              {issue.severity === 'error' ? '❌ ' : '⚠️ '}
              {issue.type === 'single_responsibility' ? '單一職責違反' :
               issue.type === 'coherence' ? '描述與目標不一致' :
               issue.type === 'specificity' ? '目標太過模糊' :
               issue.type === 'mismatch' ? '領域不匹配' : '其他'}
            </div>
            <div style={{ fontSize: 13, color: '#666' }}>{issue.detail}</div>
          </div>
        ))}
        {warningData?.suggestion && (
          <div style={{ marginTop: 12, padding: '8px 12px', background: '#f6f8fa', borderRadius: 6, fontSize: 13, color: '#555' }}>
            💡 建議：{warningData.suggestion}
          </div>
        )}
      </Modal>

      <Modal
        title="完整性檢查報告"
        open={checkResultVisible}
        onCancel={() => setCheckResultVisible(false)}
        footer={
          <Space>
            <Button onClick={() => setCheckResultVisible(false)}>關閉</Button>
            <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => {
              setCheckResultVisible(false);
              handleCheck();
            }}>
              重新檢查
            </Button>
          </Space>
        }
        width={600}
        style={{ top: 20 }}
        destroyOnClose
      >
        {checkResultData ? (
          <div>
            <div
              style={{
                marginBottom: 16,
                padding: 12,
                borderRadius: 6,
                background: checkResultData.status === 'passed' ? '#f6ffed' :
                  checkResultData.status === 'warning' ? '#fffbe6' : '#fff2f0',
                border: `1px solid ${
                  checkResultData.status === 'passed' ? '#b7eb8f' :
                  checkResultData.status === 'warning' ? '#ffe58f' : '#ffccc7'
                }`,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 4 }}>
                整體評價：
                {checkResultData.status === 'passed' ? '✅ 通過' :
                 checkResultData.status === 'warning' ? '⚠️ 警告' : '❌ 失敗'}
              </div>
              <div style={{ fontSize: 13, color: '#555' }}>{checkResultData.summary}</div>
            </div>

            {['design', 'completeness', 'feasibility', 'resources'].map((dim) => {
              const d = checkResultData[dim];
              if (!d) return null;
              const dimLabels: Record<string, string> = {
                design: '設計品質',
                completeness: '完整性',
                feasibility: '可行性',
                resources: '資源可用性',
              };
              return (
                <div key={dim} style={{ marginBottom: 12, padding: '8px 12px', border: '1px solid #f0f0f0', borderRadius: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontWeight: 500 }}>{dimLabels[dim] || dim}</span>
                    <Tag color={d.score >= 7 ? 'green' : d.score >= 4 ? 'orange' : 'red'}>
                      {d.score}/10
                    </Tag>
                  </div>
                  {d.issues && d.issues.length > 0 && (
                    <ul style={{ margin: '4px 0', paddingLeft: 16, fontSize: 13, color: '#cc0000' }}>
                      {d.issues.map((issue: string, i: number) => <li key={i}>{issue}</li>)}
                    </ul>
                  )}
                  {d.suggestions && d.suggestions.length > 0 && (
                    <ul style={{ margin: '4px 0', paddingLeft: 16, fontSize: 13, color: '#1677ff' }}>
                      {d.suggestions.map((s: string, i: number) => <li key={i}>{s}</li>)}
                    </ul>
                  )}
                </div>
              );
            })}

            {checkResultData.resources?.missing && checkResultData.resources.missing.length > 0 && (
              <div style={{ marginTop: 8, padding: 8, background: '#fff7e6', borderRadius: 6, fontSize: 13 }}>
                <span style={{ fontWeight: 500 }}>缺少的資源：</span>
                {checkResultData.resources.missing.join(', ')}
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>暫無檢查結果</div>
        )}
      </Modal>
    </div>
  );
}

function SortableStepItem({ step, index, total, onEdit, onRemove, onMove }: {
  step: StepItem;
  index: number;
  total: number;
  onEdit: (i: number) => void;
  onRemove: (i: number) => void;
  onMove: (i: number, dir: 'up' | 'down') => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: String(index) });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    cursor: isDragging ? 'grabbing' : undefined,
  };

  return (
    <div ref={setNodeRef} style={style}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          border: '1px solid #d9d9d9',
          borderRadius: 6,
          background: '#fafafa',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
          <span {...attributes} {...listeners} style={{ cursor: 'grab', fontSize: 16, color: '#999', flexShrink: 0 }}>
            <HolderOutlined />
          </span>
          <div style={{ flex: 1, minWidth: 0 }} onDoubleClick={() => onEdit(index)}>
            <span style={{ fontWeight: 500 }}>{`${index + 1}. ${step.title}`}</span>
            <Tag style={{ marginLeft: 8 }} color="blue">{step.type}</Tag>
            {step.description && (
              <div style={{ fontSize: 12, color: '#888', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{step.description}</div>
            )}
          </div>
        </div>
        <Space>
          <Button type="text" size="small" icon={<UpOutlined />} disabled={index === 0} onClick={() => onMove(index, 'up')} />
          <Button type="text" size="small" icon={<DownOutlined />} disabled={index === total - 1} onClick={() => onMove(index, 'down')} />
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(index)} />
          <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => onRemove(index)} />
        </Space>
      </div>
    </div>
  );
}
