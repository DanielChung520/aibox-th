/**
 * @file        智慧報表 Modal
 * @description Schema 頁面的智慧報表功能 — 報告列表、樣板管理、產生新報告（支援非同步）
 * @lastUpdate  2026-05-01 03:00:00
 * @author      Daniel Chung / Sisyphus
 * @version     1.1.0
 */

import { useState, useEffect, useCallback } from 'react';
import { Modal, Table, Form, Input, Select, Button, Space, Tag, Badge, Switch, TimePicker, Checkbox, App, theme } from 'antd';
import { FileTextOutlined, PlusOutlined } from '@ant-design/icons';
import type { TableInfo } from '../../services/dataAgentApi';
import { dataAgentApi } from '../../services/dataAgentApi';
import { toolsApi, schemaReportsApi, schemaReportTemplatesApi, type SchemaReportTemplate } from '../../services/api';

const { TextArea } = Input;

export interface SchemaReport {
  report_id: string;
  report_name: string;
  created_at: string;
  report_link: string;
  status?: string;
  error_message?: string;
}

interface SchemaReportModalProps {
  open: boolean;
  tableInfo: TableInfo;
  onClose: () => void;
}

interface ReportFormValues {
  goal: string;
  description: string;
  chartType?: string;
  legendShow?: boolean;
  legendPosition?: string;
  fieldHints?: string;
  specialNotes?: string;
  scheduleType?: string;
  scheduleTime?: string;
  scheduleDays?: number[];
  notes?: string;
}

const WEEK_OPTIONS = [
  { label: '日', value: 0 },
  { label: '一', value: 1 },
  { label: '二', value: 2 },
  { label: '三', value: 3 },
  { label: '四', value: 4 },
  { label: '五', value: 5 },
  { label: '六', value: 6 },
];

const CHART_TYPES = [
  { value: 'pie', label: '圓餅圖 (Pie)' },
  { value: 'bar', label: '長條圖 (Bar)' },
  { value: 'line', label: '折線圖 (Line)' },
  { value: 'area', label: '區域圖 (Area)' },
  { value: 'scatter', label: '散點圖 (Scatter)' },
  { value: 'combo', label: '組合圖 (Combo)' },
];

