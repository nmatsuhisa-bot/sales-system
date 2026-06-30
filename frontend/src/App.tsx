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
import MastersPage from './pages/MastersPage';
import EstimateListPage from './pages/EstimateListPage';
import EstimateFormPage from './pages/EstimateFormPage';
import UsersPage from './pages/UsersPage';
import SchedulePage from './pages/SchedulePage';
import SalesPlanPage from './pages/SalesPlanPage';
import ProcurementPage from './pages/ProcurementPage';
import ManufacturingPage from './pages/ManufacturingPage';
import ProcessPage from './pages/ProcessPage';
import BomMasterPage from './pages/BomMasterPage';
import HelpPage from './pages/HelpPage';

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
          <Route path="quotations" element={<Navigate to="/estimates" replace />} />
          <Route path="quotations/new" element={<Navigate to="/estimates/new" replace />} />
          <Route path="quotations/:id/edit" element={<Navigate to="/estimates" replace />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="inventory" element={<InventoryPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="masters" element={<MastersPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="estimates" element={<EstimateListPage />} />
          <Route path="estimates/new" element={<EstimateFormPage />} />
          <Route path="estimates/:id/edit" element={<EstimateFormPage />} />
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="sales-plan" element={<SalesPlanPage />} />
          <Route path="procurement" element={<ProcurementPage />} />
          <Route path="manufacturing" element={<ManufacturingPage />} />
          <Route path="process" element={<ProcessPage />} />
          <Route path="bom-master" element={<BomMasterPage />} />
          <Route path="help" element={<HelpPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
