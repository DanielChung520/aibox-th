/**
 * @file        EEA-CRM 頁面外殼元件
 * @description EEA-CRM 各頁面通用外殼：提供右下 🤖 FAB + Agent Drawer
 *              所有 EEA-CRM 頁面只需包裹此元件即可獲得 Agent 整合能力
 * @lastUpdate  2026-06-08
 * @author      Sisyphus
 * @version     1.1.0
 */

import { useEffect, ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { Tooltip } from 'antd';
import { useCrmStore, CRMContext } from '../../stores/crmStore';
import AgentDrawer from '../../components/crm/AgentDrawer';

interface Props {
  children: ReactNode;
  /** CRM 頁面類型，決定 Agent Drawer 推薦哪幾隻 Agent */
  context: CRMContext;
}

/**
 * 將路徑對映成 CRMContext
 * 自動從 `/app/eea-crm/{module}` 推斷
 */
function contextFromPath(path: string): CRMContext {
  const base = path.replace(/^\/app\/eea-crm\//, '');
  if (base.startsWith('dashboard')) return 'dashboard';
  if (base.startsWith('customer')) return 'customers';
  if (base.startsWith('contact')) return 'contacts';
  if (base.startsWith('timeline')) return 'timeline';
  if (base.startsWith('tags')) return 'tags';
  if (base.startsWith('params')) return 'params';
  return 'dashboard';
}

export default function EeaCrmLayout({ children, context }: Props) {
  const location = useLocation();
  const { openAgentDrawer } = useCrmStore();
  const effectiveCtx = context || contextFromPath(location.pathname);

  // Ctrl+Shift+A → 開關 Agent Drawer
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'A') {
        e.preventDefault();
        openAgentDrawer(effectiveCtx);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [effectiveCtx, openAgentDrawer]);

  return (
    <>
      {children}

      {/* FAB */}
      <Tooltip title="AI Agent 助手 (Ctrl+Shift+A)" placement="left">
        <button
          onClick={() => openAgentDrawer(effectiveCtx)}
          style={{
            position: 'fixed',
            bottom: 32,
            right: 32,
            width: 52,
            height: 52,
            borderRadius: '50%',
            border: 'none',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: '#fff',
            fontSize: 24,
            cursor: 'pointer',
            zIndex: 100,
            boxShadow: '0 4px 16px rgba(102, 126, 234, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'transform 0.2s, box-shadow 0.2s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.transform = 'scale(1.1)';
            e.currentTarget.style.boxShadow = '0 6px 24px rgba(102, 126, 234, 0.7)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = 'scale(1)';
            e.currentTarget.style.boxShadow = '0 4px 16px rgba(102, 126, 234, 0.5)';
          }}
        >
          🤖
        </button>
      </Tooltip>

      {/* Agent Drawer */}
      <AgentDrawer />
    </>
  );
}
