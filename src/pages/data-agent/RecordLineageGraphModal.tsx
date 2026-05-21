/**
 * @file        資料記錄血緣圖譜 Modal
 * @description 逐步拼湊模式：先載入 root 記錄 + FK 邊 ghost，點擊 ghost 才展開該邊。
 *              也保留「全部展開」按鈕保持舊版一次性 BFS 行為。
 * @lastUpdate  2026-05-01
 * @author      Daniel Chung
 * @version     2.0.0
 */
import { useRef, useState, useCallback, useEffect } from 'react';
import { Modal, Spin, Empty, Typography, Segmented, Button, Space, App, Input, AutoComplete, Tooltip } from 'antd';
import { ZoomInOutlined, ZoomOutOutlined, ReloadOutlined, SearchOutlined, CloseCircleOutlined, ApartmentOutlined } from '@ant-design/icons';
import { Graph } from '@antv/g6';
import { dataAgentApi } from '../../services/dataAgentApi';
import SchemaGraph3D, { type SchemaGraph3DHandle } from './SchemaGraph3D';
import {
  getLayout, getHighlightSet, buildG6NodeConfig, buildG6EdgeConfig,
  buildGhostNodeConfig, buildGhostEdgeConfig, isGhostNode,
  hashColor, NODE_COLORS, ROOT_NODE_COLOR, GHOST_NODE_COLOR,
  convertRecordTraceToGraph,
  type LayoutMode, type ViewMode, type ParsedGraph, type HighlightSet, type HighlightMode,
} from './schemaGraphUtils';

const { Text } = Typography;

interface RecordLineageGraphModalProps {
  open: boolean;
  onClose: () => void;
  tableKey: string;
  recordId: string;
  account: string;
}

interface GhostEdge {
  id: string;
  from_record_id: string;
  from_table_key: string;
  from_field_id: string;
  from_field_name: string;
  from_field_value: string;
  target_table_key: string;
  target_table_name: string;
  relation_type: string;
}

