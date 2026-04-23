/**
 * @file        Data Agent Query Playground
 * @description NL→Ragic 自然語言查詢工作台，支援意圖匹配與 Ragic API 查詢
 *              兼容舊版（NLQueryData）與新版（五區塊 NLQueryResponse）API 回應格式
 * @lastUpdate  2026-04-13 03:37:18
 * @author      Daniel Chung
 * @version     1.3.0
 */

import { useState, useCallback, useEffect } from 'react';
import { Card, Input, Button, Table, Tag, Space, Typography, Spin, Alert, Row, Col, Statistic, App, Tabs, Descriptions, Result, theme, Collapse } from 'antd';
import {
  PlayCircleOutlined, ClearOutlined, DatabaseOutlined, TableOutlined,
  ThunderboltOutlined, SearchOutlined, FileTextOutlined,
  ExclamationCircleOutlined, CloseCircleOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import { dataAgentApi, RagicNLQueryResponse } from '../../services/dataAgentApi';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { useEntityPerception } from '../../hooks/useEntityPerception';
import { pageContextManager } from '../../services/PageContextManager';
import { resolvePageContext } from '../../components/FloatingAssistant/types';

const { Title, Text } = Typography;
const { TextArea } = Input;

// ---------------------------------------------------------------------------
// 舊版 API 回應格式（向下兼容）
// ---------------------------------------------------------------------------
interface LegacyNLQueryData {
  query: string;
  intent_matched: { intent_id: string; score: number; action: string; table_key: string } | null;
  translated_params: { where: unknown[]; limit: number; offset: number; naming: string; order_field: string | null; order_direction: string } | null;
  records: { ragic_id: string; fields: Record<string, unknown> }[];
  record_count: number;
  pagination: { offset: number; limit: number; returned_count: number; has_more: boolean };
  execution_time_ms: number;
  field_labels: Record<string, string>;
}

interface LegacyResponse {
  code: number;
  data: LegacyNLQueryData;
  error: string | null;
  metadata: { connection: string; table_key: string; output_format: string } | null;
}

/**
 * 偵測 API 回應是舊版（{code, data, error, metadata}）還是新版（{code, status, ...}），
 * 統一轉換成 RagicNLQueryResponse 格式。
 */
function normalizeResponse(raw: unknown): RagicNLQueryResponse {
  const obj = raw as Record<string, unknown>;

  // 新版格式已有 status 欄位
  if (typeof obj.status === 'string' && ['success', 'clarification_needed', 'error'].includes(obj.status)) {
    return obj as unknown as RagicNLQueryResponse;
  }

  // 舊版格式：{ code, data: {...}, error, metadata }
  const legacy = obj as unknown as LegacyResponse;
  const d = legacy.data;
  if (!d) {
    return {
      code: legacy.code ?? -1,
      status: 'error',
      clarification: null,
      result: null,
      intent: null,
      post_error: { error_code: legacy.code ?? -1, raw_error: legacy.error || '', message: legacy.error || '未知錯誤' },
      metadata: null,
    };
  }

  const im = d.intent_matched;
  return {
    code: legacy.code,
    status: legacy.code === 0 ? 'success' : 'error',
    clarification: null,
    result: {
      records: d.records || [],
      record_count: d.record_count ?? 0,
      pagination: d.pagination ?? { offset: 0, limit: 1000, returned_count: 0, has_more: false },
      field_labels: d.field_labels ?? {},
      execution_time_ms: d.execution_time_ms ?? 0,
      stats: null,
    },
    intent: im ? {
      intent_id: im.intent_id,
      score: im.score,
      confidence: im.score >= 0.65 ? 'high' : im.score >= 0.45 ? 'medium' : 'low',
      action: im.action,
      table_key: im.table_key,
    } : null,
    post_error: legacy.error ? { error_code: legacy.code, raw_error: legacy.error, message: legacy.error } : null,
    metadata: legacy.metadata ? {
      connection: legacy.metadata.connection ?? '',
      table_key: legacy.metadata.table_key ?? '',
      output_format: legacy.metadata.output_format ?? 'json',
      query: d.query ?? '',
      translated_params: d.translated_params ? {
        where: ((d.translated_params.where ?? []) as unknown[]).map(w => {
          const wc = w as Record<string, string>;
          return { field_id: wc.field_id, operator: wc.operator as 'eq' | 'like' | 'gte' | 'lte' | 'gt' | 'lt' | 'regex', value: wc.value };
        }),
        limit: d.translated_params.limit ?? 1000,
        offset: d.translated_params.offset ?? 0,
        naming: d.translated_params.naming ?? 'EID',
        order_field: d.translated_params.order_field ?? undefined,
        order_direction: d.translated_params.order_direction,
      } : null,
    } : null,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function QueryPlayground() {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const contentTokens = useContentTokens();
  const { dispatch } = useEntityPerception({ defaultEntityType: 'query', defaultAction: 'list' });
  const pageInfo = resolvePageContext('/app/data-agent/playground');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RagicNLQueryResponse | null>(null);
  const [activeTab, setActiveTab] = useState('result');

  useEffect(() => {
    const sampleRecord = result?.result?.records?.[0];
    const sampleFields = sampleRecord
      ? Object.entries(sampleRecord.fields || {})
        .filter(([key]) => !key.startsWith('_'))
        .slice(0, 5)
        .reduce<Record<string, unknown>>((acc, [key, value]) => {
          acc[key] = value;
          return acc;
        }, {})
      : undefined;

    pageContextManager.report({
      page: '/app/data-agent/playground',
      pageName: pageInfo.name,
      component: result ? 'QueryResultPanel' : 'QueryEditor',
      componentName: result?.intent?.table_key || '自然語言查詢',
      entity: result?.intent?.intent_id || query || undefined,
      entityType: query.trim() ? 'query' : undefined,
      action: loading ? 'execute' : result ? 'view' : 'list',
      data: {
        current_query: query.trim() || undefined,
        status: result?.status,
        active_tab: activeTab,
        record_count: result?.result?.record_count,
        execution_time_ms: result?.result?.execution_time_ms,
        matched_intent: result?.intent
          ? {
              intent_id: result.intent.intent_id,
              score: result.intent.score,
              action: result.intent.action,
              table_key: result.intent.table_key,
            }
          : undefined,
        translated_filters: result?.metadata?.translated_params?.where?.slice(0, 5),
        sample_record: sampleFields,
      },
    });

    return () => {
      pageContextManager.report({
        page: '/app/data-agent/playground',
        pageName: pageInfo.name,
        component: undefined,
        componentName: undefined,
        entity: undefined,
        entityType: undefined,
        action: undefined,
        data: undefined,
      });
    };
  }, [query, loading, result, activeTab, pageInfo.name]);

  const quickTemplates = [
    '查詢所有採購訂單',
    '列出所有供應商',
    '查詢上個月的進貨單',
    '查詢庫存異動記錄',
    '查詢所有報價單',
    '查詢本月銷售訂單',
    '查詢所有生產製令單',
    '查詢近30天收貨單',
    '查詢所有員工清單',
    '查詢品項的基本資訊',
  ];

  const handleExecute = useCallback(async (overrideQuery?: string) => {
    const q = (overrideQuery ?? query).trim();
    if (!q) { message.warning('請輸入查詢內容'); return; }
    setLoading(true);
    setResult(null);
    try {
      const res = await dataAgentApi.ragicNLQuery({
        query: q,
        connection_name: '2025shianyong',
      });
      const normalized = normalizeResponse(res.data);
      setResult(normalized);
      if (normalized.status === 'success') {
        setActiveTab('result');
        dispatch('query', q, 'execute', {
          record_count: normalized.result?.record_count ?? 0,
          execution_time_ms: normalized.result?.execution_time_ms ?? 0,
          intent_id: normalized.intent?.intent_id,
        });
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : '查詢執行失敗';
      setResult({
        code: -1,
        status: 'error',
        clarification: null,
        result: null,
        intent: null,
        post_error: {
          error_code: -1,
          raw_error: err instanceof Error ? err.message : 'unknown',
          message: errMsg,
        },
        metadata: null,
      });
    } finally {
      setLoading(false);
    }
  }, [query, message, dispatch]);

  const handleClear = () => {
    setQuery('');
    setResult(null);
    setActiveTab('result');
  };

  const handleSuggestionClick = useCallback((suggestion: string) => {
    setQuery(suggestion);
    handleExecute(suggestion);
  }, [handleExecute]);

  // ---------------------------------------------------------------------------
  // 結果表格欄位
  // ---------------------------------------------------------------------------

  const buildColumns = () => {
    const rs = result?.result;
    if (!rs || rs.records.length === 0) return [];
    const labels = rs.field_labels || {};
    const fieldIds = Object.keys(rs.records[0].fields)
      .filter(fid => !fid.startsWith('_')); // 過濾內部欄位
    return fieldIds.map(fid => ({
      title: labels[fid] || fid,
      dataIndex: ['fields', fid],
      key: fid,
      ellipsis: true,
      render: (val: unknown) => val === null || val === undefined || val === '' ? <Text type="secondary">-</Text> : String(val),
    }));
  };

  // ---------------------------------------------------------------------------
  // 狀態渲染區域
  // ---------------------------------------------------------------------------

  /** 錯誤狀態：顯示 Result + raw_error 展開 */
  const renderError = () => {
    if (!result || result.status !== 'error') return null;
    const pe = result.post_error;
    return (
      <Result
        status="error"
        title="查詢執行失敗"
        subTitle={pe?.message || '發生未知錯誤'}
        extra={
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => handleExecute()}>
            重新執行
          </Button>
        }
      >
        {pe?.raw_error && (
          <Collapse
            items={[{
              key: 'raw',
              label: '錯誤詳情',
              children: <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{pe.raw_error}</pre>,
            }]}
          />
        )}
        {result.intent && (
          <Descriptions bordered size="small" column={1} style={{ marginTop: 16 }}>
            <Descriptions.Item label="匹配意圖">{result.intent.intent_id}</Descriptions.Item>
            <Descriptions.Item label="匹配分數">{(result.intent.score * 100).toFixed(1)}%</Descriptions.Item>
            <Descriptions.Item label="目標表單">{result.intent.table_key}</Descriptions.Item>
          </Descriptions>
        )}
      </Result>
    );
  };

  /** 澄清狀態：顯示 Alert + 可點擊建議 */
  const renderClarification = () => {
    if (!result || result.status !== 'clarification_needed') return null;
    const cl = result.clarification;
    return (
      <Result
        status="warning"
        icon={<ExclamationCircleOutlined />}
        title="需要進一步澄清"
        subTitle={cl?.message || '無法理解您的查詢意圖'}
        extra={
          cl?.suggestions && cl.suggestions.length > 0 ? (
            <Space direction="vertical" align="center" size="middle">
              <Text type="secondary">試試以下查詢：</Text>
              <Space wrap>
                {cl.suggestions.map(s => (
                  <Tag.CheckableTag
                    key={s}
                    checked={false}
                    onChange={() => handleSuggestionClick(s)}
                    style={{ padding: '4px 12px', fontSize: 14 }}
                  >
                    {s}
                  </Tag.CheckableTag>
                ))}
              </Space>
            </Space>
          ) : undefined
        }
      >
        {result.intent && (
          <Descriptions bordered size="small" column={1} style={{ marginTop: 16 }}>
            <Descriptions.Item label="部分匹配意圖">{result.intent.intent_id}</Descriptions.Item>
            <Descriptions.Item label="匹配分數">{(result.intent.score * 100).toFixed(1)}%</Descriptions.Item>
          </Descriptions>
        )}
      </Result>
    );
  };

  /** 成功狀態上方提示（中確信提示 / 0 筆提示） */
  const renderSuccessAlerts = () => {
    if (!result || result.status !== 'success') return null;
    const alerts: React.ReactNode[] = [];

    if (result.clarification?.message) {
      alerts.push(
        <Alert
          key="clarification"
          type="info"
          message={result.clarification.message}
          showIcon
          style={{ marginBottom: 12 }}
        />
      );
    }

    if (result.post_error?.message) {
      alerts.push(
        <Alert
          key="post_error"
          type="warning"
          message={result.post_error.message}
          showIcon
          style={{ marginBottom: 12 }}
        />
      );
    }

    return alerts.length > 0 ? <>{alerts}</> : null;
  };

  // ---------------------------------------------------------------------------
  // Tabs（僅在 success 狀態顯示）
  // ---------------------------------------------------------------------------

  const renderTabs = () => {
    const rs = result?.result;
    const intent = result?.intent;
    const meta = result?.metadata;

    return (
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'result',
            label: <Space><TableOutlined />結果 {rs && <Tag>{rs.record_count} 筆</Tag>}</Space>,
            children: rs && rs.records.length > 0 ? (
              <Table
                columns={buildColumns()}
                dataSource={rs.records}
                rowKey="ragic_id"
                pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
                scroll={{ x: 'max-content' }}
                size="small"
              />
            ) : (
              <Result
                status="info"
                icon={<SearchOutlined />}
                title="查詢完成，未找到符合條件的資料"
                subTitle="請嘗試調整查詢條件或換個描述方式"
              />
            )
          },
          {
            key: 'intent',
            label: <Space><ThunderboltOutlined />意圖匹配</Space>,
            children: intent ? (
              <Descriptions bordered size="small" column={1}>
                <Descriptions.Item label="意圖 ID">{intent.intent_id}</Descriptions.Item>
                <Descriptions.Item label="匹配分數">
                  <Text style={{
                    color: intent.score >= 0.8
                      ? contentTokens.colorSuccess
                      : intent.score >= 0.6
                        ? contentTokens.colorPrimary
                        : contentTokens.colorWarning
                  }}>
                    {(intent.score * 100).toFixed(1)}%
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="信心等級">
                  {renderConfidenceTag(intent.confidence)}
                </Descriptions.Item>
                <Descriptions.Item label="操作類型">{intent.action}</Descriptions.Item>
                <Descriptions.Item label="目標表單">{intent.table_key}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Alert message="未匹配到意圖" type="info" showIcon />
            )
          },
          {
            key: 'params',
            label: <Space><SearchOutlined />查詢參數</Space>,
            children: meta?.translated_params ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                {meta.translated_params.where && meta.translated_params.where.length > 0 && (
                  <Table
                    size="small"
                    dataSource={meta.translated_params.where}
                    rowKey={(_r, i) => i?.toString() || '0'}
                    pagination={false}
                    columns={[
                      { title: '欄位 ID', dataIndex: 'field_id' },
                      { title: '運算符', dataIndex: 'operator' },
                      { title: '值', dataIndex: 'value', render: (val: unknown) => String(val) }
                    ]}
                  />
                )}
                <Descriptions bordered size="small" column={2}>
                  <Descriptions.Item label="Limit">{meta.translated_params.limit ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label="Offset">{meta.translated_params.offset ?? '-'}</Descriptions.Item>
                </Descriptions>
              </Space>
            ) : (
              <Alert message="無查詢參數" type="info" showIcon />
            )
          },
          {
            key: 'debug',
            label: <Space><FileTextOutlined />偵錯</Space>,
            children: (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label="回應碼">{result?.code ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label="狀態">{result?.status || '-'}</Descriptions.Item>
                  <Descriptions.Item label="連線名稱">{meta?.connection || '-'}</Descriptions.Item>
                  <Descriptions.Item label="表單鍵值">{meta?.table_key || '-'}</Descriptions.Item>
                  <Descriptions.Item label="輸出格式">{meta?.output_format || '-'}</Descriptions.Item>
                  <Descriptions.Item label="原始查詢">{meta?.query || '-'}</Descriptions.Item>
                  <Descriptions.Item label="執行路徑">
                    {meta?.path_used ? (
                      <Tag color={meta.path_used === 'path_a' ? 'blue' : meta.path_used === 'path_b' ? 'purple' : 'default'}>
                        {meta.path_used === 'path_a' ? 'Path A (Tool-Calling)' : meta.path_used === 'path_b' ? 'Path B (Pandas 聚合)' : meta.path_used}
                      </Tag>
                    ) : '-'}
                  </Descriptions.Item>
                </Descriptions>
                {rs?.field_labels && Object.keys(rs.field_labels).length > 0 && (
                  <Collapse
                    items={[{
                      key: 'labels',
                      label: `欄位標籤 (${Object.keys(rs.field_labels).length} 個)`,
                      children: <pre style={{ fontSize: 12 }}>{JSON.stringify(rs.field_labels, null, 2)}</pre>,
                    }]}
                  />
                )}
                {result?.post_error?.raw_error && (
                  <Collapse
                    items={[{
                      key: 'raw_error',
                      label: 'Raw Error',
                      children: <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{result.post_error.raw_error}</pre>,
                    }]}
                  />
                )}
              </Space>
            )
          }
        ]}
      />
    );
  };

  // ---------------------------------------------------------------------------
  // 共用元件
  // ---------------------------------------------------------------------------

  const renderConfidenceTag = (confidence: string) => {
    const map: Record<string, { color: string; label: string }> = {
      high: { color: 'green', label: '高確信' },
      medium: { color: 'orange', label: '中確信' },
      low: { color: 'red', label: '低確信' },
    };
    const cfg = map[confidence] || { color: 'default', label: confidence || '-' };
    return <Tag color={cfg.color}>{cfg.label}</Tag>;
  };

  // ---------------------------------------------------------------------------
  // 主結果區域渲染
  // ---------------------------------------------------------------------------

  const renderResultArea = () => {
    if (loading) {
      return (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: token.colorTextSecondary }}>查詢執行中...</div>
        </div>
      );
    }

    if (!result) {
      return (
        <Result
          icon={<DatabaseOutlined style={{ color: token.colorTextQuaternary }} />}
          title={<Text type="secondary">輸入自然語言查詢並點擊執行</Text>}
          subTitle={<Text type="secondary" style={{ fontSize: 12 }}>支援中文自然語言，如「查詢所有採購訂單」</Text>}
        />
      );
    }

    if (result.status === 'error') return renderError();
    if (result.status === 'clarification_needed') return renderClarification();

    // success
    return (
      <>
        {renderSuccessAlerts()}
        {renderTabs()}
      </>
    );
  };

  // ---------------------------------------------------------------------------
  // 右側統計面板
  // ---------------------------------------------------------------------------

  const renderStatsPanel = () => {
    const rs = result?.result;
    const hasStats = result?.status === 'success' && rs;
    const intent = result?.intent;

    return (
      <Card title="查詢統計" size="small" style={{ marginBottom: 24 }}>
        {hasStats ? (
          <>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="執行時間" value={rs.execution_time_ms ?? 0} precision={0} suffix="ms" />
              </Col>
              <Col span={8}>
                <Statistic title="結果筆數" value={rs.record_count ?? 0} />
              </Col>
              <Col span={8}>
                <Statistic title="預估 Tokens" value={rs.stats?.estimated_tokens ?? 0} />
              </Col>
            </Row>
            <Space style={{ marginTop: 16 }} wrap>
              {intent && renderConfidenceTag(intent.confidence)}
              {rs.stats && <Tag>{rs.stats.total_fields} 個欄位</Tag>}
              {rs.pagination?.has_more && <Tag color="blue">還有更多資料</Tag>}
            </Space>
          </>
        ) : result ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Tag
              color={result.status === 'error' ? 'error' : 'warning'}
              icon={result.status === 'error' ? <CloseCircleOutlined /> : <ExclamationCircleOutlined />}
            >
              {result.status === 'error' ? '查詢失敗' : '需要澄清'}
            </Tag>
            {intent && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                意圖匹配：{intent.intent_id} ({(intent.score * 100).toFixed(0)}%)
              </Text>
            )}
          </Space>
        ) : (
          <Text type="secondary">執行查詢後顯示統計資訊</Text>
        )}
      </Card>
    );
  };

  // ---------------------------------------------------------------------------
  // JSX
  // ---------------------------------------------------------------------------

  return (
    <div style={{ padding: 24 }}>
      <Title level={4} style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
        <DatabaseOutlined />
        Data Agent Query Playground
        <Tag color="blue" style={{ marginLeft: 'auto' }}>NL → Ragic</Tag>
        {result?.status && (
          <Tag
            color={result.status === 'success' ? 'success' : result.status === 'error' ? 'error' : 'warning'}
            icon={result.status === 'success' ? <CheckCircleOutlined /> : result.status === 'error' ? <CloseCircleOutlined /> : <ExclamationCircleOutlined />}
          >
            {result.status === 'success' ? '成功' : result.status === 'error' ? '失敗' : '待澄清'}
          </Tag>
        )}
      </Title>

      <Row gutter={24}>
        <Col span={14}>
          <Card title="自然語言查詢" size="small" style={{ marginBottom: 24 }}>
            <TextArea
              rows={4}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); handleExecute(); } }}
              placeholder="請輸入自然語言查詢，例如：查詢所有採購訂單..."
              style={{ marginBottom: 16 }}
            />
            <Space style={{ marginBottom: 16, flexWrap: 'wrap' }}>
              {quickTemplates.map(t => (
                <Tag
                  key={t}
                  color="processing"
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleSuggestionClick(t)}
                >
                  {t}
                </Tag>
              ))}
            </Space>
            <Row justify="end">
              <Space>
                <Button icon={<ClearOutlined />} onClick={handleClear} disabled={loading}>
                  清除
                </Button>
                <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => handleExecute()} loading={loading}>
                  執行查詢
                </Button>
              </Space>
            </Row>
          </Card>

          <Card title="查詢結果" size="small">
            {renderResultArea()}
          </Card>
        </Col>

        <Col span={10}>
          {renderStatsPanel()}

          <Card title="使用說明" size="small">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Text>輸入自然語言查詢 → 執行 → 查看結果</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                支援 Enter 快速執行（Shift+Enter 換行）
              </Text>
              <Alert message="查詢範圍：2025shianyong 帳號下所有 Ragic 表單" type="info" showIcon style={{ marginTop: 8 }} />
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
