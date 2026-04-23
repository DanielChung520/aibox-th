/**
 * @file        ServiceStatusBar
 * @description Header 服務總燈號：合併 /health（基礎設施）與 /api/v1/services（AI 服務）
 *              的狀態。全綠 → 綠燈，任一延遲 → 黃三角，任一異常或 API 不可達 → 紅燈。
 *              點擊展開 Popover 分區列出基礎設施與 AI 服務的名稱、燈號與延遲。
 * @lastUpdate  2026-04-05 22:05:00
 * @author      Daniel Chung
 * @version     3.1.0
 */

import { useState, useEffect, useCallback, useSyncExternalStore } from 'react';
import { Popover, message } from 'antd';
import { CheckCircleOutlined, WarningOutlined, CloseCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { servicesApi, healthApi, type ServiceStatus, type HealthServices, type ServiceInfo } from '../services/api';
import { useContentTokens, useShellTokens } from '../contexts/AppThemeProvider';
import { authStore } from '../stores/auth';

type LightColor = 'green' | 'yellow' | 'red';

interface ServiceLight {
  name: string;
  displayName: string;
  color: LightColor;
  startedAt: string | null;
}

function svcStatusToColor(status: ServiceStatus): LightColor {
  if (status === 'stopped' || status === 'error') return 'red';
  if (status === 'starting' || status === 'stopping') return 'yellow';
  return 'green';
}

function boolToColor(ok: boolean): LightColor {
  return ok ? 'green' : 'red';
}

function worstColor(lights: ServiceLight[]): LightColor {
  if (lights.some((l) => l.color === 'red')) return 'red';
  if (lights.some((l) => l.color === 'yellow')) return 'yellow';
  return 'green';
}

const INFRA_DISPLAY_NAMES: Record<keyof HealthServices, string> = {
  main_api: 'Rust API Gateway',
  chat_api: 'AI Task (Chat)',
  arangodb: 'ArangoDB',
  qdrant: 'Qdrant',
};

const HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000; // 5 分鐘

const COLOR_LABEL: Record<LightColor, string> = {
  green: '正常',
  yellow: '延遲',
  red: '異常',
};

export default function ServiceStatusBar() {
  const contentTokens = useContentTokens();
  const shellTokens = useShellTokens();
  const authState = useSyncExternalStore(
    (cb) => authStore.subscribe(cb),
    () => authStore.getState()
  );
  const isAdmin = authState.user?.role_key === 'admin';

  const [infraLights, setInfraLights] = useState<ServiceLight[]>([]);
  const [aiLights, setAiLights] = useState<ServiceLight[]>([]);
  const [apiUnreachable, setApiUnreachable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [restartingSet, setRestartingSet] = useState<Set<string>>(new Set());

  const colorHex: Record<LightColor, string> = {
    green: contentTokens.colorSuccess,
    yellow: contentTokens.colorWarning,
    red: contentTokens.colorError,
  };

  function formatUptime(isoString: string | null): string {
    if (!isoString) return '-';
    const started = new Date(isoString).getTime();
    const elapsed = Math.floor((Date.now() - started) / 1000);
    if (elapsed < 0) return '-';
    if (elapsed < 60) return `${elapsed}s`;
    const minutes = Math.floor(elapsed / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h${minutes % 60}m`;
    const days = Math.floor(hours / 24);
    return `${days}d${hours % 24}h`;
  }

  const fetchStatuses = useCallback(async () => {
    const TIMEOUT_MS = 8_000;

    const withTimeout = async <T,>(p: Promise<T>): Promise<'timeout' | T> => {
      return Promise.race([
        p,
        new Promise<'timeout'>((resolve) => setTimeout(() => resolve('timeout'), TIMEOUT_MS)),
      ]);
    };

    const [healthResult, servicesResult] = await Promise.all([
      withTimeout(healthApi.check()),
      withTimeout(servicesApi.list()),
    ]);

    let reachable = false;

    if (healthResult === 'timeout') {
      setInfraLights(
        (Object.keys(INFRA_DISPLAY_NAMES) as (keyof HealthServices)[]).map((key) => ({
          name: key,
          displayName: INFRA_DISPLAY_NAMES[key] ?? key,
          color: 'red' as LightColor,
          startedAt: null,
        }))
      );
    } else if (healthResult.status >= 200 && healthResult.status < 300) {
      reachable = true;
      const h = healthResult.data;
      const entries = Object.entries(h.services ?? {}) as [keyof HealthServices, boolean][];
      setInfraLights(
        entries.map(([key, ok]) => ({
          name: key,
          displayName: INFRA_DISPLAY_NAMES[key] ?? key,
          color: boolToColor(ok),
          startedAt: null,
        }))
      );
    } else {
      setInfraLights(
        (Object.keys(INFRA_DISPLAY_NAMES) as (keyof HealthServices)[]).map((key) => ({
          name: key,
          displayName: INFRA_DISPLAY_NAMES[key] ?? key,
          color: 'red' as LightColor,
          startedAt: null,
        }))
      );
    }

    if (servicesResult === 'timeout') {
      setAiLights([
        {
          name: 'ai_services',
          displayName: 'AI 服務群組',
          color: 'red' as LightColor,
          startedAt: null,
        },
      ]);
    } else if (servicesResult.status >= 200 && servicesResult.status < 300) {
      reachable = true;
      const services = servicesResult.data.services ?? [];
      setAiLights(
        services.map((svc) => {
          const service = svc as ServiceInfo & { started_at?: string | null };
          return {
            name: service.name,
            displayName: service.display_name,
            color: svcStatusToColor(service.status),
            startedAt: service.started_at ?? null,
          };
        })
      );
    } else {
      setAiLights([
        {
          name: 'ai_services',
          displayName: 'AI 服務群組',
          color: 'red' as LightColor,
          startedAt: null,
        },
      ]);
    }

    if (healthResult === 'timeout') {
      reachable = false;
    }

    setApiUnreachable(!reachable);
    setLoading(false);
  }, []);

  useEffect(() => {
    void fetchStatuses();
    const timer = setInterval(() => void fetchStatuses(), HEARTBEAT_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchStatuses]);

  const handleRestart = async (serviceName: string) => {
    setRestartingSet((prev) => new Set(prev).add(serviceName));
    try {
      await servicesApi.restart(serviceName);
      message.success(`${serviceName} 重啟指令已送出`);
      setTimeout(() => void fetchStatuses(), 3000);
    } catch {
      message.error(`${serviceName} 重啟失敗`);
    } finally {
      setRestartingSet((prev) => {
        const next = new Set(prev);
        next.delete(serviceName);
        return next;
      });
    }
  };

  if (loading) return null;

  const allLights = [...infraLights, ...aiLights];
  const overall: LightColor = apiUnreachable
    ? 'red'
    : allLights.length === 0
      ? 'yellow'
      : worstColor(allLights);

  const overallHex = colorHex[overall];

  const OverallIcon =
    overall === 'red'
      ? CloseCircleOutlined
      : overall === 'yellow'
        ? WarningOutlined
        : CheckCircleOutlined;

  const renderLightRow = (light: ServiceLight, restartable: boolean) => (
    <div
      key={light.name}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '5px 0',
        borderBottom: `1px solid ${contentTokens.textSecondary}30`,
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: colorHex[light.color],
          boxShadow: `0 0 4px ${colorHex[light.color]}`,
          flexShrink: 0,
        }}
      />
      <span style={{ flex: 1, color: contentTokens.colorTextBase }}>{light.displayName}</span>
      <span style={{ color: colorHex[light.color], fontSize: 12, fontWeight: 500 }}>
        {COLOR_LABEL[light.color]}
      </span>
      <span style={{ color: contentTokens.textSecondary, fontSize: 11, minWidth: 50, textAlign: 'right' }}>
        {formatUptime(light.startedAt)}
      </span>
      {isAdmin && restartable && (
        <ReloadOutlined
          spin={restartingSet.has(light.name)}
          style={{
            fontSize: 12,
            color: restartingSet.has(light.name) ? contentTokens.colorPrimary : contentTokens.textSecondary,
            cursor: restartingSet.has(light.name) ? 'not-allowed' : 'pointer',
            flexShrink: 0,
            transition: 'color 0.2s',
          }}
          onClick={() => {
            if (!restartingSet.has(light.name)) void handleRestart(light.name);
          }}
        />
      )}
    </div>
  );

  const sectionTitleStyle: React.CSSProperties = {
    fontSize: 11,
    fontWeight: 600,
    color: contentTokens.textSecondary,
    padding: '6px 0 2px',
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
  };

  const popoverContent = (
    <div style={{ minWidth: 220, fontSize: 13 }}>
      {apiUnreachable && (
        <div style={{ padding: '4px 0 8px', color: colorHex.red, fontWeight: 600, borderBottom: `1px solid ${contentTokens.textSecondary}30`, marginBottom: 6 }}>
          ⚠ API Gateway 無法連線
        </div>
      )}

      {infraLights.length > 0 && (
        <>
          <div style={sectionTitleStyle}>基礎設施</div>
          {infraLights.map((l) => renderLightRow(l, false))}
        </>
      )}

      {aiLights.length > 0 && (
        <>
          <div style={{ ...sectionTitleStyle, marginTop: infraLights.length > 0 ? 8 : 0 }}>AI 服務</div>
          {aiLights.map((l) => renderLightRow(l, true))}
        </>
      )}

      {allLights.length === 0 && !apiUnreachable && (
        <div style={{ color: contentTokens.textSecondary, padding: '8px 0' }}>
          尚無服務資訊
        </div>
      )}

    </div>
  );

  return (
    <Popover
      content={popoverContent}
      title="服務狀態"
      trigger="click"
      placement="bottomRight"
      onOpenChange={(open) => {
        if (open) void fetchStatuses();
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          cursor: 'pointer',
          padding: '2px 6px',
          borderRadius: 4,
          transition: 'background 0.2s',
        }}
      >
        <OverallIcon style={{ fontSize: 16, color: overallHex }} />
        <span style={{ color: shellTokens.menuItemColor, fontSize: 12, opacity: 0.7 }}>
          服務狀態
        </span>
      </span>
    </Popover>
  );
}
