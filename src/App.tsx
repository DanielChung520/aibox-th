/**
 * @file        應用入口
 * @description 路由配置、ConfigProvider、主題供應
 * @lastUpdate  2026-03-28 12:19:04
 * @author      Daniel Chung
 * @version     2.2.0
 */

import { useState, useEffect, ReactNode } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { paramsApi } from './services/api';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntApp, theme } from 'antd';
import { AppThemeProvider, useEffectiveTheme, useContentTokens } from './contexts/AppThemeProvider';
import Login from './pages/Login';
import Welcome from './pages/Welcome';
import MainLayout from './pages/MainLayout';
import Home from './pages/Home';
import UserManagement from './pages/UserManagement';
import RoleManagement from './pages/RoleManagement';
import SystemParams from './pages/SystemParams';
import FunctionManagement from './pages/FunctionManagement';
import BrowseAgent from './pages/BrowseAgent';
import BrowseTools from './pages/BrowseTools';
import TaskSessionChat from './pages/TaskSessionChat';
import TaskSessionHistory from './pages/TaskSessionHistory';
import TaskSessionScheduled from './pages/TaskSessionScheduled';
import UnderDevelopment from './pages/UnderDevelopment';
import SchemaPage from './pages/data-agent/SchemaPage';
import QueryPlayground from './pages/data-agent/QueryPlayground';
import DataLakePage from './pages/data-agent/DataLakePage';
import OntologyList from './pages/knowledge/OntologyList';
import KnowledgeBaseManagement from './pages/knowledge/KnowledgeBaseManagement';
import KnowledgeBaseDetail from './pages/knowledge/KnowledgeBaseDetail';
import IntentCatalog from './pages/IntentCatalog';
import { authStore } from './stores/auth';
import AppUpdater from './components/AppUpdater';

function ProtectedRoute({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(authStore.getState().isAuthenticated);

  useEffect(() => {
    const unsubscribe = authStore.subscribe(() => {
      setIsAuthenticated(authStore.getState().isAuthenticated);
    });
    return unsubscribe;
  }, []);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function AppContent() {
  const effectiveTheme = useEffectiveTheme();
  const contentTokens = useContentTokens();

  useEffect(() => {
    paramsApi.list().then((res: any) => {
      const params = res.data.data || [];
      const appName = params.find((p: any) => p.param_key === 'app.name');
      if (appName?.param_value) {
        try {
          getCurrentWindow().setTitle(appName.param_value);
        } catch (_) {
          // non-Tauri environment
        }
      }
    }).catch(() => {});
  }, []);

  const algorithm = effectiveTheme === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm;

  const opacity = contentTokens.bgOpacity / 100;
  const bgBase = contentTokens.colorBgBase;
  const bgColor = opacity < 1 && bgBase?.startsWith('#') && bgBase?.length === 7
    ? `${bgBase}${Math.round(opacity * 255).toString(16).padStart(2, '0')}`
    : bgBase;

  const pageBg = contentTokens.pageBg || bgColor || '#0f172a';
  const containerBg = contentTokens.containerBg || bgColor || '#1e293b';
  const tooltipBgRaw = contentTokens.tooltipBg || containerBg || contentTokens.colorBgBase || '#1e293b';
  const tooltipBgOpacity = (contentTokens.tooltipBgOpacity ?? 88) / 100;
  const tooltipBg = tooltipBgRaw.startsWith('#') && tooltipBgRaw.length === 7
    ? `${tooltipBgRaw}${Math.round(tooltipBgOpacity * 255).toString(16).padStart(2, '0')}`
    : tooltipBgRaw;
  const tooltipText = contentTokens.tooltipText || contentTokens.colorTextBase;

  return (
    <div style={{
      '--table-shadow': contentTokens.tableShadow || 'none',
      '--tooltip-bg': tooltipBg,
      '--tooltip-text': tooltipText,
    } as React.CSSProperties}>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: contentTokens.colorPrimary,
          colorSuccess: contentTokens.colorSuccess,
          colorWarning: contentTokens.colorWarning,
          colorError: contentTokens.colorError,
          colorInfo: contentTokens.colorInfo,
          colorBgBase: bgColor,
          colorTextBase: contentTokens.colorTextBase,
          borderRadius: contentTokens.borderRadius,
          fontFamily: contentTokens.fontFamily,
          boxShadow: contentTokens.boxShadow,
          boxShadowSecondary: contentTokens.boxShadowSecondary,
          colorBgContainer: containerBg,
        },
        algorithm,
        components: {
          Layout: {
            bodyBg: pageBg,
          },
          Card: {
            boxShadow: contentTokens.cardShadow,
          },
          Table: {
            rowExpandedBg: contentTokens.tableExpandedRowBg,
            headerBg: contentTokens.tableHeaderBg,
            rowHoverBg: contentTokens.tableRowHoverBg,
          },
          Tooltip: {
            colorBgSpotlight: tooltipBg,
          },
        },
      }}
    >
      <BrowserRouter>
        <AntApp>
          <AppUpdater />
          <Routes>
            <Route path="/" element={<Welcome />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/app"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/app/home" replace />} />
              <Route path="home" element={<Home />} />
              <Route path="users" element={<UserManagement />} />
              <Route path="roles" element={<RoleManagement />} />
              <Route path="params" element={<SystemParams />} />
              <Route path="functions" element={<FunctionManagement />} />
              <Route path="browse-agent" element={<BrowseAgent />} />
              <Route path="browse-tools" element={<BrowseTools />} />
              <Route path="task-session/chat/:sessionKey?" element={<TaskSessionChat />} />
              <Route path="task-session/history" element={<TaskSessionHistory />} />
              <Route path="task-session/scheduled" element={<TaskSessionScheduled />} />
              <Route path="under-development" element={<UnderDevelopment />} />
              <Route path="data-agent/schema" element={<SchemaPage />} />

              <Route path="data-agent/playground" element={<QueryPlayground />} />
              <Route path="data-agent/datalake" element={<DataLakePage />} />
              <Route path="knowledge/ontology" element={<OntologyList />} />
              <Route path="knowledge/management" element={<KnowledgeBaseManagement />} />
              <Route path="knowledge/management/:id" element={<KnowledgeBaseDetail />} />
              <Route path="intent-orchestration" element={<IntentCatalog />} />
            </Route>
          </Routes>
        </AntApp>
      </BrowserRouter>
    </ConfigProvider>
    </div>
  );
}

function App() {
  return (
    <AppThemeProvider>
      <AppContent />
    </AppThemeProvider>
  );
}

export default App;
