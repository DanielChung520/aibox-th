/**
 * @file        圖標選擇器組件
 * @description 共用的圖標選擇 Modal，支援 Ant Design Icons
 * @lastUpdate  2026-03-18 08:05:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState } from 'react';
import { Modal, Row, Col, Button, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { iconMap, ANT_DESIGN_ICONS } from '../utils/icons';

interface IconPickerProps {
  open: boolean;
  onCancel: () => void;
  onSelect: (icon: string) => void;
}

export default function IconPicker({ open, onCancel, onSelect }: IconPickerProps) {
  const [searchText, setSearchText] = useState('');

  const filteredIcons = ANT_DESIGN_ICONS.filter(icon => 
    icon.label.toLowerCase().includes(searchText.toLowerCase()) ||
    icon.value.toLowerCase().includes(searchText.toLowerCase())
  );

  return (
    <Modal
      title="選擇圖標"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={800}
    >
      <Input
        placeholder="搜索圖標..."
        prefix={<SearchOutlined />}
        value={searchText}
        onChange={(e) => setSearchText(e.target.value)}
        style={{ marginBottom: 16 }}
        allowClear
      />
      <div style={{ maxHeight: 400, overflow: 'auto' }}>
        <Row gutter={[8, 8]}>
          {filteredIcons.map(opt => {
            const IconComp = iconMap[opt.value];
            return (
              <Col span={4} key={opt.value}>
                <Button
                  type="text"
                  onClick={() => {
                    onSelect(opt.value);
                    onCancel();
                  }}
                  style={{ 
                    width: '100%', 
                    height: 60, 
                    display: 'flex', 
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {IconComp && <IconComp style={{ fontSize: 20 }} />}
                  <span style={{ fontSize: 10, marginTop: 4 }}>{opt.label}</span>
                </Button>
              </Col>
            );
          })}
        </Row>
      </div>
    </Modal>
  );
}
