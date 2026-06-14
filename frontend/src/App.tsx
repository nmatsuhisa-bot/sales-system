import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/common/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import CustomersPage from './pages/CustomersPage';
import ProductsPage from './pages/ProductsPage';
import QuotationsPage from './pages/QuotationsPage';
import QuotationFormPage from './pages/QuotationFormPage';
import OrdersPage from './pages/OrdersPage';
import PurchaseOrdersPage from './pages/PurchaseOrdersPage';
import InventoryPage from './pages/InventoryPage';
import ProjectsPage from './pages/ProjectsPage';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('access_token');
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="quotations" element={<QuotationsPage />} />
          <Route path="quotations/new" element={<QuotationFormPage />} />
          <Route path="quotations/:id/edit" element={<QuotationFormPage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="inventory" element={<InventoryPage />} />
          <Route path="projects" element={<ProjectsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
