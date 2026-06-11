/**
 * @file        智慧報表 Modal
 * @description Schema 頁面的智慧報表功能 — 報告列表、樣板管理、產生新報告（支援非同步）
 * @lastUpdate  2026-05-01 03:00:00
 * @author      Daniel Chung / Sisyphus
 * @version     1.1.0
 */

import { useState, useEffect, useCallback } from 'react';
import { Modal, Table, Form, Input, InputNumber, Select, Button, Space, Tag, Badge, Switch, DatePicker, App, theme, Typography, Alert, Tooltip } from 'antd';
import { WarningOutlined, FileTextOutlined, PlusOutlined, MessageOutlined } from '@ant-design/icons';
import type { TableInfo } from '../../services/dataAgentApi';
import { dataAgentApi } from '../../services/dataAgentApi';
import api, { toolsApi, schemaReportsApi, schemaReportTemplatesApi, type SchemaReportTemplate } from '../../services/api';

const { TextArea } = Input;
const { Text } = Typography;

export interface SchemaReport {
  report_id: string;
  report_name: string;
  created_at: string;
  report_link: string;
  status?: string;
  error_message?: string;
  quality_warnings?: string[];
  quality_score?: number;
  notes?: string;
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
  selectedFields?: string[];
  specialNotes?: string;
  timeRangeType?: string;
  timeRangeValue?: number;
  dateStart?: string;
  dateEnd?: string;
  reportOrientation?: 'portrait' | 'landscape';
  reportDepth?: 'summary' | 'detailed';
  topN?: number;
  scheduleType?: string;
  scheduleTime?: string;
  scheduleDays?: number[];
  fontFamily?: string;
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
  const [regenerateForm] = Form.useForm();
  const [templates, setTemplates] = useState<SchemaReportTemplate[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [reports, setReports] = useState<SchemaReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [fieldOptions, setFieldOptions] = useState<{ label: string; value: string }[]>([]);
  const [regenerateVisible, setRegenerateVisible] = useState(false);
  const [regenerateTarget, setRegenerateTarget] = useState<SchemaReport | null>(null);

  const [precheckVisible, setPrecheckVisible] = useState(false);
  const [precheckWarnings, setPrecheckWarnings] = useState<string[]>([]);
  const [precheckPendingValues, setPrecheckPendingValues] = useState<ReportFormValues | null>(null);

  const [feedbackVisible, setFeedbackVisible] = useState(false);
  const [feedbackTarget, setFeedbackTarget] = useState<SchemaReport | null>(null);
  const [feedbackText, setFeedbackText] = useState('');

  useEffect(() => {
    if (open && tableInfo.table_id) {
      schemaReportTemplatesApi.list(tableInfo.table_id).then(res => {
        setTemplates(res.data.data || []);
      }).catch(() => {
        setTemplates([]);
      });

      // 載入欄位選項
      dataAgentApi.listFields(tableInfo.table_id).then(res => {
        const fields: Array<{ field_id: string; field_name: string; field_type: string }> = res.data.data || [];
        setFieldOptions(
          fields
            .filter(f => !f.field_id?.startsWith('_subtable_'))
            .filter(f => !['日期 (yyyyMMdd)'].includes(f.field_type))
            .map(f => ({ label: `${f.field_name} (${f.field_id})`, value: f.field_id }))
        );
      }).catch(() => setFieldOptions([]));

      fetchReports();
    }
  }, [open, tableInfo.table_id]);

  const fetchReports = useCallback(() => {
    setLoading(true);
    schemaReportsApi.list(tableInfo.table_id).then(res => {
      const rows = res.data.data || [];
      setReports(rows.map((r: any) => ({
        report_id: r._key,
        report_name: r.report_name,
        created_at: new Date(r.created_at).toLocaleString('zh-TW'),
        report_link: r.report_url,
        status: r.status || 'completed',
        error_message: r.error_message,
        quality_warnings: r.quality_warnings || [],
        quality_score: r.quality_score,
        notes: r.notes || '',
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

  const handleApplyTemplate = useCallback((tpl: SchemaReportTemplate & { legend_show?: boolean; legend_position?: string }) => {
    setShowForm(true);
    form.setFieldsValue({
      goal: tpl.goal,
      description: tpl.description,
      chartType: tpl.chart_type || undefined,
      legendShow: tpl.legend_show ?? true,
      legendPosition: tpl.legend_position || 'bottom',
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
        legend_show: values.legendShow ?? true,
        legend_position: values.legendPosition || 'bottom',
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

  /** 預先檢查：根據欄位結構 + 使用者目標，判斷可行性並產出警告 */
  const preCheckReport = useCallback(async (values: ReportFormValues): Promise<string[]> => {
    const warnings: string[] = [];
    try {
      const fieldRes = await dataAgentApi.listFields(tableInfo.table_id);
      const fields: Array<{ field_name: string; field_type: string }> = (fieldRes.data.data || []);
      const fieldNames = fields.map(f => f.field_name);
      const fieldTypes = fields.map(f => f.field_type);

      const goal = values.goal;

      // 檢查日期欄位（趨勢分析需要）
      const hasDateField = fieldTypes.some(t => t.includes('日期') || t === 'date');
      const wantsTrend = /趨勢|走勢|時間|trend|變化/i.test(goal);
      if (wantsTrend && !hasDateField) {
        warnings.push('報表目標提及「趨勢」但此表無日期類型欄位，無法產生時間趨勢圖');
      }

      // 檢查廠商欄位（廠商分析需要）
      const hasVendorField = fieldNames.some(n => /廠商|供應商|vendor|supplier/i.test(n));
      const wantsVendor = /廠商|供應商|vendor|supplier/i.test(goal);
      if (wantsVendor && !hasVendorField) {
        warnings.push('報表目標提及「廠商/供應商」但此表無廠商相關欄位');
      }

      // 檢查圖表類型與目標一致
      if (wantsTrend && values.chartType && values.chartType !== 'line') {
        warnings.push(`報表目標含「趨勢」但選擇圖表類型為「${values.chartType}」，建議改用「line」折線圖`);
      }

      // 檢查數值欄位（做統計需要）
      const hasNumericField = fieldTypes.some(t => /數字|貨幣|百分比|number/i.test(t));
      if (!hasNumericField) {
        warnings.push('此表無數值類型欄位，無法進行統計彙總，報表可能只有計數結果');
      }

      // 檢查目標是否過短
      if (goal.length < 5) {
        warnings.push('報表目標過短（少於 5 字），建議提供更具體的描述以獲得更好的分析結果');
      }

      // 檢查是否無任何篩選條件（全表分析）
      const hasTimeFilter = /本月|上月|本季|今年|年度|202[0-9]|最近|近[0-9]|期間|區間|從.*到|between|since|last\s|this\s/i.test(goal);
      const hasEntityFilter = /廠商|供應商|產品|品項|類別|部門|區域|縣市|業務/i.test(goal);
      const hasSpecificFilter = /排行|前[0-9]|top|超過|大於|小於|僅|只|篩選|過濾/i.test(goal);
      const hasCondition = hasTimeFilter || hasEntityFilter || hasSpecificFilter;

      if (!hasCondition && goal.length >= 5) {
        warnings.push(
          '報表目標未指定任何篩選條件（如時間區間、特定廠商、排行等），系統將分析全部資料（約 2 萬筆）。'
          + '建議補充具體條件以獲得更有針對性的分析，或確認後繼續提交。'
        );
      }
    } catch {
      warnings.push('無法取得欄位資訊進行預檢，將直接提交');
    }
    return warnings;
  }, [tableInfo.table_id]);

  const handleGenerate = useCallback(async () => {
    let values: ReportFormValues;
    try {
      values = await form.validateFields();
    } catch {
      message.error('請填寫必填欄位');
      return;
    }

    // 先進行預檢
    const warnings = await preCheckReport(values);
    if (warnings.length > 0) {
      setPrecheckWarnings(warnings);
      setPrecheckPendingValues(values);
      setPrecheckVisible(true);
      return; // 等待使用者確認後才真正提交
    }

    // 預檢通過，直接提交
    await doSubmitGenerate(values);
  }, [form, tableInfo, message, preCheckReport]);

  /** 實際提交生成（被 handleGenerate 和預檢確認後共用） */
  const doSubmitGenerate = useCallback(async (values: ReportFormValues) => {
    setSubmitting(true);
    try {
      const fieldRes = await dataAgentApi.listFields(tableInfo.table_id);
      const fields: Array<{ field_id: string; field_name: string; field_type: string }> = fieldRes.data.data || [];
      const cleanFields = fields
        .filter((f: any) => !f.field_id?.startsWith('_subtable_'))
        .map((f: any) => ({ field_id: f.field_id, field_name: f.field_name, field_type: f.field_type }));

      const username = 'user_' + (localStorage.getItem('user_key') || 'anonymous');
      const scheduleTime = values.scheduleTime || undefined;
      const resp = await toolsApi.executeAsync('tool_reports', {
        table_id: tableInfo.table_id,
        fields_schema: cleanFields,
        report_goal: values.goal,
        preferred_chart: values.chartType,
        title: values.goal.slice(0, 30),
        author: 'system',
        username,
        legend_show: values.legendShow ?? true,
        legend_position: values.legendPosition || 'bottom',
        field_hints: (values.selectedFields?.length ? `請優先分析以下欄位：${values.selectedFields.join(',')}` : values.fieldHints) || undefined,
        special_notes: values.specialNotes || undefined,
        schedule_type: values.scheduleType || undefined,
        schedule_time: scheduleTime,
        schedule_days: values.scheduleDays || undefined,
        font_family: values.fontFamily || undefined,
        report_orientation: values.reportOrientation || 'portrait',
        report_depth: values.reportDepth || 'detailed',
        top_n: values.topN || 20,
        time_range_type: values.timeRangeType || undefined,
        time_range_value: values.timeRangeValue || undefined,
        date_start: values.dateStart || undefined,
        date_end: values.dateEnd || undefined,
      });

      if (resp.data.success) {
        const reportName = values.goal.slice(0, 20);
        setReports(prev => [{
          report_id: (resp.data as any).report_key,
          report_name: reportName,
          created_at: new Date().toLocaleString('zh-TW'),
          report_link: '',
          status: 'generating',
        }, ...prev]);
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

  const handleFeedback = useCallback((record: SchemaReport) => {
    setFeedbackTarget(record);
    setFeedbackText('');
    setFeedbackVisible(true);
  }, []);

  const handleFeedbackSubmit = useCallback(async () => {
    if (!feedbackTarget || !feedbackText.trim()) {
      message.warning('請輸入改善意見');
      return;
    }
    setFeedbackVisible(false);
    setSubmitting(true);

    const record = feedbackTarget;
    setFeedbackTarget(null);

    try {
      await schemaReportsApi.delete(record.report_id);
    } catch { void 0; }

    try {
      const fieldRes = await dataAgentApi.listFields(tableInfo.table_id);
      const fields = (fieldRes.data.data || [])
        .filter((f: any) => !f.field_id?.startsWith('_subtable_'))
        .map((f: any) => ({ field_id: f.field_id, field_name: f.field_name, field_type: f.field_type }));

      // 清除名稱中可能殘留的「注意：…」後綴
      const cleanGoal = record.report_name.replace(/[。，]注意：.*$/, '');
      const username = 'user_' + (localStorage.getItem('user_key') || 'anonymous');

      const resp = await toolsApi.executeAsync('tool_reports', {
        table_id: tableInfo.table_id,
        fields_schema: fields,
        report_name: cleanGoal,
        report_goal: cleanGoal,
        title: cleanGoal.slice(0, 30),
        author: 'system',
        username,
        legend_show: true,
        legend_position: 'bottom',
        field_hints: feedbackText,
        special_notes: feedbackText,
        notes: feedbackText,                  // 回饋內容寫入備註
      });
      if (resp.data.success) {
        setReports(prev => [{
          report_id: (resp.data as any).report_key,
          report_name: cleanGoal,
          created_at: new Date().toLocaleString('zh-TW'),
          report_link: '',
          status: 'generating',
        }, ...prev]);
        message.success('已收到回饋，新報告已提交生成');
      } else {
        message.error(resp.data.error || '提交失敗');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      message.error(`提交失敗：${msg}`);
    } finally {
      setSubmitting(false);
    }
  }, [feedbackTarget, feedbackText, tableInfo, message]);

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
      const fieldRes = await dataAgentApi.listFields(tableInfo.table_id);
      const fields = (fieldRes.data.data || [])
        .filter((f: any) => !f.field_id?.startsWith('_subtable_'))
        .map((f: any) => ({ field_id: f.field_id, field_name: f.field_name, field_type: f.field_type }));

      const goal = values.report_goal || record.report_name;
      const username = 'user_' + (localStorage.getItem('user_key') || 'anonymous');
      const resp = await toolsApi.executeAsync('tool_reports', {
        table_id: tableInfo.table_id,
        fields_schema: fields,
        report_goal: goal,
        preferred_chart: values.preferred_chart || undefined,
        title: goal.slice(0, 30),
        author: 'system',
        username,
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
      ellipsis: true,
      render: (name: string, record: SchemaReport) => {
        const openReport = async () => {
          if (!record.report_id) return;
          try {
            const resp = await api.get(`/api/v1/da/schema-reports/${record.report_id}/download`, { responseType: 'blob' });
            const url = URL.createObjectURL(new Blob([resp.data], { type: 'text/html;charset=utf-8' }));
            window.open(url, '_blank');
          } catch {
            message.error('無法開啟報告');
          }
        };
        return record.report_id ? (
          <a onClick={openReport} style={{ cursor: 'pointer' }}>{name}</a>
        ) : <Text style={{ color: '#999' }}>{name}</Text>;
      },
    },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 70,
      render: (status: string) => {
        const m: Record<string, { color: string; text: string }> = {
          generating: { color: 'orange', text: '生成中' },
          completed: { color: 'green', text: '完成' },
          completed_with_warnings: { color: 'gold', text: '有警告' },
          error: { color: 'red', text: '異常' },
        };
        const c = m[status] || m.completed;
        return <Badge color={c.color} text={c.text} />;
      },
    },
    {
      title: '備註',
      key: 'notes',
      width: 140,
      ellipsis: true,
      render: (_: unknown, record: SchemaReport) => {
        const warns = record.quality_warnings ?? [];
        const hasWarnings = warns.length > 0 && record.status !== 'generating';
        return (
          <Space size={4}>
            {hasWarnings && (
              <Tag color="gold" style={{ fontSize: 10, lineHeight: '16px', marginRight: 0 }}>{warns.length}項</Tag>
            )}
            {record.notes ? (
              <Tooltip title={record.notes}>
                <Text style={{ fontSize: 11, color: '#999' }} ellipsis>{record.notes.slice(0, 10)}{record.notes.length > 10 ? '…' : ''}</Text>
              </Tooltip>
            ) : null}
            {!hasWarnings && !record.notes && <Text style={{ fontSize: 11, color: '#ddd' }}>--</Text>}
          </Space>
        );
      },
    },
    { title: '產生日期', dataIndex: 'created_at', key: 'created_at', width: 130 },
    {
      title: '品質',
      key: 'quality',
      width: 55,
      render: (_: unknown, record: SchemaReport) => {
        if (record.status === 'generating') return <Text style={{ fontSize: 11 }}>-</Text>;
        if (record.status === 'error') return <Text type="danger" style={{ fontSize: 11 }}>異常</Text>;
        if (record.quality_score == null) return <Text style={{ fontSize: 11, color: '#999' }}>--</Text>;
        const warnings = record.quality_warnings?.length ?? 0;
        return (
          <Tag color={warnings > 0 ? 'gold' : 'green'} style={{ fontSize: 10 }}>
            {record.quality_score}分
          </Tag>
        );
      },
    },
    {
      title: '重新生成',
      key: 'regenerate',
      width: 70,
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
      width: 130,
      render: (_: unknown, record: SchemaReport) => (
        <Space size="small">
          {record.status === 'completed' || record.status === 'completed_with_warnings' ? (
            <Button
              type="link"
              size="small"
              icon={<MessageOutlined />}
              onClick={() => handleFeedback(record)}
            >
              反饋
            </Button>
          ) : null}
          <Button
            type="text"
            danger
            size="small"
            onClick={() => handleDeleteReport(record.report_id)}
          >
            刪除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Modal
      title={<><FileTextOutlined /> 智慧報表</>}
      open={open}
      onCancel={onClose}
      footer={null}
      width={960}
      style={{ minWidth: 600, maxWidth: 960 }}
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
          expandable={{
            expandedRowRender: (record: SchemaReport) => {
              const hasQualityWarnings = (record.quality_warnings?.length ?? 0) > 0;
              const hasError = record.status === 'error' && record.error_message;
              if (!hasQualityWarnings && !hasError) return <Text type="secondary" style={{ fontSize: 12 }}>無詳細資訊</Text>;
              return (
                <div style={{ padding: '8px 0' }}>
                  {hasError && (
                    <div style={{ marginBottom: 8, padding: '8px 12px', background: '#fff2f0', borderRadius: 6, border: '1px solid #ffccc7' }}>
                      <Text type="danger" style={{ fontSize: 12 }}>{record.error_message}</Text>
                    </div>
                  )}
                  {record.quality_warnings?.map((w, i) => (
                    <div key={i} style={{ marginBottom: 4, display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                      <WarningOutlined style={{ color: '#faad14', marginTop: 2, fontSize: 12 }} />
                      <Text style={{ fontSize: 12, color: '#666' }}>{w}</Text>
                    </div>
                  ))}
                  {record.quality_score != null && record.quality_score < 100 && (
                    <div style={{ marginTop: 6 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>品質評分：{record.quality_score}/100</Text>
                    </div>
                  )}
                </div>
              );
            },
            rowExpandable: (record: SchemaReport) => (
              (record.quality_warnings?.length ?? 0) > 0 || (record.status === 'error' && !!record.error_message)
            ),
          }}
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

            <Form.Item name="selectedFields" label="指定欄位">
              <Select
                mode="multiple"
                allowClear
                placeholder="選取要分析的欄位（不選則自動判斷）"
                style={{ width: '100%' }}
                options={fieldOptions}
                maxTagCount={5}
              />
            </Form.Item>

            <Form.Item label="時間範圍">
              <Space>
                <Form.Item name="timeRangeType" noStyle>
                  <Select allowClear placeholder="不限制" style={{ width: 100 }}
                    options={[
                      { value: 'last', label: '最近' },
                      { value: 'range', label: '自訂區間' },
                    ]}
                  />
                </Form.Item>
                <Form.Item noStyle shouldUpdate={(prev, cur) => prev.timeRangeType !== cur.timeRangeType}>
                  {({ getFieldValue }) => {
                    const t = getFieldValue('timeRangeType');
                    if (t === 'last') return (
                      <Space>
                        <Form.Item name="timeRangeValue" noStyle>
                          <InputNumber min={1} max={99} style={{ width: 60 }} placeholder="N" />
                        </Form.Item>
                        <Form.Item name="timeRangeUnit" noStyle initialValue="year">
                          <Select style={{ width: 80 }}
                            options={[
                              { value: 'year', label: '年' },
                              { value: 'quarter', label: '季' },
                              { value: 'month', label: '月' },
                              { value: 'week', label: '周' },
                            ]}
                          />
                        </Form.Item>
                      </Space>
                    );
                    if (t === 'range') return (
                      <Space>
                        <Form.Item name="dateStart" noStyle><DatePicker placeholder="開始日期" /></Form.Item>
                        <span>~</span>
                        <Form.Item name="dateEnd" noStyle><DatePicker placeholder="結束日期" /></Form.Item>
                      </Space>
                    );
                    return null;
                  }}
                </Form.Item>
              </Space>
            </Form.Item>

            <Form.Item label="顯示筆數" style={{ marginBottom: 8 }}>
              <Form.Item name="topN" noStyle initialValue={20}>
                <InputNumber min={5} max={100} style={{ width: 80 }} />
              </Form.Item>
              <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>圖表與表格顯示前 N 筆</Text>
            </Form.Item>

            <Form.Item label="報告設定" style={{ marginBottom: 8 }}>
              <Space size="middle">
                <Form.Item name="reportDepth" noStyle initialValue="detailed">
                  <Select style={{ width: 100 }}
                    options={[
                      { value: 'summary', label: '📋 摘要' },
                      { value: 'detailed', label: '📝 詳細' },
                    ]}
                  />
                </Form.Item>
                <Form.Item name="reportOrientation" noStyle initialValue="portrait">
                  <Select style={{ width: 100 }}
                    options={[
                      { value: 'portrait', label: '📄 直式' },
                      { value: 'landscape', label: '📑 橫式' },
                    ]}
                  />
                </Form.Item>
                <Form.Item name="fontFamily" noStyle>
                  <Select allowClear placeholder="字體" style={{ width: 120 }}
                    options={[
                      { value: '', label: '預設字型' },
                      { value: "'Noto Sans TC','Microsoft JhengHei',sans-serif", label: '正黑體' },
                      { value: "'Noto Serif TC','PMingLiU',serif", label: '明體' },
                      { value: "'DFKai-SB','BiauKai','KaiTi',serif", label: '標楷體' },
                    ]}
                  />
                </Form.Item>
              </Space>
            </Form.Item>

            <Form.Item name="specialNotes" label="特別提示（選填）">
              <TextArea rows={2} placeholder="例：數值超過1000的以紅色標註；前五名特別放大" />
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

      {/* 預先檢查確認 Modal */}
      <Modal
        title="提交前檢查結果"
        open={precheckVisible}
        onCancel={() => { setPrecheckVisible(false); setPrecheckPendingValues(null); }}
        onOk={() => {
          setPrecheckVisible(false);
          if (precheckPendingValues) {
            doSubmitGenerate(precheckPendingValues);
            setPrecheckPendingValues(null);
          }
        }}
        okText="忽略警告，繼續提交"
        cancelText="返回修改"
      >
        <div style={{ marginBottom: 12 }}>
          <Alert
            type="warning"
            showIcon
            message="發現以下可能問題，建議先調整後再提交："
          />
        </div>
        {precheckWarnings.map((w, i) => (
          <div key={i} style={{ marginBottom: 8, display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <WarningOutlined style={{ color: '#faad14', marginTop: 3, fontSize: 14 }} />
            <Text style={{ fontSize: 13 }}>{w}</Text>
          </div>
        ))}
      </Modal>

      {/* 使用者反饋 Modal */}
      <Modal
        title="反饋意見"
        open={feedbackVisible}
        onCancel={() => { setFeedbackVisible(false); setFeedbackTarget(null); setFeedbackText(''); }}
        onOk={handleFeedbackSubmit}
        confirmLoading={submitting}
        okText="提交並重新產生"
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">
            你認為這份報告有哪些地方需要改進？你的意見將作為提示詞的一部分傳給 AI，重新產生更符合需求的報表。
          </Text>
        </div>
        <TextArea
          rows={4}
          value={feedbackText}
          onChange={e => setFeedbackText(e.target.value)}
          placeholder="例：我希望看到各供應商的佔比圓餅圖、加入去年同期比較、分析文字更詳細…"
        />
      </Modal>
    </Modal>
  );
}
