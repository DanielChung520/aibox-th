/**
 * @file        EEA-CRM 客戶地圖元件
 * @description Leaflet 地圖整合 — 包含客戶標記、篩選面板、圖例顯示、統計摘要
 *              仿照衛福部長照地圖（ltcpap.mohw.gov.tw）的左側覆蓋面板 + 全幅地圖佈局
 * @lastUpdate  2026-06-22
 * @author      Sisyphus-Junior
 * @version     2.0.0
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Input, Button, Checkbox, Typography, Spin, Card, Space, Drawer, App } from 'antd';
import { SearchOutlined, EyeOutlined, CalendarOutlined, RobotOutlined, ReloadOutlined, FlagOutlined, AimOutlined } from '@ant-design/icons';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import { useContentTokens } from '../../contexts/AppThemeProvider';

/** 台灣福祉總部位置 */
const HQ_POSITION: [number, number] = [24.9907, 121.4205];
import { crmApi, CRMMapMarker, CRMMapResponse } from '../../services/api';
import { useCrmStore } from '../../stores/crmStore';

const { Text } = Typography;

/* ---------- Constants ---------- */

const ABC_CONFIG: Record<string, { color: string; radius: number; label: string }> = {
  A: { color: '#52c41a', radius: 10, label: 'A 類 · 高價值' },
  B: { color: '#faad14', radius: 8, label: 'B 類 · 中等' },
  C: { color: '#ff4d4f', radius: 6, label: 'C 類 · 一般' },
  E: { color: '#b37feb', radius: 7, label: 'E 類 · 外部來源' },
};

