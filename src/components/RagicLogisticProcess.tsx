/**
 * @file        Ragic 採購流程圖元件
 * @description 使用 G6 呈現採購-訂單-生產流程圖
 * @lastUpdate  2026-04-09 13:58:25
 * @author      Daniel Chung
 * @version     1.3.0
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Card, Col, Empty, Row, Space, Tag, Typography, theme } from 'antd';
import { CompressOutlined, EyeOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';
import { CanvasEvent, Graph, NodeEvent } from '@antv/g6';
import type { ComboData, EdgeData, IElementEvent, NodeData } from '@antv/g6';

const { Title, Text } = Typography;

type FlowRegion = 'entry' | 'upstream' | 'downstream' | 'planning' | 'production';

interface FlowNodeMeta {
  [key: string]: unknown;
  label: string;
  subtitle: string;
  table?: string;
  detail: string;
  region: FlowRegion;
  fill: string;
  stroke: string;
  opacity?: number;
  lineWidth?: number;
  shadowBlur?: number;
  shadowColor?: string;
}

interface FlowEdgeMeta {
  [key: string]: unknown;
  label?: string;
  dashed?: boolean;
  stroke?: string;
  sourcePort?: string;
  targetPort?: string;
  opacity?: number;
  lineWidth?: number;
  /** Per-edge controlPoints override (absolute coordinates) */
  controlPoints?: [number, number][];
  /** Per-edge router override; set false to disable orth routing */
  noRouter?: boolean;
}

const regionInfo: Record<
  FlowRegion,
  { title: string; color: string; description: string }
> = {
  entry: { title: '流程入口', color: 'blue', description: '主流程起點與總控入口' },
  upstream: { title: '上游流程', color: 'cyan', description: '請購、詢價、採購、收貨與退貨閉環' },
  downstream: { title: '下游流程', color: 'green', description: '報價到訂購的業務轉換' },
  planning: { title: '生產需求流程', color: 'orange', description: '生產需求、MRP、採購預算規劃' },
  production: { title: '生產製令 / 入庫', color: 'purple', description: '製令、領料、派工、檢驗與成品入庫' },
};

const NODE_HEIGHT = 104;
const GRAPH_VERTICAL_PADDING = 220;

