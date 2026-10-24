from ._generated.api.account_api import AccountApi, AsyncAccountApi
from ._generated.api.datacenters_api import DatacentersApi, AsyncDatacentersApi
from ._generated.api.images_api import ImagesApi, AsyncImagesApi
from ._generated.api.invoices_api import InvoicesApi, AsyncInvoicesApi
from ._generated.api.locations_api import LocationsApi, AsyncLocationsApi
from ._generated.api.plans_api import PlansApi, AsyncPlansApi
from ._generated.api.ssh_keys_api import SshKeysApi, AsyncSshKeysApi
from ._resources import Pagination, AsyncPagination, Servers, AsyncServers
from ._transport import Transport


class Images(Pagination, ImagesApi): pass
class Datacenters(Pagination, DatacentersApi): pass
class Invoices(Pagination, InvoicesApi): pass
class Locations(Pagination, LocationsApi): pass
class Plans(Pagination, PlansApi): pass
class SshKeys(Pagination, SshKeysApi): pass
class AsyncImages(AsyncPagination, AsyncImagesApi): pass
class AsyncDatacenters(AsyncPagination, AsyncDatacentersApi): pass
class AsyncInvoices(AsyncPagination, AsyncInvoicesApi): pass
class AsyncLocations(AsyncPagination, AsyncLocationsApi): pass
class AsyncPlans(AsyncPagination, AsyncPlansApi): pass
class AsyncSshKeys(AsyncPagination, AsyncSshKeysApi): pass


class Arct:
    def __init__(self, *, token=None, base_url="https://api.arct.cloud/v1", transport=None, timeout=30.0, operation_timeout=600.0):
        self._transport = Transport(token=token, base_url=base_url, transport=transport, timeout=timeout, operation_timeout=operation_timeout)
        self.account = AccountApi(self._transport)
        self.servers = Servers(self._transport)
        self.ssh_keys = SshKeys(self._transport)
        self.locations = Locations(self._transport)
        self.datacenters = Datacenters(self._transport)
        self.plans = Plans(self._transport)
        self.images = Images(self._transport)
        self.invoices = Invoices(self._transport)

    def close(self):
        self._transport.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncArct:
    def __init__(self, *, token=None, base_url="https://api.arct.cloud/v1", transport=None, timeout=30.0, operation_timeout=600.0):
        self._transport = Transport(token=token, base_url=base_url, transport=transport, timeout=timeout, operation_timeout=operation_timeout, asynchronous=True)
        self.account = AsyncAccountApi(self._transport)
        self.servers = AsyncServers(self._transport)
        self.ssh_keys = AsyncSshKeys(self._transport)
        self.locations = AsyncLocations(self._transport)
        self.datacenters = AsyncDatacenters(self._transport)
        self.plans = AsyncPlans(self._transport)
        self.images = AsyncImages(self._transport)
        self.invoices = AsyncInvoices(self._transport)

    async def aclose(self):
        await self._transport.http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()
