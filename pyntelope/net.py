"""
Blockchain network main class and its derivatives.

Nodeos api reference:
https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index
"""

import base64
import logging
import types
from typing import Optional, Type, Union
from urllib.parse import urljoin

import httpx
import pydantic

from xprpy import exc
from xprpy._version import __version__

logger = logging.getLogger(__name__)

DEPRECATION_WARNING = (
    "The abi_bin_to_json and abi_json_to_bin conversion APIs are "
    "both deprecated as of the Leap v3.1 release. "
    "(https://eosnetwork.com/blog/leap-v3-1-release-features/)"
    "They will also be removed from xprpy in a future version."
)


class Net:
    """
    A Net is an interface to the blockchain network api.

    It holds the connection information and methods for some of its endpoints
    host: any http url
        the address of the host you're connecting to
    headers: dict
        optional if you want to send a custom header in the request
    auth: tuple
        optional if your host requires basic http authentication
    """

    def __init__(
        self,
        *,
        host: str,
        headers: dict = dict(),
        auth: Optional[tuple] = None,
        client: Optional[Union[httpx.Client, httpx.AsyncClient]] = None,
    ):
        pydantic.parse_obj_as(pydantic.AnyHttpUrl, host)
        self.host = host
        self.headers = headers
        self.auth = auth
        self.client = client

    def __new__(cls, *args, **kwargs):
        if hasattr(cls, "default_host"):

            def __init__(
                self,
                *,
                host: str = cls.default_host,
                headers: dict = dict(),
                auth: Optional[tuple] = None,
                client: Optional[
                    Union[httpx.Client, httpx.AsyncClient]
                ] = None,
            ):
                pydantic.parse_obj_as(pydantic.AnyHttpUrl, host)
                self.host = host
                self.headers = headers
                self.auth = auth
                self.client = client

            cls.__init__ = __init__

        return super().__new__(cls)

    def _request(
        self,
        *,
        endpoint: str,
        payload: Optional[dict] = dict(),
    ):
        url = urljoin(self.host, endpoint)

        headers = {
            "user-agent": f"xprpy/{__version__}",
            "content-type": "application/json",
        }
        headers.update(self.headers)

        client = self.client
        if client is None:
            client = httpx.Client()

        try:
            resp = client.post(
                url, json=payload, headers=headers, auth=self.auth
            )
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.WriteError,
        ) as e:
            raise exc.ConnectionError(
                response=None, url=url, payload=payload, error=e
            )

        if resp.status_code > 299 and resp.status_code != 500:
            raise exc.ConnectionError(
                response=resp, url=url, payload=payload, error=None
            )

        return resp.json()

    def abi_bin_to_json(
        self, *, account_name: str, action: str, bytes: dict
    ) -> dict:
        logger.warning(DEPRECATION_WARNING)
        endpoint = "/v1/chain/abi_bin_to_json"
        payload = dict(code=account_name, action=action, binargs=bytes.hex())
        data = self._request(endpoint=endpoint, payload=payload)
        return data["args"]

    def abi_json_to_bin(
        self, *, account_name: str, action: str, json: dict
    ) -> bytes:
        """
        Return a dict containing the serialized action data.

        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/abi_json_to_bin
        """
        logger.warning(DEPRECATION_WARNING)
        endpoint = "/v1/chain/abi_json_to_bin"
        payload = dict(code=account_name, action=action, args=json)
        data = self._request(endpoint=endpoint, payload=payload)
        if "binargs" not in data:
            return data
        hex_ = data["binargs"]
        bytes_ = bytes.fromhex(hex_)
        return bytes_

    def get_raw_code_and_abi(self, *, account_name: str) -> bytes:
        """
        Retrieve raw code and ABI for a contract based on account name.

        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/get_raw_code_and_abi
        """
        endpoint = "/v1/chain/get_raw_code_and_abi"
        payload = dict({"account_name": account_name})
        data = self._request(endpoint=endpoint, payload=payload)

        data["abi"] = base64.b64decode(data["abi"])
        data["wasm"] = base64.b64decode(data["wasm"])
        return data

    def get_info(self):
        endpoint = "/v1/chain/get_info"
        data = self._request(endpoint=endpoint)
        return data

    def get_account(self, *, account_name: str):
        """
        Return an account information.

        If no account is found, then raises an connection error
        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/get_account
        """
        endpoint = "/v1/chain/get_account"
        payload = dict(account_name=account_name)
        data = self._request(endpoint=endpoint, payload=payload)
        return data

    def get_abi(self, *, account_name: str):
        """
        Retrieve the ABI for a contract based on its account name.

        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/get_abi
        """
        endpoint = "/v1/chain/get_abi"
        payload = dict(account_name=account_name)
        data = self._request(endpoint=endpoint, payload=payload)
        if len(data) == 1:
            return None
        return data

    def get_block(self, *, block_num_or_id: str):
        """
        Return various details about a specific block on the blockchain.

        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/get_block
        """
        endpoint = "/v1/chain/get_block"
        payload = dict(block_num_or_id=block_num_or_id)
        data = self._request(endpoint=endpoint, payload=payload)
        return data

    def get_block_info(self, *, block_num: str):
        """
        Return a fixed-size smaller subset of the block data.

        Similar to get_block
        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/get_block_info
        """
        endpoint = "/v1/chain/get_block_info"
        payload = dict(block_num=block_num)
        data = self._request(endpoint=endpoint, payload=payload)
        return data

    def get_table_by_scope(
        self,
        code: str,
        table: str = None,
        lower_bound: str = None,
        upper_bound: str = None,
        limit: int = None,
        reverse: bool = None,
        show_payer: bool = None,
    ):
        """
        Return a dict with all tables and their scope.

        Similar to get_table_by_scope
        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/get_table_by_scope
        """
        endpoint = "/v1/chain/get_table_by_scope"
        payload = dict(
            code=code,
            table=table,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            limit=limit,
            reverse=reverse,
            show_payer=show_payer,
        )
        for k in list(payload.keys()):
            if payload[k] is None:
                del payload[k]
        data = self._request(endpoint=endpoint, payload=payload)
        return data

    def get_table_rows(
        self,
        code: str,
        table: str,
        scope: str,
        json: bool = True,
        index_position: str = None,
        key_type: str = None,
        encode_type: str = None,
        lower_bound: str = None,
        upper_bound: str = None,
        limit: int = 1000,
        reverse: int = None,
        show_payer: int = None,
        full: bool = False,
    ):
        """
        Return a list with the rows in the table.

        Similar to get_table_rows
        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/get_table_rows

        Parameters:
        -----------
        json: bool = True
            Get the response as json
        full: bool = True
            Get the full table.
            Requires multiple requests to be made.
            The maximum number of requests made is 1000.
        """
        endpoint = "/v1/chain/get_table_rows"

        payload = dict(
            code=code,
            table=table,
            scope=scope,
            json=json,
            index_position=index_position,
            key_type=key_type,
            encode_type=encode_type,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            limit=limit,
            reverse=reverse,
            show_payer=show_payer,
        )
        payload = {k: v for k, v in payload.items() if v is not None}

        rows = []
        for _ in range(1000):
            logger.debug(f"Get data with {lower_bound=}")
            data = self._request(endpoint=endpoint, payload=payload)
            if "rows" not in data:
                return data
            rows += data["rows"]

            if not full or not data.get("more"):
                break

            lower_bound = data["next_key"]
            payload["lower_bound"] = lower_bound
        else:
            raise ValueError("Too many requests (>1000) for table")

        return rows

    def push_transaction(
        self,
        *,
        transaction: object,
        compression: bool = False,
        packed_context_free_data: str = "",
    ):
        """
        Send a transaction to the blockchain.

        https://developers.eos.io/manuals/eos/latest/nodeos/plugins/chain_api_plugin/api-reference/index#operation/push_transaction
        """
        endpoint = "/v1/chain/push_transaction"
        payload = dict(
            signatures=transaction.signatures,
            compression=compression,
            packed_context_free_data=packed_context_free_data,
            packed_trx=transaction.pack(),
        )
        data = self._request(endpoint=endpoint, payload=payload)
        return data

    def __enter__(self):
        if self.client is None:
            self.client = httpx.Client()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[types.TracebackType] = None,
    ) -> None:
        self.client.__exit__(exc_type, exc_value, traceback)