const rawNodes: Array<{ id: string; combo?: string; style: Record<string, unknown>; data: FlowNodeMeta }> = [
  {
    id: 'entry',
    style: {
      x: 1090,
      y: -84,
      port: true,
      portR: 0,
      ports: [
        { key: 'to-pr', placement: [0.12, 1] },
        { key: 'to-quote', placement: [0.88, 1] },
        { key: 'right-center', placement: [1, 0.5] },
        { key: 'left-center', placement: [0, 0.5] },
      ],
    },
    data: {
      label: '表單成立追蹤（主）',
      subtitle: '流程總入口',
      detail: '由主流程節點分流至採購與訂單流程',
      region: 'entry',
      fill: '#f0f7ff',
      stroke: '#1677ff',
    },
  },
  {
    id: 'pr',
    combo: 'combo-upstream',
    style: {
      x: 220,
      y: 130,
      port: true,
      portR: 0,
      ports: [
        { key: 'in-top', placement: [0.5, 0] },
        { key: 'to-po', placement: [1, 0.35] },
        { key: 'to-rfq', placement: [1, 0.7] },
      ],
    },
    data: {
      label: '請購單',
      subtitle: '需求發起',
      detail: '由需求部門提出採購申請',
      region: 'upstream',
      fill: '#eef5ff',
      stroke: '#2f74ff',
    },
  },
  {
    id: 'rfq',
    combo: 'combo-upstream',
    style: {
      x: 520,
      y: 220,
      port: true,
      portR: 0,
      ports: [
        { key: 'in-left', placement: [0, 0.38] },
        { key: 'to-po', placement: [1, 0.6] },
      ],
    },
    data: {
      label: '詢價單',
      subtitle: '供應商比價',
      table: 'ERP_59',
      detail: '向供應商取得報價條件',
      region: 'upstream',
      fill: '#fff6e8',
      stroke: '#fa8c16',
    },
  },
  {
    id: 'po',
    combo: 'combo-upstream',
    style: {
      x: 830,
      y: 130,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-pr', placement: [0, 0.35] },
        { key: 'from-rfq', placement: [0, 0.5] },
        { key: 'from-budget', placement: [0, 0.35] },
        { key: 'from-so', placement: [1, 0.18] },
        { key: 'to-receive', placement: [1, 0.5] },
        { key: 'to-receive-low', placement: [1, 0.7] },
        { key: 'bottom-po-left', placement: [0.409, 1] },
        { key: 'bottom-po', placement: [0.5, 1] },
      ],
    },
    data: {
      label: '採購單（PO）',
      subtitle: '正式採購',
      table: 'ERP_13',
      detail: '採購主單，串接收貨與預算回推',
      region: 'upstream',
      fill: '#f6ffed',
      stroke: '#52c41a',
    },
  },
  {
    id: 'receive',
    combo: 'combo-upstream',
    style: {
      x: 1140,
      y: 250,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-po', placement: [0, 0.5] },
        { key: 'to-return', placement: [1, 0.35] },
        { key: 'back-po', placement: [0.2, 1] },
        { key: 'to-status', placement: [0.5, 0] },
      ],
    },
    data: {
      label: '收貨單',
      subtitle: '到貨驗收',
      table: 'ERP_15',
      detail: '確認供應商交貨與狀態回寫',
      region: 'upstream',
      fill: '#fff7e6',
      stroke: '#fa8c16',
    },
  },
  {
    id: 'return',
    combo: 'combo-upstream',
    style: {
      x: 1440,
      y: 250,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-receive', placement: [0, 0.35] },
        { key: 'back-po', placement: [0.5, 0] },
      ],
    },
    data: {
      label: '退貨 / 進貨異常',
      subtitle: '異常閉環',
      table: 'ERP_16',
      detail: '不良與多送貨物回沖採購單',
      region: 'upstream',
      fill: '#fff0f6',
      stroke: '#eb2f96',
    },
  },
  {
    id: 'quote',
    combo: 'combo-downstream',
    style: {
      x: 1760,
      y: 250,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-entry', placement: [0.5, 0] },
        { key: 'to-so', placement: [1, 0.5] },
      ],
    },
    data: {
      label: '報價憑證單',
      subtitle: '開新報價單',
      table: 'ERP_57',
      detail: '可輸出 ISO 文件與間結帳價單',
      region: 'downstream',
      fill: '#eef5ff',
      stroke: '#1677ff',
    },
  },
  {
    id: 'so',
    combo: 'combo-downstream',
    style: {
      x: 2070,
      y: 130,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-quote', placement: [0, 0.5] },
        { key: 'to-po-left', placement: [0, 0.18] },
        { key: 'to-po', placement: [0.2, 1] },
        { key: 'to-prod', placement: [0.8, 1] },
        { key: 'to-mo', placement: [0.45, 1] },
        { key: 'bottom-left', placement: [0.2, 1] },
      ],
    },
    data: {
      label: '訂購單（SO）',
      subtitle: '轉訂購單 / 自製件',
      table: 'ERP_14',
      detail: '承接客戶需求並拆分採購件 / 自製件',
      region: 'downstream',
      fill: '#f6ffed',
      stroke: '#52c41a',
    },
  },
  {
    id: 'prodDemand',
    combo: 'combo-planning',
    style: {
      x: 1630,
      y: 530,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-so', placement: [0.75, 0] },
        { key: 'to-mrp', placement: [0, 0.5] },
        { key: 'right-middle', placement: [1, 0.5] },
      ],
    },
    data: {
      label: '生產需求單',
      subtitle: '需求拆解',
      table: 'ERP_43',
      detail: '由訂購單轉入生產需求',
      region: 'planning',
      fill: '#f9f0ff',
      stroke: '#722ed1',
    },
  },
  {
    id: 'mrp',
    combo: 'combo-planning',
    style: {
      x: 1360,
      y: 530,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-prod', placement: [1, 0.5] },
        { key: 'to-budget', placement: [0, 0.5] },
      ],
    },
    data: {
      label: '物料需求單（MRP）',
      subtitle: '物料展開',
      table: 'ERP_42',
      detail: '計算原料需求與採購缺口',
      region: 'planning',
      fill: '#fff7e6',
      stroke: '#fa8c16',
    },
  },
  {
    id: 'budget',
    combo: 'combo-planning',
    style: {
      x: 1090,
      y: 530,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-mrp', placement: [1, 0.5] },
        { key: 'to-po', placement: [0, 0.25] },
        { key: 'bottom-budget', placement: [0.5, 1] },
        { key: 'left-budget', placement: [0, 0.5] },
      ],
    },
    data: {
      label: '採購預算表',
      subtitle: '預算回推採購',
      table: 'ERP_41',
      detail: '預算審核後回推正式採購',
      region: 'planning',
      fill: '#eef5ff',
      stroke: '#1677ff',
    },
  },
  {
    id: 'mo',
    combo: 'combo-production',
    style: {
      x: 2060,
      y: 820,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-so', placement: [0.5, 0.5] },
        { key: 'to-issue', placement: [0, 0.5] },
      ],
    },
    data: {
      label: '生產製令單',
      subtitle: 'P-4-P-01-05',
      table: 'ERP_44',
      detail: '製令明細與產線排程',
      region: 'production',
      fill: '#f9f0ff',
      stroke: '#722ed1',
    },
  },
  {
    id: 'issue',
    combo: 'combo-production',
    style: {
      x: 1760,
      y: 820,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-mo', placement: [1, 0.5] },
        { key: 'to-dispatch', placement: [0, 0.5] },
      ],
    },
    data: {
      label: '領料單',
      subtitle: 'P-4-P-01-04 / 03',
      table: 'ERP_46',
      detail: '依製令進行備料與領用',
      region: 'production',
      fill: '#fff7e6',
      stroke: '#fa8c16',
    },
  },
  {
    id: 'dispatch',
    combo: 'combo-production',
    style: {
      x: 1460,
      y: 820,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-issue', placement: [1, 0.5] },
        { key: 'to-report', placement: [0, 0.5] },
      ],
    },
    data: {
      label: '派工單',
      subtitle: 'P-4-P-02-03 B',
      table: 'ERP_47',
      detail: '製程管制與工序追蹤',
      region: 'production',
      fill: '#f6ffed',
      stroke: '#52c41a',
    },
  },
  {
    id: 'report',
    combo: 'combo-production',
    style: {
      x: 1160,
      y: 820,
      port: true,
      portR: 0,
      ports: [
        { key: 'from-dispatch', placement: [1, 0.5] },
        { key: 'to-fg', placement: [0, 0.5] },
      ],
    },
    data: {
      label: '報工事項',
      subtitle: '現場回報',
      detail: '領工事項與製程作業紀錄',
      region: 'production',
      fill: '#eef5ff',
      stroke: '#1677ff',
    },
  },
  {
    id: 'fg',
    combo: 'combo-production',
    style: {
      x: 860,
      y: 820,
      port: true,
      portR: 0,
      ports: [{ key: 'from-report', placement: [1, 0.5] }],
    },
    data: {
      label: '入庫 / IQC / 異常處理',
      subtitle: '成品入庫閉環',
      table: 'ERP_45 / ERP_48',
      detail: '最終檢驗、包裝檢核與不合格處理',
      region: 'production',
      fill: '#fff0f6',
      stroke: '#eb2f96',
    },
  },
];

