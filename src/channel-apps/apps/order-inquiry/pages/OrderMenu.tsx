/**
 * @file        OrderMenu.tsx
 * @description Order-inquiry mini app main menu with 4 feature cards
 * @lastUpdate  2026-05-21
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useNavigate } from 'react-router-dom';
import ChannelShell from '../../../shell/ChannelShell';
import './OrderMenu.css';

interface MenuItem {
  icon: string;
  title: string;
  desc: string;
  route: string;
}

const menuItems: MenuItem[] = [
  {
    icon: '📋',
    title: '瀏覽品項',
    desc: '查看可訂購品項與庫存',
    route: '/channel/order-inquiry/products',
  },
  {
    icon: '🛒',
    title: '預訂下單',
    desc: '勾選品項、填寫數量下單',
    route: '/channel/order-inquiry/order',
  },
  {
    icon: '📤',
    title: '上傳訂購單',
    desc: '上傳圖片或檔案，AI 自動解析',
    route: '/channel/order-inquiry/upload',
  },
  {
    icon: '📦',
    title: '訂單查詢',
    desc: '查看預購單資訊與進度',
    route: '/channel/order-inquiry/status',
  },
];

export default function OrderMenu() {
  const navigate = useNavigate();

  return (
    <ChannelShell title="訂單小幫手">
      <div className="order-menu">
        {menuItems.map((item) => (
          <div
            key={item.route}
            className="order-menu__card"
            onClick={() => navigate(item.route)}
            role="button"
            tabIndex={0}
            onKeyDown={(e: React.KeyboardEvent) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                navigate(item.route);
              }
            }}
          >
            <span className="order-menu__card-icon">{item.icon}</span>
            <div className="order-menu__card-body">
              <span className="order-menu__card-title">{item.title}</span>
              <span className="order-menu__card-desc">{item.desc}</span>
            </div>
          </div>
        ))}
      </div>
    </ChannelShell>
  );
}
