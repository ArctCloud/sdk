// Generated file.
import * as runtime from '../runtime.js';
import type {
    CreateServerRequest,
    CreateServerResponse,
    ErrorResponse,
    PageServer,
    ReinstallResponse,
    ResizeOptions,
    ResizeResponse,
    ResizeServerRequest,
    Server,
    ServerReinstall,
    ServerUpdate,
} from '../models/index.js';

export interface ServersCancelDeletionRequest {

    serverId: string;
}

export interface ServersCreateRequest {

    createServerRequest: CreateServerRequest;
}

export interface ServersDeleteRequest {

    serverId: string;

    atPeriodEnd?: boolean;
}

export interface ServersGetRequest {

    serverId: string;
}

export interface ServersListRequest {

    status?: ServersListStatusEnum;

    location?: string | null;

    datacenter?: string | null;

    page?: number;

    perPage?: number;
}

export interface ServersReinstallRequest {

    serverId: string;

    serverReinstall: ServerReinstall;
}

export interface ServersResizeRequest {

    serverId: string;

    resizeServerRequest: ResizeServerRequest;
}

export interface ServersResizeOptionsRequest {

    serverId: string;
}

export interface ServersRestartRequest {

    serverId: string;
}

export interface ServersStartRequest {

    serverId: string;
}

export interface ServersStopRequest {

    serverId: string;
}

export interface ServersUpdateRequest {

    serverId: string;

    serverUpdate: ServerUpdate;
}

export class ServersApi extends runtime.BaseAPI {


