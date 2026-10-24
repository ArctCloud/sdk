// Generated file.
import * as runtime from '../runtime.js';
import type {
    ErrorResponse,
    PageDatacenter,
    PageImage,
    PageLocation,
    PagePlan,
} from '../models/index.js';

export interface DatacentersListRequest {

    page?: number;

    perPage?: number;
}

export interface ImagesListRequest {

    location?: string | null;

    datacenter?: string | null;

    page?: number;

    perPage?: number;
}

export interface LocationsListRequest {

    page?: number;

    perPage?: number;
}

export interface PlansListRequest {

    location?: string | null;

    datacenter?: string | null;

    page?: number;

    perPage?: number;
}

export class CatalogApi extends runtime.BaseAPI {


    async datacentersListRequestOpts(requestParameters: DatacentersListRequest): Promise<runtime.RequestOpts> {
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

        let urlPath = `/datacenters`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async datacentersListRaw(requestParameters: DatacentersListRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<PageDatacenter>> {
        const requestOptions = await this.datacentersListRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async datacentersList(requestParameters: DatacentersListRequest = {}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<PageDatacenter> {
        const response = await this.datacentersListRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async imagesListRequestOpts(requestParameters: ImagesListRequest): Promise<runtime.RequestOpts> {
        const queryParameters: any = {};

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

        let urlPath = `/images`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async imagesListRaw(requestParameters: ImagesListRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<PageImage>> {
        const requestOptions = await this.imagesListRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async imagesList(requestParameters: ImagesListRequest = {}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<PageImage> {
        const response = await this.imagesListRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async locationsListRequestOpts(requestParameters: LocationsListRequest): Promise<runtime.RequestOpts> {
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

        let urlPath = `/locations`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async locationsListRaw(requestParameters: LocationsListRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<PageLocation>> {
        const requestOptions = await this.locationsListRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async locationsList(requestParameters: LocationsListRequest = {}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<PageLocation> {
        const response = await this.locationsListRaw(requestParameters, initOverrides);
        return await response.value();
    }


    async plansListRequestOpts(requestParameters: PlansListRequest): Promise<runtime.RequestOpts> {
        const queryParameters: any = {};

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

        let urlPath = `/plans`;

        return {
            path: urlPath,
            method: 'GET',
            headers: headerParameters,
            query: queryParameters,
        };
    }


    async plansListRaw(requestParameters: PlansListRequest, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<runtime.ApiResponse<PagePlan>> {
        const requestOptions = await this.plansListRequestOpts(requestParameters);
        const response = await this.request(requestOptions, initOverrides);

        return new runtime.JSONApiResponse(response);
    }


    async plansList(requestParameters: PlansListRequest = {}, initOverrides?: RequestInit | runtime.InitOverrideFunction): Promise<PagePlan> {
        const response = await this.plansListRaw(requestParameters, initOverrides);
        return await response.value();
    }

}
