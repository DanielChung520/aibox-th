/**
 * @file        AvatarPicker.tsx
 * @description 頭像選擇器，格狀顯示 src/assets/avatar/ 下的所有圖片供選擇
 */

import { useState } from 'react';
import { Modal } from 'antd';

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

  const current = avatarList.find((a) => a.name === value);

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
          <img
            src={current.src}
            alt={current.name}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <span style={{ color: '#999', fontSize: 11, textAlign: 'center', padding: 4 }}>
            選擇圖示
          </span>
        )}
      </div>

      <Modal
        title="選擇 Channel 圖示"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={520}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(6, 1fr)',
            gap: 8,
            maxHeight: 320,
            overflowY: 'auto',
            padding: '8px 0',
          }}
        >
          {avatarList.map((avatar) => (
            <div
              key={avatar.name}
              onClick={() => {
                onChange(avatar.name);
                setOpen(false);
              }}
              style={{
                cursor: 'pointer',
                width: 64,
                height: 64,
                borderRadius: 8,
                border:
                  value === avatar.name
                    ? '2px solid #00b900'
                    : '1px solid #d9d9d9',
                overflow: 'hidden',
                transition: 'border-color 0.2s',
              }}
              title={avatar.name}
            >
              <img
                src={avatar.src}
                alt={avatar.name}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>
          ))}
        </div>
      </Modal>
    </>
  );
}
