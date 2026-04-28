/**
 * @file        Schema 圖譜共用工具
 * @description 型別定義、色彩常量、G6/3D 資料轉換函式
 * @lastUpdate  2026-04-24 12:56:23
 * @author      Daniel Chung
 * @version     1.9.0
 */

import type { NodeData, EdgeData } from '@antv/g6';
import type { GraphNode, GraphLink } from './SchemaGraph3D';
import { TAB_CATEGORIES, TAB_LABELS } from './schemaConstants';

/* =================== 型別 =================== */

export type LayoutMode = 'force' | 'grid' | 'circular';
export type ViewMode = '2D' | '3D';
export type HighlightMode = 'both' | 'upstream' | 'downstream';

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
  ...TAB_CATEGORIES.map(category => ({ value: category.label, label: category.label })),
  { value: '其他', label: '其他' },
];

const MODULE_OPTION_SET = new Set(MODULE_OPTIONS.map(option => option.value));

const LEGACY_MODULE_ALIASES: Record<string, string> = {
  BASE: '基礎資料',
  ERP: '進銷存',
  INVENTORY: '進銷存',
  PURCHASE: '進銷存',
  TRADE: '進銷存',
  PRODUCTION: '生產製造',
  MFG: '生產製造',
  ISO: '品質/ISO',
  QC: '品質/ISO',
  SALES: 'CRM/SCM',
  CRM_SCM: 'CRM/SCM',
  HR: '人資/行政',
  PROJECT: '專案/研發',
  MGMT: '管理',
  MISC: '其他',
};

const TAB_LABEL_TO_CATEGORY = new Map<string, string>(
  TAB_CATEGORIES.flatMap(category =>
    category.tabs.map(tab => [TAB_LABELS[tab] ?? tab, category.label] as const)
  )
);

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

export function normalizeGraphModuleSelection(values: string[]): string[] {
  const normalized = values
    .map(value => value.trim())
    .filter(Boolean)
    .map(value => LEGACY_MODULE_ALIASES[value] ?? value)
    .filter(value => MODULE_OPTION_SET.has(value));

  return Array.from(new Set(normalized));
}

export function getDefaultGraphModules(paramValue: string): string[] {
  if (!paramValue.trim()) {
    return MODULE_OPTIONS.map(option => option.value);
  }

  const normalized = normalizeGraphModuleSelection(paramValue.split(','));
  return normalized.length ? normalized : MODULE_OPTIONS.map(option => option.value);
}

export function getTableCategory(moduleName: string): string {
  if (!moduleName) {
    return '';
  }

  if (MODULE_OPTION_SET.has(moduleName)) {
    return moduleName;
  }

  return TAB_LABEL_TO_CATEGORY.get(moduleName) ?? '其他';
}

export function parseRelations(relations: Record<string, unknown>[]): ParsedGraph {
  const nodeSet = new Set<string>();
  const g6Edges: G6Edge[] = [];
  const fgLinks: GraphLink[] = [];
  const edgeKeyCounts = new Map<string, number>();

  for (const rel of relations) {
    const src = String(rel['from_table'] ?? '');
    const tgt = String(rel['to_table'] ?? '');
    if (!src || !tgt) continue;
    nodeSet.add(src);
    nodeSet.add(tgt);
    const sf = String(rel['from_field'] ?? rel['source_field'] ?? '');
    const tf = String(rel['to_field'] ?? rel['target_field'] ?? '');
    const relationType = String(rel['relation_type'] ?? '');
    const label = sf && tf ? `${sf}→${tf}` : '';
    const edgeBaseKey = [src, tgt, sf, tf, relationType].join('→');
    const edgeOccurrence = edgeKeyCounts.get(edgeBaseKey) ?? 0;
    edgeKeyCounts.set(edgeBaseKey, edgeOccurrence + 1);
    const ek = `${edgeBaseKey}#${edgeOccurrence}`;
    g6Edges.push({ id: ek, source: src, target: tgt, data: { label } });
    fgLinks.push({ id: ek, source: src, target: tgt, label });
  }

  const g6Nodes = Array.from(nodeSet).map(n => ({ id: n, data: { label: n, module: n.split('_')[0] ?? '' } }));
  const fgNodes = Array.from(nodeSet).map(n => ({ id: n, label: n, module: n.split('_')[0] ?? '' }));
  return { g6Nodes, g6Edges, fgNodes, fgLinks };
}

