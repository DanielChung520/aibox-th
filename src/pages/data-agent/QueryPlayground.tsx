/**
 * @file        Data Agent Query Playground
 * @description 用於測試和執行自然語言查詢的互動式介面
 * @lastUpdate  2026-03-24 19:01:41
 * @author      Daniel Chung
 */

import { useState, useEffect } from 'react';
import { 
  Card, Input, Button, Select, Table, Tag, Space, 
  Typography, Spin, Alert, Divider, Row, Col, 
  Badge, Collapse, Empty, Statistic, App, Tabs, Descriptions, theme,
  Radio, Steps, Progress
} from 'antd';
import { 
  PlayCircleOutlined, CopyOutlined, ClearOutlined, 
  DatabaseOutlined, ClockCircleOutlined,
  TableOutlined, BranchesOutlined, ThunderboltOutlined,
  InfoCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
  LikeOutlined, DislikeOutlined, QuestionCircleOutlined, WarningOutlined
} from '@ant-design/icons';
import { dataAgentApi, TableInfo, QueryResponse, NL2SqlResponse } from '../../services/dataAgentApi';
import { useContentTokens } from '../../contexts/AppThemeProvider';

import type { TabsProps } from 'antd';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

type QueryMode = 'SQL' | 'AQL';

interface AqlQueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
}

