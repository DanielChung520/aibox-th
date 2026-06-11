/**
 * @file        useDragResize.ts
 * @description 悬浮窗口拖拽與調整大小的自訂 Hook
 * @lastUpdate  2026-04-18 22:45:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { useState, useRef, useEffect } from 'react';
import type { FloatingAssistantConfig } from './types';

const MIN_WIDTH = 280;
const MIN_HEIGHT = 300;

interface DragState {
  startX: number;
  startY: number;
  initX: number;
  initY: number;
}

interface ResizeState {
  startX: number;
  startY: number;
  initW: number;
  initH: number;
}

interface UseDragResizeReturn {
  isDragging: boolean;
  isResizing: boolean;
  size: { width: number; height: number };
  handleHeaderMouseDown: (e: React.MouseEvent | React.TouchEvent) => void;
  handleResizeMouseDown: (e: React.MouseEvent) => void;
}

export function useDragResize(
  initialConfig: FloatingAssistantConfig,
  position: { x: number; y: number },
  onPositionChange: (pos: { x: number; y: number }) => void
): UseDragResizeReturn {
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [size, setSize] = useState({ width: initialConfig.modalWidth, height: initialConfig.modalHeight });
  const [config, setConfig] = useState(initialConfig);

  const dragRef = useRef<DragState>({
    startX: 0,
    startY: 0,
    initX: 0,
    initY: 0,
  });

  const resizeRef = useRef<ResizeState>({
    startX: 0,
    startY: 0,
    initW: config.modalWidth,
    initH: config.modalHeight,
  });

  // 同步來自父元件的 config 更新（fetchConfig 完成後）
  useEffect(() => {
    setConfig(initialConfig);
  }, [initialConfig]);

  // 同步 config 到 size 與 resizeRef
  useEffect(() => {
    setSize({ width: config.modalWidth, height: config.modalHeight });
    resizeRef.current.initW = config.modalWidth;
    resizeRef.current.initH = config.modalHeight;
  }, [config.modalWidth, config.modalHeight]);

  // 聽取 window 事件同步 config
  useEffect(() => {
    const handleConfigUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<FloatingAssistantConfig>;
      setConfig(customEvent.detail);
    };
    window.addEventListener('floating-assistant-config-update', handleConfigUpdate);
    return () => window.removeEventListener('floating-assistant-config-update', handleConfigUpdate);
  }, []);

  const handleHeaderMouseDown = (e: React.MouseEvent | React.TouchEvent) => {
    setIsDragging(true);
    
    let clientX, clientY;
    if ('touches' in e) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = e.clientX;
      clientY = e.clientY;
    }

    dragRef.current = {
      startX: clientX,
      startY: clientY,
      initX: position.x,
      initY: position.y,
    };
  };

  const handleResizeMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsResizing(true);
    resizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initW: size.width,
      initH: size.height,
    };
  };

  // 拖拽與調整大小事件監聽器
  useEffect(() => {
    if (!isDragging && !isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;

        const newX = dragRef.current.initX + dx;
        const newY = dragRef.current.initY + dy;

        const maxX = window.innerWidth - size.width;
        const maxY = window.innerHeight - size.height;
        
        onPositionChange({
          x: Math.max(0, Math.min(newX, maxX)),
          y: Math.max(0, Math.min(newY, maxY)),
        });
      } else if (isResizing) {
        const dx = e.clientX - resizeRef.current.startX;
        const dy = e.clientY - resizeRef.current.startY;

        const newWidth = Math.max(MIN_WIDTH, Math.min(resizeRef.current.initW + dx, window.innerWidth - position.x));
        const newHeight = Math.max(MIN_HEIGHT, Math.min(resizeRef.current.initH + dy, window.innerHeight - position.y));

        setSize({ width: newWidth, height: newHeight });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      setIsResizing(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, isResizing, onPositionChange, position, size]);

  return {
    isDragging,
    isResizing,
    size,
    handleHeaderMouseDown,
    handleResizeMouseDown,
  };
}
