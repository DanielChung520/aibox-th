/**
 * @file        智慧報表 Modal
 * @description Schema 頁面的智慧報表功能 — 報告列表、樣板管理、產生新報告
 * @lastUpdate  2026-04-30 01:35:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import { Modal, Table, Form, Input, Select, Button, Space, Tag, App, theme } from 'antd';
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
  notes?: string;
}

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
  const [templates, setTemplates] = useState<SchemaReportTemplate[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [reports, setReports] = useState<SchemaReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && tableInfo.table_id) {
      schemaReportTemplatesApi.list(tableInfo.table_id).then(res => {
        setTemplates(res.data.data || []);
      }).catch(() => {
        setTemplates([]);
      });

      setLoading(true);
      schemaReportsApi.list(tableInfo.table_id).then(res => {
        const rows = res.data.data || [];
        setReports(rows.map((r: { _key: string; report_name: string; created_at: string; report_url: string }) => ({
          report_id: r._key,
          report_name: r.report_name,
          created_at: new Date(r.created_at).toLocaleString('zh-TW'),
          report_link: r.report_url,
        })));
      }).catch(() => {
        setReports([]);
      }).finally(() => {
        setLoading(false);
      });
    }
  }, [open, tableInfo.table_id]);

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
        return;
      }
      const resp = await toolsApi.execute('tool_reports', {
        dataset,
        report_goal: values.goal,
        preferred_chart: values.chartType,
        title: values.goal.slice(0, 30),
        author: 'system',
        username: 'user_' + (localStorage.getItem('user_key') || 'anonymous'),
      });
      if (resp.data.success && resp.data.result?.report_url) {
        const reportUrl = resp.data.result.report_url;
        const reportName = values.goal.slice(0, 20);
        const chartType = values.chartType || '';
        try {
          const saved = await schemaReportsApi.create({
            table_id: tableInfo.table_id,
            report_name: reportName,
            report_url: reportUrl,
            chart_type: chartType,
            username: 'user_' + (localStorage.getItem('user_key') || 'anonymous'),
            created_at: new Date().toISOString(),
          });
          const created = saved.data.data;
          setReports(prev => [
            {
              report_id: created._key,
              report_name: created.report_name,
              created_at: new Date(created.created_at).toLocaleString('zh-TW'),
              report_link: created.report_url,
            },
            ...prev,
          ]);
        } catch {
          setReports(prev => [
            {
              report_id: `rpt_${tableInfo.table_id}_${Date.now()}`,
              report_name: reportName,
              created_at: new Date().toLocaleString('zh-TW'),
              report_link: reportUrl,
            },
            ...prev,
          ]);
        }
        message.success('報告產生成功');
        setShowForm(false);
        form.resetFields();
      } else {
        message.error(resp.data.error || '報告產生失敗');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      message.error(`報告產生失敗：${msg}`);
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

  const reportColumns = [
    { title: '報告名稱', dataIndex: 'report_name', key: 'report_name' },
    { title: '產生日期', dataIndex: 'created_at', key: 'created_at', width: 160 },
    {
      title: '報告連結',
      dataIndex: 'report_link',
      key: 'report_link',
      width: 80,
      render: (link: string) => (
        <a href={link} target="_blank" rel="noopener noreferrer">開啟</a>
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
    </Modal>
  );
}
