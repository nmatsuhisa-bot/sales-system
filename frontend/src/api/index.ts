import axios from 'axios';

// B012修正: VITE_API_URL未設定時のフォールバックを共通化（PDF URL等の直接生成にも使用）
export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// リクエストインターセプター（JWT自動付与）
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// レスポンスインターセプター（401時にログアウト）
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// =============================================
// 顧客API
// =============================================
export const customerApi = {
  list: (params?: any) => api.get('/customers', { params }),
  get: (id: string) => api.get(`/customers/${id}`),
  create: (data: any) => api.post('/customers', data),
  update: (id: string, data: any) => api.put(`/customers/${id}`, data),
  delete: (id: string) => api.delete(`/customers/${id}`),
};

// =============================================
// 商品API
// =============================================
export const productApi = {
  list: (params?: any) => api.get('/products', { params }),
  get: (id: string) => api.get(`/products/${id}`),
  create: (data: any) => api.post('/products', data),
  update: (id: string, data: any) => api.put(`/products/${id}`, data),
  listOptions: (product_type?: string) => api.get('/products/options', { params: { product_type } }),
};

// =============================================
// 見積API
// =============================================
export const quotationApi = {
  list: (params?: any) => api.get('/quotations', { params }),
  get: (id: string) => api.get(`/quotations/${id}`),
  create: (data: any) => api.post('/quotations', data),
  update: (id: string, data: any) => api.put(`/quotations/${id}`, data),
  delete: (id: string) => api.delete(`/quotations/${id}`),
  convertToOrder: (id: string) => api.post(`/quotations/${id}/convert-to-order`),
};

// =============================================
// 受注API
// =============================================
export const orderApi = {
  list: (params?: any) => api.get('/orders', { params }),
  get: (id: string) => api.get(`/orders/${id}`),
  create: (data: any) => api.post('/orders', data),
  updateStatus: (id: string, status: string) => api.patch(`/orders/${id}/status`, null, { params: { status } }),
};

// =============================================
// 発注API
// =============================================
export const purchaseOrderApi = {
  list: (params?: any) => api.get('/purchase-orders', { params }),
  create: (data: any) => api.post('/purchase-orders', data),
  updateStatus: (id: string, status: string) => api.patch(`/purchase-orders/${id}/status`, null, { params: { status } }),
};

// =============================================
// 在庫API
// =============================================
export const inventoryApi = {
  list: () => api.get('/inventory'),
  addMovement: (data: any) => api.post('/inventory/movements', data),
  getMovements: (productId: string) => api.get(`/inventory/movements/${productId}`),
  // 部材在庫（入荷−利用）
  listMaterialStock: (search?: string, low_only?: boolean) => api.get('/inventory/materials', { params: { search, low_only } }),
  addMaterialMovement: (data: any) => api.post('/inventory/material-movements', data),
  materialHistory: (materialId: string) => api.get(`/inventory/material-movements/${materialId}`),
};

// =============================================
// レポートAPI
// =============================================
export const reportApi = {
  dashboard: (year?: number) => api.get('/reports/dashboard', { params: year !== undefined ? { year } : {} }),
  sales: (year?: number) => api.get('/reports/sales', { params: { year } }),
};