export default function SchemaReportModal({ open, tableInfo, onClose }: SchemaReportModalProps) {
  const { message } = App.useApp();
  const { token: antToken } = theme.useToken();
  const [form] = Form.useForm<ReportFormValues>();
  const [regenerateForm] = Form.useForm();
  const [templates, setTemplates] = useState<SchemaReportTemplate[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [reports, setReports] = useState<SchemaReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [regenerateVisible, setRegenerateVisible] = useState(false);
  const [regenerateTarget, setRegenerateTarget] = useState<SchemaReport | null>(null);

  useEffect(() => {
    if (open && tableInfo.table_id) {
      schemaReportTemplatesApi.list(tableInfo.table_id).then(res => {
        setTemplates(res.data.data || []);
      }).catch(() => {
        setTemplates([]);
      });

      fetchReports();
    }
  }, [open, tableInfo.table_id]);

  const fetchReports = useCallback(() => {
    setLoading(true);
    schemaReportsApi.list(tableInfo.table_id).then(res => {
      const rows = res.data.data || [];
      setReports(rows.map((r: { _key: string; report_name: string; created_at: string; report_url: string; status?: string; error_message?: string }) => ({
        report_id: r._key,
        report_name: r.report_name,
        created_at: new Date(r.created_at).toLocaleString('zh-TW'),
        report_link: r.report_url,
        status: r.status || 'completed',
        error_message: r.error_message,
      })));
    }).catch(() => {
      setReports([]);
    }).finally(() => {
      setLoading(false);
    });
  }, [tableInfo.table_id]);

  useEffect(() => {
    if (!open) return;
    const interval = setInterval(fetchReports, 5000);
    return () => clearInterval(interval);
  }, [open, fetchReports]);

  const handleApplyTemplate = useCallback((tpl: SchemaReportTemplate) => {
    setShowForm(true);
    form.setFieldsValue({
      goal: tpl.goal,
      description: tpl.description,
      chartType: tpl.chart_type || undefined,
      notes: tpl.notes,
    });
    message.success(`已套用樣板「${tpl.name}」`);
  }, [form, message]);

  const handleDeleteTemplate = useCallback((tplKey: string) => {
    schemaReportTemplatesApi.delete(tplKey).then(() => {
      setTemplates(prev => prev.filter(t => t._key !== tplKey));
      message.success('樣板已刪除');
    }).catch(() => {
      message.error('刪除失敗');
    });
  }, [message]);

  const handleSaveAsTemplate = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const name = `樣板${templates.length + 1}`;
      schemaReportTemplatesApi.create({
        table_id: tableInfo.table_id,
        name,
        goal: values.goal,
        description: values.description,
        chart_type: values.chartType || '',
        notes: values.notes || '',
      }).then(res => {
        const created = res.data.data;
        if (created) {
          setTemplates(prev => [created, ...prev]);
          message.success(`已保存為「${name}」`);
        }
      }).catch(() => {
        message.error('保存失敗');
      });
    } catch {
      message.error('請填寫必填欄位');
    }
  }, [form, templates, tableInfo.table_id, message]);

  const handleGenerate = useCallback(async () => {
    let values: ReportFormValues;
    try {
      values = await form.validateFields();
    } catch {
      message.error('請填寫必填欄位');
      return;
    }

    setSubmitting(true);
    try {
      const tableDataRes = await dataAgentApi.ragicProxyData(tableInfo.table_id, 0, 100);
      const rawRows = tableDataRes.data.rows || [];
      const fieldMap: Record<string, string> = {};
      for (const f of tableDataRes.data.fields || []) {
        if (f.field_id && f.field_name) {
          fieldMap[f.field_id] = f.field_name;
        }
      }
      const dataset = rawRows.map(row => {
        const mapped: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(row)) {
          mapped[fieldMap[k] ?? k] = v;
        }
        return mapped;
      });
      if (dataset.length === 0) {
        message.error('無法取得資料錶的資料');
        setSubmitting(false);
        return;
      }

      const username = 'user_' + (localStorage.getItem('user_key') || 'anonymous');
      const scheduleTime = values.scheduleTime || undefined;
      const resp = await toolsApi.executeAsync('tool_reports', {
        dataset,
        report_goal: values.goal,
        preferred_chart: values.chartType,
        title: values.goal.slice(0, 30),
        author: 'system',
        username,
        table_id: tableInfo.table_id,
        legend_show: values.legendShow ?? true,
        legend_position: values.legendPosition || 'bottom',
        field_hints: values.fieldHints || undefined,
        special_notes: values.specialNotes || undefined,
        schedule_type: values.scheduleType || undefined,
        schedule_time: scheduleTime,
        schedule_days: values.scheduleDays || undefined,
      });

      if (resp.data.success) {
        const reportName = values.goal.slice(0, 20);
        setReports(prev => [
          {
            report_id: (resp.data as any).report_key,
            report_name: reportName,
            created_at: new Date().toLocaleString('zh-TW'),
            report_link: '',
            status: 'generating',
          },
          ...prev,
        ]);
        message.success('報告已提交生成');
        setShowForm(false);
        form.resetFields();
      } else {
        message.error(resp.data.error || '提交失敗');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      message.error(`提交失敗：${msg}`);
    } finally {
      setSubmitting(false);
    }
  }, [form, tableInfo, message]);

  const handleDeleteReport = useCallback((reportId: string) => {
    schemaReportsApi.delete(reportId).then(() => {
      setReports(prev => prev.filter(r => r.report_id !== reportId));
      message.success('報告已刪除');
    }).catch(() => {
      message.error('刪除失敗');
    });
  }, [message]);

  const handleRegenerate = useCallback((record: SchemaReport) => {
    setRegenerateTarget(record);
    regenerateForm.setFieldsValue({
      report_goal: record.report_name,
      field_hints: '',
      special_notes: '',
      preferred_chart: undefined,
    });
    setRegenerateVisible(true);
  }, [regenerateForm]);

  const handleRegenerateConfirm = useCallback(async () => {
    const values = await regenerateForm.validateFields().catch(() => null);
    if (!values || !regenerateTarget) return;

    setRegenerateVisible(false);
    const record = regenerateTarget;
    setRegenerateTarget(null);

    try {
      await schemaReportsApi.delete(record.report_id);
      setReports(prev => prev.filter(r => r.report_id !== record.report_id));
    } catch { /* proceed even if delete fails */ }

    setSubmitting(true);
    try {
      const tableDataRes = await dataAgentApi.ragicProxyData(tableInfo.table_id, 0, 100);
      const rawRows = tableDataRes.data.rows || [];
      const fieldMap: Record<string, string> = {};
      for (const f of tableDataRes.data.fields || []) {
        if (f.field_id && f.field_name) fieldMap[f.field_id] = f.field_name;
      }
      const dataset = rawRows.map(row => {
        const mapped: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(row)) mapped[fieldMap[k] ?? k] = v;
        return mapped;
      });
      if (dataset.length === 0) {
        message.error('無法取得資料表資料');
        return;
      }

      const goal = values.report_goal || record.report_name;
      const username = 'user_' + (localStorage.getItem('user_key') || 'anonymous');
      const resp = await toolsApi.executeAsync('tool_reports', {
        dataset,
        report_goal: goal,
        preferred_chart: values.preferred_chart || undefined,
        title: goal.slice(0, 30),
        author: 'system',
        username,
        table_id: tableInfo.table_id,
        field_hints: values.field_hints || undefined,
        special_notes: values.special_notes || undefined,
      });
      if (resp.data.success) {
        setReports(prev => [{
          report_id: (resp.data as any).report_key,
          report_name: goal.slice(0, 20),
          created_at: new Date().toLocaleString('zh-TW'),
          report_link: '',
          status: 'generating',
        }, ...prev]);
        message.success('已重新提交生成');
      } else {
        message.error(resp.data.error || '重新生成失敗');
      }
    } catch {
      message.error('重新生成失敗');
    } finally {
      setSubmitting(false);
    }
  }, [regenerateTarget, regenerateForm, tableInfo, message]);

  const reportColumns = [
    {
      title: '報告名稱',
      dataIndex: 'report_name',
      key: 'report_name',
      render: (name: string, record: SchemaReport) => record.report_link ? (
        <a href={record.report_link} target="_blank" rel="noopener noreferrer">{name}</a>
      ) : name,
    },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          generating: { color: 'orange', text: '生成中' },
          completed: { color: 'green', text: '完成' },
          error: { color: 'red', text: '異常' },
        };
        const cfg = statusMap[status] || statusMap.completed;
        return <Badge color={cfg.color} text={cfg.text} />;
      },
    },
    { title: '產生日期', dataIndex: 'created_at', key: 'created_at', width: 160 },
    {
      title: '重新生成',
      key: 'regenerate',
      width: 80,
      render: (_: unknown, record: SchemaReport) => (
        <Button
          type="link"
          size="small"
          onClick={() => handleRegenerate(record)}
        >
          重新生成
        </Button>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: SchemaReport) => (
        <Button
          type="text"
          danger
          size="small"
          onClick={() => handleDeleteReport(record.report_id)}
        >
          刪除
        </Button>
      ),
    },
  ];

  return (
    <Modal
      title={<><FileTextOutlined /> 智慧報表</>}
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
      style={{ minWidth: 600, maxWidth: 800 }}
      destroyOnHidden
    >
      {/* 報告列表 */}
      <div style={{ marginBottom: 24 }}>
        <Table
          dataSource={reports}
          rowKey="report_id"
          columns={reportColumns}
          loading={loading}
          size="small"
          pagination={false}
          locale={{ emptyText: '尚無報告' }}
        />
      </div>

      {/* 樣板標籤 */}
      {templates.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Space size={4} wrap>
            {templates.map(tpl => (
              <Tag
                key={tpl._key}
                closable
                onClose={() => handleDeleteTemplate(tpl._key)}
                onClick={() => handleApplyTemplate(tpl)}
                style={{ cursor: 'pointer', marginBottom: 4 }}
              >
                {tpl.name}
              </Tag>
            ))}
          </Space>
        </div>
      )}

      {/* 產生新報告 */}
      {!showForm ? (
        <Button
          type="default"
          icon={<PlusOutlined />}
          onClick={() => setShowForm(true)}
          style={{ width: '100%' }}
        >
          產生新報告
        </Button>
      ) : (
        <div style={{
          border: `1px solid ${antToken.colorBorder}`,
          borderRadius: antToken.borderRadiusLG,
          padding: 16,
        }}>
          <Form
            form={form}
            layout="vertical"
            size="small"
          >
            <Form.Item
              name="goal"
              label="報表目標"
              rules={[{ required: true, message: '請輸入報表目標' }]}
            >
              <Input placeholder="例：分析本月銷售額與客戶分布" />
            </Form.Item>

            <Form.Item
              name="description"
              label="需求說明"
              rules={[{ required: true, message: '請輸入需求說明' }]}
            >
              <TextArea
                rows={3}
                placeholder="例：依產品類別統計銷售額，並顯示前五大客戶貢獻度"
              />
            </Form.Item>

            <Form.Item
              name="chartType"
              label="報表類型"
            >
              <Select
                allowClear
                placeholder="選擇圖表類型（選填）"
                options={CHART_TYPES}
              />
            </Form.Item>

            <Form.Item label="圖例設定" style={{ marginBottom: 8 }}>
              <Space>
                <Form.Item name="legendShow" noStyle valuePropName="checked" initialValue={true}>
                  <Switch checkedChildren="顯示" unCheckedChildren="隱藏" />
                </Form.Item>
                <Form.Item name="legendPosition" noStyle initialValue="bottom">
                  <Select
                    style={{ width: 80 }}
                    options={[
                      { value: 'top', label: '上' },
                      { value: 'bottom', label: '下' },
                      { value: 'left', label: '左' },
                      { value: 'right', label: '右' },
                    ]}
                  />
                </Form.Item>
              </Space>
            </Form.Item>

            <Form.Item name="fieldHints" label="指定欄位">
              <TextArea rows={2} placeholder="例：關注「銷售金額」和「利潤率」兩欄；不需理會「備註」欄（選填）" />
            </Form.Item>

            <Form.Item name="specialNotes" label="特別提示">
              <TextArea rows={2} placeholder="例：數值超過1000的以紅色標註；前五名特別放大（選填）" />
            </Form.Item>

            <Form.Item label="排程設定" style={{ marginBottom: 8 }}>
              <Space>
                <Form.Item name="scheduleType" noStyle>
                  <Select
                    allowClear
                    placeholder="不排程"
                    style={{ width: 100 }}
                    options={[
                      { value: 'daily', label: '每天' },
                      { value: 'weekly', label: '每週' },
                    ]}
                  />
                </Form.Item>
                <Form.Item name="scheduleTime" noStyle>
                  <TimePicker format="HH:mm" placeholder="時間" style={{ width: 100 }} />
                </Form.Item>
              </Space>
            </Form.Item>

            <Form.Item noStyle shouldUpdate={(prev, cur) => prev.scheduleType !== cur.scheduleType}>
              {({ getFieldValue }) => getFieldValue('scheduleType') === 'weekly' && (
                <Form.Item name="scheduleDays" label="星期" style={{ marginBottom: 16 }}>
                  <Checkbox.Group options={WEEK_OPTIONS} />
                </Form.Item>
              )}
            </Form.Item>

            <Form.Item name="notes" label="備註">
              <TextArea rows={2} placeholder="額外需求或備註（選填）" />
            </Form.Item>

            <Form.Item noStyle>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Button onClick={handleSaveAsTemplate}>保存為樣板</Button>
                <Space>
                  <Button onClick={() => { setShowForm(false); form.resetFields(); }}>取消</Button>
                  <Button type="primary" loading={submitting} onClick={handleGenerate}>
                    產生
                  </Button>
                </Space>
              </Space>
            </Form.Item>
          </Form>
        </div>
      )}

      <Modal
        title="修改提示意見"
        open={regenerateVisible}
        onCancel={() => { setRegenerateVisible(false); setRegenerateTarget(null); }}
        onOk={handleRegenerateConfirm}
        confirmLoading={submitting}
        okText="重新生成"
      >
        <Form form={regenerateForm} layout="vertical" size="small">
          <Form.Item name="report_goal" label="報表目標" rules={[{ required: true }]}>
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="preferred_chart" label="圖表類型">
            <Select allowClear placeholder="沿用原設定" options={CHART_TYPES} />
          </Form.Item>
          <Form.Item name="field_hints" label="指定欄位">
            <TextArea rows={2} placeholder="例：關注「銷售金額」和「利潤率」" />
          </Form.Item>
          <Form.Item name="special_notes" label="特別提示">
            <TextArea rows={2} placeholder="例：超過1000以紅色標註" />
          </Form.Item>
        </Form>
      </Modal>
    </Modal>
  );
}