export default function RecordLineageGraphModal({
  open, onClose, tableKey, recordId, account,
}: RecordLineageGraphModalProps) {
  const { message } = App.useApp();
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const zoomRef = useRef(1);
  const bodyRef = useRef<HTMLDivElement>(null);
  const fg3dRef = useRef<SchemaGraph3DHandle>(null);

  const [loading, setLoading] = useState(false);
  const [hasData, setHasData] = useState(false);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('force');
  const [viewMode, setViewMode] = useState<ViewMode>('2D');
  const [parsedGraph, setParsedGraph] = useState<ParsedGraph | null>(null);
  const [bodySize, setBodySize] = useState<{ w: number; h: number }>({ w: 800, h: 600 });
  const [searchValue, setSearchValue] = useState('');
  const [highlightMode, setHighlightMode] = useState<HighlightMode>('both');
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [highlightSet, setHighlightSet] = useState<HighlightSet | null>(null);

  // Progressive state
  const [loadedNodes, setLoadedNodes] = useState<Map<string, Record<string, unknown>>>(new Map());
  const [loadedEdges, setLoadedEdges] = useState<Array<Record<string, unknown>>>([]);
  const [ghostEdges, setGhostEdges] = useState<GhostEdge[]>([]);
  const [expandingEdges, setExpandingEdges] = useState<Set<string>>(new Set());
  const [rootTableName, setRootTableName] = useState('');
  const [isProgressive, setIsProgressive] = useState(true);

  const destroyG6 = useCallback(() => { graphRef.current?.destroy(); graphRef.current = null; }, []);

  const clearHighlight = useCallback(() => {
    setActiveNodeId(null);
    setHighlightSet(null);
    const g = graphRef.current;
    if (!g) return;
    const pg = parsedGraph;
    if (!pg) return;
    const stateMap: Record<string, string[]> = {};
    for (const n of pg.g6Nodes) stateMap[n.id] = [];
    for (const e of pg.g6Edges) { if (e.id) stateMap[e.id] = []; }
    g.setElementState(stateMap);
  }, [parsedGraph]);

  const handleGraphNodeSelect = useCallback((nodeId: string) => {
    if (isGhostNode(nodeId)) return;
    setActiveNodeId(nodeId);
    if (viewMode === '3D') fg3dRef.current?.focusNode(nodeId);
  }, [viewMode]);

  /** Build a ParsedGraph from current loaded state + ghost edges. */
  const buildGraph = useCallback((
    nodes: Map<string, Record<string, unknown>>,
    edges: Array<Record<string, unknown>>,
    ghosts: GhostEdge[],
  ): ParsedGraph => {
    const g6Nodes: Array<{ id: string; data: Record<string, unknown> }> = [];
    const fgNodes: Array<{ id: string; label: string; module: string; color?: string }> = [];
    const g6Edges: Array<{ id: string; source: string; target: string; data: Record<string, unknown> }> = [];
    const fgLinks: Array<{ id: string; source: string; target: string; label: string; color?: string }> = [];

    const nodeData = (id: string) => nodes.get(id);
    const getLabel = (nd: Record<string, unknown> | undefined) => {
      if (!nd) return '';
      const tbl = String(nd.table_name || '');
      const flds = nd.fields as Record<string, unknown> | undefined;
      if (flds) {
        for (const k of ['品名', '品項', '名稱', '編號', '料號', 'name', 'Name']) {
          for (const [fk, fv] of Object.entries(flds)) {
            if (fk.includes(k) && fv != null && String(fv).trim()) {
              return `${tbl}\n${String(fv).trim()}`;
            }
          }
        }
        const firstVal = Object.values(flds).find(v => typeof v === 'string' && v.trim() && v.length < 50);
        if (firstVal) return `${tbl}\n${String(firstVal).trim()}`;
      }
      return tbl || id;
    };

    // Real nodes
    for (const [id, nd] of nodes) {
      const label = getLabel(nd);
      const isRoot = nd.isRoot === true;
      g6Nodes.push({ id, data: { label, isRoot, table_name: nd.table_name } });
      fgNodes.push({ id, label, module: String(nd.table_name || ''), color: isRoot ? ROOT_NODE_COLOR : undefined });
    }

    // Ghost nodes
    const ghostNodeIds = new Set<string>();
    for (const g of ghosts) {
      if (!ghostNodeIds.has(g.target_table_key)) {
        ghostNodeIds.add(g.target_table_key);
        const gid = `ghost_${g.target_table_key}_${g.from_field_value}`;
        g6Nodes.push({ id: gid, data: { label: g.target_table_name, isGhost: true, ghostTableKey: g.target_table_key } });
        fgNodes.push({ id: gid, label: g.target_table_name, module: g.target_table_name, color: GHOST_NODE_COLOR });
      }
    }

    // Real edges
    for (const e of edges) {
      const eid = String(e.from_ragic_id || '') + '\u2192' + String(e.to_ragic_id || '');
      const label = String(e.via_field_name || '');
      g6Edges.push({ id: eid, source: String(e.from_ragic_id || ''), target: String(e.to_ragic_id || ''), data: { label } });
      fgLinks.push({ id: eid, source: String(e.from_ragic_id || ''), target: String(e.to_ragic_id || ''), label });
    }

    // Ghost edges
    for (const g of ghosts) {
      const ghostNid = `ghost_${g.target_table_key}_${g.from_field_value}`;
      const eid = g.id;
      g6Edges.push({ id: eid, source: g.from_record_id, target: ghostNid, data: { label: `${g.from_field_name}=${g.from_field_value}` } });
      fgLinks.push({ id: eid, source: g.from_record_id, target: ghostNid, label: `${g.from_field_name}=${g.from_field_value}` });
    }

    return { g6Nodes, g6Edges, fgNodes, fgLinks };
  }, []);

  /** Rebuild graph and re-init G6 whenever state changes. */
  const updateGraph = useCallback((
    nodes: Map<string, Record<string, unknown>>,
    edges: Array<Record<string, unknown>>,
    ghosts: GhostEdge[],
  ) => {
    const parsed = buildGraph(nodes, edges, ghosts);
    setParsedGraph(parsed);
    setHasData(nodes.size > 0);
    setTimeout(() => {
      if (bodyRef.current) setBodySize({ w: bodyRef.current.offsetWidth, h: bodyRef.current.offsetHeight });
      const container = containerRef.current;
      if (container) {
        destroyG6();
        const graph = new Graph({
          container, autoResize: true,
          data: { nodes: parsed.g6Nodes, edges: parsed.g6Edges },
          node: buildRecordNodeConfig(),
          edge: buildG6EdgeConfig(),
          layout: getLayout('force'),
          behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
        });
        graphRef.current = graph;
        graph.render().catch(() => {});
        graph.on('node:click', (event) => {
          const t = 'target' in event ? event.target : null;
          const nid = t && typeof t === 'object' && 'id' in t ? String(t.id ?? '') : '';
          if (!nid) return;
          if (isGhostNode(nid)) { handleGhostNodeClick(nid, ghosts, nodes); return; }
          handleGraphNodeSelect(nid);
        });
        graph.on('canvas:click', () => { clearHighlight(); });
      }
    }, 0);
  }, [buildGraph, destroyG6, clearHighlight, handleGraphNodeSelect]);

  /** Handle click on a ghost node - expand the corresponding FK edge. */
  const handleGhostNodeClick = useCallback((
    ghostNid: string,
    currentGhosts: GhostEdge[],
    currentNodes: Map<string, Record<string, unknown>>,
  ) => {
    // Find the first ghost edge leading to this ghost node
    const targetGhosts = currentGhosts.filter(g => {
      const expectedId = `ghost_${g.target_table_key}_${g.from_field_value}`;
      return expectedId === ghostNid;
    });
    if (targetGhosts.length === 0) return;
    const ghost = targetGhosts[0];
    if (expandingEdges.has(ghost.id)) return;

    setExpandingEdges(prev => new Set(prev).add(ghost.id));

    (async () => {
      try {
        const res = await dataAgentApi.fkExpandEdge({
          table_key: ghost.from_table_key,
          record_id: ghost.from_record_id,
          field_id: ghost.from_field_id,
          field_value: ghost.from_field_value,
          account,
          via_field_name: ghost.from_field_name,
        });
        const result = res.data.data;
        if (!result || !result.nodes?.length) {
          setExpandingEdges(prev => { const n = new Set(prev); n.delete(ghost.id); return n; });
          return;
        }

        const newNodes = new Map(currentNodes);
        const newEdges = [...loadedEdges];
        const newGhosts = currentGhosts.filter(g => g.id !== ghost.id);

        for (const n of result.nodes) {
          const nid = n.ragic_id;
          if (!newNodes.has(nid)) {
            newNodes.set(nid, { ...n, table_name: n.table_name, fields: n.fields });
          }
          // Real edge: source → target
          newEdges.push({
            from_ragic_id: ghost.from_record_id,
            from_table_key: ghost.from_table_key,
            to_ragic_id: nid,
            to_table_key: n.table_key,
            via_field_id: ghost.from_field_id,
            via_field_name: ghost.from_field_name,
            relation_type: result.relation_type || '',
          });
        }

        // Add new ghost edges from FK previews
        if (result.fk_previews) {
          for (const [rid, previews] of Object.entries(result.fk_previews)) {
            for (const p of (previews as Array<Record<string, unknown>>)) {
              const pval = String(p.from_field_value || '');
              if (!pval) continue;
              newGhosts.push({
                id: `${rid}_${p.from_field_id}`,
                from_record_id: rid,
                from_table_key: String(p.target_table_key || ''),
                from_field_id: String(p.from_field_id || ''),
                from_field_name: String(p.from_field_name || ''),
                from_field_value: String(p.from_field_value || ''),
                target_table_key: String(p.target_table_key || ''),
                target_table_name: String(p.target_table_name || ''),
                relation_type: String(p.relation_type || 'link'),
              });
            }
          }
        }

        setLoadedNodes(newNodes);
        setLoadedEdges(newEdges);
        setGhostEdges(newGhosts);
        updateGraph(newNodes, newEdges, newGhosts);
        setExpandingEdges(prev => { const n = new Set(prev); n.delete(ghost.id); return n; });
      } catch (err: unknown) {
        const e = err as { response?: { data?: { message?: string } } };
        message.error(e.response?.data?.message || '展開 FK 邊失敗');
        setExpandingEdges(prev => { const n = new Set(prev); n.delete(ghost.id); return n; });
      }
    })();
  }, [account, loadedEdges, expandingEdges, updateGraph, message]);

  // Open modal: start with FK preview (progressive) or full trace
  const handleAfterOpenChange = useCallback((visible: boolean) => {
    if (!visible) {
      destroyG6(); setHasData(false); setLayoutMode('force'); setViewMode('2D');
      setParsedGraph(null); setSearchValue(''); setHighlightSet(null); setActiveNodeId(null);
      setHighlightMode('both');
      setLoadedNodes(new Map()); setLoadedEdges([]); setGhostEdges([]);
      setExpandingEdges(new Set()); setRootTableName(''); setIsProgressive(true);
      return;
    }
    if (!tableKey || !recordId) { setLoading(false); return; }
    setLoading(true); setIsProgressive(true);

    (async () => {
      try {
        const res = await dataAgentApi.fkPreview({ table_key: tableKey, record_id: recordId, account });
        const data = res.data.data;
        if (!data || !data.record) { setLoading(false); setHasData(false); return; }

        setRootTableName(data.table_name || '');
        const initNodes = new Map<string, Record<string, unknown>>();
        initNodes.set(recordId, {
          ragic_id: recordId,
          table_key: tableKey,
          table_name: data.table_name,
          fields: data.record,
          isRoot: true,
        });

        const initGhosts: GhostEdge[] = (data.fk_edges || []).map((e: Record<string, unknown>) => ({
          id: `${recordId}_${e.from_field_id}`,
          from_record_id: recordId,
          from_table_key: tableKey,
          from_field_id: String(e.from_field_id || ''),
          from_field_name: String(e.from_field_name || ''),
          from_field_value: String(e.from_field_value || ''),
          target_table_key: String(e.target_table_key || ''),
          target_table_name: String(e.target_table_name || ''),
          relation_type: String(e.relation_type || 'link'),
        }));

        setLoadedNodes(initNodes);
        setLoadedEdges([]);
        setGhostEdges(initGhosts);
        updateGraph(initNodes, [], initGhosts);
      } catch (err: unknown) {
        const e = err as { response?: { data?: { message?: string } } };
        message.error(e.response?.data?.message || '載入記錄血緣失敗');
      } finally {
        setLoading(false);
      }
    })();
  }, [tableKey, recordId, account, message, updateGraph, destroyG6]);

  /** Full trace: uses original BFS mode to expand everything at once. */
  const handleFullTrace = useCallback(() => {
    if (!isProgressive) return;
    setLoading(true);
    (async () => {
      try {
        const res = await dataAgentApi.recordTrace({ table_key: tableKey, record_id: recordId, account, depth: 3 });
        const traceData = res.data.data;
        if (!traceData || !traceData.nodes?.length) { setLoading(false); return; }
        const parsed = convertRecordTraceToGraph(traceData);

        setLoadedNodes(new Map());
        setLoadedEdges([]);
        setGhostEdges([]);
        setIsProgressive(false);
        setParsedGraph(parsed);
        setHasData(true);

        setTimeout(() => {
          if (bodyRef.current) setBodySize({ w: bodyRef.current.offsetWidth, h: bodyRef.current.offsetHeight });
          const container = containerRef.current;
          if (container) {
            destroyG6();
            const graph = new Graph({
              container, autoResize: true,
              data: { nodes: parsed.g6Nodes, edges: parsed.g6Edges },
              node: buildRecordNodeConfig(),
              edge: buildG6EdgeConfig(),
              layout: getLayout('force'),
              behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
            });
            graphRef.current = graph;
            graph.render().catch(() => {});
            graph.on('node:click', (event) => {
              const t = 'target' in event ? event.target : null;
              const nid = t && typeof t === 'object' && 'id' in t ? String(t.id ?? '') : '';
              if (!nid) return;
              handleGraphNodeSelect(nid);
            });
            graph.on('canvas:click', () => { clearHighlight(); });
          }
        }, 0);
      } catch (err: unknown) {
        const e = err as { response?: { data?: { message?: string } } };
        message.error(e.response?.data?.message || '全部展開失敗');
      } finally {
        setLoading(false);
      }
    })();
  }, [tableKey, recordId, account, isProgressive, message, destroyG6, clearHighlight, handleGraphNodeSelect]);

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    if (mode === '3D') {
      destroyG6();
      setViewMode('3D');
      if (bodyRef.current) setBodySize({ w: bodyRef.current.offsetWidth, h: bodyRef.current.offsetHeight });
    } else {
      setViewMode('2D');
      setTimeout(() => {
        if (containerRef.current && parsedGraph) {
          destroyG6();
          const graph = new Graph({
            container: containerRef.current, autoResize: true,
            data: { nodes: parsedGraph.g6Nodes, edges: parsedGraph.g6Edges },
            node: isProgressive ? buildRecordNodeConfig() : buildG6NodeConfig(),
            edge: isProgressive ? buildG6EdgeConfig() : buildG6EdgeConfig(),
            layout: getLayout(layoutMode),
            behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
          });
          graphRef.current = graph;
          graph.render().catch(() => {});
          graph.on('node:click', (event) => {
            const t = 'target' in event ? event.target : null;
            const nid = t && typeof t === 'object' && 'id' in t ? String(t.id ?? '') : '';
            if (!nid) return;
            handleGraphNodeSelect(nid);
          });
          graph.on('canvas:click', () => { clearHighlight(); });
        }
      }, 50);
    }
  }, [parsedGraph, isProgressive, layoutMode, destroyG6, clearHighlight, handleGraphNodeSelect]);

  const handleLayoutChange = useCallback((mode: LayoutMode) => {
    setLayoutMode(mode);
    const g = graphRef.current;
    if (!g) return;
    g.setLayout(getLayout(mode));
    g.layout().catch(() => {});
  }, []);

  const applyZoom = useCallback((delta: number) => {
    const g = graphRef.current;
    if (!g) return;
    zoomRef.current = Math.max(0.15, Math.min(3, zoomRef.current + delta));
    g.zoomTo(zoomRef.current, undefined);
  }, []);

  const searchOptions = useCallback(() => {
    if (!parsedGraph || !searchValue.trim()) return [];
    const kw = searchValue.trim().toLowerCase();
    const matched: { value: string; label: string }[] = [];
    for (const n of parsedGraph.fgNodes) {
      if (isGhostNode(n.id)) continue;
      if (n.id.toLowerCase().includes(kw) || n.label.toLowerCase().includes(kw)) {
        matched.push({ value: n.id, label: n.label });
      }
      if (matched.length >= 20) break;
    }
    return matched;
  }, [parsedGraph, searchValue]);

  const handleSearchSelect = useCallback((nodeId: string) => {
    setSearchValue('');
    handleGraphNodeSelect(nodeId);
  }, [handleGraphNodeSelect]);

  const abs: React.CSSProperties = { position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' };

  const realNodeCount = parsedGraph?.g6Nodes.filter(n => !isGhostNode(n.id)).length ?? 0;
  const ghostCount = ghostEdges.length;
  const realEdgeCount = loadedEdges.length;
  const expandingCount = expandingEdges.size;

  return (
    <Modal
      title={`🔗 記錄血緣圖譜 — ${rootTableName || tableKey}`}
      open={open}
      onCancel={onClose}
      footer={null}
      width="90vw"
      styles={{ body: { height: '75vh', display: 'flex', flexDirection: 'column', padding: 0 } }}
      destroyOnHidden
      afterOpenChange={handleAfterOpenChange}
    >
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 16px', borderBottom: '1px solid #f0f0f0', flexWrap: 'wrap', gap: 6,
      }}>
        <Space size="small" wrap>
          <Segmented value={viewMode} onChange={v => handleViewModeChange(v as ViewMode)} size="small"
            options={[{ label: '2D', value: '2D' }, { label: '3D', value: '3D' }]} />
          {hasData && (
            <>
              <Segmented value={highlightMode} onChange={v => setHighlightMode(v as HighlightMode)} size="small"
                options={[{ label: '雙向', value: 'both' }, { label: '上游', value: 'upstream' }, { label: '下游', value: 'downstream' }]} />
            </>
          )}
          {viewMode === '2D' && (
            <>
              <Segmented value={layoutMode} onChange={v => handleLayoutChange(v as LayoutMode)} size="small"
                options={[{ label: '力導向', value: 'force' }, { label: '網格', value: 'grid' }, { label: '環形', value: 'circular' }]} />
              <Button icon={<ZoomInOutlined />} size="small" onClick={() => applyZoom(0.15)} />
              <Button icon={<ZoomOutOutlined />} size="small" onClick={() => applyZoom(-0.15)} />
              <Button icon={<ReloadOutlined />} size="small" onClick={() => { zoomRef.current = 1; graphRef.current?.zoomTo(1); }} />
            </>
          )}
        </Space>
        <Space size="small">
          {isProgressive && (
            <Tooltip title="一次性展開全部關聯（較慢）">
              <Button icon={<ApartmentOutlined />} size="small" loading={loading} onClick={handleFullTrace}>
                全部展開
              </Button>
            </Tooltip>
          )}
          {hasData && (
            <AutoComplete options={searchOptions()} onSelect={handleSearchSelect}
              value={searchValue} onChange={setSearchValue} style={{ width: 200 }}
              popupStyle={{ zIndex: 9999 }}>
              <Input size="small" placeholder="搜尋記錄" prefix={<SearchOutlined />} allowClear />
            </AutoComplete>
          )}
          {activeNodeId && <Button size="small" icon={<CloseCircleOutlined />} onClick={clearHighlight}>清除高亮</Button>}
          {hasData && parsedGraph && (
            <Text type="secondary">
              {realNodeCount} 記錄{ghostCount > 0 && <> +{ghostCount} 待展開</>}
              {realEdgeCount > 0 && <> · {realEdgeCount} 關聯</>}
              {expandingCount > 0 && <> · 展開中({expandingCount})</>}
            </Text>
          )}
        </Space>
      </div>

      <div ref={bodyRef} style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {loading && <div style={{ ...abs, zIndex: 10 }}><Spin description={isProgressive ? '載入記錄中...' : '全部展開中...'} /></div>}
        {!loading && !hasData && <div style={abs}><Empty description="尚無關聯記錄" /></div>}
        {viewMode === '2D' && <div ref={containerRef} style={{ width: '100%', height: '100%' }} />}
        {viewMode === '3D' && hasData && parsedGraph && (
          <div style={{ position: 'relative', zIndex: 0, width: '100%', height: '100%' }}>
            <SchemaGraph3D ref={fg3dRef} nodes={parsedGraph.fgNodes} links={parsedGraph.fgLinks}
              width={bodySize.w} height={bodySize.h} highlightSet={highlightSet}
              onNodeClick={(nid) => { if (!isGhostNode(nid)) handleGraphNodeSelect(nid); }}
              onBackgroundClick={clearHighlight} />
          </div>
        )}
      </div>
    </Modal>
  );
}

