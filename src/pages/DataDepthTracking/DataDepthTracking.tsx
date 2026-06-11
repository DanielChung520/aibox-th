/**
 * @file        資料深度追蹤主頁面
 * @description 左右分區：左側場景選擇+輸入，右側結果展示
 * @lastUpdate  2026-05-17
 */
import React, { useState, useCallback } from 'react';
import { Row, Col, Card, Spin, message, notification, Button, Tag, Empty } from 'antd';
import { SaveOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import ScenarioSelector from './components/ScenarioSelector';
import TraceInputForm from './components/TraceInputForm';
import TraceGraphView from './components/TraceGraphView';
import TraceResultTable from './components/TraceResultTable';
import ResultSummary from './components/ResultSummary';
import ReportSaveModal from './components/ReportSaveModal';
import { dataAgentApi } from '../../services/dataAgentApi';
import type { RecordTraceNode, RecordTraceEdge } from '../../services/dataAgentApi_types';

interface TraceResultData {
  nodes: RecordTraceNode[]; edges: RecordTraceEdge[];
  summary: { node_count: number; edge_count: number; max_depth: number; total_time_ms: number };
}

const DataDepthTracking: React.FC = () => {
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [traceResult, setTraceResult] = useState<TraceResultData | null>(null);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const tokens = useContentTokens();

  const handleTrace = useCallback(async (params: { entry_batch: string; depth?: number; entry_table?: string }) => {
    if (!params.entry_batch) { message.warning('請輸入批號'); return; }
    setLoading(true); setTraceResult(null);
    try {
      const res = await dataAgentApi.recordTrace({
        table_key: params.entry_table || 'ERP_48',
        record_id: params.entry_batch,
        account: '2025shianyong',
        depth: params.depth || 3,
      });
      const data = res.data?.data;
      if (data?.nodes?.length > 0) {
        setTraceResult({
          nodes: data.nodes.map((n: RecordTraceNode) => ({
            table_key: n.table_key, table_name: n.table_name,
            ragic_id: n.ragic_id, fields: n.fields || {},
            depth: n.depth || 0,
          })),
          edges: (data.edges || []).map((e: RecordTraceEdge) => ({
            from_ragic_id: e.from_ragic_id, from_table_key: e.from_table_key,
            to_ragic_id: e.to_ragic_id, to_table_key: e.to_table_key,
            via_field_id: e.via_field_id || '', via_field_name: e.via_field_name || '',
            relation_type: e.relation_type || 'link',
          })),
          summary: {
            node_count: data.nodes.length,
            edge_count: data.edges?.length || 0,
            max_depth: Math.max(...data.nodes.map((n: any) => n.depth || 0), 0),
            total_time_ms: data.total_time_ms || 0,
          },
        });
      } else {
        setTraceResult(null);
        message.info('查無追蹤結果');
      }
    } catch (err: any) {
      notification.error({ message: '追蹤失敗', description: err?.response?.data?.message || err.message });
    } finally { setLoading(false); }
  }, []);

  const handleRowClick = useCallback((ragicId: string) => setActiveNodeId(ragicId), []);
  const handleGraphNodeClick = useCallback((nodeId: string) => {
    setActiveNodeId(nodeId);
    const el = document.getElementById(`row-${nodeId}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, []);

  return (
    <div style={{ padding: 2, height: '100%', overflow: 'auto' }}>
      <Row gutter={8} style={{ height: '100%' }}>
        {/* Left Panel: Scenario + Input */}
        <Col xs={24} md={8} style={{ height: '100%', overflow: 'hidden' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, height: '100%', overflow: 'auto' }}>
            <Card
              title={<><Tag color="blue">場景</Tag> 選擇追蹤類型</>}
              size="small"
              style={{ borderRadius: 10 }}
            >
              <ScenarioSelector selectedScenario={selectedScenario} onSelect={setSelectedScenario} />
            </Card>
            {selectedScenario && (
              <Card
                title={<><Tag color="green">參數</Tag> 輸入追蹤條件</>}
                size="small"
                style={{ borderRadius: 10 }}
              >
                <TraceInputForm scenario={selectedScenario} onTrace={handleTrace} loading={loading} />
              </Card>
            )}
            {selectedScenario && traceResult && (
              <Card size="small" style={{ borderRadius: 10 }}>
                <Button block icon={<ArrowLeftOutlined />} onClick={() => { setTraceResult(null); setActiveNodeId(null); }}>
                  重新查詢
                </Button>
              </Card>
            )}
          </div>
        </Col>

        {/* Right Panel: Results */}
        <Col xs={24} md={16} style={{ height: '100%' }}>
          {loading && (
            <Card style={{ borderRadius: 10, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Spin size="large" />
              <div style={{ marginTop: 16, color: tokens?.textSecondary }}>正在追蹤中...</div>
            </Card>
          )}

          {!loading && !traceResult && (
            <Card style={{ borderRadius: 10, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Empty description="請先在左側選擇場景並輸入參數" />
            </Card>
          )}

          {traceResult && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%', overflow: 'auto' }}>
              <Card style={{ borderRadius: 10 }}>
                <ResultSummary
                  nodeCount={traceResult.summary.node_count}
                  edgeCount={traceResult.summary.edge_count}
                  maxDepth={traceResult.summary.max_depth}
                  totalTimeMs={traceResult.summary.total_time_ms}
                  nodes={traceResult.nodes}
                />
              </Card>
              <Card
                title="關聯圖譜"
                style={{ borderRadius: 10 }}
                extra={
                  <Button size="small" type="primary" icon={<SaveOutlined />} onClick={() => setReportModalOpen(true)}>
                    儲存報告
                  </Button>
                }
              >
                <TraceGraphView
                  nodes={traceResult.nodes}
                  edges={traceResult.edges}
                  onNodeClick={handleGraphNodeClick}
                  loading={false}
                />
              </Card>
              <Card title="追蹤明細" style={{ borderRadius: 10 }}>
                {traceResult.nodes.length > 0 ? (
                  <TraceResultTable
                    nodes={traceResult.nodes}
                    onRowClick={handleRowClick}
                    loading={false}
                    activeRagicId={activeNodeId}
                  />
                ) : (
                  <Empty description="無追蹤資料" />
                )}
              </Card>
            </div>
          )}
        </Col>
      </Row>

      <ReportSaveModal
        open={reportModalOpen}
        onClose={() => setReportModalOpen(false)}
        onSave={async (data) => {
          try {
            await dataAgentApi.fkPreview({
              table_key: 'ERP_48', record_id: data.name || '', account: '2025shianyong',
            });
            message.success('報告已儲存');
            setReportModalOpen(false);
          } catch { message.error('儲存失敗'); }
        }}
        scenario={selectedScenario || ''}
        loading={false}
      />
    </div>
  );
};

export default DataDepthTracking;
