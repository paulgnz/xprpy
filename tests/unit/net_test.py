import re
from unittest.mock import Mock, patch

import httpx
import pydantic
import pytest

import xprpy


def test_should_always_pass():
    pass


def test_when_instantiate_net_returns_net_object():
    net = xprpy.Net(host="http://127.0.0.1:8888")
    assert isinstance(net, xprpy.Net)


def test_when_instantiate_net_with_incorrect_host_format_then_raises_error():
    with pytest.raises(pydantic.ValidationError):
        xprpy.Net(host="rpc://127.0.0.1:8888")


def test_when_net_get_info_then_returns_dict(net):
    info = net.get_info()
    assert isinstance(info, dict)


def test_given_http_timeout_when_net_get_info_then_raise_connection_error(
    httpx_mock, net
):
    with pytest.raises(xprpy.exc.ConnectionError):
        net.get_info()


def test_given_http_write_error_when_net_get_info_then_raise_connection_error(
    httpx_mock, net
):
    def raise_write_error(*args, **kwargs):
        raise httpx.WriteError("")

    httpx_mock.add_callback(raise_write_error)
    with pytest.raises(xprpy.exc.ConnectionError):
        net.get_info()


def test_given_http_return_400_when_net_get_info_then_raise_connection_error(
    httpx_mock, net
):
    httpx_mock.add_response(status_code=400)
    with pytest.raises(xprpy.exc.ConnectionError):
        net.get_info()


def test_when_net_get_info_then_return_has_chain_id(net):
    info = net.get_info()
    assert "chain_id" in info


def test_when_net_get_info_then_chain_id_has_correct_format(net):
    info = net.get_info()
    patt = r"[a-f0-9]{64}"
    assert re.fullmatch(patt, info["chain_id"])


aliases = [
    "EosMainnet",
    "KylinTestnet",
    "Jungle3Testnet",
    "TelosMainnet",
    "TelosTestnet",
    "ProtonMainnet",
    "ProtonTestnet",
    "UosMainnet",
    "FioMainnet",
    "XPRTestnet",
    "WaxMainnet",
]


@pytest.mark.parametrize("alias", aliases)
def test_when_instantiate_though_alias_then_host_has_tld(alias):
    net_factory = getattr(xprpy, alias)
    net = net_factory()
    patt = r"^https://[\w\.]{3,}"
    assert re.match(patt, net.host)


def test_when_instantiate_localnet_then_host_is_localhost():
    net = xprpy.Local()
    assert net.host.startswith("http://127.0.0.1")


accounts = ["eosio", "user1", "user2"]


@pytest.mark.parametrize("account_name", accounts)
def test_when_get_account_X_then_return_has_account_name(net, account_name):
    account_info = net.get_account(account_name=account_name)
    assert "account_name" in account_info


@pytest.mark.parametrize("account_name", accounts)
def test_when_get_account_X_then_return_account_name_match(net, account_name):
    account_info = net.get_account(account_name=account_name)
    assert account_info["account_name"] == account_name


def test_when_get_non_existing_account(net):
    resp = net.get_account(account_name="qweasdzxc")
    assert resp["error"]["details"][0]["message"].startswith("unknown key")


def test_user1_has_no_abi(net):
    abi = net.get_abi(account_name="user1")
    assert abi is None


def test_user2_has_an_abi(net):
    abi = net.get_abi(account_name="user2")
    assert abi is not None


def test_when_get_abi_then_returns_has_account_name(net):
    abi = net.get_abi(account_name="user2")
    assert "account_name" in abi


def test_when_get_abi_then_returned_abi_account_name_matches(net):
    abi = net.get_abi(account_name="user2")
    abi["account_name"] == "user2"


def test_get_block_previous_field_is_000(net):
    block = net.get_block(block_num_or_id=1)
    assert block["previous"] == "0" * 64


def test_get_block_info_previous_field_is_000(net):
    block = net.get_block_info(block_num=1)
    assert block["previous"] == "0" * 64


def test_abi_json_to_bin_return_bytes(net):
    json = {"from": "abcdef", "message": "a sample message"}
    bindata = net.abi_json_to_bin(
        account_name="user2",
        action="sendmsg",
        json=json,
    )
    assert isinstance(bindata, bytes)


def test_abi_bin_to_json_return_dict(net):
    json = {"from": "abcdef", "message": "a sample message"}
    bindata = net.abi_json_to_bin(
        account_name="user2",
        action="sendmsg",
        json=json,
    )
    d = net.abi_bin_to_json(
        account_name="user2",
        action="sendmsg",
        bytes=bindata,
    )
    assert isinstance(d, dict)


def test_abi_json_to_bin_and_bin_to_json_return_same_as_sent(net):
    json = {"from": "abcdef", "message": "a sample message"}
    bindata = net.abi_json_to_bin(
        account_name="user2",
        action="sendmsg",
        json=json,
    )
    d = net.abi_bin_to_json(
        account_name="user2",
        action="sendmsg",
        bytes=bindata,
    )
    assert d == json


