/**
 * @file        Ragic 3D 關聯圖譜元件
 * @description 使用 react-force-graph-3d 渲染 3D 力導向圖
 * @lastUpdate  2026-04-12 00:58:49
 * @author      Daniel Chung
 * @version     1.3.0
 */

import { useRef, useCallback, useEffect, useMemo, forwardRef, useImperativeHandle } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import type { ForceGraphMethods } from 'react-force-graph-3d';
import { hashColor, NODE_COLORS, EDGE_COLORS } from './schemaGraphUtils';
import type { HighlightSet } from './schemaGraphUtils';

interface GraphNode {
  id: string;
  label: string;
  module: string;
  color?: string;
  x?: number;
  y?: number;
  z?: number;
}

interface GraphLink {
  source: string;
  target: string;
  label: string;
  color?: string;
}

interface SchemaGraph3DProps {
  nodes: GraphNode[];
  links: GraphLink[];
  width: number;
  height: number;
  highlightSet?: HighlightSet | null;
  onBackgroundClick?: () => void;
}

interface SchemaGraph3DHandle {
  focusNode: (nodeId: string) => void;
}

export type { GraphNode, GraphLink, SchemaGraph3DHandle };

const SchemaGraph3D = forwardRef<SchemaGraph3DHandle, SchemaGraph3DProps>(
  function SchemaGraph3D({ nodes, links, width, height, highlightSet, onBackgroundClick }, ref) {
    const fgRef = useRef<ForceGraphMethods<GraphNode, GraphLink>>(undefined);

    useImperativeHandle(ref, () => ({
      focusNode(nodeId: string) {
        const fg = fgRef.current;
        if (!fg) return;
        const node = nodes.find(n => n.id === nodeId);
        if (!node) return;
        const distance = 200;
        const distRatio = 1 + distance / Math.hypot(node.x ?? 0, node.y ?? 0, node.z ?? 0);
        fg.cameraPosition(
          { x: (node.x ?? 0) * distRatio, y: (node.y ?? 0) * distRatio, z: (node.z ?? 0) * distRatio },
          { x: node.x ?? 0, y: node.y ?? 0, z: node.z ?? 0 },
          1000,
        );
      },
    }), [nodes]);

    const coloredNodes = useMemo(() =>
      nodes.map(n => ({ ...n, color: hashColor(n.module, NODE_COLORS) })),
      [nodes],
    );

    const coloredLinks = useMemo(() =>
      links.map(l => ({ ...l, color: hashColor(l.label, EDGE_COLORS) })),
      [links],
    );

    const graphData = useMemo(() => ({
      nodes: coloredNodes,
      links: coloredLinks,
    }), [coloredNodes, coloredLinks]);

    useEffect(() => {
      const fg = fgRef.current;
      if (!fg) return;
      const timer = window.setTimeout(() => fg.zoomToFit(400, 40), 1500);
      return () => window.clearTimeout(timer);
    }, [nodes.length]);

    const handleNodeLabel = useCallback((node: GraphNode) => node.label, []);
    const handleLinkLabel = useCallback((link: GraphLink) => link.label, []);

    const handleNodeColor = useCallback((node: GraphNode) => {
      if (!highlightSet) return node.color ?? '#3b82f6';
      return highlightSet.nodes.has(node.id) ? (node.color ?? '#3b82f6') : 'rgba(100,100,100,0.15)';
    }, [highlightSet]);

    const handleLinkColor = useCallback((link: GraphLink) => {
      if (!highlightSet) return link.color ?? '#999';
      const srcId = typeof link.source === 'object' ? (link.source as GraphNode).id : link.source;
      const tgtId = typeof link.target === 'object' ? (link.target as GraphNode).id : link.target;
      const connected = highlightSet.nodes.has(srcId) && highlightSet.nodes.has(tgtId);
      return connected ? (link.color ?? '#999') : 'rgba(100,100,100,0.04)';
    }, [highlightSet]);

    const handleLinkWidth = useCallback((link: GraphLink) => {
      if (!highlightSet) return 1.2;
      const srcId = typeof link.source === 'object' ? (link.source as GraphNode).id : link.source;
      const tgtId = typeof link.target === 'object' ? (link.target as GraphNode).id : link.target;
      return (highlightSet.nodes.has(srcId) && highlightSet.nodes.has(tgtId)) ? 2.5 : 0.3;
    }, [highlightSet]);

    const handleBackgroundClick = useCallback(() => { onBackgroundClick?.(); }, [onBackgroundClick]);

    return (
      <ForceGraph3D<GraphNode, GraphLink>
        ref={fgRef}
        graphData={graphData}
        width={width}
        height={height}
        backgroundColor="#0a0f1e"
        nodeLabel={handleNodeLabel}
        nodeColor={handleNodeColor}
        nodeRelSize={5}
        nodeOpacity={0.9}
        linkLabel={handleLinkLabel}
        linkColor={handleLinkColor}
        linkWidth={handleLinkWidth}
        linkOpacity={0.7}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        linkDirectionalParticles={1}
        linkDirectionalParticleSpeed={0.004}
        linkDirectionalParticleWidth={1.5}
        enableNodeDrag
        enableNavigationControls
        showNavInfo={false}
        onBackgroundClick={handleBackgroundClick}
      />
    );
  },
);

export default SchemaGraph3D;
