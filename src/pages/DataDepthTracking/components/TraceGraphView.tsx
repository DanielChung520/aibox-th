/**
 * @file        追蹤結果圖譜視圖
 * @description 使用 G6 v5 渲染追蹤結果的互動圖譜：節點 = 記錄（依 table type 設色）、邊 = FK 關聯
 *              支援 zoom/pan、hover tooltip、click highlight、canvas click 清除高亮
 * @lastUpdate  2026-05-17
 * @author      Daniel Chung
 * @version     1.0.0
 */
import { useRef, useEffect, useCallback } from 'react';
import { Empty, Spin } from 'antd';
import { Graph } from '@antv/g6';
import type { NodeData } from '@antv/g6';
import {
  buildG6NodeConfig, buildG6EdgeConfig, getLayout,
  hashColor, NODE_COLORS, ROOT_NODE_COLOR, getNodeDisplayLabel,
} from '../../data-agent/schemaGraphUtils';
import type { RecordTraceNode, RecordTraceEdge } from '../../../services/dataAgentApi_types';

export interface TraceGraphViewProps {
  /** 追蹤結果節點（記錄） */
  nodes: RecordTraceNode[];
  /** 追蹤結果邊（FK 關聯） */
  edges: RecordTraceEdge[];
  /** 根記錄的 ragic_id（用於 root 節點特殊標色，可選） */
  rootRagicId?: string;
  /** 載入中狀態 */
  loading: boolean;
  /** 點擊節點回呼（供 parent 同步表格等） */
  onNodeClick?: (nodeId: string) => void;
}

const absCenter: React.CSSProperties = {
  position: 'absolute', inset: 0,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};

const tooltipStyle: React.CSSProperties = {
  position: 'absolute',
  display: 'none',
  pointerEvents: 'none',
  zIndex: 100,
  background: '#fff',
  border: '1px solid #e8e8e8',
  borderRadius: 6,
  padding: '8px 12px',
  boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
  fontSize: 12,
  lineHeight: 1.5,
  maxWidth: 300,
};

