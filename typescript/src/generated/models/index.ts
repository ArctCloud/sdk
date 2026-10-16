// Generated file.
export interface Account {
    [key: string]: unknown;

    id: string;

    email: string;

    name: string | null;

    email_verified: boolean;

    created_at: string;

    token: TokenInfo;
}

export interface CreateServerRequest {

    hostname: string;

    location: string;

    plan: string;

    image_id: string;

    billing_period?: CreateServerRequestBillingPeriodEnum;

    ssh_key_ids?: Array<string>;

    coupon_code?: string | null;

    enable_backups?: boolean;
}

export const CreateServerRequestBillingPeriodEnum = {
    Monthly: 'monthly',
    Quarterly: 'quarterly',
    SemiAnnual: 'semi_annual',
    Yearly: 'yearly',
} as const;
export type CreateServerRequestBillingPeriodEnum = typeof CreateServerRequestBillingPeriodEnum[keyof typeof CreateServerRequestBillingPeriodEnum];

export interface CreateServerResponse {
    [key: string]: unknown;

    order: Order;

    server: Server | null;

    password?: string | null;
}

export interface ErrorDetail {
    [key: string]: unknown;

    code: string;

    message: string;

    details?: object | null;
}

export interface ErrorResponse {
    [key: string]: unknown;

    error: ErrorDetail;
}

export type ExpectedAmount = number | string;

export interface Image {
    [key: string]: unknown;

    id: string;

    name: string;

    version: string;

    display_name: string;

    location: string;

    allowed_plans: Array<string>;
}

export interface Invoice {
    [key: string]: unknown;

    id: string;

    invoice_number: string;

    status: InvoiceStatus;

    subtotal: number;

    tax: number;

    total: number;

    refunded_total: number;

    period_start: string;

    period_end: string;

    due_date: string;

    paid_at: string | null;

    payment_method: string | null;

    hosted_invoice_url: string | null;

    created_at: string;

    items: Array<InvoiceItem>;
}

export interface InvoiceItem {
    [key: string]: unknown;

    description: string;

    quantity: number;

    unit_price: number;

    total: number;

    server_id: string | null;
}

export const InvoiceStatus = {
    Draft: 'draft',
    Pending: 'pending',
    Paid: 'paid',
    Failed: 'failed',
    Refunded: 'refunded',
    Cancelled: 'cancelled',
} as const;
export type InvoiceStatus = typeof InvoiceStatus[keyof typeof InvoiceStatus] | (string & {});

export interface Location {
    [key: string]: unknown;

    code: string;

    name: string;

    region: string | null;

    status: string;

    is_preorder: boolean;
}

export interface Order {
    [key: string]: unknown;

    id: string;

    order_number: string;

    status: string;

    payment_method: OrderPaymentMethodEnum;

    amount: number;

    currency: string;

    created_at: string;

    paid_at: string | null;

    server_id: string | null;
}

export const OrderPaymentMethodEnum = {
    Card: 'card',
    Promo: 'promo',
} as const;
export type OrderPaymentMethodEnum = typeof OrderPaymentMethodEnum[keyof typeof OrderPaymentMethodEnum] | (string & {});

export interface PageImage {

    data: Array<Image>;

    pagination: Pagination;
}

export interface PageInvoice {

    data: Array<Invoice>;

    pagination: Pagination;
}

export interface PageLocation {

    data: Array<Location>;

    pagination: Pagination;
}

export interface PagePlan {

    data: Array<Plan>;

    pagination: Pagination;
}

export interface PageServer {

    data: Array<Server>;

    pagination: Pagination;
}

export interface PageSshKey {

    data: Array<SshKey>;

    pagination: Pagination;
}

export interface Pagination {
    [key: string]: unknown;

    page: number;

    per_page: number;

    total: number;

    total_pages: number;
}

export interface PendingResize {
    [key: string]: unknown;

    id: string;

    to_plan: string;

    amount: number;

    status: string;

    created_at: string | null;
}

export interface Plan {
    [key: string]: unknown;

    slug: string;