def test_get_table_by_scope_returns_dict(net):
    resp = net.get_table_by_scope(code="user2")
    assert isinstance(resp, dict)


def test_when_get_table_by_scope_then_resp_has_rows(net):
    resp = net.get_table_by_scope(code="user2")
    assert "rows" in resp


def test_when_get_table_by_scope_with_no_contract_then_rows_are_empty(net):
    resp = net.get_table_by_scope(code="user1")
    assert len(resp["rows"]) == 0


def test_when_get_table_by_scope_with_contract_then_rows_have_objects(net):
    # send a transaction just for the table to be created
    data = [
        xprpy.Data(name="from", value=xprpy.types.Name("user2")),
        xprpy.Data(
            name="message",
            value=xprpy.types.String("hello"),
        ),
    ]
    trans = xprpy.Transaction(
        actions=[
            xprpy.Action(
                account="user2",
                name="sendmsg",
                data=data,
                authorization=[
                    xprpy.Authorization(actor="user2", permission="active")
                ],
            )
        ],
    )
    linked_trans = trans.link(net=net)
    signed_trans = linked_trans.sign(
        key="5K5UHY2LjHw2QQFJKCd2PdF7hxPJnknMfQLhxbEguJJttr1DFdp"
    )
    resp = signed_trans.send()

    resp = net.get_table_by_scope(code="user2")
    assert len(resp["rows"]) > 0


def test_when_get_table_by_scope_from_non_existent_account_then_rows_are_empty(
    net,
):
    resp = net.get_table_by_scope(code="xxx")
    assert len(resp["rows"]) == 0


def test_get_table_rows_returns_list(net):
    resp = net.get_table_rows(code="user2", table="messages", scope="user2")
    assert isinstance(resp, list)


def test_get_table_rows_from_non_existing_table_returns_error(net):
    resp = net.get_table_rows(code="user2", table="xxx", scope="user2")
    assert "code" in resp
    assert resp["code"] == 500


def test_get_table_rows_from_no_contract_account_returns_error(net):
    resp = net.get_table_rows(code="user1", table="messages", scope="user2")
    assert "code" in resp
    assert resp["code"] == 500


def test_get_table_rows_from_non_existing_account_returns_error(net):
    resp = net.get_table_rows(code="xxx", table="messages", scope="user2")
    assert "code" in resp
    assert resp["code"] == 500


def test_get_table_rows_with_strange_bounds_returns_empty_list(net):
    resp = net.get_table_rows(
        code="user2", table="messages", scope="user2", lower_bound="zzzzzz"
    )
    assert resp == []


def test_get_table_rows_with_strange_scope_returns_empty_list(net):
    resp = net.get_table_rows(code="user2", table="messages", scope="user1")
    assert resp == []


def test_get_table_rows_returns_non_empty_list(net):
    resp = net.get_table_rows(code="user2", table="longtable", scope="user2")
    assert len(resp) > 0


def test_get_table_rows_with_limit_returns_limit_items(net):
    limit = 15
    resp = net.get_table_rows(
        code="user2", table="longtable", scope="user2", limit=limit
    )
    assert len(resp) == limit


def test_get_table_rows_full_returns_3000_items(net):
    resp = net.get_table_rows(
        code="user2", table="longtable", scope="user2", full=True
    )
    assert len(resp) == 3000


@pytest.mark.slow
def test_get_table_rows_full_with_limit_raise_value_error(net):
    with pytest.raises(ValueError):
        net.get_table_rows(
            code="user2", table="longtable", scope="user2", full=True, limit=1
        )


def test_get_info_request_headers_include_pyntelope_user_agent(
    net, httpx_mock
):
    httpx_mock.add_response(json={}, status_code=200)
    net.get_info()
    requests = httpx_mock.get_requests()
    headers = requests[0].headers
    assert "xprpy" in headers["user-agent"].lower()


def test_get_info_request_headers_include_main_headers(net, httpx_mock):
    httpx_mock.add_response(json={}, status_code=200)
    net.get_info()
    requests = httpx_mock.get_requests()
    headers = requests[0].headers
    main_headers = [
        "host",
        "accept",
        "accept-encoding",
        "connection",
        "user-agent",
        "content-length",
        "content-type",
    ]
    for header in main_headers:
        assert header in headers


def test_given_net_with_specific_header_then_use_specific_header(httpx_mock):
    httpx_mock.add_response(json={}, status_code=200)
    custom_headers = {"user-agent": "aaa", "x-bbb": "ccc"}
    net = xprpy.Local(headers=custom_headers)
    net.get_info()
    requests = httpx_mock.get_requests()
    headers = requests[0].headers
    assert headers["x-bbb"] == "ccc"


