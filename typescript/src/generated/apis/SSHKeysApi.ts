// Generated file.
import * as runtime from '../runtime.js';
import type {
    ErrorResponse,
    PageSshKey,
    SshKey,
    SshKeyCreate,
} from '../models/index.js';

export interface SshKeysCreateRequest {

    sshKeyCreate: SshKeyCreate;
}

export interface SshKeysDeleteRequest {

    keyId: string;
}

export interface SshKeysGetRequest {

    keyId: string;
}

export interface SshKeysListRequest {

    page?: number;

    perPage?: number;
}

export class SSHKeysApi extends runtime.BaseAPI {


    async sshKeysCreateRequestOpts(requestParameters: SshKeysCreateRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['sshKeyCreate'] == null) {
            throw new runtime.RequiredError(
                'sshKeyCreate',
                'Required parameter "sshKeyCreate" was null or undefined when calling sshKeysCreate().'
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

        let urlPath = `/ssh-keys`;

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
            body: requestParameters['sshKeyCreate'],
        };
    }


    async sshKeysCreateRaw(requestParameters: SshKeysCreateRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<SshKey>> {
        const requestOptions = await this.sshKeysCreateRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async sshKeysCreate(requestParameters: SshKeysCreateRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<SshKey> {
        const response = await this.sshKeysCreateRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async sshKeysDeleteRequestOpts(requestParameters: SshKeysDeleteRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['keyId'] == null) {
            throw new runtime.RequiredError(
                'keyId',
                'Required parameter "keyId" was null or undefined when calling sshKeysDelete().'
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

        let urlPath = `/ssh-keys/{key_id}`;
        urlPath = urlPath.replace('{key_id}', encodeURIComponent(String(requestParameters['keyId'])));

        return {
            path: urlPath,
            method: 'DELETE',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async sshKeysDeleteRaw(requestParameters: SshKeysDeleteRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<void>> {
        const requestOptions = await this.sshKeysDeleteRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.VoidApiResponse(response);
    }


    async sshKeysDelete(requestParameters: SshKeysDeleteRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<void> {
        await this.sshKeysDeleteRaw(requestParameters, initOverrides);
    }


    async sshKeysGetRequestOpts(requestParameters: SshKeysGetRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['keyId'] == null) {
            throw new runtime.RequiredError(
                'keyId',
                'Required parameter "keyId" was null or undefined when calling sshKeysGet().'
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

        let urlPath = `/ssh-keys/{key_id}`;
        urlPath = urlPath.replace('{key_id}', encodeURIComponent(String(requestParameters['keyId'])));

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async sshKeysGetRaw(requestParameters: SshKeysGetRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<SshKey>> {
        const requestOptions = await this.sshKeysGetRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async sshKeysGet(requestParameters: SshKeysGetRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<SshKey> {
        const response = await this.sshKeysGetRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async sshKeysListRequestOpts(requestParameters: SshKeysListRequest): Promise<runtime.RequestOpts> {
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

        let urlPath = `/ssh-keys`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async sshKeysListRaw(requestParameters: SshKeysListRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<PageSshKey>> {
        const requestOptions = await this.sshKeysListRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async sshKeysList(requestParameters: SshKeysListRequest = {}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<PageSshKey> {
        const response = await this.sshKeysListRaw(requestParameters, initOverrides);
        return await response.value();
    }

}
