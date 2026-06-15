/**
 * @file        EEA-CRM 客戶地圖元件
 * @description Leaflet 地圖整合 — 包含客戶標記、篩選面板、圖例顯示、統計摘要
 *              仿照衛福部長照地圖（ltcpap.mohw.gov.tw）的左側覆蓋面板 + 全幅地圖佈局
 * @lastUpdate  2026-06-08
 * @author      Sisyphus-Junior
 * @version     1.0.0
 */

import { useState, useEffect, useRef, useMemo } from 'react';
import { Input, Button, Checkbox, Typography, Tag } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useContentTokens } from '../../contexts/AppThemeProvider';

const { Text } = Typography;

/* ---------- Types ---------- */

interface CustomerMarker {
  id: string;
  name: string;
  lat: number;
  lng: number;
  abc: 'A' | 'B' | 'C';
  region: '北部' | '中部' | '南部' | '東部';
  tags: string[];
  address: string;
  salesRep: string;
  lastVisit: string;
  revenue: number;
}

/* ---------- Constants ---------- */

const ABC_CONFIG: Record<string, { color: string; radius: number; label: string }> = {
  A: { color: '#52c41a', radius: 10, label: 'A 類 · 高價值' },
  B: { color: '#faad14', radius: 8, label: 'B 類 · 中等' },
  C: { color: '#ff4d4f', radius: 6, label: 'C 類 · 一般' },
};

const REGIONS = ['北部', '中部', '南部', '東部'] as const;

const SERVICE_TYPES = ['養護機構', '居家服務', '護理之家', '長照機構', '社區服務'];

/* ---------- Mock Data (20 筆全台機構) ---------- */

