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
  getOrder: (orderId: string) => api.get(`/projects/orders/${orderId}`),
  addOrder: (projectId: string, data: any) => api.post(`/projects/${projectId}/orders`, data),
  updateOrder: (orderId: string, data: any) => api.put(`/projects/orders/${orderId}`, data),
  deleteOrder: (orderId: string) => api.delete(`/projects/orders/${orderId}`),
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