    async serversCancelDeletionRequestOpts(requestParameters: ServersCancelDeletionRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversCancelDeletion().'
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

        let urlPath = `/servers/{server_id}/cancel-deletion`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async serversCancelDeletionRaw(requestParameters: ServersCancelDeletionRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Server>> {
        const requestOptions = await this.serversCancelDeletionRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversCancelDeletion(requestParameters: ServersCancelDeletionRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Server> {
        const response = await this.serversCancelDeletionRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversCreateRequestOpts(requestParameters: ServersCreateRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['createServerRequest'] == null) {
            throw new runtime.RequiredError(
                'createServerRequest',
                'Required parameter "createServerRequest" was null or undefined when calling serversCreate().'
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

        let urlPath = `/servers`;

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
            body: requestParameters['createServerRequest'],
        };
    }


    async serversCreateRaw(requestParameters: ServersCreateRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<CreateServerResponse>> {
        const requestOptions = await this.serversCreateRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversCreate(requestParameters: ServersCreateRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<CreateServerResponse> {
        const response = await this.serversCreateRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversDeleteRequestOpts(requestParameters: ServersDeleteRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversDelete().'
            );
        }

        const queryParameters: any = {};

        if (requestParameters['atPeriodEnd'] != null) {
            queryParameters['at_period_end'] = requestParameters['atPeriodEnd'];
        }

        const headerParameters: runtime.HTTPHeaders = {};

        if (this.configuration && this.configuration.accessToken) {
            const token = this.configuration.accessToken;
            const tokenString = await token("bearerAuth", []);

            if (tokenString) {
                headerParameters["Authorization"] = `Bearer ${tokenString}`;
            }
        }

        let urlPath = `/servers/{server_id}`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'DELETE',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async serversDeleteRaw(requestParameters: ServersDeleteRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Server>> {
        const requestOptions = await this.serversDeleteRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversDelete(requestParameters: ServersDeleteRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Server | null | undefined > {
        const response = await this.serversDeleteRaw(requestParameters, initOverrides);
        switch (response.raw.status) {
            case 204:
                return null;
            case 200:
                return await response.value();
            default:
                return await response.value();
        }
    }


    async serversGetRequestOpts(requestParameters: ServersGetRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversGet().'
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

        let urlPath = `/servers/{server_id}`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async serversGetRaw(requestParameters: ServersGetRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Server>> {
        const requestOptions = await this.serversGetRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversGet(requestParameters: ServersGetRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Server> {
        const response = await this.serversGetRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversListRequestOpts(requestParameters: ServersListRequest): Promise<runtime.RequestOpts> {
        const queryParameters: any = {};

        if (requestParameters['status'] != null) {
            queryParameters['status'] = requestParameters['status'];
        }

        if (requestParameters['location'] != null) {
            queryParameters['location'] = requestParameters['location'];
        }

        if (requestParameters['datacenter'] != null) {
            queryParameters['datacenter'] = requestParameters['datacenter'];
        }

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

        let urlPath = `/servers`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async serversListRaw(requestParameters: ServersListRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<PageServer>> {
        const requestOptions = await this.serversListRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversList(requestParameters: ServersListRequest = {}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<PageServer> {
        const response = await this.serversListRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversReinstallRequestOpts(requestParameters: ServersReinstallRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversReinstall().'
            );
        }

        if (requestParameters['serverReinstall'] == null) {
            throw new runtime.RequiredError(
                'serverReinstall',
                'Required parameter "serverReinstall" was null or undefined when calling serversReinstall().'
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

        let urlPath = `/servers/{server_id}/reinstall`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
            body: requestParameters['serverReinstall'],
        };
    }


    async serversReinstallRaw(requestParameters: ServersReinstallRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<ReinstallResponse>> {
        const requestOptions = await this.serversReinstallRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversReinstall(requestParameters: ServersReinstallRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<ReinstallResponse> {
        const response = await this.serversReinstallRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversResizeRequestOpts(requestParameters: ServersResizeRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversResize().'
            );
        }

        if (requestParameters['resizeServerRequest'] == null) {
            throw new runtime.RequiredError(
                'resizeServerRequest',
                'Required parameter "resizeServerRequest" was null or undefined when calling serversResize().'
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

        let urlPath = `/servers/{server_id}/resize`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
            body: requestParameters['resizeServerRequest'],
        };
    }


    async serversResizeRaw(requestParameters: ServersResizeRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<ResizeResponse>> {
        const requestOptions = await this.serversResizeRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversResize(requestParameters: ServersResizeRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<ResizeResponse> {
        const response = await this.serversResizeRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversResizeOptionsRequestOpts(requestParameters: ServersResizeOptionsRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversResizeOptions().'
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

        let urlPath = `/servers/{server_id}/resize-options`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async serversResizeOptionsRaw(requestParameters: ServersResizeOptionsRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<ResizeOptions>> {
        const requestOptions = await this.serversResizeOptionsRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversResizeOptions(requestParameters: ServersResizeOptionsRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<ResizeOptions> {
        const response = await this.serversResizeOptionsRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversRestartRequestOpts(requestParameters: ServersRestartRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversRestart().'
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

        let urlPath = `/servers/{server_id}/restart`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async serversRestartRaw(requestParameters: ServersRestartRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Server>> {
        const requestOptions = await this.serversRestartRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversRestart(requestParameters: ServersRestartRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Server> {
        const response = await this.serversRestartRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversStartRequestOpts(requestParameters: ServersStartRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversStart().'
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

        let urlPath = `/servers/{server_id}/start`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async serversStartRaw(requestParameters: ServersStartRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Server>> {
        const requestOptions = await this.serversStartRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversStart(requestParameters: ServersStartRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Server> {
        const response = await this.serversStartRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversStopRequestOpts(requestParameters: ServersStopRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversStop().'
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

        let urlPath = `/servers/{server_id}/stop`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'POST',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async serversStopRaw(requestParameters: ServersStopRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Server>> {
        const requestOptions = await this.serversStopRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversStop(requestParameters: ServersStopRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Server> {
        const response = await this.serversStopRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async serversUpdateRequestOpts(requestParameters: ServersUpdateRequest): Promise<runtime.RequestOpts> {
        if (requestParameters['serverId'] == null) {
            throw new runtime.RequiredError(
                'serverId',
                'Required parameter "serverId" was null or undefined when calling serversUpdate().'
            );
        }

        if (requestParameters['serverUpdate'] == null) {
            throw new runtime.RequiredError(
                'serverUpdate',
                'Required parameter "serverUpdate" was null or undefined when calling serversUpdate().'
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

        let urlPath = `/servers/{server_id}`;
        urlPath = urlPath.replace('{server_id}', encodeURIComponent(String(requestParameters['serverId'])));

        return {
            path: urlPath,
            method: 'PATCH',
            headers: headerParameters,
            query: queryParameters,
            body: requestParameters['serverUpdate'],
        };
    }


    async serversUpdateRaw(requestParameters: ServersUpdateRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<Server>> {
        const requestOptions = await this.serversUpdateRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async serversUpdate(requestParameters: ServersUpdateRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<Server> {
        const response = await this.serversUpdateRaw(requestParameters, initOverrides);
        return await response.value();
    }

}

export const ServersListStatusEnum = {
    Provisioning: 'provisioning',
    Running: 'running',
    Stopped: 'stopped',
    Restarting: 'restarting',
    Reinstalling: 'reinstalling',
    Restoring: 'restoring',
    Deleting: 'deleting',
    Suspended: 'suspended',
    PreOrder: 'pre_order',
} as const;
export type ServersListStatusEnum = typeof ServersListStatusEnum[keyof typeof ServersListStatusEnum];
