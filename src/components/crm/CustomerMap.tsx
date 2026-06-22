/**
 * @file        EEA-CRM 客戶地圖元件
 * @description Leaflet 地圖整合 — 包含客戶標記、篩選面板、圖例顯示、統計摘要
 *              仿照衛福部長照地圖（ltcpap.mohw.gov.tw）的左側覆蓋面板 + 全幅地圖佈局
 * @lastUpdate  2026-06-22
 * @author      Sisyphus-Junior
 * @version     2.0.0
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Input, Button, Checkbox, Typography, Tag, Spin, Card, Space } from 'antd';
import { SearchOutlined, EyeOutlined, CalendarOutlined, RobotOutlined, ReloadOutlined } from '@ant-design/icons';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { crmApi, CRMMapMarker, CRMMapResponse } from '../../services/api';
import { useCrmStore } from '../../stores/crmStore';

const { Text } = Typography;

/* ---------- Constants ---------- */

const ABC_CONFIG: Record<string, { color: string; radius: number; label: string }> = {
  A: { color: '#52c41a', radius: 10, label: 'A 類 · 高價值' },
  B: { color: '#faad14', radius: 8, label: 'B 類 · 中等' },
  C: { color: '#ff4d4f', radius: 6, label: 'C 類 · 一般' },
  E: { color: '#722ed1', radius: 7, label: 'E 類 · 外部來源' },
};

const REGIONS = ['北部', '中部', '南部', '東部'] as const;

const SERVICE_TYPES = ['養護機構', '居家服務', '護理之家', '長照機構', '社區服務'];

/** Check if category array contains meaningful Chinese labels (not just ASCII codes) */
function hasExternalType(category?: string[]): boolean {
  if (!category) return false;
  return category.some(c => /[\u4e00-\u9fff]/.test(c));
}

/** Classify a city string into one of the four Taiwan regions */
function classifyRegion(city?: string): string {
  if (!city) return '未分類';
  if (
    city.startsWith('台北') || city.startsWith('新北') ||
    city.startsWith('桃園') || city.startsWith('基隆') ||
    city.startsWith('宜蘭') || city.startsWith('新竹')
  ) return '北部';
  if (
    city.startsWith('台中') || city.startsWith('彰化') ||
    city.startsWith('南投') || city.startsWith('苗栗') ||
    city.startsWith('雲林')
  ) return '中部';
  if (
    city.startsWith('高雄') || city.startsWith('台南') ||
    city.startsWith('嘉義') || city.startsWith('屏東')
  ) return '南部';
  if (city.startsWith('花蓮') || city.startsWith('台東')) return '東部';
  return '未分類';
}

/* ==================== Component ==================== */

