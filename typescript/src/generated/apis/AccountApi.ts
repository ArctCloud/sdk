// Generated file.
import * as runtime from '../runtime.js';
import type {
    Account,
    ErrorResponse,
} from '../models/index.js';

export class AccountApi extends runtime.BaseAPI {


    async accountGetRequestOpts(): Promise<runtime.RequestOpts> {
        const queryParameters: any = {};

        const headerParameters: runtime.HTTPHeaders = {};

        if (this.configuration && this.configuration.accessToken) {
            const token = this.configuration.accessToken;
            const tokenString = await token("bearerAuth", []);

            if (tokenString) {
                headerParameters["Authorization"] = `Bearer ${tokenString}`;
            }
        }

        let urlPath = `/account`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async accountGetRaw(initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Account>> {
        const requestOptions = await this.accountGetRequestOpts();
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async accountGet(initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Account> {
        const response = await this.accountGetRaw(initOverrides);
        return await response.value();
    }

}
