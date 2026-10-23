// Generated file.
import * as runtime from '../runtime.js';
import type {
    ErrorResponse,
    PageCreditTransaction,
} from '../models/index.js';

export interface CreditTransactionsListRequest {

    page?: number;

    perPage?: number;
}

export class AccountCreditApi extends runtime.BaseAPI {


    async creditTransactionsListRequestOpts(requestParameters: CreditTransactionsListRequest): Promise<runtime.RequestOpts> {
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

        let urlPath = `/credit-transactions`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async creditTransactionsListRaw(requestParameters: CreditTransactionsListRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<PageCreditTransaction>> {
        const requestOptions = await this.creditTransactionsListRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async creditTransactionsList(requestParameters: CreditTransactionsListRequest = {}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<PageCreditTransaction> {
        const response = await this.creditTransactionsListRaw(requestParameters, initOverrides);
        return await response.value();
    }

}
