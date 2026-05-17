/**
 * @file        資料深度追蹤主頁面
 * @description 整合場景選擇、輸入、圖譜、表格、報告等子元件
 * @lastUpdate  2026-05-17
 */
import React, { useState, useCallback } from 'react';
import { Typography, Layout, Row, Col, Spin, message, notification, Button } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import ScenarioSelector from './components/ScenarioSelector';
import TraceInputForm from './components/TraceInputForm';
import TraceGraphView from './components/TraceGraphView';
import TraceResultTable from './components/TraceResultTable';
import ResultSummary from './components/ResultSummary';
import ReportSaveModal from './components/ReportSaveModal';
import { dataAgentApi } from '../../services/dataAgentApi';
import type { RecordTraceNode, RecordTraceEdge } from '../../services/dataAgentApi_types';

const { Title } = Typography;

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
    <Layout style={{ padding: 24, background: 'transparent', minHeight: '100%' }}>
      <Title level={3} style={{ marginBottom: 24, color: tokens?.colorTextBase }}>資料深度追蹤</Title>
      <Row gutter={[24, 24]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={6}>
          <ScenarioSelector selectedScenario={selectedScenario} onSelect={setSelectedScenario} />
        </Col>
        <Col xs={24} md={18}>
          <TraceInputForm scenario={selectedScenario} onTrace={handleTrace} loading={loading} />
        </Col>
      </Row>
      {loading && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin size="large" tip="正在追蹤中..." />
        </div>
      )}
      {traceResult && !loading && (
        <>
          <Row gutter={[24, 24]} style={{ marginBottom: 16 }}>
            <Col span={24}>
              <ResultSummary
                nodeCount={traceResult.summary.node_count}
                edgeCount={traceResult.summary.edge_count}
                maxDepth={traceResult.summary.max_depth}
                totalTimeMs={traceResult.summary.total_time_ms}
                nodes={traceResult.nodes}
              />
            </Col>
          </Row>
          <Row gutter={[24, 24]}>
            <Col xs={24} lg={14}>
              <TraceGraphView
                nodes={traceResult.nodes}
                edges={traceResult.edges}
                onNodeClick={handleGraphNodeClick}
                loading={false}
              />
            </Col>
            <Col xs={24} lg={10}>
              <TraceResultTable
                nodes={traceResult.nodes}
                onRowClick={handleRowClick}
                loading={false}
                activeRagicId={activeNodeId}
              />
            </Col>
          </Row>
          <div style={{ marginTop: 16, textAlign: 'right' }}>
            <Button type="primary" icon={<SaveOutlined />} onClick={() => setReportModalOpen(true)}>
              儲存報告
            </Button>
          </div>
        </>
      )}
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
    </Layout>
  );
};

export default DataDepthTracking;
