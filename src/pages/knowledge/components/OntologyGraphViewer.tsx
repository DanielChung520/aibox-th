/**
 * @file        本體圖譜視圖面板
 * @description 將 Ontology 實體類別 + 物件屬性轉換為 G6 力導向圖，
 *              支援 2D（force/grid/circular/dagre）與 3D 力導向圖，
 *              提供節點詳情面板、圖例說明與說明 Modal。
 * @lastUpdate  2026-04-04 11:10:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Spin, Typography, Button, Segmented, Tag, Drawer, Descriptions, Divider, Modal } from 'antd';
import { ZoomInOutlined, ZoomOutOutlined, ReloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { Graph, NodeEvent, CanvasEvent } from '@antv/g6';
import type { IElementEvent, NodeData, EdgeData } from '@antv/g6';
import { Ontology } from '../../../services/api';
import KBGraph3DPanel from './KBGraph3DPanel';
import Markdown from 'markdown-to-jsx';

const { Text } = Typography;
type LayoutMode = 'force' | 'grid' | 'circular' | 'dagre' | '3d';

const TOKEN = {
  colorPrimary: '#3b82f6',
  colorTextSecondary: '#94a3b8',
  colorBorderSecondary: '#475569',
  colorBgContainer: '#1e293b',
  borderRadiusLG: 8,
};

const BASE_CLASS_COLORS: Record<string, string> = {
  Concept: '#3b82f6',
  Document: '#22c55e',
  Process: '#f59e0b',
  Agent: '#8b5cf6',
  Requirement: '#ec4899',
  Tool: '#14b8a6',
  Event: '#f97316',
  Metadata: '#6366f1',
};

const COLOR_PALETTE = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

const getNodeColor = (baseClass: string): string => {
  return BASE_CLASS_COLORS[baseClass] || COLOR_PALETTE[Math.abs(baseClass.split('').reduce((h, c) => h + c.charCodeAt(0), 0)) % COLOR_PALETTE.length];
};

const EDGE_PALETTE = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
  '#475569', '#60a5fa', '#a78bfa', '#fb923c', '#34d399',
];

const getEdgeColor = (label: string): string => {
  return EDGE_PALETTE[Math.abs(label.split('').reduce((h, c) => h + c.charCodeAt(0), 0)) % EDGE_PALETTE.length];
};

const BASE_CLASS_LABELS: Record<string, string> = {
  Concept: '概念',
  Document: '文件',
  Process: '流程',
  Agent: '主體',
  Requirement: '需求',
  Tool: '工具',
  Event: '事件',
  Metadata: '元數據',
};

export function ontologyToGraph(ontology: Ontology) {
  const nodes = ontology.entity_classes.map((ec: { name: string; base_class: string; description: string }) => ({
    id: ec.name,
    data: { label: ec.name, type: ec.base_class, description: ec.description, tag: ec.base_class },
  }));

  const seenEdges = new Set<string>();
  const edges: { source: string; target: string; data: { label: string; description: string } }[] = [];
  for (const prop of ontology.object_properties) {
    for (const src of prop.domain) {
      for (const tgt of prop.range) {
        if (
          ontology.entity_classes.some((e: { name: string }) => e.name === src) &&
          ontology.entity_classes.some((e: { name: string }) => e.name === tgt)
        ) {
          const key = `${src}||${tgt}`;
          if (!seenEdges.has(key)) {
            seenEdges.add(key);
            edges.push({ source: src, target: tgt, data: { label: prop.name, description: prop.description } });
          }
        }
      }
    }
  }

  return { nodes, edges };
}

interface OntologyGraphViewerProps {
  ontology: Ontology;
  height?: number;
}

type G6Node = { id: string; data?: Record<string, unknown> };
type G6Edge = { source: string; target: string; data?: Record<string, unknown> };
type SelectedNode = {
  id: string;
  label: string;
  baseClass: string;
  description: string;
  outgoing: { label: string; target: string; description: string }[];
  incoming: { label: string; source: string; description: string }[];
};

export default function OntologyGraphViewer({ ontology, height = 480 }: OntologyGraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('force');
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [containerSize, setContainerSize] = useState({ w: 800, h: height });
  const [zoom, setZoom] = useState(1);
  const instanceRef = useRef(0);
  const [baseClassFilter, setBaseClassFilter] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  const { nodes: rawNodes, edges: rawEdges } = useMemo(() => ontologyToGraph(ontology), [ontology]);

  const filteredNodes = baseClassFilter
    ? rawNodes.filter((n: G6Node) => (n.data as Record<string, unknown>)?.['tag'] === baseClassFilter)
    : rawNodes;

  const filteredNodeIds = new Set(filteredNodes.map((n: G6Node) => n.id));
  const filteredEdges = rawEdges.filter((e: G6Edge) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target));

  const allBaseClasses = useMemo(
    () => Array.from(new Set(rawNodes.map((n: G6Node) => String((n.data as Record<string, unknown>)?.['tag'] || '')))),
    [rawNodes]
  );

  const getLayout = useCallback((mode: LayoutMode) => {
    switch (mode) {
      case 'force':
        return { type: 'force' as const, preventOverlap: true, linkDistance: 160, nodeStrength: -800, edgeStrength: 0.3, animated: true, alpha: 0.3, alphaDecay: 0.02 };
      case 'grid':
        return { type: 'grid' as const, cols: Math.max(4, Math.ceil(Math.sqrt(filteredNodes.length))) };
      case 'circular':
        return { type: 'circular' as const, startAngle: 0, endAngle: 2 * Math.PI, autoRadius: true };
      case 'dagre':
        return { type: 'dagre' as const, rankdir: 'TB', nodesep: 40, ranksep: 60 };
      default:
        return { type: 'force' as const, preventOverlap: true, linkDistance: 160, animated: true };
    }
  }, [filteredNodes.length]);

  const zoomIn = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    const next = Math.min(zoom + 0.2, 3);
    setZoom(next);
    g.zoomTo(next, undefined);
  }, [zoom]);

  const zoomOut = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    const next = Math.max(zoom - 0.2, 0.3);
    setZoom(next);
    g.zoomTo(next, undefined);
  }, [zoom]);

  const resetZoom = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    setZoom(1);
    g.zoomTo(1, undefined);
    g.fitCenter();
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height: h } = entry.contentRect;
      if (width > 0) setContainerSize({ w: Math.round(width), h: h > 0 ? Math.round(h) : height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [height]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || layoutMode === '3d') return;

    const currentInstance = ++instanceRef.current;
    graphRef.current?.destroy();
    graphRef.current = null;
    setLoading(true);

    const graph = new Graph({
      container: el,
      autoResize: true,
      data: { nodes: filteredNodes as G6Node[], edges: filteredEdges as G6Edge[] },
      node: {
        style: {
          size: 52,
          labelText: (d: NodeData): string => {
            const rec = d.data as Record<string, unknown> | undefined;
            const label = rec && typeof rec['label'] === 'string' ? rec['label'] : String(d.id);
            return label.length > 18 ? label.slice(0, 16) + '…' : label;
          },
          labelFill: '#1e293b',
          labelFontSize: 11,
          labelPlacement: 'bottom',
          fill: (d: NodeData): string => {
            const rec = d.data as Record<string, unknown> | undefined;
            const tag = rec && typeof rec['tag'] === 'string' ? rec['tag'] : '';
            return getNodeColor(tag);
          },
          stroke: TOKEN.colorBorderSecondary,
          lineWidth: 2,
          shadowColor: 'rgba(0,0,0,0.15)',
          shadowBlur: 6,
          shadowOffsetY: 2,
        },
        state: {
          selected: {
            fill: getNodeColor('Concept'),
            stroke: TOKEN.colorPrimary,
            lineWidth: 3,
            shadowBlur: 12,
          },
        },
      },
      edge: {
        style: {
          labelText: (d: EdgeData): string => {
            const rec = d.data as Record<string, unknown> | undefined;
            const label = rec && typeof rec['label'] === 'string' ? rec['label'] : '';
            return label.length > 20 ? label.slice(0, 18) + '…' : label;
          },
          labelFill: '#555',
          labelFontSize: 10,
          labelBackground: true,
          labelBackgroundFill: 'rgba(255,255,255,0.92)',
          labelBackgroundRadius: 3,
          labelBackgroundPadding: [2, 4],
          stroke: (d: EdgeData): string => {
            const rec = d.data as Record<string, unknown> | undefined;
            const label = rec && typeof rec['label'] === 'string' ? rec['label'] : '';
            return getEdgeColor(label);
          },
          lineWidth: 1.5,
          lineOpacity: 0.7,
          endArrow: true,
          endArrowSize: 6,
        },
        state: {
          selected: {
            stroke: '#e74c3c',
            lineWidth: 2.5,
            lineOpacity: 1,
          },
        },
      },
      layout: getLayout(layoutMode),
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    });

    graph.on(NodeEvent.CLICK, (evt: IElementEvent) => {
      const nodeId = String((evt.target as { id?: string | number }).id ?? '');
      if (!nodeId) return;
      const nodeData = graph.getNodeData(nodeId) as Record<string, unknown> | undefined;
      const label = nodeData && typeof nodeData['label'] === 'string' ? nodeData['label'] : nodeId;
      const tag = nodeData && typeof nodeData['tag'] === 'string' ? nodeData['tag'] : '';
      const description = nodeData && typeof nodeData['description'] === 'string' ? nodeData['description'] : '';

      const outgoing = filteredEdges
        .filter((e: G6Edge) => e.source === nodeId)
        .map((e: G6Edge) => ({ label: String(e.data?.['label'] || ''), target: e.target, description: String(e.data?.['description'] || '') }));

      const incoming = filteredEdges
        .filter((e: G6Edge) => e.target === nodeId)
        .map((e: G6Edge) => ({ label: String(e.data?.['label'] || ''), source: e.source, description: String(e.data?.['description'] || '') }));

      setSelectedNode({ id: nodeId, label, baseClass: tag, description, outgoing, incoming });
      setDrawerOpen(true);
    });

    graph.on(CanvasEvent.CLICK, () => {
      setDrawerOpen(false);
      setSelectedNode(null);
    });

    const silentRender = async (g: Graph) => {
      const orig = console.error;
      console.error = () => {};
      try { await g.render(); } catch { /* destroyed */ }
      finally { console.error = orig; }
    };

    silentRender(graph).then(() => {
      if (instanceRef.current !== currentInstance) return;
      graph.fitCenter();
      graphRef.current = graph;
    });

    setLoading(false);

    return () => {
      if (instanceRef.current === currentInstance) {
        instanceRef.current = -1;
        graphRef.current = null;
        graph.destroy();
      }
    };
  }, [ontology, layoutMode, filteredNodes, filteredEdges, getLayout]);

  useEffect(() => {
    const g = graphRef.current;
    if (!g || layoutMode === '3d') return;
    g.setLayout(getLayout(layoutMode));
    g.render().catch(() => {});
  }, [layoutMode, getLayout]);

  const graph3dNodes = useMemo(() => filteredNodes.map((n: G6Node) => {
    const d = n.data as Record<string, unknown>;
    return {
      id: n.id,
      label: typeof d?.['label'] === 'string' ? d['label'] : n.id,
      type: typeof d?.['tag'] === 'string' ? d['tag'] : '',
    };
  }), [filteredNodes]);

  const graph3dEdges = useMemo(() => filteredEdges.map((e: G6Edge) => ({
    source: e.source,
    target: e.target,
    label: typeof e.data?.['label'] === 'string' ? e.data['label'] : '',
  })), [filteredEdges]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 8 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
        padding: '4px 8px', background: '#f1f5f9', borderRadius: 8,
        border: '1px solid #cbd5e1', boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
      }}>
        <Segmented
          value={layoutMode}
          onChange={v => setLayoutMode(v as LayoutMode)}
          options={[
            { label: '力導圖', value: 'force' },
            { label: '網格', value: 'grid' },
            { label: '環形', value: 'circular' },
            { label: 'Dagre', value: 'dagre' },
            { label: '3D', value: '3d' },
          ]}
        />

        <Divider orientation="vertical" style={{ margin: '0 4px', height: 20 }} />

        <Button size="small" icon={<ZoomOutOutlined />} onClick={zoomOut} />
        <Text style={{ fontSize: 12, minWidth: 36, textAlign: 'center', color: TOKEN.colorTextSecondary }}>
          {Math.round(zoom * 100)}%
        </Text>
        <Button size="small" icon={<ZoomInOutlined />} onClick={zoomIn} />
        <Button size="small" icon={<ReloadOutlined />} onClick={resetZoom} />

        <Divider orientation="vertical" style={{ margin: '0 4px', height: 20 }} />

        <Text style={{ fontSize: 12, color: TOKEN.colorTextSecondary }}>篩選：</Text>
        {allBaseClasses.map(bc => (
          <Button
            key={bc} size="small"
            type={baseClassFilter === bc ? 'primary' : 'default'}
            onClick={() => setBaseClassFilter(baseClassFilter === bc ? null : bc)}
          >
            <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: getNodeColor(bc), marginRight: 4 }} />
            {BASE_CLASS_LABELS[bc] || bc}
          </Button>
        ))}
        {baseClassFilter && (
          <Button size="small" danger onClick={() => setBaseClassFilter(null)}>清除</Button>
        )}

        <Button size="small" icon={<InfoCircleOutlined />} onClick={() => setHelpOpen(true)} title="圖譜說明" />

        <Text style={{ fontSize: 11, color: TOKEN.colorTextSecondary, marginLeft: 'auto' }}>
          {filteredNodes.length} 節點 / {filteredEdges.length} 邊
        </Text>
      </div>

      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          {loading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(255,255,255,0.7)', zIndex: 10 }}>
              <Spin />
            </div>
          )}

        {layoutMode === '3d' ? (
          <KBGraph3DPanel
            nodes={graph3dNodes as { id: string; label: string; type: string }[]}
            edges={graph3dEdges as { source: string; target: string; label: string }[]}
            width={containerSize.w}
            height={containerSize.h}
            onNodeSelect={(nodeId: string | null) => {
              if (!nodeId) { setDrawerOpen(false); return; }
              const n = filteredNodes.find((n: G6Node) => n.id === nodeId);
              if (!n) return;
              const nodeData = n.data as Record<string, unknown>;
              const outgoing = filteredEdges.filter((e: G6Edge) => e.source === nodeId).map((e: G6Edge) => ({ label: String(e.data?.['label'] || ''), target: e.target, description: String(e.data?.['description'] || '') }));
              const incoming = filteredEdges.filter((e: G6Edge) => e.target === nodeId).map((e: G6Edge) => ({ label: String(e.data?.['label'] || ''), source: e.source, description: String(e.data?.['description'] || '') }));
              setSelectedNode({ id: nodeId, label: String(nodeData['label'] || nodeId), baseClass: String(nodeData['tag'] || ''), description: String(nodeData['description'] || ''), outgoing, incoming });
              setDrawerOpen(true);
            }}
          />
        ) : (
          <div
            ref={containerRef}
            style={{
              width: '100%', height: '100%', borderRadius: TOKEN.borderRadiusLG,
              border: '1px solid #e2e8f0', background: '#ffffff',
            }}
          />
        )}

        <div style={{
          position: 'absolute', bottom: 8, left: 8,
          background: 'rgba(255,255,255,0.92)', borderRadius: 6, padding: '6px 10px',
          border: `1px solid ${TOKEN.colorBorderSecondary}`, maxWidth: 160,
        }}>
          <Text style={{ fontSize: 10, color: TOKEN.colorTextSecondary, display: 'block', marginBottom: 4 }}>實體類別</Text>
          {allBaseClasses.map(bc => (
            <div key={bc} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: getNodeColor(bc), flexShrink: 0, display: 'inline-block' }} />
              <Text style={{ fontSize: 10, color: TOKEN.colorTextSecondary }}>{BASE_CLASS_LABELS[bc] || bc}</Text>
            </div>
          ))}
        </div>
      </div>

      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Tag color={getNodeColor(selectedNode?.baseClass || '')} style={{ margin: 0 }}>
              {BASE_CLASS_LABELS[selectedNode?.baseClass || ''] || selectedNode?.baseClass}
            </Tag>
            <Text strong>{selectedNode?.label}</Text>
          </div>
        }
        placement="right"
        styles={{ wrapper: { width: 360 } }}
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setSelectedNode(null); }}
      >
        {selectedNode && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="實體名稱">
                <Text code style={{ fontSize: 12 }}>{selectedNode.label}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="基礎類別">
                <Tag color={getNodeColor(selectedNode.baseClass)}>{selectedNode.baseClass}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="說明">
                <Text style={{ fontSize: 12 }}>{selectedNode.description}</Text>
              </Descriptions.Item>
            </Descriptions>

            {selectedNode.outgoing.length > 0 && (
              <>
                <Divider style={{ margin: '4px 0' }}>向外關係 ({selectedNode.outgoing.length})</Divider>
                {selectedNode.outgoing.map((e, i) => (
                  <div key={i} style={{ marginBottom: 8, padding: '6px 8px', background: '#f1f5f9', borderRadius: 6, border: `1px solid ${TOKEN.colorBorderSecondary}` }}>
                    <Text style={{ fontSize: 11, color: TOKEN.colorPrimary }}>{e.label}</Text>
                    <Text style={{ fontSize: 11, color: TOKEN.colorTextSecondary, display: 'block' }}>→ {e.target}</Text>
                    <Text style={{ fontSize: 10, color: TOKEN.colorTextSecondary, display: 'block' }}>{e.description}</Text>
                  </div>
                ))}
              </>
            )}

            {selectedNode.incoming.length > 0 && (
              <>
                <Divider style={{ margin: '4px 0' }}>向內關係 ({selectedNode.incoming.length})</Divider>
                {selectedNode.incoming.map((e, i) => (
                  <div key={i} style={{ marginBottom: 8, padding: '6px 8px', background: '#f1f5f9', borderRadius: 6, border: `1px solid ${TOKEN.colorBorderSecondary}` }}>
                    <Text style={{ fontSize: 11, color: TOKEN.colorPrimary }}>{e.label}</Text>
                    <Text style={{ fontSize: 11, color: TOKEN.colorTextSecondary, display: 'block' }}>{e.source} →</Text>
                    <Text style={{ fontSize: 10, color: TOKEN.colorTextSecondary, display: 'block' }}>{e.description}</Text>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </Drawer>

      <Modal
        title="圖譜視圖說明"
        open={helpOpen}
        onCancel={() => setHelpOpen(false)}
        onOk={() => setHelpOpen(false)}
        okText="關閉"
        width={560}
        styles={{ body: { maxHeight: '65vh', overflow: 'auto', padding: '16px 24px' } }}
      >
        <Markdown>
          {`## 佈局模式

| 佈局 | 說明 |
|------|------|
| **力導圖（Force）** | 節點互相排斥，邊像彈簧連接，自然拉開。適合看不出明顯階層結構的圖，佈局自動平衡。 |
| **網格（Grid）** | 節點整齊排列成網格狀。適合節點數量多、需要快速掃描所有節點的場景。 |
| **環形（Circular）** | 節點沿圓周均勻分布，邊為弦。適合強調節點間的相對關係而非結構層次。 |
| **Dagre** | 有向無環圖專用，由上而下（TB）或由左至右（LR）分層排列。**最適合本體論**，清晰呈現 Domain → Major → Entity 的繼承與包含關係。 |
| **3D 力導圖** | Three.js 驅動的 3D 力導向圖，可拖轉查看立體結構。適合節點豐富、關係複雜的圖。 |

## 節點顏色

| 基礎類別 | 顏色 | 說明 |
|---------|------|------|
| Concept | 藍色 | 抽象概念、原則、理論 |
| Document | 綠色 | 文件、規格、報告 |
| Process | 黃色 | 流程、步驟、方法論 |
| Agent | 紫色 | 主體、角色、團隊 |
| Requirement | 粉色 | 需求、功能約束 |
| Tool | 青色 | 工具、系統、平台 |
| Event | 橙色 | 事件、觸發、里程碑 |
| Metadata | 靛色 | 元數據、標籤、分類 |

## 操作說明

- **點擊節點**：右側浮出該實體的詳細資訊（名稱、類別、描述、向內/向外關係）
- **縮放**：使用工具列的 +/- 按鈕，或滾輪
- **拖曳節點**：按住拖動可自訂位置
- **篩選**：點擊基礎類別按鈕可只看特定類別的實體
- **佈局切換**：隨時切換不同佈局，圖形即時更新`}
        </Markdown>
      </Modal>
    </div>
  );
}