const suggestedGraphHeight = Math.max(
  640,
  Math.ceil(
    Math.max(
      ...rawNodes.map((node) => {
        const y = typeof node.style.y === 'number' ? node.style.y : 0;
        return y + NODE_HEIGHT / 2;
      })
    ) + GRAPH_VERTICAL_PADDING
  )
);

const rawEdges: Array<{ id: string; source: string; target: string; data?: FlowEdgeMeta }> = [
  { id: 'e1', source: 'entry', target: 'pr', data: { label: '主流程 → 上游', stroke: '#7c8aa5', sourcePort: 'left-center', targetPort: 'in-top', noRouter: true, controlPoints: [[220, -32]] } },
  { id: 'e2', source: 'entry', target: 'quote', data: { label: '開新報價單', stroke: '#fa8c16', sourcePort: 'right-center', targetPort: 'from-entry', noRouter: true, controlPoints: [[1760, -32]] } },
  { id: 'e3', source: 'pr', target: 'rfq', data: { sourcePort: 'to-rfq', targetPort: 'in-left' } },
  { id: 'e4', source: 'pr', target: 'po', data: { sourcePort: 'to-po', targetPort: 'from-pr' } },
  { id: 'e5', source: 'rfq', target: 'po', data: { sourcePort: 'to-po', targetPort: 'from-rfq' } },
  { id: 'e6', source: 'po', target: 'receive', data: { sourcePort: 'bottom-po', targetPort: 'from-po' } },
  { id: 'e7', source: 'receive', target: 'return', data: { sourcePort: 'to-return', targetPort: 'from-receive' } },
  { id: 'e8', source: 'return', target: 'po', data: { dashed: true, label: '異常回寫', stroke: '#cbd5e1', sourcePort: 'back-po', targetPort: 'to-receive' } },
  { id: 'e9', source: 'receive', target: 'po', data: { dashed: true, label: '收貨狀態更新', stroke: '#cbd5e1', sourcePort: 'to-status', targetPort: 'to-receive-low' } },
  { id: 'e10', source: 'quote', target: 'so', data: { label: '轉訂購單', stroke: '#fa8c16', sourcePort: 'to-so', targetPort: 'from-quote' } },
  { id: 'e11', source: 'so', target: 'prodDemand', data: { label: '自製件', stroke: '#722ed1', sourcePort: 'bottom-left', targetPort: 'right-middle', noRouter: true, controlPoints: [[1960, 530]] } },
  { id: 'e12', source: 'prodDemand', target: 'mrp', data: { sourcePort: 'to-mrp', targetPort: 'from-prod' } },
  { id: 'e13', source: 'mrp', target: 'budget', data: { sourcePort: 'to-budget', targetPort: 'from-mrp' } },
  { id: 'e14', source: 'budget', target: 'po', data: { dashed: true, label: '預算回推採購', stroke: '#cbd5e1', sourcePort: 'left-budget', targetPort: 'bottom-po-left', noRouter: true, controlPoints: [[810, 530]] } },
  { id: 'e15', source: 'so', target: 'po', data: { label: '轉採購單（採購件）', stroke: '#52c41a', sourcePort: 'to-po-left', targetPort: 'from-so' } },
  { id: 'e16', source: 'so', target: 'mo', data: { sourcePort: 'to-mo', targetPort: 'from-so' } },
  { id: 'e17', source: 'mo', target: 'issue', data: { sourcePort: 'to-issue', targetPort: 'from-mo' } },
  { id: 'e18', source: 'issue', target: 'dispatch', data: { sourcePort: 'to-dispatch', targetPort: 'from-issue' } },
  { id: 'e19', source: 'dispatch', target: 'report', data: { sourcePort: 'to-report', targetPort: 'from-dispatch' } },
  { id: 'e20', source: 'report', target: 'fg', data: { sourcePort: 'to-fg', targetPort: 'from-report' } },
];

