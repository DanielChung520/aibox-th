/**
 * @file        Schema 圖譜共用工具
 * @description 型別定義、色彩常量、G6/3D 資料轉換函式
 * @lastUpdate  2026-04-19 12:31:30
 * @author      Daniel Chung
 * @version     1.5.0
 */

import type { NodeData, EdgeData } from '@antv/g6';
import type { GraphNode, GraphLink } from './SchemaGraph3D';

/* =================== 型別 =================== */

export type LayoutMode = 'force' | 'grid' | 'circular';
export type ViewMode = '2D' | '3D';

export interface G6Node { id: string; data?: Record<string, unknown>; [key: string]: unknown }
export interface G6Edge { id?: string; source: string; target: string; data?: Record<string, unknown>; [key: string]: unknown }

export interface ParsedGraph {
  g6Nodes: G6Node[];
  g6Edges: G6Edge[];
  fgNodes: GraphNode[];
  fgLinks: GraphLink[];
}

export interface TableMeta { name: string; sheetKey: string; module: string }

export interface ModuleOption { value: string; label: string }

/* =================== 常量 =================== */

export const NODE_COLORS = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];
export const EDGE_COLORS = [
  '#e74c3c', '#2ecc71', '#3498db', '#9b59b6', '#f39c12',
  '#1abc9c', '#e91e63', '#00bcd4', '#ff5722', '#8bc34a',
];

export const MODULE_OPTIONS: ModuleOption[] = [
  { value: 'BASE', label: '基礎資料' },
  { value: 'ERP', label: '進銷存' },
  { value: 'PRODUCTION', label: '生產製造' },
  { value: 'ISO', label: '品質/ISO' },
  { value: 'SALES', label: 'CRM/SCM' },
  { value: 'INVENTORY', label: '庫存' },
  { value: 'HR', label: '人資' },
  { value: 'PURCHASE', label: '採購' },
  { value: 'PROJECT', label: '專案' },
  { value: 'MISC', label: '其他' },
];

/* =================== 工具函式 =================== */

export function hashColor(str: string, palette: string[]): string {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
  return palette[Math.abs(h) % palette.length];
}

export function getLabelFromData(d: NodeData | EdgeData, fallback = ''): string {
  const rec = d.data as Record<string, unknown> | undefined;
  return rec && typeof rec['label'] === 'string' ? rec['label'] : fallback;
}

export function getLayout(mode: LayoutMode) {
  switch (mode) {
    case 'force': return { type: 'force' as const, preventOverlap: true, linkDistance: 120, animated: true };
    case 'grid': return { type: 'grid' as const, cols: 12 };
    case 'circular': return { type: 'circular' as const, autoRadius: true };
  }
}

export function parseRelations(relations: Record<string, unknown>[]): ParsedGraph {
  const nodeSet = new Set<string>();
  const g6Edges: G6Edge[] = [];
  const fgLinks: GraphLink[] = [];
  const edgeKeySet = new Set<string>();

  for (const rel of relations) {
    const src = String(rel['from_table'] ?? '');
    const tgt = String(rel['to_table'] ?? '');
    if (!src || !tgt) continue;
    nodeSet.add(src);
    nodeSet.add(tgt);
    const ek = `${src}→${tgt}`;
    if (edgeKeySet.has(ek)) continue;
    edgeKeySet.add(ek);
    const sf = String(rel['from_field'] ?? rel['source_field'] ?? '');
    const tf = String(rel['to_field'] ?? rel['target_field'] ?? '');
    const label = sf && tf ? `${sf}→${tf}` : '';
    g6Edges.push({ id: ek, source: src, target: tgt, data: { label } });
    fgLinks.push({ source: src, target: tgt, label });
  }

  const g6Nodes = Array.from(nodeSet).map(n => ({ id: n, data: { label: n, module: n.split('_')[0] ?? '' } }));
  const fgNodes = Array.from(nodeSet).map(n => ({ id: n, label: n, module: n.split('_')[0] ?? '' }));
  return { g6Nodes, g6Edges, fgNodes, fgLinks };
}

