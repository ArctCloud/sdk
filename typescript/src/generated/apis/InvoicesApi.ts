// Generated file.
import * as runtime from '../runtime.js';
import type {
    ErrorResponse,
    Invoice,
    PageInvoice,
    PayInvoiceRequest,
} from '../models/index.js';

export interface InvoicesGetRequest {

    invoiceId: string;
}

export interface InvoicesListRequest {

    page?: number;

    perPage?: number;
}

export interface InvoicesPayRequest {

    invoiceId: string;

    payInvoiceRequest: PayInvoiceRequest;
}

export class InvoicesApi extends runtime.BaseAPI {


    async invoicesGetRequestOpts(requestParameters: InvoicesGetRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['invoiceId'] == null) {
            throw new runtime.RequiredError(
                'invoiceId',
                'Required parameter "invoiceId" was null or undefined when calling invoicesGet().'
            );
        }

        const queryParameters: any = {};

        const headerParameters: runtime.HTTPHeaders = {};

        if (this.configuration && this.configuration.accessToken) {
            const token = this.configuration.accessToken;
            const tokenString = await token("bearerAuth", []);

            if (tokenString) {
                headerParameters["Authorization"] = `Bearer ${tokenString}`;
            }
        }

        let urlPath = `/invoices/{invoice_id}`;
        urlPath = urlPath.replace('{invoice_id}', encodeURIComponent(String(requestParameters['invoiceId'])));

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async invoicesGetRaw(requestParameters: InvoicesGetRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Invoice>> {
        const requestOptions = await this.invoicesGetRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async invoicesGet(requestParameters: InvoicesGetRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Invoice> {
        const response = await this.invoicesGetRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async invoicesListRequestOpts(requestParameters: InvoicesListRequest): Promise<runtime.RequestOpts> {
        const queryParameters: any = {};

        if (requestParameters['page'] != null) {
            queryParameters['page'] = requestParameters['page'];
        }

        if (requestParameters['perPage'] != null) {
            queryParameters['per_page'] = requestParameters['perPage'];
        }

        const headerParameters: runtime.HTTPHeaders = {};

        if (this.configuration && this.configuration.accessToken) {
            const token = this.configuration.accessToken;
            const tokenString = await token("bearerAuth", []);

            if (tokenString) {
                headerParameters["Authorization"] = `Bearer ${tokenString}`;
            }
        }

        let urlPath = `/invoices`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async invoicesListRaw(requestParameters: InvoicesListRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<PageInvoice>> {
        const requestOptions = await this.invoicesListRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async invoicesList(requestParameters: InvoicesListRequest = {}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<PageInvoice> {
        const response = await this.invoicesListRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async invoicesPayRequestOpts(requestParameters: InvoicesPayRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['invoiceId'] == null) {
            throw new runtime.RequiredError(
                'invoiceId',
                'Required parameter "invoiceId" was null or undefined when calling invoicesPay().'
            );
        }

        if (requestParameters['payInvoiceRequest'] == null) {
            throw new runtime.RequiredError(
                'payInvoiceRequest',
                'Required parameter "payInvoiceRequest" was null or undefined when calling invoicesPay().'
            );
        }

        const queryParameters: any = {};

        const headerParameters: runtime.HTTPHeaders = {};

        headerParameters['Content-Type'] = 'application/json';

        if (this.configuration && this.configuration.accessToken) {
            const token = this.configuration.accessToken;
            const tokenString = await token("bearerAuth", []);

            if (tokenString) {
                headerParameters["Authorization"] = `Bearer ${tokenString}`;
            }
        }

        let urlPath = `/invoices/{invoice_id}/pay`;
        urlPath = urlPath.replace('{invoice_id}', encodeURIComponent(String(requestParameters['invoiceId'])));

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
            body: requestParameters['payInvoiceRequest'],
        };
    }


    async invoicesPayRaw(requestParameters: InvoicesPayRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Invoice>> {
        const requestOptions = await this.invoicesPayRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async invoicesPay(requestParameters: InvoicesPayRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Invoice> {
        const response = await this.invoicesPayRaw(requestParameters, initOverrides);
        return await response.value();
    }

}
