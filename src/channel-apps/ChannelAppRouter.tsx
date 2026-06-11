/**
 * @file        ChannelAppRouter.tsx
 * @description LINE 頻道應用路由 - 管理頻道內子應用的路由分發與認證包裝
 * @lastUpdate  2026-05-21 16:35:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Routes, Route, Navigate } from 'react-router-dom';
import { ChannelAuthProvider } from './auth/AuthProvider';
import DemoApp from './apps/DemoApp';
import OrderMenu from './apps/order-inquiry/pages/OrderMenu';
import ProductBrowser from './apps/order-inquiry/pages/ProductBrowser';
import OrderForm from './apps/order-inquiry/pages/OrderForm';
import OrderUpload from './apps/order-inquiry/pages/OrderUpload';
import OrderStatus from './apps/order-inquiry/pages/OrderStatus';

export default function ChannelAppRouter() {
  return (
    <ChannelAuthProvider>
      <Routes>
        <Route index element={<Navigate to="demo" replace />} />
        <Route path="demo" element={<DemoApp />} />
        <Route path="order-inquiry" element={<OrderMenu />} />
        <Route path="order-inquiry/products" element={<ProductBrowser />} />
        <Route path="order-inquiry/order" element={<OrderForm />} />
        <Route path="order-inquiry/upload" element={<OrderUpload />} />
        <Route path="order-inquiry/status" element={<OrderStatus />} />
        <Route path="*" element={<Navigate to="demo" replace />} />
      </Routes>
    </ChannelAuthProvider>
  );
}