export default function QueryPlayground() {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const contentTokens = useContentTokens();
  const [queryMode, setQueryMode] = useState<QueryMode>('SQL');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [selectedModule, setSelectedModule] = useState<string>('ALL');
  const [moduleScope, setModuleScope] = useState<string[]>([]);
  
  // AQL State
  const [aqlResult, setAqlResult] = useState<AqlQueryResult | null>(null);
  const [aqlQueryResponse, setAqlQueryResponse] = useState<QueryResponse | null>(null);
  
  // SQL State
  const [sqlResponse, setSqlResponse] = useState<NL2SqlResponse | null>(null);
  
  // Common State
  const [error, setError] = useState<string | null>(null);
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [sqlCopied, setSqlCopied] = useState(false);
  const [activeTab, setActiveTab] = useState('result');
  const [feedbackGiven, setFeedbackGiven] = useState<'up' | 'down' | null>(null);

  useEffect(() => {
    dataAgentApi.listTables()
      .then(res => setTables(res.data.data || []))
      .catch(err => console.error('載入資料表失敗', err));
  }, []);

  const handleExecuteAql = async (startTime: number) => {
    try {
      const params: Parameters<typeof dataAgentApi.query>[0] = {
        query: query,
        options: {
          timezone: 'Asia/Taipei',
          limit: 100,
          return_debug: true,
          ...(moduleScope.length > 0 ? { module_scope: moduleScope } : {})
        }
      };

      const res = await dataAgentApi.query(params);
      const data = res.data;

      if (data.code === 0) {
        setAqlResult({
          columns: data.data?.columns || [],
          rows: data.data?.results || []
        });
        setAqlQueryResponse(data);
        setActiveTab('intent');
      } else {
        setError(data.message || '查詢執行失敗');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '查詢執行失敗');
    } finally {
      setExecutionTime(Date.now() - startTime);
      setLoading(false);
    }
  };

  const handleExecuteSql = async () => {
    try {
      const res = await dataAgentApi.nl2sql({ natural_language: query });
      const data = res.data;
      // Always store response for clarification/error_explanation display
      setSqlResponse(data);
      if (data.success) {
        setActiveTab('result');
      } else if (data.clarification?.needs_clarification) {
        // Pre-query clarification — not a real error
        setActiveTab('result');
      } else {
        setError(data.error || '查詢執行失敗');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '查詢執行失敗');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!query.trim()) {
      message.warning('請輸入查詢內容');
      return;
    }

    setLoading(true);
    setError(null);
    setAqlResult(null);
    setAqlQueryResponse(null);
    setSqlResponse(null);
    setExecutionTime(null);
    setFeedbackGiven(null);

    const startTime = Date.now();

    if (queryMode === 'AQL') {
      await handleExecuteAql(startTime);
    } else {
      await handleExecuteSql();
    }
  };

  const handleClear = () => {
    setQuery('');
    setAqlResult(null);
    setAqlQueryResponse(null);
    setSqlResponse(null);
    setError(null);
    setExecutionTime(null);
    setSqlCopied(false);
    setFeedbackGiven(null);
  };

  const handleCopySql = () => {
    const textToCopy = queryMode === 'SQL' 
      ? sqlResponse?.generated_sql 
      : aqlQueryResponse?.data?.sql;
      
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setSqlCopied(true);
      message.success('SQL 已複製到剪貼簿');
      setTimeout(() => setSqlCopied(false), 2000);
    }
  };

  const handleModuleChange = (module: string) => {
    setSelectedModule(module);
    setModuleScope(module === 'ALL' ? [] : [module]);
  };

  const handleFeedback = async (action: 'thumbs_up' | 'thumbs_down') => {
    if (!sqlResponse?.matched_intent?.intent_id || !query.trim()) return;
    setFeedbackGiven(action === 'thumbs_up' ? 'up' : 'down');
    if (action === 'thumbs_up') {
      try {
        await dataAgentApi.feedbackIntent(sqlResponse.matched_intent.intent_id, { action, nl_query: query.trim() });
        message.success('已將查詢加入意圖訓練資料');
      } catch { message.error('回饋提交失敗'); }
    } else {
      message.info('感謝您的回饋');
    }
  };

  const renderGenerateSqlCard = () => {
    if (queryMode !== 'SQL' || !sqlResponse?.matched_intent) return null;
    const intent = sqlResponse.matched_intent;
    const scorePercent = Math.round(intent.score * 100);
    const scoreColor = scorePercent >= 80 ? contentTokens.colorSuccess : scorePercent >= 60 ? contentTokens.colorPrimary : contentTokens.colorWarning;
    const strategyConfig: Record<string, { color: string; label: string }> = {
      template: { color: 'green', label: '模板替換' },
      small_llm: { color: 'blue', label: 'Small LLM' },
      large_llm: { color: 'orange', label: 'Large LLM' },
    };
    const strategy = strategyConfig[intent.generation_strategy] ?? { color: 'default', label: intent.generation_strategy };

    return (
      <Card title="Generate SQL 分析" style={{ marginBottom: 16 }}>
        <Space orientation="vertical" style={{ width: '100%' }} size={12}>
          <Row>
            <Col span={8}><Text type="secondary">意圖分類</Text></Col>
            <Col span={16}><Tag color="purple">{intent.intent_type}</Tag></Col>
          </Row>
          <Row>
            <Col span={8}><Text type="secondary">意圖群組</Text></Col>
            <Col span={16}><Tag color="cyan">{intent.group}</Tag></Col>
          </Row>
          <Row>
            <Col span={8}><Text type="secondary">生成策略</Text></Col>
            <Col span={16}><Tag color={strategy.color}>{strategy.label}</Tag></Col>
          </Row>
          <Row align="middle">
            <Col span={8}><Text type="secondary">置信度</Text></Col>
            <Col span={16}>
              <Space>
                <Progress percent={scorePercent} size="small" style={{ width: 120 }} strokeColor={scoreColor} showInfo={false} />
                <Text style={{ color: scoreColor, fontWeight: 600 }}>{scorePercent}%</Text>
              </Space>
            </Col>
          </Row>
          {intent.tables.length > 0 && (
            <Row>
              <Col span={8}><Text type="secondary">相關資料表</Text></Col>
              <Col span={16}>
                <Space wrap size={4}>
                  {intent.tables.map(t => <Tag key={t}>{t}</Tag>)}
                </Space>
              </Col>
            </Row>
          )}
          <Row>
            <Col span={8}><Text type="secondary">意圖描述</Text></Col>
            <Col span={16}><Text>{intent.description}</Text></Col>
          </Row>
          <Row>
            <Col span={8}><Text type="secondary">Intent ID</Text></Col>
            <Col span={16}><Text code style={{ fontSize: 11 }}>{intent.intent_id}</Text></Col>
          </Row>
        </Space>
      </Card>
    );
  };

  const availableModules = [...new Set(tables.map(t => t.module))];

  const quickTemplatesAql = [
    { label: '採購訂單查詢', query: '查詢上個月的採購訂單', module: 'MM' },
    { label: '供應商列表', query: '列出所有供應商', module: 'MM' },
    { label: '銷售訂單', query: '查詢本月銷售訂單', module: 'SD' },
    { label: '員工清單', query: '查詢所有員工', module: 'BASE' },
    { label: '進貨單查詢', query: '查詢近30天進貨單', module: 'PUR' },
  ];
  const quickTemplatesSql = [
    ...([
      '查詢上個月的採購訂單',
      '列出所有供應商',
      '各供應商的採購金額排名',
      '查詢庫存異動記錄',
      '本月物料入庫總量',
      // 採購流程
      '查詢所有詢價單',
      '查詢一筆詢價單的完整採購流程',
      '查詢所有採購單(PO)',
      '查詢近30天收貨單',
      '查詢所有進貨退出單',
      // 訂單/報價流程
      '查詢所有報價單',
      '查詢所有訂購單(SO)',
      '查詢一張訂購單的完整生命週期',
      // 生產需求流程
      '查詢所有生產需求單',
      '查詢所有物料需求單(MRP)',
      '查詢所有採購預算表',
      // 生產執行流程
      '查詢所有生產製令單',
      '查詢所有領料單',
      '查詢所有派工單',
      // 品檢與入庫
      '查詢近30天進貨檢驗(IQC)記錄',
      '查詢本月成品入庫記錄',
      // 跨流程追蹤
      '追蹤一張訂購單從報價到入庫的完整流程',
    ].map(q => ({ label: q, query: q, module: 'MM' }))),
    ...(['查詢近30天各供應商的進貨明細', '各部門的員工人數', '查詢在職中的員工清單', '查詢品項的基本資訊'].map(q => ({ label: q, query: q, module: 'BASE' }))),
  ];
  const templatesToUse = queryMode === 'SQL' ? quickTemplatesSql : quickTemplatesAql;

