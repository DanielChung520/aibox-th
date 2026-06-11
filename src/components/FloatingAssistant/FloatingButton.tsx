/**
 * @file        FloatingButton.tsx
 * @description 悬浮助手按钮，可全局拖拽，点击打开聊天窗口
 * @lastUpdate  2026-04-14 22:20:01
 * @author      Daniel Chung
 * @version     1.1.0
 */

import React, { useState, useRef, useEffect } from 'react';
import { RobotOutlined } from '@ant-design/icons';

interface FloatingButtonProps {
  onClick: () => void;
  position: { x: number; y: number };
  onPositionChange: (pos: { x: number; y: number }) => void;
  avatarSrc?: string;
}

export default function FloatingButton({ onClick, position, onPositionChange, avatarSrc }: FloatingButtonProps) {
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; initX: number; initY: number; hasMoved: boolean }>({
    startX: 0,
    startY: 0,
    initX: 0,
    initY: 0,
    hasMoved: false,
  });

  const handleMouseDown = (e: React.MouseEvent | React.TouchEvent) => {
    if ('button' in e && e.button !== 0) return;
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
      hasMoved: false,
    };

    e.preventDefault(); // 防止默認選中行為
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent | TouchEvent) => {
      let clientX, clientY;
      if ('touches' in e) {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
      } else {
        clientX = e.clientX;
        clientY = e.clientY;
      }

      const dx = clientX - dragRef.current.startX;
      const dy = clientY - dragRef.current.startY;

      // 如果移動距離超過3px，則認為是拖拽而不是點擊
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        dragRef.current.hasMoved = true;
      }

      const newX = dragRef.current.initX + dx;
      const newY = dragRef.current.initY + dy;

      // 限制在屏幕範圍內
      const maxX = window.innerWidth - 56;
      const maxY = window.innerHeight - 56;
      
      onPositionChange({
        x: Math.max(0, Math.min(newX, maxX)),
        y: Math.max(0, Math.min(newY, maxY)),
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      // 如果沒有發生實際拖拽，則觸發點擊事件
      if (!dragRef.current.hasMoved) {
        onClick();
      }
    };

    document.addEventListener('mousemove', handleMouseMove, { passive: false });
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('touchmove', handleMouseMove, { passive: false });
    document.addEventListener('touchend', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('touchmove', handleMouseMove);
      document.removeEventListener('touchend', handleMouseUp);
    };
  }, [isDragging, onPositionChange, onClick]);

  return (
    <div
      className="floating-button"
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
      }}
      onMouseDown={handleMouseDown}
      onTouchStart={handleMouseDown}
    >
      {avatarSrc ? (
        <img src={avatarSrc} alt="AI" style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover', pointerEvents: 'none' }} />
      ) : (
        <RobotOutlined style={{ fontSize: '24px' }} />
      )}
    </div>
  );
}
