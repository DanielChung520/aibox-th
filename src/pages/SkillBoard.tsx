/**
 * @file        技能看板
 * @description 技能規格管理，支援 CRUD、狀態流、版本管控
 *             狀態流：draft → spec → developing → testing → live → deprecated
 * @lastUpdate  2026-04-29 14:00:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Select, Tag, Space, App, Spin, Descriptions, Popconfirm, Divider } from 'antd';
import { PlusOutlined, CodeOutlined, ArrowLeftOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons';
import { MarkdownContent } from '../components/FloatingAssistant/ChatMarkdown';
import { useNavigate } from 'react-router-dom';
import type { SkillSpec } from '../services/api';
import { skillApi } from '../services/api';
import { authStore } from '../stores/auth';

const statusFlow: Record<string, { label: string; color: string; next: string[] }> = {
  draft: { label: '草稿', color: 'default', next: ['spec'] },
  spec: { label: '規格中', color: 'blue', next: ['developing', 'draft'] },
  developing: { label: '開發中', color: 'orange', next: ['testing', 'draft'] },
  testing: { label: '測試中', color: 'cyan', next: ['live', 'developing'] },
  live: { label: '已上線', color: 'green', next: ['deprecated', 'developing'] },
  deprecated: { label: '已淘汰', color: 'red', next: ['draft'] },
};

const skillTypeOptions = [
  { value: 'data', label: '資料技能' },
  { value: 'knowledge', label: '知識技能' },
  { value: 'tool', label: '工具技能' },
  { value: 'process', label: '流程技能' },
  { value: 'system', label: '系統技能' },
];

const statusOptions = Object.entries(statusFlow).map(([k, v]) => ({ value: k, label: v.label }));

function renderList(val: any): string[] {
  if (Array.isArray(val)) return val.filter(Boolean);
  if (typeof val === 'string') return val.split('\n').map(s => s.trim()).filter(Boolean);
  return [];
}

export default function SkillBoard() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<SkillSpec[]>([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selected, setSelected] = useState<SkillSpec | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<SkillSpec | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [specOpen, setSpecOpen] = useState(false);
  const [specContent, setSpecContent] = useState<string>('');
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [specRecord, setSpecRecord] = useState<SkillSpec | null>(null);
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [revisionText, setRevisionText] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [form] = Form.useForm();

  const user = authStore.getState().user;
  const userName = user?.name || user?.username || 'system';

  const fetchList = async () => {
    setLoading(true);
    try {
      const res = await skillApi.list();
      setData(res.data.data || []);
    } catch {
      message.error('載入技能列表失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchList(); }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setEditOpen(true);
  };

  const openEdit = (record: SkillSpec) => {
    setEditing(record);
    const formVals: any = { ...record };
    if (Array.isArray(formVals.tags)) formVals.tags = (formVals.tags || []).join(', ');
    if (Array.isArray(formVals.steps)) formVals.steps = (formVals.steps || []).join('\n');
    if (Array.isArray(formVals.guardrails)) formVals.guardrails = (formVals.guardrails || []).join('\n');
    if (Array.isArray(formVals.linked_intents)) formVals.linked_intents = (formVals.linked_intents || []).join(', ');
    form.setFieldsValue(formVals);
    setEditOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      // 轉換 tags/steps/guardrails/linked_intents 字串 → 陣列
      const payload: any = { ...values };
      if (typeof payload.tags === 'string') payload.tags = payload.tags.split(',').map((s: string) => s.trim()).filter(Boolean);
      if (typeof payload.steps === 'string') payload.steps = payload.steps.split('\n').map((s: string) => s.trim()).filter(Boolean);
      if (typeof payload.guardrails === 'string') payload.guardrails = payload.guardrails.split('\n').map((s: string) => s.trim()).filter(Boolean);
      if (typeof payload.linked_intents === 'string') payload.linked_intents = payload.linked_intents.split(',').map((s: string) => s.trim()).filter(Boolean);
      setConfirmLoading(true);
      if (editing?._key) {
        await skillApi.update(editing._key, payload);
        message.success('更新成功');
      } else {
        await skillApi.create({ ...payload, created_by: userName });
        message.success('新增成功');
      }
      setEditOpen(false);
      fetchList();
    } catch (err: any) {
      const errMsg = err?.response?.data?.message || err?.message || '儲存失敗';
      console.error('[SkillBoard] 儲存失敗:', errMsg, err?.response?.data);
      message.error(errMsg);
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleDelete = async (key: string) => {
    try {
      await skillApi.delete(key);
      message.success('已刪除');
      fetchList();
    } catch {
      message.error('刪除失敗');
    }
  };

  const handleStatusChange = async (key: string, newStatus: string) => {
    try {
      await skillApi.update(key, { status: newStatus } as any);
      message.success('狀態已更新');
      fetchList();
    } catch {
      message.error('更新狀態失敗');
    }
  };

  const handleAnalyze = async (record: SkillSpec) => {
    setAnalyzing(record._key);
    try {
      const res = await skillApi.analyze(record._key);
      if (res.data.code === 200) {
        message.success('技能規格產生成功');
        fetchList();
      } else {
        message.error('分析失敗');
      }
    } catch {
      message.error('分析失敗');
    } finally {
      setAnalyzing(null);
    }
  };

  const buildSpecMarkdown = (record: SkillSpec): string => {
    const spec = (record as any).dev_spec || {};
    const biz = spec.business || {};
    const impl = spec.implementation || {};
    const lines: string[] = [];
    lines.push(`# 技能規格書：${record.title || record.name || record.skill_no}`);
    lines.push('');
    if (biz.summary) lines.push(`> ${biz.summary}`);
    lines.push('');
    lines.push('## 📋 業務流程');
    lines.push(`| 項目 | 內容 |`);
    lines.push(`|------|------|`);
    lines.push(`| 技能編號 | ${record.skill_no} |`);
    lines.push(`| 名稱 | ${impl.name || record.name || '-'} |`);
    lines.push(`| 類型 | ${record.skill_type} |`);
    lines.push(`| 版本 | ${record.version} |`);
    lines.push('');
    if (biz.user_flow) {
      lines.push('### 使用者流程圖');
      const flow = biz.user_flow.startsWith('```') ? biz.user_flow : '```mermaid\n' + biz.user_flow + '\n```';
      lines.push(flow);
      lines.push('');
    }
    if (biz.component_relations) {
      lines.push('### 組件關係圖');
      const comp = biz.component_relations.startsWith('```') ? biz.component_relations : '```mermaid\n' + biz.component_relations + '\n```';
      lines.push(comp);
      lines.push('');
    }
    if (biz.data_flow) {
      lines.push('### 資料流');
      lines.push(biz.data_flow);
      lines.push('');
    }
    lines.push('---');
    lines.push('## 💻 開發規格');
    if (impl.file_path) lines.push(`- **檔案路徑**：\`${impl.file_path}\``);
    if (impl.class_name) lines.push(`- **類別**：\`${impl.class_name}\``);
    if (impl.base_class) lines.push(`- **基礎類別**：\`${impl.base_class}\``);
    if (impl.registration) lines.push(`- **註冊方式**：\`${impl.registration}\``);
    if (impl.test_file) lines.push(`- **測試檔案**：\`${impl.test_file}\``);
    lines.push('');
    if (Array.isArray(impl.tech_stack) && impl.tech_stack.length > 0) {
      lines.push('### 技術棧');
      for (const t of impl.tech_stack) lines.push(`- ${t}`);
      lines.push('');
    }
    if (impl.input_schema && Object.keys(impl.input_schema).length > 0) {
      lines.push('### 輸入參數');
      for (const [k, v] of Object.entries(impl.input_schema)) {
        lines.push(`- \`${k}\`: ${v}`);
      }
      lines.push('');
    }
    if (impl.output_schema && Object.keys(impl.output_schema).length > 0) {
      lines.push('### 輸出參數');
      for (const [k, v] of Object.entries(impl.output_schema)) {
        lines.push(`- \`${k}\`: ${v}`);
      }
      lines.push('');
    }
    if (Array.isArray(impl.data_access)) {
      lines.push('### 資料源');
      lines.push('| 類型 | 名稱 | 集合 | 鍵 |');
      lines.push('|------|------|------|-----|');
      for (const da of impl.data_access) {
        lines.push(`| ${da.type || '-'} | ${da.name || '-'} | ${da.collection || '-'} | ${da.key || '-'} |`);
      }
      lines.push('');
    }
    if (spec.hour_breakdown || impl.hour_breakdown) {
      const hb = impl.hour_breakdown || spec.hour_breakdown || {};
      const total = (hb.design || 0) + (hb.development || 0) + (hb.testing || 0) + (hb.review || 0);
      lines.push('### 工時評估');
      lines.push('| 階段 | 工時 |');
      lines.push('|------|------|');
      lines.push(`| 🎨 設計 | ${hb.design || 0}h |`);
      lines.push(`| 💻 開發 | ${hb.development || 0}h |`);
      lines.push(`| 🧪 測試 | ${hb.testing || 0}h |`);
      lines.push(`| ✅ 審查 | ${hb.review || 0}h |`);
      lines.push(`| **合計** | **${total}h** |`);
      lines.push('');
    }
    if (Array.isArray(spec.error_handling)) {
      lines.push('### 錯誤處理');
      lines.push('| 情境 | 回應 | 錯誤碼 |');
      lines.push('|------|------|--------|');
      for (const eh of spec.error_handling) {
        lines.push(`| ${eh.scenario || '-'} | ${eh.response || '-'} | ${eh.code || '-'} |`);
      }
      lines.push('');
    }
    if (Array.isArray(spec.risks)) {
      lines.push('### 風險');
      for (const r of spec.risks) lines.push(`- ⚠️ ${r}`);
      lines.push('');
    }
    if (Array.isArray(spec.suggestions)) {
      lines.push('### 建議');
      for (const s of spec.suggestions) lines.push(`- 💡 ${s}`);
      lines.push('');
    }
    return lines.join('\n');
  };

  const handleShowSpec = (record: SkillSpec) => {
    setSpecRecord(record);
    setSpecContent(buildSpecMarkdown(record));
    setSpecOpen(true);
  };

  const handleRegenerate = async () => {
    if (!specRecord || !revisionText.trim()) return;
    setRegenerating(true);
    setRevisionOpen(false);
    try {
      await skillApi.analyze(specRecord._key, { revision: revisionText.trim() });
      message.success('規格書已重新產生');
      setRevisionText('');
      // Fetch updated record
      const res = await skillApi.get(specRecord._key);
      const updated = res.data.data;
      if (updated) {
        setSpecRecord(updated);
        setSpecContent(buildSpecMarkdown(updated));
      }
    } catch {
      message.error('重新產生失敗');
    } finally {
      setRegenerating(false);
    }
  };

  const columns = [
    {
      title: '技能編號',
      dataIndex: 'skill_no',
      width: 80,
      render: (no: string, record: SkillSpec) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => { setSelected(record); setDetailOpen(true); }}>
          {no}
        </Button>
      ),
    },
    {
      title: '標題',
      dataIndex: 'title',
      width: 100,
      ellipsis: true,
      render: (t: string, record: SkillSpec) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => { setSelected(record); setDetailOpen(true); }}>
          {t || record.name || '-'}
        </Button>
      ),
    },
    {
      title: '程式名稱',
      dataIndex: 'name',
      width: 120,
      ellipsis: true,
      render: (n: string) => n ? <Tag>{n}</Tag> : '-',
    },
    {
      title: '類型',
      dataIndex: 'skill_type',
      width: 80,
      render: (t: string) => {
        const opt = skillTypeOptions.find(o => o.value === t);
        return <Tag>{opt?.label || t}</Tag>;
      },
    },
    {
      title: '語言',
      dataIndex: 'code_language',
      width: 70,
      render: (l: string) => l ? <Tag>{l}</Tag> : '-',
    },
    {
      title: '標籤',
      dataIndex: 'tags',
      width: 140,
      ellipsis: true,
      render: (tags: any) => {
        const arr = Array.isArray(tags) ? tags : typeof tags === 'string' ? tags.split(',').map(s => s.trim()) : [];
        const visible = arr.slice(0, 3);
        const excess = arr.length - visible.length;
        return (
          <span>
            {visible.map((t: string) => <Tag key={t} style={{ marginBottom: 2 }}>{t}</Tag>)}
            {excess > 0 && <Tag style={{ marginBottom: 2 }}>+{excess}</Tag>}
          </span>
        );
      },
    },
    {
      title: '版本',
      dataIndex: 'version',
      width: 50,
    },
    {
      title: '狀態',
      dataIndex: 'status',
      width: 70,
      render: (s: string, record: SkillSpec) => {
        const cfg = statusFlow[s] || { label: s, color: 'default', next: [] };
        return (
          <Select
            value={s}
            size="small"
            style={{ width: 85 }}
            onChange={(v) => handleStatusChange(record._key, v)}
            options={cfg.next.map((n: string) => ({ value: n, label: statusFlow[n]?.label || n }))}
          />
        );
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      width: 140,
      ellipsis: { showTitle: true },
      render: (d: string) => d ? <span title={d}>{d.length > 20 ? d.slice(0, 20) + '…' : d}</span> : '-',
    },
    {
      title: '更新',
      dataIndex: 'updated_at',
      width: 80,
      ellipsis: true,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-',
    },
    {
      title: '操作',
      width: 100,
      render: (_: any, record: SkillSpec) => (
        <Space size={4}>
          {(record.status === 'draft' || record.status === 'spec') && (
            <Button type="primary" size="small" icon={<PlayCircleOutlined />} loading={analyzing === record._key} onClick={() => handleAnalyze(record)}>分析</Button>
          )}
          {(record.status === 'spec' || record.status === 'developing') && (record as any).dev_spec && (
            <Button type="link" size="small" icon={<FileTextOutlined />} onClick={() => handleShowSpec(record)} />
          )}
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="確定刪除？" onConfirm={() => handleDelete(record._key)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/app/browse-agent')}>返回</Button>
          <h2 style={{ margin: 0 }}><CodeOutlined /> 技能看板</h2>
        </div>
        <Space>
          <Button onClick={fetchList}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增技能</Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={data}
          rowKey="_key"
          size="small"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1000 }}
        />
      </Spin>

      <Modal title="技能詳情" open={detailOpen} onCancel={() => setDetailOpen(false)} footer={null} width={700}>
        {selected && (
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="編號">{selected.skill_no}</Descriptions.Item>
            <Descriptions.Item label="狀態">
              <Tag color={statusFlow[selected.status]?.color}>{statusFlow[selected.status]?.label || selected.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="名稱">{selected.title || selected.name}</Descriptions.Item>
            <Descriptions.Item label="程式名稱">{selected.name ? <Tag>{selected.name}</Tag> : '(規格階段產生)'}</Descriptions.Item>
            <Descriptions.Item label="類型">{skillTypeOptions.find(o => o.value === selected.skill_type)?.label || selected.skill_type}</Descriptions.Item>
            <Descriptions.Item label="版本">{selected.version}</Descriptions.Item>
            <Descriptions.Item label="程式語言">{selected.code_language || 'Python'}</Descriptions.Item>
            <Descriptions.Item label="標籤">{(Array.isArray(selected.tags) ? selected.tags : []).join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="描述" span={2}>{selected.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="步驟" span={2}>
              {(Array.isArray(selected.steps) ? selected.steps : []).map((s, i) => <div key={i}>{i + 1}. {s}</div>) || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="護欄規則" span={2}>
              {(Array.isArray(selected.guardrails) ? selected.guardrails : []).map((g, i) => <Tag key={i} color="red">{g}</Tag>) || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="關聯意圖">{renderList(selected.linked_intents).join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="建立者">{selected.created_by || '-'}</Descriptions.Item>
            <Descriptions.Item label="開發者">{selected.developed_by || '-'}</Descriptions.Item>
            <Descriptions.Item label="建立時間">{selected.created_at ? new Date(selected.created_at).toLocaleString('zh-TW') : '-'}</Descriptions.Item>
            <Descriptions.Item label="更新時間">{selected.updated_at ? new Date(selected.updated_at).toLocaleString('zh-TW') : '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      <Modal title={editing ? '編輯技能' : '新增技能'} open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={handleSave} confirmLoading={confirmLoading}
        okText={editing ? '更新' : '建立'} width={700}>
        <Form form={form} layout="vertical">
          <Space style={{ width: '100%' }}>
            <Form.Item name="title" label="技能標題" rules={[{ required: true }]} style={{ width: 250 }}>
              <Input placeholder="例如：庫存品項查詢" />
            </Form.Item>
            <Form.Item name="skill_type" label="類型" rules={[{ required: true }]} style={{ width: 150 }}>
              <Select options={skillTypeOptions} />
            </Form.Item>
            <Form.Item name="status" label="狀態" style={{ width: 120 }}>
              <Select options={statusOptions} defaultValue="draft" />
            </Form.Item>
          </Space>
          <Form.Item name="name" label="程式名稱（規格階段填入）">
            <Input placeholder="規格分析時產生，例如 query_stock" disabled />
          </Form.Item>
          <Form.Item name="code_language" label="程式語言" style={{ width: 130 }}>
            <Select options={[
              { value: 'python', label: 'Python' },
              { value: 'pyo3', label: 'PyO3 (Rust)' },
              { value: 'rust', label: 'Rust' },
              { value: 'typescript', label: 'TypeScript' },
            ]} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="技能的中文描述" />
          </Form.Item>
          <Form.Item name="tags" label="標籤（逗號分隔）">
            <Input placeholder="庫存, STOCK_16, ragic" />
          </Form.Item>
          <Divider style={{ margin: '12px 0' }}>技能定義</Divider>
          <Form.Item name="steps" label="執行步驟（每行一步）">
            <Input.TextArea rows={3} placeholder="1. 從 product_cache 讀取&#10;2. 套用 allowed_fields 過濾&#10;3. LLM 格式化輸出" />
          </Form.Item>
          <Form.Item name="guardrails" label="護欄規則（每行一條）">
            <Input.TextArea rows={2} placeholder="禁止編造假產品&#10;禁止輸出JSON" />
          </Form.Item>
          <Form.Item name="linked_intents" label="關聯意圖（逗號分隔）">
            <Input placeholder="product_list, order_text" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 規格書 Modal */}
      <Modal title="📄 技能規格書" open={specOpen} onCancel={() => setSpecOpen(false)} footer={[
        <Button key="close" onClick={() => setSpecOpen(false)}>關閉</Button>,
        <Button key="regenerate" loading={regenerating} onClick={() => { setRevisionText(''); setRevisionOpen(true); }}>重新產生</Button>,
        <Button key="copy" type="primary" onClick={() => { navigator.clipboard.writeText(specContent).then(() => message.success('已複製規格書')); }}>複製 Markdown</Button>,
      ]} width={1200}>
        <Spin spinning={regenerating} tip="AI 重新產生規格書中...">
          <div style={{ display: 'flex', gap: 16, maxHeight: '70vh', overflow: 'hidden' }}>
            {/* 左側：需求書 */}
            <div style={{ flex: 1, overflow: 'auto', padding: '8px', borderRight: '1px solid #f0f0f0' }}>
              <h3>📋 技能需求</h3>
              {specRecord && (
                <>
                  <p><strong>{specRecord.title || specRecord.name || specRecord.skill_no}</strong></p>
                  <p style={{ fontSize: 13, color: '#666' }}>{specRecord.description || ''}</p>
                  <Divider style={{ margin: '8px 0' }} />
                  <h4>執行步驟</h4>
                  <ol style={{ fontSize: 13 }}>
                    {renderList(specRecord.steps).map((s: string, i: number) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ol>
                  <h4>護欄規則</h4>
                  <ul style={{ fontSize: 13 }}>
                    {renderList(specRecord.guardrails).map((g: string, i: number) => (
                      <li key={i}><Tag color="red">{g}</Tag></li>
                    ))}
                  </ul>
                  <p style={{ fontSize: 12, color: '#999' }}>
                    類型: {specRecord.skill_type} | 標籤: {renderList(specRecord.tags).join(', ')}
                  </p>
                </>
              )}
            </div>
            {/* 右側：系統開發規格書 */}
            <div style={{ flex: 2, overflow: 'auto', padding: '8px' }}>
              <MarkdownContent content={specContent} />
            </div>
          </div>
        </Spin>
      </Modal>

      {/* 重新產生規格書 Modal */}
      <Modal title="🔄 重新產生規格書" open={revisionOpen} onCancel={() => setRevisionOpen(false)}
        onOk={handleRegenerate} confirmLoading={regenerating} okText="重新產生">
        <div style={{ marginBottom: 8 }}>請描述需要調整的方向，AI 將根據您的指示重新產生規格書：</div>
        <Input.TextArea rows={4} value={revisionText}
          onChange={(e) => setRevisionText(e.target.value)}
          placeholder="例如：增加錯誤處理、調整技術棧、補充資料流說明..."
        />
      </Modal>
    </div>
  );
}