const SERVICE_TYPES = ['養護機構', '居家服務', '護理之家', '長照機構', '社區服務', '其他'];

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
  const { message } = App.useApp();
  const tokens = useContentTokens();
  const { openAgentDrawer } = useCrmStore();

  const DRAWER_WIDTH = 300;
  const CACHE_KEY = 'crm_map_cache';
  const CACHE_MAX_AGE = 3600000;

  // IndexedDB helpers
  const idb = useMemo(() => ({
    async get(key: string) {
      return new Promise<unknown>((resolve) => {
        try {
          const req = indexedDB.open('CRMmap', 1);
          req.onupgradeneeded = () => req.result.createObjectStore('kv');
          req.onsuccess = () => {
            const tx = req.result.transaction('kv', 'readonly');
            const getReq = tx.objectStore('kv').get(key);
            getReq.onsuccess = () => resolve(getReq.result);
            getReq.onerror = () => resolve(null);
          };
          req.onerror = () => resolve(null);
        } catch { resolve(null); }
      });
    },
    async set(key: string, value: unknown) {
      return new Promise<void>((resolve) => {
        try {
          const req = indexedDB.open('CRMmap', 1);
          req.onupgradeneeded = () => req.result.createObjectStore('kv');
          req.onsuccess = () => {
            const tx = req.result.transaction('kv', 'readwrite');
            tx.objectStore('kv').put(value, key);
            tx.oncomplete = () => resolve();
            tx.onerror = () => resolve();
          };
          req.onerror = () => resolve();
        } catch { resolve(); }
      });
    },
    async remove(key: string) {
      return new Promise<void>((resolve) => {
        try {
          const req = indexedDB.open('CRMmap', 1);
          req.onupgradeneeded = () => req.result.createObjectStore('kv');
          req.onsuccess = () => {
            const tx = req.result.transaction('kv', 'readwrite');
            tx.objectStore('kv').delete(key);
            tx.oncomplete = () => resolve();
            tx.onerror = () => resolve();
          };
          req.onerror = () => resolve();
        } catch { resolve(); }
      });
    },
  }), []);

  /* ── State ── */
  const [searchQuery, setSearchQuery] = useState('');
  const [abcFilter, setAbcFilter] = useState<string>('all');
  const [serviceTypeFilter, setServiceTypeFilter] = useState<string[]>([]);
  const [markers, setMarkers] = useState<CRMMapMarker[]>([]);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<CRMMapResponse['summary'] | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [activeMarker, setActiveMarker] = useState<typeof filteredCustomers[number] | null>(null);
  const [startPoint, setStartPoint] = useState<typeof filteredCustomers[number] | null>(null);
  const [endPoint, setEndPoint] = useState<typeof filteredCustomers[number] | null>(null);
  const [baselineStats, setBaselineStats] = useState<{ total: number; aCount: number; bCount: number; cCount: number; eCount: number } | null>(null);

  /* ── Refs ── */
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerGroupRef = useRef<L.LayerGroup | null>(null);
  const initDoneRef = useRef(false);

  /* ── Fetch data from API (with IndexedDB cache) ── */
  const loadMapData = useCallback(async (forceRefresh = false) => {
    if (!forceRefresh) {
      const cached = await idb.get(CACHE_KEY) as { ts: number; markers: CRMMapMarker[]; summary: CRMMapResponse['summary'] } | null;
      if (cached && Date.now() - cached.ts < CACHE_MAX_AGE) {
        setMarkers(cached.markers);
        setSummary(cached.summary);
        computeBaseline(cached.markers);
        setLoading(false);
        return;
      }
    }

    setLoading(true);
    try {
      const res = await crmApi.map();
      const full = res.data.markers;
      const light: CRMMapMarker[] = full.map((m) => ({
        id: m.id, name: m.name, lat: m.lat, lng: m.lng,
        status: m.status || '', abc_grade: m.abc_grade,
        category: m.category, source: m.source || '',
        city: m.city, address: m.address, sales_rep: m.sales_rep,
        phone: m.phone,
      }));
      const data = { ts: Date.now(), markers: light, summary: res.data.summary };
      await idb.set(CACHE_KEY, data);
      setMarkers(light);
      setSummary(res.data.summary);
      computeBaseline(light);
    } catch (err) {
      console.error('Failed to load CRM map data:', err);
    } finally {
      setLoading(false);
    }
  }, [idb]);

  const computeBaseline = useCallback((data: CRMMapMarker[]) => {
    let aCount = 0, bCount = 0, cCount = 0, eCount = 0;
    for (const m of data) {
      const g = m.abc_grade;
      if (g === 'A') aCount++;
      else if (g === 'B') bCount++;
      else if (g === 'E') eCount++;
      else cCount++;
    }
    setBaselineStats({ total: data.length, aCount, bCount, cCount, eCount });
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
        phone: m.phone || '',
        lastVisit: 'N/A' as string,
        revenue: 0,
      }))
      .filter(c => {
        if (abcFilter !== 'all' && c.abc !== abcFilter) return false;
        if (serviceTypeFilter.length > 0 && !c.tags.some(t => serviceTypeFilter.includes(t))) return false;
        if (searchQuery) {
          const q = searchQuery.toLowerCase();
          if (!c.name.toLowerCase().includes(q) && !c.address.toLowerCase().includes(q)) return false;
        }
        return true;
      });
  }, [markers, abcFilter, serviceTypeFilter, searchQuery]);

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
        zoomControl: false,
        attributionControl: true,
      });
      L.control.zoom({ position: 'topright' }).addTo(map);

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

    /* HQ marker */
    const hqIcon = L.divIcon({
      html: '<div style="width:24px;height:24px;background:#ff4d4f;border:3px solid #fff;border-radius:50%;box-shadow:0 2px 8px rgba(255,77,79,0.5);display:flex;align-items:center;justify-content:center;"><div style="width:6px;height:6px;background:#fff;border-radius:50%;"></div></div>',
      iconSize: [24, 24],
      iconAnchor: [12, 12],
      className: '',
    });
    L.marker(HQ_POSITION, { icon: hqIcon, zIndexOffset: 1000 })
      .addTo(map)
      .bindTooltip('🏢 台灣福祉總部', { permanent: true, direction: 'top', offset: [0, -16] });

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

  /* ── Route markers (start/end) ── */
  const routeLayerRef = useRef<L.LayerGroup | null>(null);
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    if (!routeLayerRef.current) {
      routeLayerRef.current = L.layerGroup().addTo(mapInstanceRef.current);
    }
    routeLayerRef.current.clearLayers();

    if (startPoint) {
      L.circleMarker([startPoint.lat, startPoint.lng], {
        radius: 14, fillColor: '#52c41a', color: '#fff', weight: 3, fillOpacity: 1,
      }).addTo(routeLayerRef.current).bindTooltip('🚩 起點', { permanent: true, direction: 'top' });
    }
    if (endPoint) {
      L.circleMarker([endPoint.lat, endPoint.lng], {
        radius: 14, fillColor: '#ff4d4f', color: '#fff', weight: 3, fillOpacity: 1,
      }).addTo(routeLayerRef.current).bindTooltip('🎯 終點', { permanent: true, direction: 'top' });
    }
  }, [startPoint, endPoint]);

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
          background: tokens.contentBg,
          zIndex: 2000,
          borderRadius: 8,
        }}>
          <Spin size="large" />
          <div style={{ marginTop: 12, color: tokens.textSecondary, fontSize: 14 }}>載入地圖資料...</div>
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

      {/* ── 左側篩選 Drawer ── */}
      <Drawer
        title={<span style={{ fontSize: 14 }}>🔍 篩選條件</span>}
        placement="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={DRAWER_WIDTH}
        styles={{ body: { padding: '16px 20px' } }}
        mask={false}
        getContainer={false}
        style={{ position: 'absolute', zIndex: 1000 }}
      >
        {/* Search + Refresh */}
        <div style={{ marginBottom: 16, display: 'flex', gap: 6 }}>
          <Input
            prefix={<SearchOutlined style={{ color: tokens.iconDefault }} />}
            placeholder="搜尋機構名稱或地址"
            allowClear
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            size="middle"
            style={{ flex: 1 }}
          />
          <Button size="small" icon={<ReloadOutlined />} onClick={async () => {
            await idb.remove(CACHE_KEY);
            loadMapData(true);
          }} />
        </div>

        {/* ABC/E Classification with counts */}
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
            分類
            <Text style={{ fontSize: 11, fontWeight: 400, marginLeft: 6 }}>{baselineStats?.total ?? 0} 筆</Text>
          </Text>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {(['all', 'A', 'B', 'C', 'E'] as const).map(key => {
              const bs = baselineStats;
              const count = key === 'all' ? (bs?.total ?? 0)
                : key === 'A' ? (bs?.aCount ?? 0)
                : key === 'B' ? (bs?.bCount ?? 0)
                : key === 'C' ? (bs?.cCount ?? 0)
                : (bs?.eCount ?? 0);
              return (
                <Button
                  key={key}
                  size="small"
                  type={abcFilter === key ? 'primary' : 'default'}
                  style={key === 'all' ? { fontSize: 12 } : {
                    background: abcFilter === key ? ABC_CONFIG[key].color : `${ABC_CONFIG[key].color}18`,
                    borderColor: ABC_CONFIG[key].color,
                    color: abcFilter === key ? '#fff' : ABC_CONFIG[key].color,
                    fontSize: 12,
                  }}
                  onClick={() => setAbcFilter(key)}
                >
                  {key === 'all' ? '全部' : `${key} 類`} {count}
                </Button>
              );
            })}
          </div>
        </div>

        {/* Institution type */}
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>機構類型</Text>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
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

        {/* 路線狀態 */}
        {(startPoint || endPoint) && (
          <div style={{ marginBottom: 8, padding: '8px 10px', background: tokens.tableHeaderBg, borderRadius: 8 }}>
            <div style={{ fontSize: 12, lineHeight: 1.8 }}>
              {startPoint && <div>🚩 起點：<Text strong>{startPoint.name}</Text></div>}
              {endPoint && <div>🎯 終點：<Text strong>{endPoint.name}</Text></div>}
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <Button size="small" type="primary" icon={<AimOutlined />} style={{ flex: 1, fontSize: 11 }}
                disabled={!startPoint || !endPoint}
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('crm:route', { detail: { startId: startPoint?.id, endId: endPoint?.id } }));
                }}>
                計算路程
              </Button>
              <Button size="small" style={{ fontSize: 11 }}
                onClick={() => { setStartPoint(null); setEndPoint(null); }}>
                清除路線
              </Button>
            </div>
          </div>
        )}

        {/* 客戶詳情 */}
        {activeMarker && (
          <div style={{
            borderTop: `1px solid ${tokens.tableHeaderBg}`, marginTop: 8, paddingTop: 12,
          }}>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>📋 {activeMarker.name}</Text>
            <div style={{ fontSize: 12, lineHeight: 1.8 }}>
              {activeMarker.salesRep && <div>👤 {activeMarker.salesRep}</div>}
              {activeMarker.address && <div>📍 {activeMarker.address}</div>}
              {activeMarker.phone && <div>📞 {activeMarker.phone}</div>}
            </div>
          </div>
        )}
      </Drawer>

      {/* 展開按鈕（抽屜關閉時可在左側點擊重新打開） */}
      {!drawerOpen && (
        <Button
          size="small"
          type="default"
          icon={<SearchOutlined />}
          onClick={() => setDrawerOpen(true)}
          style={{
            position: 'absolute', top: 16, left: 16, zIndex: 1000,
            boxShadow: tokens.tableShadow,
            borderRadius: 8,
          }}
        />
      )}

      {/* ── 浮動行動選單（點擊標記後顯示） ── */}
      {activeMarker && (
        <div style={{
          position: 'absolute',
          bottom: 80,
          left: drawerOpen ? 316 : 16,
          zIndex: 1000,
          transition: 'left 0.25s ease',
        }}>
          <Card size="small" style={{
            width: 200, borderRadius: 10,
            boxShadow: tokens.cardShadow,
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
              <Button size="small" block icon={<FlagOutlined />}
                onClick={() => { setStartPoint(activeMarker); setActiveMarker(null); }}
                type={startPoint?.id === activeMarker.id ? 'primary' : 'default'}>
                起點
              </Button>
              <Button size="small" block icon={<AimOutlined />}
                onClick={() => { setEndPoint(activeMarker); setActiveMarker(null); }}
                type={endPoint?.id === activeMarker.id ? 'primary' : 'default'}>
                終點
              </Button>
              <Button size="small" block
                onClick={() => {
                  if (startPoint && endPoint) {
                    message.success(`已規劃拜訪路線：${startPoint.name} → ${endPoint.name}`);
                    window.dispatchEvent(new CustomEvent('crm:route', { detail: { startId: startPoint.id, endId: endPoint.id } }));
                  } else {
                    message.warning('請先設定起點與終點');
                  }
                  setActiveMarker(null);
                }}>
                規劃拜訪
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
        boxShadow: tokens.tableShadow,
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