// =============================================
// 案件管理API
// =============================================
export const projectApi = {
  list: (params?: any) => api.get('/projects', { params }),
  get: (id: string) => api.get(`/projects/${id}`),
  create: (data: any) => api.post('/projects', data),
  update: (id: string, data: any) => api.put(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
  stats: () => api.get('/projects/stats'),
  searchOrders: (q: string) => api.get('/projects/orders/search', { params: { q } }),
  getOrder: (orderId: string) => api.get(`/projects/orders/${orderId}`),
  addOrder: (projectId: string, data: any) => api.post(`/projects/${projectId}/orders`, data),
  updateOrder: (orderId: string, data: any) => api.put(`/projects/orders/${orderId}`, data),
  deleteOrder: (orderId: string) => api.delete(`/projects/orders/${orderId}`),
  duplicateOrder: (orderId: string) => api.post(`/projects/orders/${orderId}/duplicate`),
  linkQuotation: (orderId: string, quotationId: string) =>
    api.post(`/projects/orders/${orderId}/link-quotation`, null, { params: { quotation_id: quotationId } }),
};



// =============================================
// 見積管理API（新）
// =============================================
export const arrangementApi = {
  getCrane: (orderId: string) => api.get(`/arrangements/crane/${orderId}`),
  saveCrane: (orderId: string, data: any) => api.put(`/arrangements/crane/${orderId}`, data),
  getShipping: (orderId: string) => api.get(`/arrangements/shipping/${orderId}`),
  saveShipping: (orderId: string, data: any) => api.put(`/arrangements/shipping/${orderId}`, data),
  getHotel: (orderId: string) => api.get(`/arrangements/hotel/${orderId}`),
  saveHotel: (orderId: string, data: any) => api.put(`/arrangements/hotel/${orderId}`, data),
  cranePdf: (orderId: string) => `${API_BASE}/arrangements/crane/${orderId}/pdf`,
  shippingPdf: (orderId: string) => `${API_BASE}/arrangements/shipping/${orderId}/pdf`,
  hotelPdf: (orderId: string) => `${API_BASE}/arrangements/hotel/${orderId}/pdf`,
  // 手配業者マスタ
  listVendors: (category?: string, search?: string) => api.get('/arrangements/vendors', { params: { category, search } }),
  createVendor: (data: any) => api.post('/arrangements/vendors', data),
  updateVendor: (id: string, data: any) => api.put(`/arrangements/vendors/${id}`, data),
  deleteVendor: (id: string) => api.delete(`/arrangements/vendors/${id}`),
  vendorCount: () => api.get('/arrangements/vendors/count'),
};

export const estimateApi = {
  // パターンマスタ
  getBfrBodies: () => api.get('/estimate-quotations/patterns/bfr-bodies'),
  getBfrFans: (model: string) => api.get(`/estimate-quotations/patterns/bfr-fans/${model}`),
  getBfrRvs: (model: string) => api.get(`/estimate-quotations/patterns/bfr-rvs/${model}`),
  getScaBodies: () => api.get('/estimate-quotations/patterns/sca-bodies'),
  getPlFans: () => api.get('/estimate-quotations/patterns/pl-fans'),
  getCyclones: () => api.get('/estimate-quotations/patterns/cyclones'),
  getLaborItems: () => api.get('/estimate-quotations/labor-items'),
  // 見積CRUD
  list: (params?: any) => api.get('/estimate-quotations', { params }),
  get: (id: string) => api.get(`/estimate-quotations/${id}`),
  create: (data: any) => api.post('/estimate-quotations', data),
  update: (id: string, data: any) => api.put(`/estimate-quotations/${id}`, data),
  delete: (id: string) => api.delete(`/estimate-quotations/${id}`),
  // 受注票
  issueOrderTicket: (quotationId: string) => api.post(`/estimate-quotations/${quotationId}/issue-order-ticket`),
  listOrderTickets: (params?: any) => api.get("/estimate-quotations/order-tickets", { params }),
  adoptQuotation: (quotationId: string) => api.post(`/estimate-quotations/${quotationId}/adopt`),
  unadoptQuotation: (quotationId: string) => api.delete(`/estimate-quotations/${quotationId}/adopt`),
  duplicate: (quotationId: string, project_order_id: string) => api.post(`/estimate-quotations/${quotationId}/duplicate`, { project_order_id }),
  cranePdf: (orderId: string) => `${API_BASE}/arrangements/crane/${orderId}/pdf`,
  shippingPdf: (orderId: string) => `${API_BASE}/arrangements/shipping/${orderId}/pdf`,
  hotelPdf: (orderId: string) => `${API_BASE}/arrangements/hotel/${orderId}/pdf`,
};

// =============================================
// マスタ管理API
// =============================================
export const mastersApi = {
  // 商社
  listAgencies: (search?: string) => api.get('/masters/agencies', { params: { search } }),
  createAgency: (data: any) => api.post('/masters/agencies', data),
  updateAgency: (id: string, data: any) => api.put(`/masters/agencies/${id}`, data),
  deleteAgency: (id: string) => api.delete(`/masters/agencies/${id}`),
  // 納入先
  listDeliveryDestinations: (search?: string) => api.get('/masters/delivery-destinations', { params: { search } }),
  createDeliveryDestination: (data: any) => api.post('/masters/delivery-destinations', data),
  updateDeliveryDestination: (id: string, data: any) => api.put(`/masters/delivery-destinations/${id}`, data),
  deleteDeliveryDestination: (id: string) => api.delete(`/masters/delivery-destinations/${id}`),
  // 従業員
  listEmployees: (search?: string) => api.get('/masters/employees', { params: { search } }),
  createEmployee: (data: any) => api.post('/masters/employees', data),
  updateEmployee: (id: string, data: any) => api.put(`/masters/employees/${id}`, data),
  deleteEmployee: (id: string) => api.delete(`/masters/employees/${id}`),
};

// =============================================
// 仕入（発注）管理API
// =============================================
export const procurementApi = {
  // 部材マスタ
  listMaterials: (search?: string) => api.get('/procurement/materials', { params: { search } }),
  createMaterial: (data: any) => api.post('/procurement/materials', data),
  updateMaterial: (id: string, data: any) => api.put(`/procurement/materials/${id}`, data),
  deleteMaterial: (id: string) => api.delete(`/procurement/materials/${id}`),
  // BOMマスタ
  listBom: (product_type?: string, model_no?: string) => api.get('/procurement/bom', { params: { product_type, model_no } }),
  createBom: (data: any) => api.post('/procurement/bom', data),
  updateBom: (id: string, data: any) => api.put(`/procurement/bom/${id}`, data),
  deleteBom: (id: string) => api.delete(`/procurement/bom/${id}`),
  expandBom: (order_id: string) => api.get('/procurement/bom/expand', { params: { order_id } }),
  // 部材発注管理
  listMaterialOrders: (order_id?: string, status?: string) => api.get('/procurement/material-orders', { params: { order_id, status } }),
  createMaterialOrder: (data: any) => api.post('/procurement/material-orders', data),
  updateMaterialOrder: (id: string, data: any) => api.put(`/procurement/material-orders/${id}`, data),
  deleteMaterialOrder: (id: string) => api.delete(`/procurement/material-orders/${id}`),
  // 仕入先
  listSuppliers: (search?: string) => api.get('/procurement/suppliers', { params: { search } }),
  // ユニットから部材を一括取込（方式B）
  listBomUnits: (search?: string) => api.get('/procurement/units', { params: { search } }),
  previewUnitMaterials: (unitId: string) => api.get(`/procurement/units/${unitId}/materials`),
  createOrdersFromUnit: (data: any) => api.post('/procurement/material-orders/from-unit', data),
  adoptedUnits: (project_order_id: string) => api.get('/procurement/adopted-units', { params: { project_order_id } }),
  createOrdersFromUnits: (data: any) => api.post('/procurement/material-orders/from-units', data),
  // 発注書（発注番号ヘッダー）
  createPurchaseOrder: (data: any) => api.post('/procurement/purchase-orders', data),
  listPurchaseOrders: (status?: string, project_order_id?: string) => api.get('/procurement/purchase-orders', { params: { status, project_order_id } }),
  getPurchaseOrder: (id: string) => api.get(`/procurement/purchase-orders/${id}`),
  updatePurchaseOrder: (id: string, data: any) => api.put(`/procurement/purchase-orders/${id}`, data),
  updatePoStatus: (id: string, status: string) => api.patch(`/procurement/purchase-orders/${id}/status`, null, { params: { status } }),
  deletePurchaseOrder: (id: string) => api.delete(`/procurement/purchase-orders/${id}`),
  createPOsFromUnits: (data: any) => api.post('/procurement/purchase-orders/from-units', data),
  poPdfUrl: (id: string) => `${API_BASE}/procurement/purchase-orders/${id}/pdf`,
  allocateFromStock: (moId: string) => api.post(`/procurement/material-orders/${moId}/allocate-stock`),
  receiveLine: (moId: string, quantity?: number) => api.post(`/procurement/material-orders/${moId}/receive`, { quantity }),
  receivePoStock: (poId: string) => api.post(`/procurement/purchase-orders/${poId}/receive-stock`),
};

// =============================================
// 製造計画API
// =============================================
export const manufacturingApi = {
  listPlans: (year?: number, status?: string) => api.get('/manufacturing/plans', { params: { year, status } }),
  createPlan: (data: any) => api.post('/manufacturing/plans', data),
  draftFromEstimate: (project_order_id: string) => api.post('/manufacturing/plans/draft-from-estimate', { project_order_id }),
  updatePlan: (id: string, data: any) => api.put(`/manufacturing/plans/${id}`, data),
  deletePlan: (id: string) => api.delete(`/manufacturing/plans/${id}`),
  listCapacity: (year?: number) => api.get('/manufacturing/capacity', { params: { year } }),
  upsertCapacity: (data: any) => api.post('/manufacturing/capacity', data),
  listProductHours: (product_type?: string) => api.get('/manufacturing/product-hours', { params: { product_type } }),
  upsertProductHours: (data: any) => api.post('/manufacturing/product-hours', data),
  deleteProductHours: (id: string) => api.delete(`/manufacturing/product-hours/${id}`),
  getMonthlyLoad: (year: number, factory?: string) => api.get('/manufacturing/load', { params: { year, factory } }),
};

// =============================================
// 工程管理API
// =============================================
export const processApi = {
  listTemplates: (product_type?: string) => api.get('/process/templates', { params: { product_type } }),
  createTemplate: (data: any) => api.post('/process/templates', data),
  updateTemplate: (id: string, data: any) => api.put(`/process/templates/${id}`, data),
  deleteTemplate: (id: string) => api.delete(`/process/templates/${id}`),
  listSchedules: (year?: number, month?: number, order_id?: string, span?: number) =>
    api.get('/process/schedules', { params: { year, month, order_id, span } }),
  createSchedule: (data: any) => api.post('/process/schedules', data),
  getSchedule: (id: string) => api.get(`/process/schedules/${id}`),
  updateSchedule: (id: string, data: any) => api.put(`/process/schedules/${id}`, data),
  deleteSchedule: (id: string) => api.delete(`/process/schedules/${id}`),
  generateSchedule: (data: any) => api.post('/process/schedules/generate', data),
  pdfUrl: (id: string, unit?: string) => `${API_BASE}/process/schedules/${id}/pdf${unit ? `?unit=${unit}` : ''}`,
};

// =============================================
// 製品BOMマスタAPI（製品→ユニット→部品 + 案件展開）
// =============================================
export const bomMasterApi = {
  // 製品マスタ
  listProducts: (search?: string, product_type?: string) => api.get('/bom-master/products', { params: { search, product_type } }),
  createProduct: (data: any) => api.post('/bom-master/products', data),
  updateProduct: (id: string, data: any) => api.put(`/bom-master/products/${id}`, data),
  deleteProduct: (id: string) => api.delete(`/bom-master/products/${id}`),
  // ユニットマスタ
  listUnits: (search?: string, unit_type?: string) => api.get('/bom-master/units', { params: { search, unit_type } }),
  createUnit: (data: any) => api.post('/bom-master/units', data),
  updateUnit: (id: string, data: any) => api.put(`/bom-master/units/${id}`, data),
  deleteUnit: (id: string) => api.delete(`/bom-master/units/${id}`),
  // 製品構成BOM（製品→ユニット）
  listProductUnits: (productId: string) => api.get(`/bom-master/products/${productId}/units`),
  addProductUnit: (data: any) => api.post('/bom-master/product-units', data),
  updateProductUnit: (id: string, data: any) => api.put(`/bom-master/product-units/${id}`, data),
  deleteProductUnit: (id: string) => api.delete(`/bom-master/product-units/${id}`),
  // ユニット構成BOM（ユニット→部品）
  listUnitMaterials: (unitId: string) => api.get(`/bom-master/units/${unitId}/materials`),
  addUnitMaterial: (data: any) => api.post('/bom-master/unit-materials', data),
  updateUnitMaterial: (id: string, data: any) => api.put(`/bom-master/unit-materials/${id}`, data),
  deleteUnitMaterial: (id: string) => api.delete(`/bom-master/unit-materials/${id}`),
  // 見積パターンから型式を取込
  seedFromEstimatePatterns: () => api.post('/bom-master/seed-from-estimate-patterns'),
  // サンプル一括取込／削除
  sampleCount: () => api.get('/bom-master/import/sample-count'),
  deleteSampleData: () => api.delete('/bom-master/import/sample-data'),
};

// =============================================
// 認証API
// =============================================
export const authApi = {
  listUsers: () => api.get('/auth/users'),
  createUser: (data: any) => api.post('/auth/users', data),
  updateUser: (id: string, data: any) => api.put(`/auth/users/${id}`, data),
  deleteUser: (id: string) => api.delete(`/auth/users/${id}`),
  login: (email: string, password: string) => {
    const form = new URLSearchParams();
    form.append('username', email);
    form.append('password', password);
    return api.post('/auth/login', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  },
  me: () => api.get('/auth/me'),
};