const MOCK_CUSTOMERS: CustomerMarker[] = [
  // ── 北部 (8) ──
  { id: 'C001', name: '陽光老人養護中心',  lat: 25.0330, lng: 121.5432, abc: 'A', region: '北部', tags: ['養護機構'],           address: '台北市大安區忠孝東路四段100號', salesRep: '王大明', lastVisit: '2026-06-05', revenue: 3_200_000 },
  { id: 'C002', name: '仁愛居家長照機構',  lat: 25.0111, lng: 121.4598, abc: 'B', region: '北部', tags: ['居家服務'],           address: '新北市板橋區中山路一段50號',  salesRep: '陳小華', lastVisit: '2026-06-03', revenue: 1_800_000 },
  { id: 'C003', name: '平安社區服務中心',  lat: 25.0338, lng: 121.5645, abc: 'C', region: '北部', tags: ['長照機構', '社區服務'], address: '台北市信義區松仁路30號',      salesRep: '張偉強', lastVisit: '2026-05-28', revenue: 950_000 },
  { id: 'C004', name: '萬華老人服務中心',  lat: 25.0289, lng: 121.4969, abc: 'B', region: '北部', tags: ['社區服務', '長照機構'], address: '台北市萬華區桂林路20號',      salesRep: '林怡君', lastVisit: '2026-06-01', revenue: 1_450_000 },
  { id: 'C005', name: '桃園長照中心',      lat: 24.9934, lng: 121.2994, abc: 'A', region: '北部', tags: ['護理之家', '養護機構'], address: '桃園市桃園區中山路200號',     salesRep: '王大明', lastVisit: '2026-06-06', revenue: 2_800_000 },
  { id: 'C006', name: '新北居家護理所',    lat: 25.0142, lng: 121.4680, abc: 'B', region: '北部', tags: ['居家服務', '護理之家'], address: '新北市中和區景平路80號',      salesRep: '李志明', lastVisit: '2026-05-25', revenue: 1_200_000 },
  { id: 'C007', name: '基隆長照服務中心',  lat: 25.1276, lng: 121.7392, abc: 'C', region: '北部', tags: ['長照機構'],           address: '基隆市中正區義一路30號',       salesRep: '黃淑芬', lastVisit: '2026-05-20', revenue: 780_000 },
  { id: 'C008', name: '士林老人養護所',    lat: 25.0924, lng: 121.5251, abc: 'A', region: '北部', tags: ['養護機構'],           address: '台北市士林區中山北路五段60號', salesRep: '陳小華', lastVisit: '2026-06-02', revenue: 3_500_000 },

  // ── 中部 (5) ──
  { id: 'C009', name: '台中慈濟護理之家',  lat: 24.1555, lng: 120.6839, abc: 'A', region: '中部', tags: ['護理之家'],           address: '台中市北區健行路150號',        salesRep: '張偉強', lastVisit: '2026-06-04', revenue: 4_100_000 },
  { id: 'C010', name: '台中居家服務中心',  lat: 24.1446, lng: 120.6678, abc: 'B', region: '中部', tags: ['居家服務'],           address: '台中市西區公益路100號',        salesRep: '林怡君', lastVisit: '2026-05-30', revenue: 1_600_000 },
  { id: 'C011', name: '彰化老人養護中心',  lat: 24.0767, lng: 120.5359, abc: 'B', region: '中部', tags: ['養護機構'],           address: '彰化市民族路80號',            salesRep: '李志明', lastVisit: '2026-05-22', revenue: 1_350_000 },
  { id: 'C012', name: '南投長照機構',      lat: 23.9110, lng: 120.6872, abc: 'C', region: '中部', tags: ['長照機構'],           address: '南投縣南投市復興路120號',      salesRep: '黃淑芬', lastVisit: '2026-05-15', revenue: 680_000 },
  { id: 'C013', name: '員林社區服務站',    lat: 23.9610, lng: 120.5763, abc: 'C', region: '中部', tags: ['社區服務', '居家服務'], address: '彰化縣員林市中山路二段60號',   salesRep: '吳佩珊', lastVisit: '2026-05-18', revenue: 520_000 },

  // ── 南部 (5) ──
  { id: 'C014', name: '高醫附設護理之家',  lat: 22.6431, lng: 120.3244, abc: 'A', region: '南部', tags: ['護理之家', '養護機構'], address: '高雄市三民區自由一路100號',     salesRep: '王大明', lastVisit: '2026-06-07', revenue: 5_600_000 },
  { id: 'C015', name: '台南老人養護中心',  lat: 22.9937, lng: 120.2020, abc: 'B', region: '南部', tags: ['養護機構'],           address: '台南市中西區民生路一段50號',   salesRep: '陳小華', lastVisit: '2026-05-29', revenue: 1_900_000 },
  { id: 'C016', name: '嘉義長照機構',      lat: 23.4799, lng: 120.4494, abc: 'C', region: '南部', tags: ['長照機構', '居家服務'], address: '嘉義市西區中興路80號',         salesRep: '劉建宏', lastVisit: '2026-05-12', revenue: 720_000 },
  { id: 'C017', name: '高雄居家長照機構',  lat: 22.6218, lng: 120.3300, abc: 'A', region: '南部', tags: ['居家服務', '長照機構'], address: '高雄市苓雅區中正二路60號',     salesRep: '林怡君', lastVisit: '2026-06-06', revenue: 2_900_000 },
  { id: 'C018', name: '屏東社區服務中心',  lat: 22.6761, lng: 120.4959, abc: 'B', region: '南部', tags: ['社區服務'],           address: '屏東縣屏東市中華路100號',      salesRep: '趙雅婷', lastVisit: '2026-05-26', revenue: 1_100_000 },

  // ── 東部 (2) ──
  { id: 'C019', name: '花蓮慈濟長照中心',  lat: 23.9886, lng: 121.6090, abc: 'A', region: '東部', tags: ['長照機構', '護理之家'], address: '花蓮縣花蓮市中央路三段100號',  salesRep: '張偉強', lastVisit: '2026-06-01', revenue: 2_400_000 },
  { id: 'C020', name: '台東居家護理所',    lat: 22.7552, lng: 121.1470, abc: 'C', region: '東部', tags: ['居家服務'],           address: '台東縣台東市更生路60號',       salesRep: '楊宗翰', lastVisit: '2026-05-10', revenue: 450_000 },
];

/* ==================== Component ==================== */