export default function TraceGraphView({
  nodes, edges, rootRagicId, loading, onNodeClick,
}: TraceGraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const onNodeClickRef = useRef(onNodeClick);
  useEffect(() => { onNodeClickRef.current = onNodeClick; }, [onNodeClick]);

  const destroyG6 = useCallback(() => {
    graphRef.current?.destroy();
    graphRef.current = null;
  }, []);

  const clearHighlight = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    const model = g.getData();
    const stateMap: Record<string, string[]> = {};
    for (const n of model.nodes) stateMap[n.id] = [];
    for (const e of model.edges) { if (e.id) stateMap[e.id] = []; }
    g.setElementState(stateMap);
  }, []);

  const handleNodeClick = useCallback((nodeId: string) => {
    onNodeClickRef.current?.(nodeId);

    const g = graphRef.current;
    if (!g) return;

    const model = g.getData();
    const stateMap: Record<string, string[]> = {};

    const connected = new Set<string>();
    connected.add(nodeId);
    for (const e of model.edges) {
      if (e.source === nodeId) connected.add(e.target);
      if (e.target === nodeId) connected.add(e.source);
    }

    for (const n of model.nodes) {
      stateMap[n.id] = connected.has(n.id) ? ['highlight'] : ['inactive'];
    }
    for (const e of model.edges) {
      if (e.id) {
        stateMap[e.id] = (e.source === nodeId || e.target === nodeId)
          ? ['highlight']
          : ['inactive'];
      }
    }
    g.setElementState(stateMap);
  }, []);

  useEffect(() => {
    if (loading || nodes.length === 0) return;

    destroyG6();

    const container = containerRef.current;
    if (!container) return;

    const g6Nodes = nodes.map(n => ({
      id: n.ragic_id,
      data: {
        label: getNodeDisplayLabel(n),
        table_name: n.table_name,
        table_key: n.table_key,
        isRoot: n.ragic_id === rootRagicId,
      },
    }));

    const g6Edges = edges.map(e => ({
      id: `${e.from_ragic_id}→${e.to_ragic_id}`,
      source: e.from_ragic_id,
      target: e.to_ragic_id,
      data: { label: e.via_field_name },
    }));

    const graph = new Graph({
      container,
      autoResize: true,
      data: { nodes: g6Nodes, edges: g6Edges },
      node: buildTraceNodeConfig(),
      edge: buildG6EdgeConfig(),
      layout: getLayout('force'),
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    });

    graphRef.current = graph;
    graph.render().catch(() => {});

    graph.on('node:click', (event: unknown) => {
      const evt = event as { target?: { id?: string } };
      const nid = evt.target?.id;
      if (!nid) return;
      handleNodeClick(nid);
    });

    graph.on('canvas:click', () => clearHighlight());

    const tipEl = tooltipRef.current;
    if (tipEl) {
      graph.on('node:pointerenter', (event: unknown) => {
        const evt = event as { target?: { id?: string } };
        const nid = evt.target?.id;
        if (!nid) return;
        const nd = nodes.find(n => n.ragic_id === nid);
        if (!nd) return;

        const fieldEntries = Object.entries(nd.fields || {})
          .filter(([, v]) => v != null && String(v).trim())
          .slice(0, 5);
        const fieldHtml = fieldEntries.length
          ? fieldEntries
            .map(([k, v]) =>
              `<div style="display:flex;justify-content:space-between;gap:12px">`
              + `<span style="color:#64748b;white-space:nowrap">${k}</span>`
              + `<span style="font-weight:500;text-align:right;color:#1e293b">${String(v).substring(0, 40)}</span>`
              + `</div>`
            )
            .join('')
          : '';

        tipEl.innerHTML = `
          <div style="font-weight:600;margin-bottom:2px;color:#0f172a">${nd.table_name}</div>
          ${fieldHtml ? `<div style="margin-bottom:2px;border-top:1px solid #f1f5f9;padding-top:4px">${fieldHtml}</div>` : ''}
          <div style="font-size:11px;color:#94a3b8;margin-top:2px">ID: ${nid}</div>
        `;
        tipEl.style.display = 'block';
      });

      graph.on('node:pointermove', (event: unknown) => {
        const evt = event as { canvas?: { x: number; y: number } };
        if (!evt.canvas) return;
        const tipW = tipEl.offsetWidth;
        const tipH = tipEl.offsetHeight;
        const cw = container.offsetWidth;
        const ch = container.offsetHeight;
        let left = evt.canvas.x + 15;
        let top = evt.canvas.y - tipH / 2;
        if (left + tipW > cw) left = evt.canvas.x - tipW - 10;
        if (top < 4) top = 4;
        if (top + tipH > ch) top = ch - tipH - 4;
        tipEl.style.left = `${left}px`;
        tipEl.style.top = `${top}px`;
      });

      graph.on('node:pointerleave', () => { tipEl.style.display = 'none'; });
    }

    return destroyG6;
  }, [nodes, edges, loading, rootRagicId, destroyG6, handleNodeClick, clearHighlight]);

  const hasData = nodes.length > 0;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: 400 }}>
      {loading && (
        <div style={{ ...absCenter, zIndex: 10, background: 'rgba(255,255,255,0.65)' }}>
          <Spin description="載入追蹤資料..." />
        </div>
      )}
      {!loading && !hasData && (
        <div style={absCenter}>
          <Empty description="尚無追蹤結果" />
        </div>
      )}
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', display: hasData ? 'block' : 'none' }}
      />
      <div ref={tooltipRef} style={tooltipStyle} />
    </div>
  );
}

function buildTraceNodeConfig() {
  const base = buildG6NodeConfig();
  return {
    ...base,
    style: {
      ...base.style,
      size: 28,
      fill: (d: NodeData) => {
        const rec = d.data as Record<string, unknown> | undefined;
        if (rec?.['isRoot']) return ROOT_NODE_COLOR;
        if (typeof rec?.['table_name'] === 'string') return hashColor(rec['table_name'] as string, NODE_COLORS);
        return hashColor(String(d.id), NODE_COLORS);
      },
    },
    state: {
      highlight: {
        stroke: ROOT_NODE_COLOR, lineWidth: 3,
        halo: true, haloStroke: ROOT_NODE_COLOR, haloLineWidth: 6,
      },
      inactive: {
        fillOpacity: 0.15, strokeOpacity: 0.15, labelOpacity: 0.15,
      },
    },
  };
}