class WaxTestnet(Net):
    default_host = "https://testnet.wax.detroitledger.tech"


class WaxMainnet(Net):
    default_host = "https://api.wax.detroitledger.tech"


class EosMainnet(Net):
    default_host = "https://api.eos.detroitledger.tech"


class KylinTestnet(Net):
    default_host = "https://kylin.eossweden.org"


class Jungle3Testnet(Net):
    default_host = "https://jungle3.eossweden.org"


class Jungle4Testnet(Net):
    default_host = "https://jungle4.api.eosnation.io"


class TelosMainnet(Net):
    default_host = "https://telos.caleos.io/"


class TelosTestnet(Net):
    default_host = "https://testnet.telos.detroitledger.tech"


class ProtonMainnet(Net):
    default_host = "https://proton.cryptolions.io"


class ProtonTestnet(Net):
    default_host = "https://testnet.protonchain.com"


class UosMainnet(Net):
    default_host = "https://uos.eosusa.news"


class FioMainnet(Net):
    default_host = "https://fio.cryptolions.io"


class Local(Net):
    default_host = "http://127.0.0.1:8888"


__all__ = [
    "Net",
    "EosMainnet",
    "KylinTestnet",
    "Jungle3Testnet",
    "Jungle4Testnet",
    "TelosMainnet",
    "TelosTestnet",
    "ProtonMainnet",
    "ProtonTestnet",
    "UosMainnet",
    "FioMainnet",
    "WaxTestnet",
    "WaxMainnet",
    "Local",
]