const rawCombos: ComboData[] = [
  {
    id: 'combo-upstream',
    data: { label: '上游流程' },
    style: {
      type: 'rect',
      padding: [44, 28, 28, 28],
      fill: '#93c5fd',
      fillOpacity: 0.16,
      stroke: '#2563eb',
      lineWidth: 4,
      lineDash: [8, 8],
      radius: 12,
      labelText: '上游流程',
      labelPlacement: 'top',
      labelOffsetY: -12,
      labelFill: '#1d4ed8',
      labelFontSize: 18,
      labelFontWeight: 700,
      labelBackground: true,
      labelBackgroundFill: 'rgba(219,234,254,0.98)',
      labelBackgroundPadding: [4, 8],
    },
  },
  {
    id: 'combo-downstream',
    data: { label: '下游流程' },
    style: {
      type: 'rect',
      padding: [44, 28, 28, 28],
      fill: '#86efac',
      fillOpacity: 0.16,
      stroke: '#16a34a',
      lineWidth: 4,
      lineDash: [8, 8],
      radius: 12,
      labelText: '下游流程',
      labelPlacement: 'top',
      labelOffsetY: -12,
      labelFill: '#15803d',
      labelFontSize: 18,
      labelFontWeight: 700,
      labelBackground: true,
      labelBackgroundFill: 'rgba(220,252,231,0.98)',
      labelBackgroundPadding: [4, 8],
    },
  },
  {
    id: 'combo-planning',
    data: { label: '生產需求流程' },
    style: {
      type: 'rect',
      padding: [44, 28, 28, 28],
      fill: '#fcd34d',
      fillOpacity: 0.18,
      stroke: '#d97706',
      lineWidth: 4,
      lineDash: [8, 8],
      radius: 12,
      labelText: '生產需求流程',
      labelPlacement: 'top',
      labelOffsetY: -12,
      labelFill: '#c2410c',
      labelFontSize: 18,
      labelFontWeight: 700,
      labelBackground: true,
      labelBackgroundFill: 'rgba(254,243,199,0.98)',
      labelBackgroundPadding: [4, 8],
    },
  },
  {
    id: 'combo-production',
    data: { label: '生產製令 / 入庫' },
    style: {
      type: 'rect',
      padding: [44, 28, 28, 28],
      fill: '#ddd6fe',
      fillOpacity: 0.14,
      stroke: '#7c3aed',
      lineWidth: 4,
      lineDash: [8, 8],
      radius: 12,
      labelText: '生產製令 / 入庫',
      labelPlacement: 'top',
      labelOffsetY: -12,
      labelFill: '#6d28d9',
      labelFontSize: 18,
      labelFontWeight: 700,
      labelBackground: true,
      labelBackgroundFill: 'rgba(243,232,255,0.98)',
      labelBackgroundPadding: [4, 8],
    },
  },
];