/** G6 node config for progressive mode: root = orange, ghost = dashed, others = module color. */
function buildRecordNodeConfig() {
  const base = buildG6NodeConfig();
  return {
    ...base,
    style: {
      ...base.style,
      size: 28,
      labelFontSize: 11,
      fill: (d: import('@antv/g6').NodeData) => {
        const rec = d.data as Record<string, unknown> | undefined;
        if (rec && rec['isRoot']) return ROOT_NODE_COLOR;
        if (rec && rec['isGhost']) return GHOST_NODE_COLOR;
        if (rec && typeof rec['table_name'] === 'string') return hashColor(rec['table_name'], NODE_COLORS);
        return hashColor(String(d.id), NODE_COLORS);
      },
      fillOpacity: (d: import('@antv/g6').NodeData) => {
        const rec = d.data as Record<string, unknown> | undefined;
        return rec?.['isGhost'] ? 0.25 : 1;
      },
      strokeDash: (d: import('@antv/g6').NodeData) => {
        const rec = d.data as Record<string, unknown> | undefined;
        return rec?.['isGhost'] ? [5, 4] : undefined;
      },
    },
    state: {
      highlight: { stroke: ROOT_NODE_COLOR, lineWidth: 3, halo: true, haloStroke: ROOT_NODE_COLOR, haloLineWidth: 6 },
      inactive: { fillOpacity: 0.15, strokeOpacity: 0.15, labelOpacity: 0.15 },
    },
  };
}