export function filterGraphByModules(
  full: ParsedGraph,
  selectedModules: string[],
  tableMeta: Map<string, TableMeta>,
): ParsedGraph {
  const allowed = new Set(selectedModules);
  const nodeModule = (id: string): string => tableMeta.get(id)?.module ?? '';

  /* Pass 1: keep nodes whose module is in allowed set */
  const coreSet = new Set<string>();
  for (const n of full.g6Nodes) {
    const m = nodeModule(n.id);
    if (m && allowed.has(m)) coreSet.add(n.id);
  }

  /* Pass 2: keep orphan nodes (no module) only if at least one edge connects them to a core node */
  const orphanNeighbours = new Set<string>();
  for (const e of full.g6Edges) {
    const srcM = nodeModule(e.source);
    const tgtM = nodeModule(e.target);
    if (!srcM && coreSet.has(e.target)) orphanNeighbours.add(e.source);
    if (!tgtM && coreSet.has(e.source)) orphanNeighbours.add(e.target);
  }

  const keepSet = new Set([...coreSet, ...orphanNeighbours]);
  const g6Nodes = full.g6Nodes.filter(n => keepSet.has(n.id));
  const g6Edges = full.g6Edges.filter(e => keepSet.has(e.source) && keepSet.has(e.target));
  const fgNodes = full.fgNodes.filter(n => keepSet.has(n.id));
  const fgLinks = full.fgLinks.filter(l => keepSet.has(l.source) && keepSet.has(l.target));
  return { g6Nodes, g6Edges, fgNodes, fgLinks };
}

/** Build highlight set: selected node + 1-hop neighbours + connecting edge IDs */
export interface HighlightSet { nodes: Set<string>; edges: Set<string> }

export function getHighlightSet(graph: ParsedGraph, nodeId: string): HighlightSet {
  const nodes = new Set<string>([nodeId]);
  const edges = new Set<string>();
  for (const e of graph.g6Edges) {
    if (e.source === nodeId) { nodes.add(e.target); if (e.id) edges.add(e.id); }
    if (e.target === nodeId) { nodes.add(e.source); if (e.id) edges.add(e.id); }
  }
  return { nodes, edges };
}

export function buildG6NodeConfig() {
  return {
    style: {
      size: 24,
      labelText: (d: NodeData) => getLabelFromData(d, String(d.id)),
      labelFill: '#1e293b', labelFontSize: 10, labelPlacement: 'bottom' as const,
      fill: (d: NodeData) => {
        const rec = d.data as Record<string, unknown> | undefined;
        return hashColor(rec && typeof rec['module'] === 'string' ? rec['module'] : '', NODE_COLORS);
      },
      stroke: '#334155', lineWidth: 1,
    },
    state: {
      highlight: { stroke: '#ff6a00', lineWidth: 3, halo: true, haloStroke: '#ff6a00', haloLineWidth: 6 },
      inactive: { fillOpacity: 0.15, strokeOpacity: 0.15, labelOpacity: 0.15 },
    },
  };
}

export function buildG6EdgeConfig() {
  return {
    style: {
      labelText: (d: EdgeData) => getLabelFromData(d),
      labelFill: '#555', labelFontSize: 9,
      labelBackground: true, labelBackgroundFill: 'rgba(255,255,255,0.85)',
      labelBackgroundRadius: 2, labelBackgroundPadding: [1, 3] as [number, number],
      stroke: (d: EdgeData) => hashColor(getLabelFromData(d), EDGE_COLORS),
      lineWidth: 1.5, strokeOpacity: 0.7, endArrow: true,
    },
    state: {
      highlight: { lineWidth: 3, strokeOpacity: 1 },
      inactive: { strokeOpacity: 0.06, labelOpacity: 0.1 },
    },
  };
}