    name: string;

    location: string;

    tier: string;

    cpu_cores: number;

    ram_gb: number;

    storage_gb: number;

    bandwidth_tb: number;

    network_speed_gbps: number | null;

    price_monthly: number;

    in_stock: boolean;

    backups_available: boolean;
}

export interface ReinstallResponse {
    [key: string]: unknown;

    server: Server;

    password?: string | null;
}

export interface ResizeCard {
    [key: string]: unknown;

    brand?: string | null;

    last4?: string | null;

    exp_month?: number | null;

    exp_year?: number | null;
}

export interface ResizeOptions {
    [key: string]: unknown;

    can_resize: boolean;

    blocked_code: string | null;

    blocked_reason: string | null;

    current_plan: string;

    billing_period: string;

    current_price_period: number | null;

    period_end: string | null;

    days_left: number | null;

    card: ResizeCard | null;

    promo: ResizePromo | null;

    unpaid_invoice: UnpaidInvoice | null;

    pending_resize: PendingResize | null;

    plans: Array<ResizePlan>;
}

export interface ResizePlan {
    [key: string]: unknown;

    slug: string;

    name: string;

    cpu_cores: number;

    ram_gb: number;

    storage_gb: number;

    bandwidth_tb: number;

    price_period: number;

    price_period_list: number;

    promo_applies: boolean;

    is_current: boolean;

    eligible: boolean;

    reason: string | null;

    reason_label: string | null;

    amount_due_today: number | null;
}

export interface ResizePromo {
    [key: string]: unknown;

    code: string;

    discount_type: string;

    discount_value: number;

    label: string;
}

export interface ResizeResponse {
    [key: string]: unknown;

    status: ResizeResponseStatusEnum;

    resize_id: string;

    invoice_id: string | null;

    invoice_number: string | null;

    amount: number;

    to_plan: string;

    restart_required: boolean;
}

export const ResizeResponseStatusEnum = {
    Applied: 'applied',
    PendingPayment: 'pending_payment',
} as const;
export type ResizeResponseStatusEnum = typeof ResizeResponseStatusEnum[keyof typeof ResizeResponseStatusEnum] | (string & {});

export interface ResizeServerRequest {

    plan: string;

    expected_amount?: ExpectedAmount | null;
}

export interface Server {
    [key: string]: unknown;

    id: string;

    hostname: string;

    status: VMStatus;

    location: string;

    plan: string;

    plan_name: string | null;

    cpu_cores: number;

    ram_gb: number;

    storage_gb: number;

    bandwidth_tb: number;

    ipv4: string | null;

    ipv6: string | null;

    os: string;

    login_user: string | null;

    labels: Array<string>;

    delete_protection: boolean;

    billing_period: string;

    price: number;

    next_due_date: string | null;

    cancel_at: string | null;

    created_at: string;
}

export interface ServerReinstall {

    image_id: string;

    ssh_key_ids?: Array<string>;

    hostname?: string;
}

export interface ServerUpdate {

    hostname?: string;

    delete_protection?: boolean;

    labels?: Array<string>;
}

export interface SshKey {
    [key: string]: unknown;

    id: string;

    name: string;

    fingerprint: string;

    created_at: string;
}

export interface SshKeyCreate {

    name: string;

    public_key: string;
}

export interface TokenInfo {
    [key: string]: unknown;

    id: string;

    name: string;

    scope: string;

    expires_at: string | null;
}

export interface UnpaidInvoice {
    [key: string]: unknown;

    id: string;

    invoice_number: string;

    total: number;

    due_date: string;

    overdue: boolean;
}

export const VMStatus = {
    Provisioning: 'provisioning',
    Running: 'running',
    Stopped: 'stopped',
    Restarting: 'restarting',
    Reinstalling: 'reinstalling',
    Restoring: 'restoring',
    Error: 'error',
    Deleting: 'deleting',
    Suspended: 'suspended',
    PreOrder: 'pre_order',
} as const;
export type VMStatus = typeof VMStatus[keyof typeof VMStatus] | (string & {});
