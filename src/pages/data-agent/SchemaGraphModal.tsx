/**
 * @file        Ragic 跨表關聯圖譜 Modal
 * @description 支援 2D（G6 v5）與 3D（react-force-graph-3d）雙模式圖譜，含模組篩選、搜尋定位與高亮清除
 * @lastUpdate  2026-04-24 12:59:34
 * @author      Daniel Chung
 * @version     3.0.0
 */

import { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { Modal, Spin, Empty, Typography, Segmented, Button, Space, App, Input, AutoComplete, Select } from 'antd';
import { ZoomInOutlined, ZoomOutOutlined, ReloadOutlined, SearchOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { Graph } from '@antv/g6';
import { dataAgentApi } from '../../services/dataAgentApi';
import type { TableInfo } from '../../services/dataAgentApi_types';
import { paramsApi } from '../../services/api';
import SchemaGraph3D, { type SchemaGraph3DHandle } from './SchemaGraph3D';
import {
  getLayout, parseRelations, filterGraphByModules, getHighlightSet, buildG6NodeConfig, buildG6EdgeConfig,
  getDefaultGraphModules,
  MODULE_OPTIONS, mergeGraphWithTableIds,
  type LayoutMode, type ViewMode, type ParsedGraph, type TableMeta, type HighlightSet, type HighlightMode,
} from './schemaGraphUtils';
const { Text } = Typography;

interface SchemaGraphModalProps { open: boolean; onClose: () => void; account: string; }

export default function SchemaGraphModal({ open, onClose, account }: SchemaGraphModalProps) {
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
  const [fullGraph, setFullGraph] = useState<ParsedGraph | null>(null);
  const [bodySize, setBodySize] = useState<{ w: number; h: number }>({ w: 800, h: 600 });
  const [tableMeta, setTableMeta] = useState<Map<string, TableMeta>>(new Map());
  const [searchValue, setSearchValue] = useState('');
  const [selectedModules, setSelectedModules] = useState<string[]>(MODULE_OPTIONS.map(m => m.value));
  const [defaultModules, setDefaultModules] = useState<string[]>(MODULE_OPTIONS.map(m => m.value));
  const [highlightMode, setHighlightMode] = useState<HighlightMode>('both');
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [highlightSet, setHighlightSet] = useState<HighlightSet | null>(null);

  const isUsingDefaultModules = useMemo(() => {
    if (selectedModules.length !== defaultModules.length) {
      return false;
    }

    const selectedSet = new Set(selectedModules);
    return defaultModules.every(module => selectedSet.has(module));
  }, [defaultModules, selectedModules]);

  const visibleData = useMemo<ParsedGraph | null>(
    () => fullGraph ? filterGraphByModules(fullGraph, selectedModules, tableMeta) : null,
    [fullGraph, selectedModules, tableMeta],
  );

  const destroyG6 = useCallback(() => { graphRef.current?.destroy(); graphRef.current = null; }, []);
  const clearHighlight = useCallback(() => {
    setActiveNodeId(null);
    setHighlightSet(null);
    const g = graphRef.current;
    if (!g) return;
    const stateMap: Record<string, string[]> = {};
    for (const n of (visibleData?.g6Nodes ?? [])) stateMap[n.id] = [];
    for (const e of (visibleData?.g6Edges ?? [])) { if (e.id) stateMap[e.id] = []; }
    g.setElementState(stateMap);
  }, [visibleData]);

  const handleGraphNodeSelect = useCallback((nodeId: string) => {
    setActiveNodeId(nodeId);
    if (viewMode === '3D') {
      fg3dRef.current?.focusNode(nodeId);
    }
  }, [viewMode]);

  useEffect(() => {
    if (!visibleData || !activeNodeId) {
      setHighlightSet(null);
      const g = graphRef.current;
      if (!g) return;
      const stateMap: Record<string, string[]> = {};
      for (const n of (visibleData?.g6Nodes ?? [])) stateMap[n.id] = [];
      for (const e of (visibleData?.g6Edges ?? [])) {
        if (e.id) stateMap[e.id] = [];
      }
      g.setElementState(stateMap);
      return;
    }

    const nodeExists = visibleData.g6Nodes.some(node => node.id === activeNodeId);
    if (!nodeExists) {
      setActiveNodeId(null);
      setHighlightSet(null);
      return;
    }

    const hs = getHighlightSet(visibleData, activeNodeId, highlightMode);
    setHighlightSet(hs);

    if (viewMode !== '2D') return;

    const g = graphRef.current;
    if (!g) return;
    const stateMap: Record<string, string[]> = {};
    for (const n of visibleData.g6Nodes) stateMap[n.id] = hs.nodes.has(n.id) ? ['highlight'] : ['inactive'];
    for (const e of visibleData.g6Edges) {
      if (e.id) stateMap[e.id] = hs.edges.has(e.id) ? ['highlight'] : ['inactive'];
    }
    g.setElementState(stateMap);
    g.focusElement(activeNodeId, true);
    zoomRef.current = 1.8;
    g.zoomTo(1.8, undefined);
  }, [activeNodeId, highlightMode, viewMode, visibleData]);

  const initG6 = useCallback((container: HTMLDivElement, parsed: ParsedGraph) => {
    destroyG6();
    const graph = new Graph({
      container, autoResize: true,
      data: { nodes: parsed.g6Nodes, edges: parsed.g6Edges },
      node: buildG6NodeConfig(),
      edge: buildG6EdgeConfig(),
      layout: getLayout('force'),
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    });
    graphRef.current = graph;
    graph.render().catch(() => {});
    graph.on('node:click', (event) => {
      const target = 'target' in event ? event.target : null;
      const nodeId = target && typeof target === 'object' && 'id' in target ? String(target.id ?? '') : '';
      if (!nodeId) return;
      handleGraphNodeSelect(nodeId);
    });
    graph.on('canvas:click', () => { clearHighlight(); });
  }, [destroyG6, clearHighlight, handleGraphNodeSelect]);

  const handleAfterOpenChange = useCallback((visible: boolean) => {
    if (!visible) {
      destroyG6(); setHasData(false); setLayoutMode('force'); setViewMode('2D');
      setFullGraph(null); setTableMeta(new Map()); setSearchValue(''); setHighlightSet(null); setActiveNodeId(null);
      setHighlightMode('both');
      setDefaultModules(MODULE_OPTIONS.map(m => m.value));
      setSelectedModules(MODULE_OPTIONS.map(m => m.value));
      return;
    }
    setLoading(true); setHasData(false);

    const fetchAndRender = async () => {
      try {
        const [relRes, tableRes, defaultGraphModulesRes] = await Promise.all([
          dataAgentApi.ragicAllRelations(account),
          dataAgentApi.listTables().catch(() => ({ data: { data: [] } })),
          paramsApi.get('ragic.default_graph_modules').catch(() => ({ data: { data: { param_value: '' } } })),
        ]);

        const meta = new Map<string, TableMeta>();
        const tables: TableInfo[] = (tableRes.data.data || []).filter((t: TableInfo) => t.data_source === 'ragic');
        for (const t of tables) {
          meta.set(t.table_id, { name: t.table_name, sheetKey: t.sheet_key, module: t.module });
        }
        setTableMeta(meta);

        // Graph endpoints are routed through the Rust Gateway in dev/prod.
        // The gateway proxies downstream services and wraps the payload.
        const relations: Record<string, unknown>[] = Array.isArray(relRes.data)
          ? relRes.data
          : (relRes.data?.data || []);
        if (!relations.length) { setLoading(false); return; }

        const parsed = mergeGraphWithTableIds(
          parseRelations(relations),
          tables.map(t => t.table_id),
        );
        setFullGraph(parsed);
        setHasData(true);

        const defaultMods = getDefaultGraphModules(defaultGraphModulesRes.data.data?.param_value || '');
        setDefaultModules(defaultMods);
        setSelectedModules(defaultMods);
        if (bodyRef.current) {
          setBodySize({ w: bodyRef.current.offsetWidth, h: bodyRef.current.offsetHeight });
        }
        // Defer initG6 to next tick so React can batch state updates first
        setTimeout(() => {
          const filtered = filterGraphByModules(parsed, defaultMods, meta);
          const container = containerRef.current;
          if (container) initG6(container, filtered);
        }, 0);
      } catch (err: unknown) {
        const e = err as { response?: { data?: { message?: string } } };
        message.error(e.response?.data?.message || '載入圖譜失敗');
      } finally {
        setLoading(false);
      }
    };
    fetchAndRender();
  }, [account, message, initG6, destroyG6]);

  const handleModuleChange = useCallback((modules: string[]) => {
    setSelectedModules(modules);
    if (!fullGraph) return;
    const filtered = filterGraphByModules(fullGraph, modules, tableMeta);
    setTimeout(() => {
      if (viewMode === '2D' && containerRef.current) {
        initG6(containerRef.current, filtered);
      }
    }, 30);
  }, [fullGraph, tableMeta, viewMode, initG6]);

  const handleResetToDefaultModules = useCallback(() => {
    handleModuleChange(defaultModules);
  }, [defaultModules, handleModuleChange]);

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    if (mode === '3D') {
      destroyG6();
      setViewMode('3D');
      if (bodyRef.current) {
        setBodySize({ w: bodyRef.current.offsetWidth, h: bodyRef.current.offsetHeight });
      }
    } else {
      setViewMode('2D');
      setTimeout(() => {
        if (containerRef.current && visibleData) initG6(containerRef.current, visibleData);
      }, 50);
    }
  }, [visibleData, initG6, destroyG6]);

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
    if (!visibleData || !searchValue.trim()) return [];
    const kw = searchValue.trim().toLowerCase();
    const matched: { value: string; label: string }[] = [];
    for (const n of visibleData.fgNodes) {
      const meta = tableMeta.get(n.id);
      const name = meta?.name ?? '';
      const sk = meta?.sheetKey ?? '';
      if (n.id.toLowerCase().includes(kw) || name.toLowerCase().includes(kw) || sk.includes(kw)) {
        const display = name ? `${n.id} - ${name}` : n.id;
        matched.push({ value: n.id, label: sk ? `${display} (${sk})` : display });
      }
      if (matched.length >= 20) break;
    }
    return matched;
  }, [visibleData, searchValue, tableMeta]);

  const handleSearchSelect = useCallback((nodeId: string) => {
    setSearchValue('');
    handleGraphNodeSelect(nodeId);
  }, [handleGraphNodeSelect]);

  const abs: React.CSSProperties = { position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' };

  return (
    <Modal title="Ragic 跨表關聯圖譜" open={open} onCancel={onClose} footer={null}
      width="90vw" styles={{ body: { height: '75vh', display: 'flex', flexDirection: 'column', padding: 0 } }}
      destroyOnHidden afterOpenChange={handleAfterOpenChange}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 16px', borderBottom: '1px solid #f0f0f0', flexWrap: 'wrap', gap: 6 }}>
        <Space size="small" wrap>
          <Segmented value={viewMode} onChange={v => handleViewModeChange(v as ViewMode)} size="small"
            options={[{ label: '2D', value: '2D' }, { label: '3D', value: '3D' }]} />
          {hasData && (
            <>
              <Select mode="multiple" size="small" value={selectedModules} onChange={handleModuleChange}
                options={MODULE_OPTIONS} maxTagCount={2} style={{ minWidth: 200 }} placeholder="選擇模組" />
              <Button size="small" onClick={handleResetToDefaultModules} disabled={isUsingDefaultModules}>回到預設模組</Button>
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
          {hasData && (
            <AutoComplete options={searchOptions()} onSelect={handleSearchSelect}
              value={searchValue} onChange={setSearchValue} style={{ width: 240 }}
              popupStyle={{ zIndex: 9999 }}>
              <Input size="small" placeholder="搜尋 Table ID / 表名 / Sheet Key" prefix={<SearchOutlined />} allowClear />
            </AutoComplete>
          )}
          {highlightSet && <Button size="small" icon={<CloseCircleOutlined />} onClick={clearHighlight}>清除高亮</Button>}
          {hasData && visibleData && <Text type="secondary">{visibleData.g6Nodes.length} 表 / {visibleData.g6Edges.length} 關聯</Text>}
        </Space>
      </div>
      <div ref={bodyRef} style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {loading && <div style={{ ...abs, zIndex: 10 }}><Spin description="載入圖譜中..." /></div>}
        {!loading && !hasData && <div style={abs}><Empty description="尚無關聯資料" /></div>}
        {viewMode === '2D' && <div ref={containerRef} style={{ width: '100%', height: '100%' }} />}
        {viewMode === '3D' && hasData && visibleData && (
          <div style={{ position: 'relative', zIndex: 0, width: '100%', height: '100%' }}>
            <SchemaGraph3D ref={fg3dRef} nodes={visibleData.fgNodes} links={visibleData.fgLinks}
              width={bodySize.w} height={bodySize.h} highlightSet={highlightSet}
              onNodeClick={handleGraphNodeSelect} onBackgroundClick={clearHighlight} />
          </div>
        )}
      </div>
    </Modal>
  );
}