export default function CustomerMapComponent() {
  const tokens = useContentTokens();

  /* ── State ── */
  const [searchQuery, setSearchQuery] = useState('');
  const [abcFilter, setAbcFilter] = useState<string>('all');
  const [regionFilter, setRegionFilter] = useState<string>('all');
  const [serviceTypeFilter, setServiceTypeFilter] = useState<string[]>([]);

  /* ── Refs ── */
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerGroupRef = useRef<L.LayerGroup | null>(null);
  const initDoneRef = useRef(false);

  /* ── Filtered data ── */
  const filteredCustomers = useMemo(() => {
    return MOCK_CUSTOMERS.filter(c => {
      if (abcFilter !== 'all' && c.abc !== abcFilter) return false;
      if (regionFilter !== 'all' && c.region !== regionFilter) return false;
      if (serviceTypeFilter.length > 0 && !c.tags.some(t => serviceTypeFilter.includes(t))) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!c.name.toLowerCase().includes(q) && !c.address.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [abcFilter, regionFilter, serviceTypeFilter, searchQuery]);

  const stats = useMemo(() => {
    const total = filteredCustomers.length;
    const aCount = filteredCustomers.filter(c => c.abc === 'A').length;
    const bCount = filteredCustomers.filter(c => c.abc === 'B').length;
    const cCount = filteredCustomers.filter(c => c.abc === 'C').length;
    return { total, aCount, bCount, cCount };
  }, [filteredCustomers]);

  /* ── Init map (once) ── */
  useEffect(() => {
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

    /* Marker layer */
    const markers = L.layerGroup().addTo(map);
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

    const popupHtml = (c: CustomerMarker, color: string) => `
      <div style="min-width:210px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
        <div style="font-weight:700;font-size:14px;margin-bottom:4px;">${c.name}</div>
        <div style="display:flex;gap:6px;margin-bottom:8px;">
          <span style="display:inline-block;padding:1px 10px;border-radius:10px;font-size:11px;font-weight:600;color:#fff;background:${color};">${c.abc} 類</span>
          <span style="display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;background:#f0f0f0;color:#666;">${c.region}</span>
        </div>
        <div style="font-size:12px;color:#555;margin-bottom:2px;">📍 ${c.address}</div>
        <div style="font-size:12px;color:#555;margin-bottom:2px;">👤 ${c.salesRep}</div>
        <div style="font-size:12px;color:#555;margin-bottom:6px;">📅 ${c.lastVisit}</div>
        <div style="font-size:12px;color:#1677ff;cursor:default;text-align:right;border-top:1px solid #f0f0f0;padding-top:6px;">查看詳情 →</div>
      </div>
    `;

    filteredCustomers.forEach(c => {
      const cfg = ABC_CONFIG[c.abc];
      const marker = L.circleMarker([c.lat, c.lng], {
        radius: cfg.radius,
        fillColor: cfg.color,
        color: '#fff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.75,
      });

      marker.bindTooltip(c.name, {
        permanent: true,
        direction: 'top',
        offset: [0, -(cfg.radius + 4)],
        className: 'crm-map-tooltip',
      });

      marker.bindPopup(popupHtml(c, cfg.color), {
        closeButton: true,
        maxWidth: 280,
        className: 'crm-map-popup',
      });

      markers.addLayer(marker);
    });

    /* Close tooltips if zoom < 9 */
    if (map.getZoom() < 9) {
      markers.eachLayer(layer => {
        if (layer instanceof L.CircleMarker) layer.closeTooltip();
      });
    }
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

      {/* ── Left overlay panel ── */}
      <div style={{
        position: 'absolute',
        top: 16,
        left: 16,
        width: 320,
        maxHeight: 'calc(100% - 32px)',
        overflowY: 'auto',
        background: tokens.contentBg,
        borderRadius: 12,
        boxShadow: '0 4px 24px rgba(0,0,0,0.12)',
        padding: '18px 20px',
        zIndex: 1000,
      }}>
        {/* Search */}
        <div style={{ marginBottom: 16 }}>
          <Input
            prefix={<SearchOutlined style={{ color: '#999' }} />}
            placeholder="搜尋機構名稱或地址"
            allowClear
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            size="middle"
          />
        </div>

        {/* ABC Classification */}
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>ABC 分類</Text>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {(['all', 'A', 'B', 'C'] as const).map(key => (
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
          </Text>
          <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
            <Tag color="#52c41a" style={{ borderRadius: 6, fontSize: 12 }}>A 類：{stats.aCount}</Tag>
            <Tag color="#faad14" style={{ borderRadius: 6, fontSize: 12 }}>B 類：{stats.bCount}</Tag>
            <Tag color="#ff4d4f" style={{ borderRadius: 6, fontSize: 12 }}>C 類：{stats.cCount}</Tag>
          </div>
        </div>
      </div>

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
          ABC 分類圖例
        </div>
        {(['A', 'B', 'C'] as const).map(c => (
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