const renderResultTabs = () => {
    const isAql = queryMode === 'AQL';
    const hasData = isAql ? !!aqlResult : !!sqlResponse;
    if (!hasData || loading) return null;

    const columns = (isAql ? aqlResult?.columns : sqlResponse?.execution_result?.columns)?.map(col => ({
      title: col, dataIndex: col, key: col, ellipsis: true,
      render: (val: unknown) => (val === null || val === undefined) ? <Text type="secondary">-</Text> : typeof val === 'number' ? val.toLocaleString() : String(val)
    })) || [];

    const rows = (isAql ? aqlResult?.rows : sqlResponse?.execution_result?.rows) || [];
    const sqlText = isAql ? aqlQueryResponse?.data?.sql : sqlResponse?.generated_sql;
    const CodeBlock = ({ content }: { content: string }) => (
      <pre style={{ background: token.colorFillTertiary, padding: 16, borderRadius: 6, overflow: 'auto', maxHeight: 300, fontSize: 12 }}>{content}</pre>
    );

    const items: TabsProps['items'] = [
      { key: 'result', label: <span><TableOutlined /> 結果</span>, children: rows.length > 0 ? <Table columns={columns} dataSource={rows} rowKey={(_, index) => String(index)} pagination={{ pageSize: 10 }} size="small" scroll={{ x: 'max-content' }} /> : <Empty description="無查詢結果" /> },
      { key: 'sql', label: <span><BranchesOutlined /> SQL</span>, children: <div><Button type="link" icon={<CopyOutlined />} onClick={handleCopySql} style={{ marginBottom: 8, padding: 0 }}>{sqlCopied ? '已複製!' : '複製 SQL'}</Button><CodeBlock content={sqlText || '-'} /></div> },
      { key: 'intent', label: <span><ThunderboltOutlined /> Intent</span>, children: <CodeBlock content={JSON.stringify(isAql ? aqlQueryResponse?.intent : sqlResponse?.matched_intent, null, 2) || ''} /> },
    ];

    if (!isAql && sqlResponse) {
      items.push(
        { key: 'plan', label: <span>Query Plan</span>, children: <CodeBlock content={JSON.stringify(sqlResponse.query_plan, null, 2) || ''} /> },
        { key: 'validation', label: <span>Validation</span>, children: <div><Alert type={sqlResponse.validation?.is_valid ? 'success' : 'error'} description={`Valid: ${sqlResponse.validation?.is_valid}`} style={{ marginBottom: 16 }} /><CodeBlock content={JSON.stringify(sqlResponse.validation, null, 2) || ''} /></div> },
        { key: 'pipeline', label: <span>Pipeline</span>, children: <Steps direction="vertical" size="small" current={sqlResponse.phases.length} items={sqlResponse.phases.map(p => ({ title: p.phase, description: `${p.duration_ms} ms ${p.error ? `- ${p.error}` : ''}`, status: (p.success ? 'finish' : 'error') as 'finish' | 'error', icon: p.success ? <CheckCircleOutlined style={{ color: token.colorSuccess }} /> : <CloseCircleOutlined style={{ color: token.colorError }} /> }))} /> }
      );
    }

    if (isAql && aqlQueryResponse) {
      items.push({
        key: 'debug', label: <span><InfoCircleOutlined /> Debug</span>, children: <Descriptions bordered column={1} size="small">
          <Descriptions.Item label="Cache Hit">{aqlQueryResponse.cache_hit ? <Badge status="success" text="是" /> : <Badge status="default" text="否" />}</Descriptions.Item>
          <Descriptions.Item label="Execution Time">{aqlQueryResponse.data?.metadata?.duration_ms}ms</Descriptions.Item>
          <Descriptions.Item label="Truncated">{aqlQueryResponse.data?.metadata?.truncated ? <Badge status="warning" text="是" /> : <Badge status="success" text="否" />}</Descriptions.Item>
          <Descriptions.Item label="Trace ID"><Text code>{aqlQueryResponse.data?.metadata?.trace_id}</Text></Descriptions.Item>
        </Descriptions>
      });
    }

    return <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />;
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
        <DatabaseOutlined /> 
        Data Agent Query Playground
        <Radio.Group 
          value={queryMode} 
          onChange={e => {
            setQueryMode(e.target.value);
            handleClear();
          }}
          optionType="button"
          buttonStyle="solid"
          size="middle"
          style={{ marginLeft: 'auto' }}
        >
          <Radio.Button value="SQL">數據湖查詢 (NL→SQL)</Radio.Button>
          <Radio.Button value="AQL">ArangoDB 查詢 (NL→AQL)</Radio.Button>
        </Radio.Group>
      </Title>

      <Row gutter={16}>
        <Col span={14}>
          <Card 
            title="查詢輸入" 
            extra={
              queryMode === 'AQL' && (
                <Select value={selectedModule} onChange={handleModuleChange} style={{ width: 120 }}>
                  <Option value="ALL">全部模組</Option>
                  {availableModules.map(m => <Option key={m} value={m}>{m}</Option>)}
                </Select>
              )
            }
          >
            <Space orientation="vertical" style={{ width: '100%' }} size="middle">
              <TextArea
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="輸入自然語言查詢..."
                rows={4}
                style={{ fontSize: 14 }}
              />
              
              <div>
                <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>
                  快速範本：
                </Text>
                <Space wrap>
                  {templatesToUse.map((t, idx) => (
                    <Button 
                      key={idx} 
                      size="small"
                      onClick={() => {
                        setQuery(t.query);
                        if (queryMode === 'AQL') {
                          setSelectedModule(t.module);
                          setModuleScope([t.module]);
                        }
                      }}
                    >
                      {t.label}
                    </Button>
                  ))}
                </Space>
              </div>

              <Space>
                <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleExecute} loading={loading} size="large">
                  執行查詢
                </Button>
                <Button icon={<ClearOutlined />} onClick={handleClear} size="large">
                  清除
                </Button>
              </Space>
            </Space>
          </Card>

          <Card 
            title={<Space><span>查詢結果</span>{((queryMode === 'AQL' && aqlResult) || (queryMode === 'SQL' && sqlResponse)) && <Tag color="blue">{(queryMode === 'AQL' ? aqlResult?.rows.length : sqlResponse?.execution_result?.row_count) ?? 0} 列</Tag>}</Space>}
            extra={queryMode === 'SQL' && sqlResponse?.success && !feedbackGiven ? (
              <Space><Button size="small" icon={<LikeOutlined />} onClick={() => handleFeedback('thumbs_up')}>有用</Button><Button size="small" icon={<DislikeOutlined />} onClick={() => handleFeedback('thumbs_down')}>無用</Button></Space>
            ) : feedbackGiven ? (<Tag color={feedbackGiven === 'up' ? 'green' : 'default'}>{feedbackGiven === 'up' ? '已加入訓練' : '已回饋'}</Tag>) : null}
            style={{ marginTop: 16 }}
          >
            {loading && (
              <div style={{ textAlign: 'center', padding: 40 }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}><Text type="secondary">正在執行查詢...</Text></div>
              </div>
            )}

            {error && (
              <Alert type="error" showIcon style={{ marginBottom: 16 }} description={
                <div>
                  <Text>{error}</Text>
                  {queryMode === 'SQL' && sqlResponse?.generated_sql && !sqlResponse?.error_explanation && (
                    <div style={{ marginTop: 12 }}>
                      <Text type="secondary" strong>產生的 SQL：</Text>
                      <pre style={{ background: token.colorFillTertiary, padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 200, fontSize: 12, marginTop: 4 }}>{sqlResponse.generated_sql}</pre>
                    </div>
                  )}
                </div>
              } />
            )}

            {sqlResponse?.clarification?.needs_clarification && (
              <Alert
                type="warning"
                icon={<QuestionCircleOutlined />}
                showIcon
                message="查詢需要澄清"
                description={
                  <div>
                    <Text>{sqlResponse.clarification.reason}</Text>
                    {sqlResponse.clarification.questions.length > 0 && (
                      <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                        {sqlResponse.clarification.questions.map((q, i) => (
                          <li key={i}><Text strong>{q.field ? `[${q.field}] ` : ''}</Text>{q.question}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                }
                style={{ marginBottom: 16 }}
              />
            )}

            {sqlResponse?.error_explanation && (
              <Alert
                type="error"
                icon={<WarningOutlined />}
                showIcon
                message={`執行異常：${sqlResponse.error_explanation.error_type}`}
                description={
                  <div>
                    <Text>{sqlResponse.error_explanation.explanation}</Text>
                    {sqlResponse.error_explanation.suggestions.length > 0 && (
                      <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                        {sqlResponse.error_explanation.suggestions.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    )}
                    {sqlResponse.generated_sql && (
                      <div style={{ marginTop: 12 }}>
                        <Text type="secondary" strong>產生的 SQL：</Text>
                        <pre style={{ background: token.colorFillTertiary, padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 200, fontSize: 12, marginTop: 4 }}>{sqlResponse.generated_sql}</pre>
                      </div>
                    )}
                  </div>
                }
                style={{ marginBottom: 16 }}
              />
            )}

            {renderResultTabs()}

            {!loading && !error && !aqlResult && !sqlResponse && <Empty description="輸入查詢並點擊執行" />}
          </Card>
        </Col>

        <Col span={10}>
          <Card title="查詢統計" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic 
                  title="執行時間" 
                  value={(queryMode === 'SQL' ? sqlResponse?.total_time_ms : executionTime) ?? 0} 
                  suffix="ms"
                  prefix={<ClockCircleOutlined />}
                  styles={{ content: { fontSize: 24 } }}
                />
              </Col>
              <Col span={12}>
                <Statistic 
                  title="結果列數" 
                  value={(queryMode === 'SQL' ? sqlResponse?.execution_result?.row_count : aqlResult?.rows.length) ?? 0} 
                  prefix={<TableOutlined />}
                  styles={{ content: { fontSize: 24 } }}
                />
              </Col>
            </Row>
          </Card>

          {renderGenerateSqlCard()}

          {queryMode === 'AQL' && (
            <Card title="可用資料表" style={{ marginBottom: 16 }}>
              <Collapse 
                ghost
                items={availableModules.map(module => ({
                  key: module,
                  label: <Tag color="blue">{module}</Tag>,
                  children: (
                    <Space orientation="vertical" style={{ width: '100%' }}>
                      {tables.filter(t => t.module === module).map(t => (
                        <div key={t.table_id} style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Text>{t.table_name}</Text>
                          <Text type="secondary" style={{ fontSize: 12 }}>{t.sheet_key || '-'}</Text>
                        </div>
                      ))}
                    </Space>
                  )
                }))}
              />
            </Card>
          )}

          <Card title="使用說明">
            <Text type="secondary">1. 選擇查詢模式 → 2. 輸入自然語言 → 3. 執行查詢 → 4. 查看結果/SQL/Plan</Text>
            <Divider style={{ margin: '12px 0' }} />
            <Alert type="info" description="複雜查詢可能需要較長時間處理，建議縮小查詢範圍以獲得更快回應。" showIcon />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
