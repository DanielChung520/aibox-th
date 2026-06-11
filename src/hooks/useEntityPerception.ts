/**
 * @file        useEntityPerception.ts
 * @description 頁面實體感知鉤子 — 頁面用它主動上報用戶正在操作的業務實體
 * @lastUpdate  2026-04-22 10:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useCallback, useRef } from 'react';
import { EntityContext, EntityTypeKey, EntityAction } from '../components/FloatingAssistant/types';

const ENTITY_INTERACT_EVENT = 'entity_interact';

export interface UseEntityPerceptionOptions {
  /** 預設實體類型（頁面主要操作的實體） */
  defaultEntityType?: EntityTypeKey;
  /** 預設操作動作 */
  defaultAction?: EntityAction;
}

export function useEntityPerception(options: UseEntityPerceptionOptions = {}) {
  const lastContextRef = useRef<EntityContext | null>(null);

  const dispatch = useCallback((
    entityType: EntityTypeKey,
    entityId: string,
    action: EntityAction,
    metadata?: Record<string, unknown>
  ) => {
    const context: EntityContext = {
      entity_type: entityType,
      entity_id: entityId,
      action,
      metadata,
    };

    lastContextRef.current = context;

    window.dispatchEvent(new CustomEvent(ENTITY_INTERACT_EVENT, {
      detail: {
        ...context,
        timestamp: Date.now(),
        page: window.location.pathname,
      },
    }));
  }, []);

  const dispatchEntity = useCallback((
    entityId: string,
    action?: EntityAction,
    metadata?: Record<string, unknown>
  ) => {
    if (!options.defaultEntityType) {
      console.warn('[useEntityPerception] defaultEntityType not set, call dispatch() with entityType');
      return;
    }
    dispatch(options.defaultEntityType, entityId, action ?? options.defaultAction ?? 'view', metadata);
  }, [options.defaultEntityType, options.defaultAction, dispatch]);

  const getLastContext = useCallback(() => lastContextRef.current, []);

  return {
    dispatch,
    dispatchEntity,
    getLastContext,
  };
}

export { ENTITY_INTERACT_EVENT };