const DEFAULT_NODE_SHADOW_COLOR = 'rgba(15, 23, 42, 0.10)';
const SELECTED_NODE_SHADOW_COLOR = 'rgba(22, 119, 255, 0.28)';

const buildGraphData = (focusedNodeId: string | null) => {
  const relatedNodeIds = new Set<string>();
  const relatedEdgeIds = new Set<string>();
  const relatedComboIds = new Set<string>();

  if (focusedNodeId) {
    relatedNodeIds.add(focusedNodeId);

    for (const edge of rawEdges) {
      if (edge.source === focusedNodeId || edge.target === focusedNodeId) {
        relatedEdgeIds.add(edge.id);
        relatedNodeIds.add(edge.source);
        relatedNodeIds.add(edge.target);
      }
    }

    for (const node of rawNodes) {
      if (node.combo && relatedNodeIds.has(node.id)) {
        relatedComboIds.add(node.combo);
      }
    }
  }

  return {
    nodes: rawNodes.map((node) => {
      const isSelected = focusedNodeId === node.id;
      const isRelated = !focusedNodeId || relatedNodeIds.has(node.id);

      return {
        ...node,
        data: {
          ...node.data,
          stroke: isSelected ? '#1677ff' : node.data.stroke,
          opacity: isRelated ? 1 : 0.35,
          lineWidth: isSelected ? 3 : 2,
          shadowBlur: isSelected ? 26 : 18,
          shadowColor: isSelected ? SELECTED_NODE_SHADOW_COLOR : DEFAULT_NODE_SHADOW_COLOR,
        },
      };
    }),
    edges: rawEdges.map((edge) => {
      const isRelated = !focusedNodeId || relatedEdgeIds.has(edge.id);
      const highlightEdge = !!focusedNodeId && relatedEdgeIds.has(edge.id);

      const perEdgeStyle =
        edge.data?.noRouter || edge.data?.controlPoints
          ? {
            ...(edge.data.noRouter ? { router: false as const } : {}),
            ...(edge.data.controlPoints ? { controlPoints: edge.data.controlPoints } : {}),
          }
          : undefined;

      return {
        ...edge,
        data: {
          ...edge.data,
          stroke: highlightEdge ? '#1677ff' : edge.data?.stroke || '#94a3b8',
          opacity: isRelated ? 1 : 0.18,
          lineWidth: highlightEdge ? 3 : 2,
        },
        ...(perEdgeStyle ? { style: perEdgeStyle } : {}),
      };
    }),
    combos: rawCombos.map((combo) => ({
      ...combo,
      style: {
        ...((combo.style as Record<string, unknown> | undefined) || {}),
        opacity: !focusedNodeId || relatedComboIds.has(String(combo.id)) ? 1 : 0.22,
      },
    })),
  };
};