export default function CustomerMapComponent() {
  const tokens = useContentTokens();
  const { openAgentDrawer } = useCrmStore();

  const DRAWER_WIDTH = 320;
  const CACHE_KEY = 'crm_map_cache';
  const CACHE_MAX_AGE = 3600000; // 1 hour

  /* ── State ── */
  const [searchQuery, setSearchQuery] = useState('');
  const [abcFilter, setAbcFilter] = useState<string>('all');
  const [regionFilter, setRegionFilter] = useState<string>('all');
  const [serviceTypeFilter, setServiceTypeFilter] = useState<string[]>([]);
  const [markers, setMarkers] = useState<CRMMapMarker[]>([]);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<CRMMapResponse['summary'] | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [activeMarker, setActiveMarker] = useState<typeof filteredCustomers[number] | null>(null);

  /* ── Refs ── */
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerGroupRef = useRef<L.LayerGroup | null>(null);
  const initDoneRef = useRef(false);

  /* ── Fetch data from API (with localStorage cache) ── */
  const loadMapData = useCallback((forceRefresh = false) => {
    const tryCache = () => {
      if (forceRefresh) return null;
      try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) return null;
        const cache = JSON.parse(raw);
        if (Date.now() - cache.ts > CACHE_MAX_AGE) return null;
        return cache;
      } catch { return null; }
    };

    const cached = tryCache();
    if (cached) {
      setMarkers(cached.markers);
      setSummary(cached.summary);
      setLoading(false);
      return;
    }

    setLoading(true);
    crmApi.map()
      .then(res => {
        const data = { ts: Date.now(), markers: res.data.markers, summary: res.data.summary };
        try { localStorage.setItem(CACHE_KEY, JSON.stringify(data)); } catch { /* quota exceeded */ }
        setMarkers(res.data.markers);
        setSummary(res.data.summary);
      })
      .catch(err => {
        console.error('Failed to fetch CRM map data:', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => { loadMapData(); }, [loadMapData]);

  /* ── Filtered data ── */
  const filteredCustomers = useMemo(() => {
    return markers
      .map(m => ({
        id: m.id,
        name: m.name,
        lat: m.lat,
        lng: m.lng,
        abc: (m.abc_grade && 'ABC'.includes(m.abc_grade)) ? m.abc_grade : (hasExternalType(m.category || m.org_tags) ? 'E' : 'C'),
        region: classifyRegion(m.city),
        tags: m.category || m.org_tags || [],
        address: m.address || '',
        salesRep: m.sales_rep || '',
        lastVisit: 'N/A' as string,
        revenue: 0,
      }))
      .filter(c => {
        if (abcFilter !== 'all' && c.abc !== abcFilter) return false;
        if (regionFilter !== 'all' && c.region !== regionFilter) return false;
        if (serviceTypeFilter.length > 0 && !c.tags.some(t => serviceTypeFilter.includes(t))) return false;
        if (searchQuery) {
          const q = searchQuery.toLowerCase();
          if (!c.name.toLowerCase().includes(q) && !c.address.toLowerCase().includes(q)) return false;
        }
        return true;
      });
  }, [markers, abcFilter, regionFilter, serviceTypeFilter, searchQuery]);

  const stats = useMemo(() => {
    const total = filteredCustomers.length;
    const aCount = filteredCustomers.filter(c => c.abc === 'A').length;
    const bCount = filteredCustomers.filter(c => c.abc === 'B').length;
    const cCount = filteredCustomers.filter(c => c.abc === 'C').length;
    const eCount = filteredCustomers.filter(c => c.abc === 'E').length;
    return { total, aCount, bCount, cCount, eCount, dbTotal: summary?.total ?? 0 };
  }, [filteredCustomers, summary]);

  /* ── Init map (once) ── */
  useEffect(() => {
    if (!mapContainerRef.current || initDoneRef.current) return;

    // Dynamically import markercluster to ensure L is available
    (window as any).L = L;
    import('leaflet.markercluster').then(() => {
      if (!mapContainerRef.current || initDoneRef.current) return;
      initDoneRef.current = true;

      const map = L.map(mapContainerRef.current, {
        center: [23.8, 121.0],
        zoom: 7.5,
        zoomControl: true,
        attributionControl: true,
      });

    /* CartoDB tiles (more reliable than raw OSM) */
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    /* Marker Cluster layer */
    const markers = L.markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 60,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      disableClusteringAtZoom: 16,
    }).addTo(map);
    markerGroupRef.current = markers;
    mapInstanceRef.current = map;

    /* Tooltip visibility on zoom */
    map.on('zoomend', () => {
      const zoom = map.getZoom();
      markerGroupRef.current?.eachLayer(layer => {
        if (layer instanceof L.CircleMarker) {
          if (zoom >= 9) layer.openTooltip();
          else layer.closeTooltip();
        }
      });
    });

    /* ResizeObserver — fixes Leaflet in dynamic containers */
    const observer = new ResizeObserver(() => { map.invalidateSize(); });
    observer.observe(mapContainerRef.current);

    /* Force invalidate after mount — tabs may hide container initially */
    const forceInvalidate = () => {
      const el = mapContainerRef.current;
      if (el && el.offsetHeight > 0 && el.offsetWidth > 0) {
        map.invalidateSize();
      }
    };
    const t1 = setTimeout(forceInvalidate, 200);
    const t2 = setTimeout(forceInvalidate, 800);
    const t3 = setTimeout(forceInvalidate, 2000);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      observer.disconnect();
      map.remove();
      mapInstanceRef.current = null;
      markerGroupRef.current = null;
      initDoneRef.current = false;
    };
    }); // end of .then()
  }, []);

  /* ── Retry invalidateSize when container becomes visible (tab switch) ── */
  useEffect(() => {
    const el = mapContainerRef.current;
    if (!el) return;
    const observer = new MutationObserver(() => {
      if (el.offsetHeight > 0 && el.offsetWidth > 0) {
        mapInstanceRef.current?.invalidateSize();
      }
    });
    observer.observe(el, { attributes: true, attributeFilter: ['style', 'class'] });
    return () => observer.disconnect();
  }, []);

  /* ── Update markers when filters change ── */
  useEffect(() => {
    const markers = markerGroupRef.current;
    const map = mapInstanceRef.current;
    if (!markers || !map) return;

    markers.clearLayers();

    filteredCustomers.forEach(c => {
      const cfg = ABC_CONFIG[c.abc] || ABC_CONFIG['C'];
      const marker = L.circleMarker([c.lat, c.lng], {
        radius: cfg.radius,
        fillColor: cfg.color,
        color: '#fff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.75,
      });

      marker.bindTooltip(c.name, { direction: 'top', offset: [0, -(cfg.radius + 4)], className: 'crm-map-tooltip' });
      marker.bindPopup(
        L.popup({ closeButton: true, maxWidth: 240, className: 'crm-map-popup' })
          .setContent(`
            <div style="min-width:180px;font-family:-apple-system,sans-serif;">
              <div style="font-weight:600;font-size:13px;margin-bottom:4px;">${c.name}</div>
              <div style="display:flex;gap:4;margin-bottom:6px;">
                <span style="display:inline-block;padding:0 8px;border-radius:8px;font-size:10px;font-weight:600;color:#fff;background:${cfg.color};">${c.abc} 類</span>
                <span style="display:inline-block;padding:0 8px;border-radius:8px;font-size:10px;background:#f0f0f0;color:#666;">${c.region}</span>
              </div>
              <div style="margin-bottom:4px;font-size:11px;color:#555;">📍 ${c.address || ''}</div>
            </div>
          `)
      );
      marker.on('click', () => setActiveMarker(c));
      markers.addLayer(marker);
    });

    /* Dismiss floating menu on map click */
    map.on('click', () => setActiveMarker(null));
  }, [filteredCustomers]);

  /* ── Handlers ── */
  const toggleServiceType = (type: string) => {
    setServiceTypeFilter(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type],
    );
  };

  /* ======== Render ======== */
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Map container */}
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', borderRadius: 8 }} />

      {/* ── Loading overlay ── */}
      {loading && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(255,255,255,0.65)',
          zIndex: 2000,
          borderRadius: 8,
        }}>
          <Spin size="large" />
          <div style={{ marginTop: 12, color: '#666', fontSize: 14 }}>載入地圖資料...</div>
        </div>
      )}

      {/* ── Inline styles for Leaflet overrides ── */}
      <style>{`
        .crm-map-tooltip {
          background: rgba(255,255,255,0.95) !important;
          border: none !important;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
          border-radius: 6px !important;
          padding: 4px 10px !important;
          font-size: 12px !important;
          font-weight: 600 !important;
          color: #333 !important;
          white-space: nowrap;
        }
        .crm-map-tooltip::before {
          border-top-color: rgba(255,255,255,0.95) !important;
        }
        .leaflet-popup-content-wrapper {
          border-radius: 10px !important;
          box-shadow: 0 4px 20px rgba(0,0,0,0.18) !important;
        }
        .leaflet-popup-content {
          margin: 12px 16px !important;
        }
      `}</style>

      {/* ── 左側篩選抽屜 ── */}
      <div style={{
        position: 'absolute',
        top: 16,
        left: drawerOpen ? 16 : -DRAWER_WIDTH + 36,
        width: DRAWER_WIDTH,
        maxHeight: 'calc(100% - 32px)',
        overflowY: 'auto',
        background: tokens.contentBg,
        borderRadius: 12,
        boxShadow: drawerOpen ? '0 4px 24px rgba(0,0,0,0.12)' : 'none',
        padding: drawerOpen ? '18px 20px' : '0',
        zIndex: 1000,
        transition: 'left 0.25s ease, box-shadow 0.25s ease',
      }}>
        {/* 收合/展開按鈕 */}
        <div style={{
          position: drawerOpen ? 'absolute' : 'relative',
          top: drawerOpen ? 8 : 0,
          right: drawerOpen ? 8 : 'auto',
          float: drawerOpen ? 'right' : 'none',
          zIndex: 2,
        }}>
          <Button
            size="small"
            type={drawerOpen ? 'text' : 'default'}
            onClick={() => setDrawerOpen(!drawerOpen)}
            style={{
              width: 28, height: 28, fontSize: 14,
              border: drawerOpen ? 'none' : '1px solid #d9d9d9',
              boxShadow: '0 2px 6px rgba(0,0,0,0.1)',
              borderRadius: 8,
            }}
          >
            {drawerOpen ? '◀' : '▶'}
          </Button>
        </div>

        {drawerOpen && (<>
          {/* Search + Refresh */}
          <div style={{ marginBottom: 16, display: 'flex', gap: 6 }}>
            <Input
              prefix={<SearchOutlined style={{ color: '#999' }} />}
              placeholder="搜尋機構名稱或地址"
              allowClear
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              size="middle"
              style={{ flex: 1 }}
            />
            <Button size="small" icon={<ReloadOutlined />} onClick={() => {
              localStorage.removeItem(CACHE_KEY);
              loadMapData(true);
            }} />
          </div>

          {/* ABC Classification */}
          <div style={{ marginBottom: 16 }}>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>ABC／E 分類</Text>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {(['all', 'A', 'B', 'C', 'E'] as const).map(key => (
                <Button
                  key={key}
                  size="small"
                  type={abcFilter === key ? 'primary' : 'default'}
                  style={
                    abcFilter === key && key !== 'all'
                      ? { background: ABC_CONFIG[key].color, borderColor: ABC_CONFIG[key].color, color: '#fff' }
                      : { fontSize: 12 }
                  }
                  onClick={() => setAbcFilter(key)}
                >
                  {key === 'all' ? '全部' : `${key} 類`}
                </Button>
              ))}
            </div>
          </div>

          {/* Region */}
          <div style={{ marginBottom: 16 }}>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>區域</Text>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {(['all', ...REGIONS] as const).map(key => (
                <Button
                  key={key}
                  size="small"
                  type={regionFilter === key ? 'primary' : 'default'}
                  onClick={() => setRegionFilter(key)}
                  style={{ fontSize: 12 }}
                >
                  {key === 'all' ? '全部' : key}
                </Button>
              ))}
            </div>
          </div>

          {/* Service type */}
          <div style={{ marginBottom: 16 }}>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>服務類型</Text>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {SERVICE_TYPES.map(type => (
                <Checkbox
                  key={type}
                  checked={serviceTypeFilter.includes(type)}
                  onChange={() => toggleServiceType(type)}
                  style={{ fontSize: 13 }}
                >
                  {type}
                </Checkbox>
              ))}
            </div>
          </div>

          {/* Divider */}
          <div style={{ height: 1, background: '#f0f0f0', marginBottom: 14 }} />

          {/* Stats */}
          <div>
            <Text style={{ fontSize: 13, color: tokens.textSecondary }}>
              顯示 <span style={{ fontWeight: 600, color: tokens.colorTextBase }}>{stats.total}</span> 筆機構
              {stats.dbTotal > 0 && (
                <span style={{ color: tokens.textSecondary }}> (資料庫共 {stats.dbTotal})</span>
              )}
            </Text>
            <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
              <Tag color="#52c41a" style={{ borderRadius: 6, fontSize: 12 }}>A 類：{stats.aCount}</Tag>
              <Tag color="#faad14" style={{ borderRadius: 6, fontSize: 12 }}>B 類：{stats.bCount}</Tag>
              <Tag color="#ff4d4f" style={{ borderRadius: 6, fontSize: 12 }}>C 類：{stats.cCount}</Tag>
              <Tag color="#722ed1" style={{ borderRadius: 6, fontSize: 12 }}>E 類：{stats.eCount}</Tag>
            </div>
          </div>
        </>)}
      </div>

      {/* ── 浮動行動選單（點擊標記後顯示） ── */}
      {activeMarker && (
        <div style={{
          position: 'absolute',
          bottom: 80,
          left: drawerOpen ? 352 : 52,
          zIndex: 1000,
          transition: 'left 0.25s ease',
        }}>
          <Card size="small" style={{
            width: 200, borderRadius: 10,
            boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
          }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6, paddingRight: 20 }}>
              {activeMarker.name}
              <Button size="small" type="text"
                onClick={() => setActiveMarker(null)}
                style={{ position: 'absolute', top: 4, right: 4, fontSize: 12, width: 22, height: 22, lineHeight: '16px' }}
              >✕</Button>
            </div>
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
              <Button size="small" block icon={<EyeOutlined />}
                onClick={() => { openAgentDrawer('customers', activeMarker.id); setActiveMarker(null); }}>
                查看詳情
              </Button>
              <Button size="small" block icon={<CalendarOutlined />}
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('crm:schedule', { detail: { recordId: activeMarker.id } }));
                  setActiveMarker(null);
                }}>
                行程規劃
              </Button>
              <Button size="small" block icon={<RobotOutlined />}
                onClick={() => { openAgentDrawer('customers', activeMarker.id); setActiveMarker(null); }}>
                AI Agent
              </Button>
            </Space>
          </Card>
        </div>
      )}

      {/* ── Legend (bottom-right) ── */}
      <div style={{
        position: 'absolute',
        bottom: 24,
        right: 16,
        background: tokens.contentBg,
        borderRadius: 10,
        padding: '10px 14px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.12)',
        fontSize: 12,
        zIndex: 1000,
        minWidth: 120,
      }}>
        <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 13, color: tokens.colorTextBase }}>
          ABC／E 分類圖例
        </div>
        {(['A', 'B', 'C', 'E'] as const).map(c => (
          <div key={c} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
            <span style={{
              width: ABC_CONFIG[c].radius,
              height: ABC_CONFIG[c].radius,
              borderRadius: '50%',
              background: ABC_CONFIG[c].color,
              border: '2px solid #fff',
              boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
              display: 'inline-block',
              flexShrink: 0,
            }} />
            <span style={{ color: tokens.textSecondary }}>{ABC_CONFIG[c].label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
