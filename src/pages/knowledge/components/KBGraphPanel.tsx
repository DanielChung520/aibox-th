/**
 * @file        知識庫圖譜面板元件
 * @description 使用 @antv/g6 v5 力導向圖視覺化知識圖譜節點與關聯
 * @lastUpdate  2026-04-08 11:04:46
 * @author      Daniel Chung
 * @version     2.4.0
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { Empty, Spin, Alert, Typography, Button, message, Segmented, Tooltip } from 'antd';
import { Graph, NodeEvent, CanvasEvent } from '@antv/g6';
import type { IElementEvent, IPointerEvent, NodeData, EdgeData } from '@antv/g6';
import { ReloadOutlined, ZoomInOutlined, ZoomOutOutlined, SearchOutlined, StopOutlined } from '@ant-design/icons';
import { findShortestPath } from '@antv/algorithm';
import { knowledgeApi, GraphNode, GraphEdge } from '../../../services/api';
import KBGraph3DPanel from './KBGraph3DPanel';

const { Text } = Typography;
type LayoutMode = 'force' | 'grid' | 'circular' | '3d';

const NODE_COLOR_PALETTE = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

const getNodeColor = (type: string): string => {
  let hash = 0;
  for (let i = 0; i < type.length; i++) {
    hash = type.charCodeAt(i) + ((hash << 5) - hash);
  }
  return NODE_COLOR_PALETTE[Math.abs(hash) % NODE_COLOR_PALETTE.length];
};

const EDGE_COLOR_PALETTE = [
  '#e74c3c', '#2ecc71', '#3498db', '#9b59b6', '#f39c12',
  '#1abc9c', '#e91e63', '#00bcd4', '#ff5722', '#8bc34a',
  '#673ab7', '#ffc107', '#607d8b', '#ff9800', '#4caf50',
  '#3f51b5', '#009688', '#f06292', '#00e676', '#ffab40',
  '#536dfe', '#76ff03', '#d500f9', '#ff1744', '#64ffda',
  '#ff6e40', '#69f0ae', '#7c4dff', '#ff9100', '#b2ff59',
];

const getEdgeColor = (label: string): string => {
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = label.charCodeAt(i) + ((hash << 5) - hash);
  }
  return EDGE_COLOR_PALETTE[Math.abs(hash) % EDGE_COLOR_PALETTE.length];
};

interface KBGraphPanelProps {
  fileId: string;
  graphStatus?: string;
  onNodeSelect?: (nodeId: string | null) => void;
  onGraphReady?: (graph: Graph) => void;
  onDataLoaded?: (nodes: GraphNode[], edges: GraphEdge[]) => void;
}

type G6Node = {
  id: string;
  data?: Record<string, unknown>;
  [key: string]: unknown;
};

type G6Edge = {
  source: string;
  target: string;
  data?: Record<string, unknown>;
  [key: string]: unknown;
};

const TOKEN = {
  colorPrimary: '#3b82f6',
  colorText: '#f1f5f9',
  colorTextSecondary: '#94a3b8',
  colorBorder: '#334155',
  colorBorderSecondary: '#475569',
  colorPrimaryActive: '#60a5fa',
  colorBgContainer: '#1e293b',
  borderRadiusLG: 8,
  padding: 16,
  paddingXS: 4,
};

export default function KBGraphPanel({ fileId, graphStatus, onNodeSelect, onGraphReady, onDataLoaded }: KBGraphPanelProps) {
  const token = TOKEN;
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasData, setHasData] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('force');
  const [rawNodes, setRawNodes] = useState<GraphNode[]>([]);
  const [rawEdges, setRawEdges] = useState<GraphEdge[]>([]);
  const [containerSize, setContainerSize] = useState({ w: 800, h: 600 });
  const [pathSearchMode, setPathSearchMode] = useState(false);
  const instanceRef = useRef(0);
  const zoomRef = useRef(1);
  const graphDataRef = useRef<{ nodes: G6Node[]; edges: G6Edge[] }>({ nodes: [], edges: [] });

  const getLayout = useCallback((mode: LayoutMode) => {
    switch (mode) {
      case 'force':
        return { type: 'force' as const, preventOverlap: true, linkDistance: 150, animated: true };
      case 'grid':
        return { type: 'grid' as const, cols: 6 };
      case 'circular':
        return { type: 'circular' as const, startAngle: 0, endAngle: 2 * Math.PI, autoRadius: true };
      default:
        return { type: 'force' as const, preventOverlap: true, linkDistance: 150, animated: true };
    }
  }, []);

  const handleLayoutChange = useCallback((mode: LayoutMode) => {
    setLayoutMode(mode);
  }, []);

  const zoomIn = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    const current = zoomRef.current;
    const next = Math.min(current + 0.15, 3);
    zoomRef.current = next;
    g.zoomTo(next, undefined);
  }, []);

  const zoomOut = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    const current = zoomRef.current;
    const next = Math.max(current - 0.15, 0.2);
    zoomRef.current = next;
    g.zoomTo(next, undefined);
  }, []);

  const resetZoom = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    zoomRef.current = 1;
    g.zoomTo(1, undefined);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setContainerSize({ w: Math.round(width), h: Math.round(height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (layoutMode === '3d') return;
    const g = graphRef.current;
    if (!g) return;
    g.setLayout(getLayout(layoutMode));
    g.render().catch(() => { });
  }, [layoutMode, getLayout]);

  // Resize graph when container size changes (e.g., when right panel collapses)
  useEffect(() => {
    if (layoutMode === '3d') return;
    const g = graphRef.current;
    if (!g) return;
    g.resize(containerSize.w, containerSize.h);
  }, [containerSize, layoutMode]);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      await knowledgeApi.regenerateGraph(fileId);
      message.success('已重新提交圖譜生成任務');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } } };
      message.error(e.response?.data?.message || '重新圖譜失敗');
    } finally {
      setRegenerating(false);
    }
  };

  useEffect(() => {
    if (!containerRef.current) return;

    const currentInstance = ++instanceRef.current;
    graphRef.current?.destroy();
    graphRef.current = null;
    setLoading(true);
    setError(null);
    setHasData(false);

    const graph = new Graph({
      container: containerRef.current,
      autoResize: true,
      data: { nodes: [], edges: [] },
      node: {
        style: {
          size: 36,
          labelText: (d: NodeData): string => {
            const rec = d.data as Record<string, unknown> | undefined;
            return rec && typeof rec['label'] === 'string' ? rec['label'] : String(d.id);
          },
          labelFill: '#1e293b',
          labelFontSize: 12,
          labelPlacement: 'bottom',
          fill: (d: NodeData): string => {
            const rec = d.data as Record<string, unknown> | undefined;
            const type = rec && typeof rec['type'] === 'string' ? rec['type'] : '';
            return getNodeColor(type);
          },
          stroke: token.colorBorder,
          lineWidth: 1,
        },
        state: {
          selected: {
            fill: token.colorPrimaryActive,
            stroke: token.colorPrimary,
            lineWidth: 2,
          },
          highlight: {
            fill: '#fbbf24',
            stroke: '#f59e0b',
            lineWidth: 3,
            labelFill: '#1e293b',
            labelFontSize: 14,
            size: 44,
          },
          inactive: {
            fillOpacity: 0.15,
            strokeOpacity: 0.15,
            labelOpacity: 0.15,
          },
        },
      },
      edge: {
        style: {
          labelText: (d: EdgeData): string => {
            const rec = d.data as Record<string, unknown> | undefined;
            return rec && typeof rec['label'] === 'string' ? rec['label'] : '';
          },
          labelFill: '#555',
          labelFontSize: 12,
          labelBackground: true,
          labelBackgroundFill: 'rgba(255,255,255,0.85)',
          labelBackgroundRadius: 3,
          labelBackgroundPadding: [2, 4],
          stroke: (d: EdgeData): string => {
            const rec = d.data as Record<string, unknown> | undefined;
            const label = rec && typeof rec['label'] === 'string' ? rec['label'] : '';
            return getEdgeColor(label);
          },
          lineWidth: 2,
          lineOpacity: 0.85,
          endArrow: true,
        },
        state: {
          selected: {
            stroke: '#e74c3c',
            lineWidth: 2,
            lineOpacity: 1,
          },
          highlight: {
            stroke: '#fbbf24',
            lineWidth: 4,
            lineOpacity: 1,
          },
          inactive: {
            lineOpacity: 0.08,
            labelOpacity: 0.1,
          },
        },
      },
      layout: getLayout(layoutMode),
      behaviors: [
        'drag-canvas',
        'zoom-canvas',
        'drag-element',
        {
          type: 'click-select',
          multiple: true,
          trigger: ['shift'],
          state: 'selected',
          degree: 0,
          unselectedState: undefined,
          neighborState: undefined,
          animation: false,
        },
      ],
    });

    graph.on(NodeEvent.CLICK, (evt: IElementEvent) => {
      onNodeSelect?.(evt.target.id);
    });

    graph.on(CanvasEvent.CLICK, (_evt: IPointerEvent) => {
      onNodeSelect?.(null);
    });

    const silentRender = async (g: Graph) => {
      const origError = console.error;
      console.error = () => { };
      try {
        await g.render();
      } catch {
        // destroyed during render — ignore
      } finally {
        console.error = origError;
      }
    };

    silentRender(graph).then(() => {
      if (instanceRef.current !== currentInstance) return;
      onGraphReady?.(graph);
    }).catch(() => { });

    graphRef.current = graph;

    const fetchGraph = async () => {
      try {
        const res = await knowledgeApi.getGraph(fileId);
        const data = res.data.data;
        if (instanceRef.current !== currentInstance) return;
        if (!data || (!data.nodes?.length && !data.edges?.length)) {
          setHasData(false);
          setLoading(false);
          return;
        }
        const nodes: G6Node[] = (data.nodes || []).map((n: GraphNode) => ({
          id: n.id,
          data: { label: n.label, type: n.type },
        }));
        const edges: G6Edge[] = (data.edges || []).map((e: GraphEdge) => ({
          id: `${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          data: { label: e.label },
        }));
        graphDataRef.current = { nodes, edges };
        if (instanceRef.current !== currentInstance) return;
        graph.setData({ nodes, edges });
        await silentRender(graph);
        if (instanceRef.current !== currentInstance) return;
        onDataLoaded?.(data.nodes || [], data.edges || []);
        setRawNodes(data.nodes || []);
        setRawEdges(data.edges || []);
        setHasData(true);
      } catch (err: unknown) {
        const e = err as { response?: { data?: { message?: string } } };
        if (instanceRef.current === currentInstance) {
          setError(e.response?.data?.message || '載入圖譜失敗');
        }
      } finally {
        if (instanceRef.current === currentInstance) {
          setLoading(false);
        }
      }
    };

    fetchGraph();

    return () => {
      if (instanceRef.current === currentInstance) {
        instanceRef.current = -1;
        graphRef.current = null;
        graph.destroy();
      }
    };
  }, [fileId, onNodeSelect, onGraphReady, onDataLoaded, token]);

  const resetElementStates = async () => {
    const g = graphRef.current;
    if (!g) return;

    const { nodes = [], edges = [] } = g.getData();
    const stateMap: Record<string, string[]> = {};
    for (const n of nodes) {
      stateMap[String(n.id)] = [];
    }
    for (const e of edges) {
      const eid = (e as { id?: string }).id;
      if (eid) stateMap[String(eid)] = [];
    }
    g.setElementState(stateMap);
    await g.draw();
  };

  const searchShortestPath = async () => {
    const g = graphRef.current;
    if (!g) return;

    // 確保 click-select 狀態已落地
    await g.draw();

    const selectedNodes = g.getElementDataByState('node', 'selected');
    if (selectedNodes.length !== 2) {
      message.warning('請選擇兩個節點（Shift+點擊）');
      return;
    }
    const [source, target] = selectedNodes;
    const { length, path: rawPath } = findShortestPath(graphDataRef.current, source.id, target.id);
    const path = rawPath as string[];
    if (length === Infinity) {
      message.warning('未找到路徑');
      return;
    }
    const pathSet = new Set(path);

    const pathEdgeIds = new Set<string>();
    for (const edge of graphDataRef.current.edges) {
      const src = String(edge.source);
      const tgt = String(edge.target);
      const srcIdx = path.indexOf(src);
      const tgtIdx = path.indexOf(tgt);
      if (srcIdx !== -1 && tgtIdx !== -1 && Math.abs(srcIdx - tgtIdx) === 1) {
        pathEdgeIds.add(String(edge.id));
      }
    }

    const states: Record<string, string[]> = {};
    for (const node of graphDataRef.current.nodes) {
      const id = String(node.id);
      states[id] = pathSet.has(id) ? [] : ['inactive'];
    }
    for (const edge of graphDataRef.current.edges) {
      const id = String(edge.id);
      states[id] = pathEdgeIds.has(id) ? [] : ['inactive'];
    }
    g.setElementState(states);
    await g.draw();

    for (const id of [...pathEdgeIds]) g.frontElement(id);
    for (const id of path) g.frontElement(id);

    message.success(`路徑長度: ${length} 步`);
  };

  const togglePathSearchMode = () => {
    if (pathSearchMode) {
      resetElementStates();
      setPathSearchMode(false);
    } else {
      setPathSearchMode(true);
      message.info('Shift+點擊選擇起點和終點，再點「查詢路徑」');
    }
  };

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        borderRadius: token.borderRadiusLG,
        border: `1px solid ${token.colorBorderSecondary}`,
        backgroundColor: '#ffffff',
        position: 'relative',
      }}
    >
      {loading && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(255,255,255,0.8)', zIndex: 10,
        }}>
          <Spin description="載入圖譜..." />
        </div>
      )}
      {!loading && error && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(255,255,255,0.9)', zIndex: 10,
        }}>
          <Alert type="error" title={error} showIcon style={{ maxWidth: 300 }} />
        </div>
      )}
      {!loading && !error && !hasData && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          zIndex: 10, gap: token.padding,
        }}>
          <Empty
            description={
              <Text style={{ color: token.colorTextSecondary }}>
                {graphStatus === 'completed' ? '圖譜未提取到實體與關係' : '圖譜待生成'}
              </Text>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
          {graphStatus && ['pending', 'processing', 'queued'].includes(graphStatus) ? (
            <Text type="secondary">圖譜生成中...</Text>
          ) : (
            <Button icon={<ReloadOutlined />} loading={regenerating} onClick={handleRegenerate}>
              重新圖譜
            </Button>
          )}
        </div>
      )}
      {layoutMode === '3d' && hasData && (
        <div style={{ position: 'absolute', inset: 0, zIndex: 2 }}>
          <KBGraph3DPanel
            nodes={rawNodes}
            edges={rawEdges}
            width={containerSize.w}
            height={containerSize.h}
            onNodeSelect={onNodeSelect}
          />
        </div>
      )}
      <div style={{
        position: 'absolute',
        top: token.paddingXS,
        right: token.paddingXS,
        zIndex: 5,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        alignItems: 'flex-end',
        backgroundColor: 'rgba(255,255,255,0.9)',
        borderRadius: 8,
        padding: 6,
      }}>
        {layoutMode !== '3d' && (
          <div style={{ display: 'flex', gap: 4 }}>
            <Button size="small" icon={<ZoomOutOutlined />} onClick={zoomOut} title="縮小" />
            <Button size="small" icon={<ZoomInOutlined />} onClick={zoomIn} title="放大" />
            <Button size="small" onClick={resetZoom} title="重置視角" style={{ fontSize: 10 }}>1:1</Button>
          </div>
        )}
        {hasData && (
          <div style={{ display: 'flex', gap: 4 }}>
            <Tooltip title={pathSearchMode ? '退出路徑搜尋' : '路徑搜尋（Shift+點擊選節點）'}>
              <Button
                size="small"
                icon={pathSearchMode ? <StopOutlined /> : <SearchOutlined />}
                onClick={togglePathSearchMode}
                type={pathSearchMode ? 'primary' : 'default'}
                style={{ fontSize: 10 }}
              >
                {pathSearchMode ? '退出' : '路徑'}
              </Button>
            </Tooltip>
            {pathSearchMode && (
              <Button
                size="small"
                icon={<SearchOutlined />}
                onClick={searchShortestPath}
                type="primary"
                style={{ fontSize: 10 }}
              >
                查詢
              </Button>
            )}
          </div>
        )}
        <Segmented
          value={layoutMode}
          onChange={(v) => handleLayoutChange(v as LayoutMode)}
          options={[
            { label: '力導圖', value: 'force' },
            { label: '網格', value: 'grid' },
            { label: '環形', value: 'circular' },
            { label: '3D', value: '3d' },
          ]}
          size="small"
        />
      </div>
    </div>
  );
}