export default function RagicLogisticProcess() {
  const { token } = theme.useToken();
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const graphReadyRef = useRef(false);
  const instanceRef = useRef(0);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [containerSize, setContainerSize] = useState({ w: 1200, h: suggestedGraphHeight });
  const [zoom, setZoom] = useState(1);

  const selectedNode = useMemo(
    () => rawNodes.find((node) => node.id === selectedNodeId) ?? null,
    [selectedNodeId]
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width } = entry.contentRect;
      if (width > 0) {
        setContainerSize({ w: Math.round(width), h: suggestedGraphHeight });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const fitGraphToView = (graph: Graph) => {
    if (!graphReadyRef.current) return;
    try {
      graph.fitView();
      const currentZoom = graph.getZoom();
      if (typeof currentZoom === 'number' && Number.isFinite(currentZoom)) {
        setZoom(Number(currentZoom.toFixed(2)));
      }
    } catch {
      undefined;
    }
  };

  const zoomIn = () => {
    const graph = graphRef.current;
    if (!graph || !graphReadyRef.current) return;
    try {
      const currentZoom = graph.getZoom();
      if (typeof currentZoom !== 'number' || !Number.isFinite(currentZoom)) return;
      const next = Math.min(currentZoom + 0.15, 2.5);
      graph.zoomTo(next, undefined);
      setZoom(Number(next.toFixed(2)));
    } catch {
      undefined;
    }
  };

  const zoomOut = () => {
    const graph = graphRef.current;
    if (!graph || !graphReadyRef.current) return;
    try {
      const currentZoom = graph.getZoom();
      if (typeof currentZoom !== 'number' || !Number.isFinite(currentZoom)) return;
      const next = Math.max(currentZoom - 0.15, 0.35);
      graph.zoomTo(next, undefined);
      setZoom(Number(next.toFixed(2)));
    } catch {
      undefined;
    }
  };

  const resetView = () => {
    const graph = graphRef.current;
    if (!graph) return;
    fitGraphToView(graph);
  };

  const clearSelection = () => {
    setSelectedNodeId(null);
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const currentInstance = ++instanceRef.current;
    graphRef.current?.destroy();
    graphRef.current = null;
    graphReadyRef.current = false;

    const graph = new Graph({
      container: el,
      autoResize: true,
      data: buildGraphData(selectedNodeId),
      node: {
        type: 'rect',
        style: {
          size: [220, 104],
          radius: 18,
          fill: (d: NodeData): string => {
            const data = d.data as FlowNodeMeta | undefined;
            return data?.fill || '#ffffff';
          },
          stroke: (d: NodeData): string => {
            const data = d.data as FlowNodeMeta | undefined;
            return data?.stroke || '#d9d9d9';
          },
          lineWidth: (d: NodeData): number => {
            const data = d.data as FlowNodeMeta | undefined;
            return typeof data?.lineWidth === 'number' ? data.lineWidth : 2;
          },
          shadowColor: (d: NodeData): string => {
            const data = d.data as FlowNodeMeta | undefined;
            return typeof data?.shadowColor === 'string' ? data.shadowColor : DEFAULT_NODE_SHADOW_COLOR;
          },
          shadowBlur: (d: NodeData): number => {
            const data = d.data as FlowNodeMeta | undefined;
            return typeof data?.shadowBlur === 'number' ? data.shadowBlur : 18;
          },
          shadowOffsetX: 0,
          shadowOffsetY: 8,
          opacity: (d: NodeData): number => {
            const data = d.data as FlowNodeMeta | undefined;
            return typeof data?.opacity === 'number' ? data.opacity : 1;
          },
          labelText: (d: NodeData): string => {
            const data = d.data as FlowNodeMeta | undefined;
            if (!data) return String(d.id);
            const rows = [data.label, data.subtitle];
            if (data.table) rows.push(`[${data.table}]`);
            return rows.join('\n');
          },
          labelPlacement: 'center',
          labelFill: '#0f172a',
          labelFontSize: 13,
          labelLineHeight: 18,
          labelFontWeight: 600,
        },
      },
      edge: {
        type: 'polyline',
        style: {
          stroke: (d: EdgeData): string => {
            const data = d.data as FlowEdgeMeta | undefined;
            return data?.stroke || '#94a3b8';
          },
          lineWidth: (d: EdgeData): number => {
            const data = d.data as FlowEdgeMeta | undefined;
            return typeof data?.lineWidth === 'number' ? data.lineWidth : 2;
          },
          radius: 16,
          router: { type: 'orth' },
          sourcePort: (d: EdgeData): string | undefined => {
            const data = d.data as FlowEdgeMeta | undefined;
            return data?.sourcePort;
          },
          targetPort: (d: EdgeData): string | undefined => {
            const data = d.data as FlowEdgeMeta | undefined;
            return data?.targetPort;
          },
          endArrow: true,
          lineDash: (d: EdgeData): number[] | undefined => {
            const data = d.data as FlowEdgeMeta | undefined;
            return data?.dashed ? [6, 4] : undefined;
          },
          labelText: (d: EdgeData): string => {
            const data = d.data as FlowEdgeMeta | undefined;
            return data?.label || '';
          },
          labelFill: '#64748b',
          labelFontSize: 10,
          labelBackground: true,
          labelBackgroundFill: 'rgba(255,255,255,0.82)',
          labelBackgroundRadius: 6,
          labelBackgroundPadding: [3, 6],
          labelPlacement: 'center',
          labelOffsetY: -12,
          opacity: (d: EdgeData): number => {
            const data = d.data as FlowEdgeMeta | undefined;
            return typeof data?.opacity === 'number' ? data.opacity : 1;
          },
        },
      },
      combo: {
        type: 'rect',
      },
      behaviors: ['drag-canvas', 'zoom-canvas'],
    });

    graph.on(NodeEvent.CLICK, (evt: IElementEvent) => {
      const nodeId = String((evt.target as { id?: string | number }).id ?? '');
      if (!rawNodes.some((node) => node.id === nodeId)) return;
      setSelectedNodeId(nodeId);
    });

    graph.on(CanvasEvent.DBLCLICK, () => {
      clearSelection();
    });

    const renderGraph = async () => {
      const origError = console.error;
      console.error = () => undefined;
      try {
        await graph.render();
        graphReadyRef.current = true;
        fitGraphToView(graph);
      } catch {
        undefined;
      } finally {
        console.error = origError;
      }
    };

    renderGraph().catch(() => undefined);
    graphRef.current = graph;

    return () => {
      if (instanceRef.current === currentInstance) {
        graphReadyRef.current = false;
        graphRef.current = null;
        graph.destroy();
      }
    };
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || !graphReadyRef.current) return;

    const syncGraphData = async () => {
      try {
        graph.setData(buildGraphData(selectedNodeId));
        await graph.render();
      } catch {
        undefined;
      }
    };

    syncGraphData().catch(() => undefined);
  }, [selectedNodeId]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || !graphReadyRef.current) return;
    graph.resize(containerSize.w, containerSize.h);
    requestAnimationFrame(() => fitGraphToView(graph));
  }, [containerSize]);

  return (
    <div style={{ padding: '8px 8px 16px' }}>
      <Card
        styles={{ body: { padding: 20 } }}
        style={{
          marginBottom: 20,
          borderRadius: 20,
          background: `linear-gradient(135deg, ${token.colorPrimaryBg} 0%, #ffffff 100%)`,
          border: `1px solid ${token.colorBorderSecondary}`,
        }}
      >
        <Title level={3} style={{ marginTop: 0, marginBottom: 8 }}>
          Ragic 採購流程
        </Title>
        <Text style={{ color: '#64748b' }}>
          使用 G6 流程圖呈現「上游採購 / 下游訂單 / 生產需求 / 生產入庫」全鏈路；可點擊節點查看細節。
        </Text>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
          {Object.values(regionInfo).map((item) => (
            <Tag key={item.title} color={item.color}>
              {item.title}
            </Tag>
          ))}
        </div>
      </Card>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={18}>
          <Card
            styles={{ body: { padding: 12 } }}
            style={{ borderRadius: 20 }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <Text style={{ color: '#64748b', fontSize: 12 }}>
                縮放比例：{Math.round(zoom * 100)}%
              </Text>
              <Space size={8}>
                <Button icon={<EyeOutlined />} size="small" onClick={clearSelection} disabled={!selectedNodeId}>
                  全部顯示
                </Button>
                <Button icon={<ZoomOutOutlined />} size="small" onClick={zoomOut} />
                <Button icon={<CompressOutlined />} size="small" onClick={resetView}>
                  自適應
                </Button>
                <Button icon={<ZoomInOutlined />} size="small" onClick={zoomIn} />
              </Space>
            </div>
            <div
              ref={containerRef}
              style={{
                width: '100%',
                height: suggestedGraphHeight,
                borderRadius: 16,
                background: '#ffffff',
                overflow: 'hidden',
              }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={6}>
          <div style={{ position: 'sticky', top: 16 }}>
            <Card styles={{ body: { padding: 18 } }} style={{ borderRadius: 20, marginBottom: 20 }}>
              <Title level={4} style={{ marginTop: 0, marginBottom: 12 }}>
                流程分區
              </Title>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {Object.entries(regionInfo).map(([key, item]) => (
                  <div
                    key={key}
                    style={{
                      padding: 12,
                      borderRadius: 12,
                      border: '1px solid #e5e7eb',
                      background: '#fafafa',
                    }}
                  >
                    <div style={{ marginBottom: 4 }}>
                      <Tag color={item.color} style={{ marginInlineEnd: 0 }}>
                        {item.title}
                      </Tag>
                    </div>
                    <Text style={{ fontSize: 12, color: '#64748b' }}>{item.description}</Text>
                  </div>
                ))}
              </div>
            </Card>

            <Card styles={{ body: { padding: 18 } }} style={{ borderRadius: 20 }}>
              <Title level={4} style={{ marginTop: 0, marginBottom: 12 }}>
                節點詳情
              </Title>
              {selectedNode ? (
                <div>
                  <Title level={5} style={{ marginTop: 0, marginBottom: 8 }}>
                    {selectedNode.data.label}
                  </Title>
                  <div style={{ marginBottom: 10 }}>
                    <Tag color={regionInfo[selectedNode.data.region].color}>
                      {regionInfo[selectedNode.data.region].title}
                    </Tag>
                    {selectedNode.data.table ? <Tag>{selectedNode.data.table}</Tag> : null}
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <Text strong>副標：</Text>
                    <Text> {selectedNode.data.subtitle}</Text>
                  </div>
                  <div>
                    <Text strong>說明：</Text>
                    <Text> {selectedNode.data.detail}</Text>
                  </div>
                </div>
              ) : (
                <Empty description="點擊左側節點查看流程說明" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </div>
        </Col>
      </Row>
    </div>
  );
}
