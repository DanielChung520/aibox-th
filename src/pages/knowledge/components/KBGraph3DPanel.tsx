/**
 * @file        知識庫 3D 圖譜面板元件
 * @description 使用 react-force-graph-3d + Three.js 渲染 3D 力導向圖
 * @lastUpdate  2026-03-26 23:23:59
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useRef, useCallback, useEffect, useMemo, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import SpriteText from 'three-spritetext';

const NODE_COLOR_PALETTE = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

const getNodeColor = (type: string): string => {
  let hash = 0;
  for (let i = 0; i < type.length; i++) hash = type.charCodeAt(i) + ((hash << 5) - hash);
  return NODE_COLOR_PALETTE[Math.abs(hash) % NODE_COLOR_PALETTE.length];
};

const EDGE_COLOR_PALETTE = [
  '#e74c3c', '#2ecc71', '#3498db', '#9b59b6', '#f39c12',
  '#1abc9c', '#e91e63', '#00bcd4', '#ff5722', '#8bc34a',
];

const getEdgeColor = (label: string): string => {
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = label.charCodeAt(i) + ((hash << 5) - hash);
  return EDGE_COLOR_PALETTE[Math.abs(hash) % EDGE_COLOR_PALETTE.length];
};

interface GraphNode {
  id: string;
  label: string;
  type: string;
}

interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

interface KBGraph3DPanelProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width: number;
  height: number;
  onNodeSelect?: (nodeId: string | null) => void;
}

interface FGNode {
  id: string;
  label: string;
  type: string;
  color: string;
  x?: number;
  y?: number;
  z?: number;
}

interface FGLink {
  source: string;
  target: string;
  label: string;
  color: string;
}

export default function KBGraph3DPanel({ nodes, edges, width, height, onNodeSelect }: KBGraph3DPanelProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const [containerSize, setContainerSize] = useState({ w: width, h: height });

  useEffect(() => {
    setContainerSize({ w: width, h: height });
  }, [width, height]);

  const graphData = useMemo(() => {
    const fgNodes: FGNode[] = nodes.map(n => ({
      id: n.id,
      label: n.label,
      type: n.type,
      color: getNodeColor(n.type),
    }));
    const fgLinks: FGLink[] = edges.map(e => ({
      source: e.source,
      target: e.target,
      label: e.label,
      color: getEdgeColor(e.label),
    }));
    return { nodes: fgNodes, links: fgLinks };
  }, [nodes, edges]);

  const handleNodeClick = useCallback((node: FGNode) => {
    onNodeSelect?.(node.id);
    const fg = fgRef.current;
    if (!fg) return;
    const distance = 120;
    const distRatio = 1 + distance / Math.hypot(node.x || 0, node.y || 0, node.z || 0);
    fg.cameraPosition(
      { x: (node.x || 0) * distRatio, y: (node.y || 0) * distRatio, z: (node.z || 0) * distRatio },
      { x: node.x || 0, y: node.y || 0, z: node.z || 0 },
      1500,
    );
  }, [onNodeSelect]);

  const handleBackgroundClick = useCallback(() => {
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  const nodeThreeObject = useCallback((node: FGNode) => {
    const sprite = new SpriteText(node.label);
    sprite.color = '#1e293b';
    sprite.textHeight = 4;
    sprite.backgroundColor = 'rgba(255,255,255,0.75)';
    sprite.padding = 1.5;
    sprite.borderRadius = 2;
    (sprite as unknown as { center: { y: number } }).center.y = -0.6;
    return sprite;
  }, []);

  if (!nodes.length) return null;

  return (
    <ForceGraph3D
      ref={fgRef}
      width={containerSize.w}
      height={containerSize.h}
      graphData={graphData}
      backgroundColor="#ffffff"
      showNavInfo={false}
      nodeId="id"
      nodeLabel="label"
      nodeColor="color"
      nodeRelSize={6}
      nodeOpacity={0.95}
      nodeThreeObjectExtend={true}
      nodeThreeObject={nodeThreeObject}
      linkSource="source"
      linkTarget="target"
      linkLabel="label"
      linkColor="color"
      linkWidth={1.5}
      linkOpacity={0.7}
      linkDirectionalArrowLength={5}
      linkDirectionalArrowRelPos={1}
      linkDirectionalParticles={2}
      linkDirectionalParticleWidth={1.5}
      onNodeClick={handleNodeClick}
      onBackgroundClick={handleBackgroundClick}
    />
  );
}