def test_given_net_with_specific_header_then_user_agent_is_overwritten(
    httpx_mock,
):
    httpx_mock.add_response(json={}, status_code=200)
    custom_headers = {"user-agent": "aaa", "x-bbb": "ccc"}
    net = xprpy.Local(headers=custom_headers)
    net.get_info()
    requests = httpx_mock.get_requests()
    headers = requests[0].headers
    assert headers["user-agent"] == "aaa"


def test_can_be_instantiated_with_auth_param():
    net = xprpy.Local(auth=("user", "password"))
    assert isinstance(net, xprpy.Net)


def test_given_net_with_auth_tuple_then_request_has_authorization_header(
    httpx_mock,
):
    httpx_mock.add_response(json={}, status_code=200)
    net = xprpy.Local(auth=("user", "password"))
    net.get_info()
    requests = httpx_mock.get_requests()
    headers = requests[0].headers
    assert "authorization" in headers


def test_given_net_with_auth_then_authorization_headers_match(httpx_mock):
    httpx_mock.add_response(json={}, status_code=200)
    net = xprpy.Local(auth=("user", "password"))
    net.get_info()
    requests = httpx_mock.get_requests()
    headers = requests[0].headers

    auth_header = headers["authorization"]
    auth_obj = httpx.BasicAuth("user", "password")
    assert auth_header == auth_obj._auth_header


def test_when_use_net_with_context_syntax_then_net_object_is_created():
    with xprpy.Local() as net:
        assert isinstance(net, xprpy.Net)


def test_when_use_net_with_context_syntax_then_info_returns_dict():
    with xprpy.Local() as net:
        info = net.get_info()
    assert isinstance(info, dict)


def test_net_accepts_client_object_in_initialization():
    with httpx.Client() as client:
        net = xprpy.Local(client=client)
    assert isinstance(net, xprpy.Net)


def test_when_initialize_net_with_client_then_client_attribute_is_the_same():
    with httpx.Client() as client:
        net = xprpy.Local(client=client)
        assert id(net.client) == id(client)


def test_when_initialize_with_context_manager_then_client_attr_is_the_same():
    with httpx.Client() as client:
        with xprpy.Local(client=client) as net:
            assert id(net.client) == id(client)


def test_when_initialize_with_context_manager_then_auto_create_client():
    with xprpy.Local() as net:
        assert isinstance(net.client, httpx.Client)


def test_when_inside_the_context_manager_then_can_get_info():
    with xprpy.Local() as net:
        info = net.get_info()
        assert isinstance(info, dict)


def test_when_outside_the_context_manager_then_get_info_raises_error():
    with xprpy.Local() as net:
        ...
    with pytest.raises(RuntimeError):
        _ = net.get_info()


def test_given_client_when_outside_the_context_manager_then_get_info_raises_error():  # NOQA: E501
    with httpx.Client() as client:
        with xprpy.Local(client=client) as net:
            ...
        with pytest.raises(RuntimeError):
            _ = net.get_info()


def test_given_client_and_context_manager_close_both_dont_raise_errors():
    with httpx.Client() as client:
        with xprpy.Local(client=client):
            ...


def test_given_no_client_when_make_two_requests_then_client_factory_is_called_twice():  # NOQA: E501
    with patch("httpx.Client") as m:
        mock_client = Mock()
        m.return_value = mock_client

        response = Mock()
        response.status_code = 200
        mock_client.post.return_value = response

        net = xprpy.Local()
        net.get_info()
        net.get_info()
        assert m.call_count == 2


def test_given_client_when_make_two_requests_then_client_factory_is_called_0_times():  # NOQA: E501
    with patch("httpx.Client") as mock_httpx_client:
        mock_client = Mock()

        response = Mock()
        response.status_code = 200
        mock_client.post.return_value = response

        net = xprpy.Local(client=mock_client)
        net.get_info()
        net.get_info()
        assert mock_httpx_client.call_count == 0


def test_given_net_with_context_manager_when_make_two_requests_then_client_post_is_called_twice():  # NOQA: E501
    mock_client = Mock()
    mock_client.__exit__ = Mock()

    response = Mock()
    response.status_code = 200
    mock_client.post.return_value = response
    with xprpy.Local(client=mock_client) as net:
        net.get_info()
        net.get_info()

    assert mock_client.post.call_count == 2


def test_given_net_with_context_manager_when_make_two_requests_then_client_factory_is_called_0():  # NOQA: E501
    with patch("httpx.Client") as mock_httpx_client:
        mock_client = Mock()
        mock_client.__exit__ = Mock()

        response = Mock()
        response.status_code = 200
        mock_client.post.return_value = response
        with xprpy.Local(client=mock_client) as net:
            net.get_info()
            net.get_info()

        assert mock_httpx_client.call_count == 0
