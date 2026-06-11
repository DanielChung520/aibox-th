/**
 * @file        index.tsx
 * @description 悬浮助手主组件，管理按钮与弹窗状态、位置、頁面感知
 * @lastUpdate  2026-04-16 22:10:00
 * @author      Daniel Chung
 * @version     1.9.0
 */

import { useState, useEffect, useRef, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { Tag } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { intentEngine } from '../../services/intentEngine';
import FloatingButton from './FloatingButton';
import ChatModal from './ChatModal';
import DebugPanel from './DebugPanel';
import { paramsApi, SystemParam } from '../../services/api';
import { useAvatar } from '../../services/avatarCache';
import { FloatingAssistantConfig, defaultConfig, resolvePageContext, IntentGuess } from './types';
import { actionTrail } from '../../services/actionTrail';
import { authStore } from '../../stores/auth';
import { pageContextManager } from '../../services/PageContextManager';
import { ENTITY_INTERACT_EVENT } from '../../hooks/useEntityPerception';
import './styles.css';

function extractPageDomContext(): Record<string, unknown> {
  const ctx: Record<string, unknown> = {};
  const rows = document.querySelectorAll('.ant-table-tbody tr.ant-table-row');
  if (rows.length > 0) ctx.recordCount = rows.length;

  const paginationTotal = document.querySelector('.ant-pagination-total-text');
  if (paginationTotal?.textContent) {
    const m = paginationTotal.textContent.match(/(\d+)/);
    if (m) ctx.recordCount = Number(m[1]);
  }

  const domainCells = document.querySelectorAll('.ant-table-tbody tr.ant-table-row td:first-child a, .ant-table-tbody tr.ant-table-row td:first-child span');
  if (domainCells.length > 0) {
    const names = Array.from(domainCells).map(el => el.textContent?.trim()).filter(Boolean);
    if (names.length > 0 && names.length <= 5) {
      ctx.domainName = names[0];
      ctx.tableName = names[0];
    }
  }
  return ctx;
}

const NUMBER_FIELDS: Array<keyof FloatingAssistantConfig> = [
  'modalWidth',
  'modalHeight',
  'blurIntensity',
  'glassOpacity',
  'saturation',
  'borderRadius',
];

export default function FloatingAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [config, setConfig] = useState<FloatingAssistantConfig>(defaultConfig);
  const avatarSrc = useAvatar();
  const location = useLocation();
  const pageContext = useMemo(() => resolvePageContext(location.pathname), [location.pathname]);

  const [intentGuesses, setIntentGuesses] = useState<IntentGuess[]>([]);
  const [intentLoading, setIntentLoading] = useState(false);
  const [intentPanelOpen, setIntentPanelOpen] = useState(false);
  const [debugPanelOpen, setDebugPanelOpen] = useState(false);
  const [modalContext, setModalContext] = useState<{
    modal: string;
    mode: string;
    agent_key?: string;
    agent_name?: string;
    demand?: {
      key: string;
      goal: string;
      expected_effect: string;
      problem_description: string;
      status: string;
    } | null;
    action: string;
  } | null>(null);
  const [fullPageContext, setFullPageContext] = useState<{
    page: string;
    pageName: string;
    component?: string;
    componentName?: string;
    entity?: string;
    entityType?: string;
    action?: string;
    data?: Record<string, unknown>;
  } | null>(null);
  const intentSelectRef = useRef<((text: string, guess: IntentGuess) => void) | null>(null);

  useEffect(() => {
    // Only start intent engine when authenticated
    if (!authStore.getState().isAuthenticated) return;

    const unsubscribe = intentEngine.subscribe((guesses) => {
      setIntentGuesses(guesses);
      setIntentLoading(intentEngine.isLoading());
      if (guesses.length > 0) {
        setIntentPanelOpen(true);
      }
    });
    intentEngine.startListening();

    const unsubscribePageContext = pageContextManager.subscribe((ctx) => {
      setFullPageContext(ctx);
    });

const handleEntityInteract = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setFullPageContext(prev => prev ? {
        ...prev,
        entity: detail.entity_id,
        entityType: detail.entity_type,
        action: detail.action,
        data: detail.metadata,
      } : null);
    };
    window.addEventListener(ENTITY_INTERACT_EVENT, handleEntityInteract);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        setDebugPanelOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      unsubscribe();
      intentEngine.stopListening();
      unsubscribePageContext();
      window.removeEventListener(ENTITY_INTERACT_EVENT, handleEntityInteract);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  useEffect(() => {
    actionTrail.setCurrentPage(location.pathname);
    const baseMeta: Record<string, unknown> = {
      path: location.pathname,
      pageName: pageContext.name,
      pageDescription: pageContext.description,
    };
    actionTrail.record('page_navigate', baseMeta);

    const timer = setTimeout(() => {
      const extra = extractPageDomContext();
      if (Object.keys(extra).length > 0) {
        actionTrail.record('page_navigate', { ...baseMeta, ...extra });
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [location.pathname, pageContext.name]);
  
  const fetchConfig = async () => {
    try {
      const response = await paramsApi.list();
      const data = response.data.data || [];
      
      const cfg: Partial<FloatingAssistantConfig> = {};
      const prefix = 'floating_assistant.';
      
      data.forEach((param: SystemParam) => {
        if (param.param_key.startsWith(prefix)) {
          const key = param.param_key.replace(prefix, '') as keyof FloatingAssistantConfig;
          const typedCfg = cfg as Record<string, unknown>;
          if (key === 'enabled') {
            typedCfg[key] = param.param_value === 'true';
          } else if (NUMBER_FIELDS.includes(key)) {
            typedCfg[key] = parseInt(param.param_value, 10);
          } else {
            typedCfg[key] = param.param_value;
          }
        }
      });
      
      const mergedConfig = { ...defaultConfig, ...cfg };
      setConfig(mergedConfig);
      applyStylesToCss(mergedConfig);
    } catch {
      // ignore errors, use defaults
    }
  };

  const applyStylesToCss = (cfg: FloatingAssistantConfig) => {
    const root = document.documentElement;
    root.style.setProperty('--fa-modal-width', `${cfg.modalWidth}px`);
    root.style.setProperty('--fa-modal-height', `${cfg.modalHeight}px`);
    root.style.setProperty('--fa-blur-intensity', `${cfg.blurIntensity}px`);
    root.style.setProperty('--fa-glass-opacity', `${Number(cfg.glassOpacity) / 100}`);
    root.style.setProperty('--fa-saturation', `${cfg.saturation}%`);
    root.style.setProperty('--fa-border-radius', `${cfg.borderRadius}px`);
    root.style.setProperty('--fa-modal-bg', String(cfg.modalBg));
    root.style.setProperty('--fa-header-bg', String(cfg.headerBg));
    root.style.setProperty('--fa-header-border', `1px solid ${String(cfg.headerBorderColor)}`);
    root.style.setProperty('--fa-title-color', String(cfg.titleColor));
    root.style.setProperty('--fa-close-btn-color', String(cfg.closeBtnColor));
    root.style.setProperty('--fa-body-bg', String(cfg.bodyBg));
    root.style.setProperty('--fa-footer-bg', String(cfg.footerBg));
    root.style.setProperty('--fa-footer-border', `1px solid ${String(cfg.footerBorderColor)}`);
    root.style.setProperty('--fa-input-bg', String(cfg.inputBg));
    root.style.setProperty('--fa-input-text-color', String(cfg.inputTextColor));
    root.style.setProperty('--fa-input-border-color', String(cfg.inputBorderColor));
    root.style.setProperty('--fa-input-placeholder-color', String(cfg.inputPlaceholderColor));
    root.style.setProperty('--fa-send-btn-bg', String(cfg.sendBtnBg));
    root.style.setProperty('--fa-send-btn-color', String(cfg.sendBtnColor));
    root.style.setProperty('--fa-bubble-ai-bg', String(cfg.bubbleAiBg));
    root.style.setProperty('--fa-bubble-ai-text-color', String(cfg.bubbleAiTextColor));
    root.style.setProperty('--fa-bubble-user-bg', String(cfg.bubbleUserBg));
    root.style.setProperty('--fa-bubble-user-text-color', String(cfg.bubbleUserTextColor));
    root.style.setProperty('--fa-button-bg', String(cfg.buttonBg));
    root.style.setProperty('--fa-button-icon-color', String(cfg.buttonIconColor));
    root.style.setProperty('--fa-button-shadow-color', String(cfg.buttonShadowColor));
    root.style.setProperty('--fa-button-pulse-color', String(cfg.buttonPulseColor));
    root.style.setProperty('--fa-shadow-color', String(cfg.shadowColor));
    root.style.setProperty('--fa-shadow-inner-color', String(cfg.shadowInnerColor));
    root.style.setProperty('--fa-gradient-start', String(cfg.gradientStart));
    root.style.setProperty('--fa-gradient-radial-1', String(cfg.gradientRadial1));
    root.style.setProperty('--fa-gradient-radial-2', String(cfg.gradientRadial2));
    root.style.setProperty('--fa-resize-handle-color', String(cfg.resizeHandleColor));
    root.style.setProperty('--fa-mermaid-bg', String(cfg.mermaidBg));
    root.style.setProperty('--fa-mermaid-text-color', String(cfg.mermaidTextColor));
    root.style.setProperty('--fa-link-color', String(cfg.linkColor));
    root.style.setProperty('--fa-quote-border-color', String(cfg.quoteBorderColor));
  };

  useEffect(() => {
    fetchConfig();

    const handleConfigUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<FloatingAssistantConfig>;
      setConfig(customEvent.detail);
      applyStylesToCss(customEvent.detail);
    };

    const handleModalContextChange = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail.action === 'open') {
        setModalContext(detail);
      } else {
        setModalContext(null);
      }
    };

    window.addEventListener('floating-assistant-config-update', handleConfigUpdate);
    window.addEventListener('modal-context-change', handleModalContextChange);
    return () => {
      window.removeEventListener('floating-assistant-config-update', handleConfigUpdate);
      window.removeEventListener('modal-context-change', handleModalContextChange);
    };
  }, []);

      // 默認位置：右下角，距離邊緣 20px
  const [buttonPosition, setButtonPosition] = useState({
    x: window.innerWidth - 56 - 20,
    y: window.innerHeight - 56 - 20,
  });

      // 彈窗默認位置：按鈕上方，略偏左
  const [modalPosition, setModalPosition] = useState({
    x: Math.max(0, window.innerWidth - config.modalWidth - 20),
    y: Math.max(0, window.innerHeight - config.modalHeight - 80 - 20),
  });

  useEffect(() => {
    setModalPosition({
      x: Math.max(0, window.innerWidth - config.modalWidth - 20),
      y: Math.max(0, window.innerHeight - config.modalHeight - 80 - 20),
    });
  }, [config.modalWidth, config.modalHeight]);

  const handleToggle = () => {
    setIsOpen(prev => {
      if (!prev) {
        setModalPosition({
          x: Math.max(0, Math.min(modalPosition.x, window.innerWidth - config.modalWidth)),
          y: Math.max(0, Math.min(modalPosition.y, window.innerHeight - config.modalHeight)),
        });
      }
      return !prev;
    });
  };

      // 監聽窗口大小改變，防止組件跑出屏幕
  useEffect(() => {
    const handleResize = () => {
      setButtonPosition(prev => ({
        x: Math.min(prev.x, window.innerWidth - 56),
        y: Math.min(prev.y, window.innerHeight - 56),
      }));
      setModalPosition(prev => ({
        x: Math.min(prev.x, window.innerWidth - config.modalWidth),
        y: Math.min(prev.y, window.innerHeight - config.modalHeight),
      }));
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [config.modalWidth, config.modalHeight]);

  const INTENT_PANEL_WIDTH = 320;
  const INTENT_PANEL_GAP = 8;
  const anchorBottom = isOpen
    ? modalPosition.y + config.modalHeight
    : buttonPosition.y + 56;
  const anchorLeft = isOpen
    ? modalPosition.x - INTENT_PANEL_WIDTH - INTENT_PANEL_GAP
    : buttonPosition.x - INTENT_PANEL_WIDTH - INTENT_PANEL_GAP;

  const intentPanelStyle: React.CSSProperties = {
    position: 'fixed',
    left: Math.max(8, anchorLeft),
    bottom: Math.max(8, window.innerHeight - anchorBottom),
    width: INTENT_PANEL_WIDTH,
    zIndex: isOpen ? 9998 : 10000,
  };

  const handleIntentSelect = (guess: IntentGuess) => {
    intentEngine.acceptGuess(guess);
    setIsOpen(true);
    setIntentPanelOpen(false);
    intentSelectRef.current?.(guess.text, guess);
  };

  if (config.enabled === false) {
    return null;
  }

  return (
    <div className="floating-assistant-container">
      {intentGuesses.length > 0 && intentPanelOpen && (
        <div className="intent-panel-standalone" style={intentPanelStyle}>
          <div className="intent-guess-popover">
            <div className="intent-guess-header">
              <span>🔮 猜你想问...</span>
              <CloseOutlined className="intent-guess-close" onClick={() => setIntentPanelOpen(false)} />
            </div>
            {intentGuesses.map((guess, i) => (
              <div key={i} className="intent-guess-item" onClick={() => handleIntentSelect(guess)}>
                <span className="intent-guess-text">{guess.text}</span>
                <Tag color={guess.confidence >= 0.8 ? 'green' : guess.confidence >= 0.5 ? 'orange' : 'default'}>
                  {guess.confidence >= 0.8 ? '★★★' : guess.confidence >= 0.5 ? '★★' : '★'}
                  {guess.source === 'template' ? ' 模板' : guess.source === 'rule' ? ' 規則' : ' AI'}
                </Tag>
              </div>
            ))}
          </div>
        </div>
      )}
      {debugPanelOpen && <DebugPanel onClose={() => setDebugPanelOpen(false)} />}
      <ChatModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        position={modalPosition}
        onPositionChange={setModalPosition}
        buttonPosition={buttonPosition}
        initialConfig={config}
        avatarSrc={avatarSrc}
        pageContext={pageContext}
        fullPageContext={fullPageContext}
        modalContext={modalContext}
        intentGuesses={intentGuesses}
        intentLoading={intentLoading}
        intentPanelOpen={intentPanelOpen}
        onIntentPanelToggle={() => setIntentPanelOpen(prev => !prev)}
        intentSelectRef={intentSelectRef}
      />
      <FloatingButton 
        onClick={handleToggle}
        position={buttonPosition}
        onPositionChange={setButtonPosition}
        avatarSrc={avatarSrc}
      />
    </div>
  );
}
