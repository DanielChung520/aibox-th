/**
 * @file        AvatarPicker.tsx
 * @description 頭像選擇器，格狀顯示 src/assets/avatar/ 下的所有圖片供選擇
 */

import { useState, useRef } from 'react';
import { Modal, Tabs, Upload, message } from 'antd';
import { UploadOutlined } from '@ant-design/icons';

const avatarModules = import.meta.glob<{ default: string }>(
  '../assets/avatar/*.png',
  { eager: true }
);

const avatarList: { name: string; src: string }[] = Object.entries(avatarModules).map(
  ([path, mod]) => {
    const name = path.split('/').pop()?.replace(/\.png$/i, '') || '';
    return { name, src: (mod as { default: string }).default };
  }
);

interface AvatarPickerProps {
  value?: string;
  onChange: (name: string) => void;
}

export default function AvatarPicker({ value, onChange }: AvatarPickerProps) {
  const [open, setOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isUploaded = value && value.startsWith('data:');
  const current = isUploaded ? null : avatarList.find((a) => a.name === value);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      message.warning('圖片大小請勿超過 2MB');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      onChange(reader.result as string);
      setOpen(false);
    };
    reader.readAsDataURL(file);
  };

  return (
    <>
      <div
        onClick={() => setOpen(true)}
        style={{
          cursor: 'pointer',
          width: 64,
          height: 64,
          borderRadius: 8,
          border: '1px solid #d9d9d9',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          background: '#fafafa',
        }}
      >
        {current ? (
          <img src={current.src} alt={current.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : isUploaded ? (
          <img src={value} alt="uploaded" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span style={{ color: '#999', fontSize: 11, textAlign: 'center', padding: 4 }}>選擇圖示</span>
        )}
      </div>

      <Modal title="選擇頭像" open={open} onCancel={() => setOpen(false)} footer={null} width={520}>
        <Tabs items={[
          {
            key: 'system',
            label: '🎨 系統圖示',
            children: (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8, maxHeight: 320, overflowY: 'auto', padding: '8px 0' }}>
                {avatarList.map((avatar) => (
                  <div key={avatar.name}
                    onClick={() => { onChange(avatar.name); setOpen(false); }}
                    style={{
                      cursor: 'pointer', width: 64, height: 64, borderRadius: 8,
                      border: value === avatar.name ? '2px solid #00b900' : '1px solid #d9d9d9',
                      overflow: 'hidden', transition: 'border-color 0.2s',
                    }}
                    title={avatar.name}>
                    <img src={avatar.src} alt={avatar.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                ))}
              </div>
            ),
          },
          {
            key: 'upload',
            label: '📁 上傳圖片',
            children: (
              <div style={{ padding: '40px 0', textAlign: 'center' }}>
                <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/gif" onChange={handleFileSelect} style={{ display: 'none' }} />
                <div onClick={() => fileInputRef.current?.click()} style={{
                  display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: 8, cursor: 'pointer',
                  padding: '24px 48px', borderRadius: 8, border: '2px dashed #d9d9d9',
                }}>
                  <UploadOutlined style={{ fontSize: 32, color: '#1677ff' }} />
                  <span style={{ fontSize: 13, color: '#666' }}>點擊選擇圖片（建議 200x200px，小於 2MB）</span>
                </div>
              </div>
            ),
          },
        ]} />
      </Modal>
    </>
  );
}