export function mergeGraphWithTableIds(full: ParsedGraph, tableIds: string[]): ParsedGraph {
  const existing = new Set(full.g6Nodes.map(node => node.id));
  const extraIds = tableIds.filter(id => id && !existing.has(id));
  if (!extraIds.length) {
    return full;
  }

  const extraG6Nodes = extraIds.map(id => ({ id, data: { label: id, module: '' } }));
  const extraFgNodes = extraIds.map(id => ({ id, label: id, module: '' }));

  return {
    g6Nodes: [...full.g6Nodes, ...extraG6Nodes],
    g6Edges: full.g6Edges,
    fgNodes: [...full.fgNodes, ...extraFgNodes],
    fgLinks: full.fgLinks,
  };
}

export function filterGraphByModules(
  full: ParsedGraph,
  selectedModules: string[],
  tableMeta: Map<string, TableMeta>,
): ParsedGraph {
  const allowed = new Set(selectedModules);
  const nodeModule = (id: string): string => getTableCategory(tableMeta.get(id)?.module ?? '');

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
  const g6Nodes = full.g6Nodes
    .filter(n => keepSet.has(n.id))
    .map(n => ({
      ...n,
      data: {
        ...(n.data ?? {}),
        module: nodeModule(n.id),
      },
    }));
  const g6Edges = full.g6Edges.filter(e => keepSet.has(e.source) && keepSet.has(e.target));
  const fgNodes = full.fgNodes
    .filter(n => keepSet.has(n.id))
    .map(n => ({
      ...n,
      module: nodeModule(n.id),
    }));
  const fgLinks = full.fgLinks.filter(l => keepSet.has(l.source) && keepSet.has(l.target));
  return { g6Nodes, g6Edges, fgNodes, fgLinks };
}

/** Build highlight set: selected node 的上游 / 下游 / 雙向完整關聯路徑 */
export interface HighlightSet { nodes: Set<string>; edges: Set<string> }

export function getHighlightSet(graph: ParsedGraph, nodeId: string, mode: HighlightMode = 'both'): HighlightSet {
  if (mode === 'both') {
    const adjacency = new Map<string, Array<{ nodeId: string; edgeId?: string }>>();

    for (const e of graph.g6Edges) {
      const srcNeighbours = adjacency.get(e.source) ?? [];
      srcNeighbours.push({ nodeId: e.target, edgeId: e.id });
      adjacency.set(e.source, srcNeighbours);

      const tgtNeighbours = adjacency.get(e.target) ?? [];
      tgtNeighbours.push({ nodeId: e.source, edgeId: e.id });
      adjacency.set(e.target, tgtNeighbours);
    }

    const nodes = new Set<string>();
    const edges = new Set<string>();

    const queue: string[] = [nodeId];
    nodes.add(nodeId);

    while (queue.length > 0) {
      const currentNodeId = queue.shift();
      if (!currentNodeId) {
        continue;
      }

      const neighbours = adjacency.get(currentNodeId) ?? [];
      for (const neighbour of neighbours) {
        if (neighbour.edgeId) {
          edges.add(neighbour.edgeId);
        }

        if (!nodes.has(neighbour.nodeId)) {
          nodes.add(neighbour.nodeId);
          queue.push(neighbour.nodeId);
        }
      }
    }

    return { nodes, edges };
  }

  const adjacency = new Map<string, Array<{ nodeId: string; edgeId?: string }>>();

  for (const e of graph.g6Edges) {
    if (mode === 'downstream') {
      const nextNodes = adjacency.get(e.source) ?? [];
      nextNodes.push({ nodeId: e.target, edgeId: e.id });
      adjacency.set(e.source, nextNodes);
      continue;
    }

    const previousNodes = adjacency.get(e.target) ?? [];
    previousNodes.push({ nodeId: e.source, edgeId: e.id });
    adjacency.set(e.target, previousNodes);
  }

  const nodes = new Set<string>();
  const edges = new Set<string>();

  const queue: string[] = [nodeId];
  nodes.add(nodeId);

  while (queue.length > 0) {
    const currentNodeId = queue.shift();
    if (!currentNodeId) {
      continue;
    }

    const neighbours = adjacency.get(currentNodeId) ?? [];
    for (const neighbour of neighbours) {
      if (neighbour.edgeId) {
        edges.add(neighbour.edgeId);
      }

      if (!nodes.has(neighbour.nodeId)) {
        nodes.add(neighbour.nodeId);
        queue.push(neighbour.nodeId);
      }
    }
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
