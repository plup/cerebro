from __future__ import annotations

import json

import httpx

from neuron.thehive import ThehiveClient


def test_get_observable_queries_alert_context_first() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{'_id': '~1', 'data': 'host1'}])

    client = ThehiveClient(
        base_url='http://thehive',
        key='secret',
        organisation='blue team',
        transport=httpx.MockTransport(handler),
    )

    assert client.get_observable(
        '~1',
        context_type='alert',
        context_id='~2',
    ) == {'_id': '~1', 'data': 'host1'}

    assert len(requests) == 1
    assert requests[0].method == 'POST'
    assert requests[0].url.path == '/api/v1/query'
    assert requests[0].headers['x-organisation'] == 'blue team'
    assert json.loads(requests[0].content) == {
        'query': [
            {'_name': 'getAlert', 'idOrName': '~2'},
            {'_name': 'observables'},
            {'_name': 'filter', '_id': '~1'},
            {'_name': 'page', 'from': 0, 'to': 1},
        ],
    }


def test_get_observable_queries_case_context_first() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{'_id': '~1', 'data': 'host1'}])

    client = ThehiveClient(
        base_url='http://thehive',
        key='secret',
        transport=httpx.MockTransport(handler),
    )

    assert client.get_observable(
        '~1',
        context_type='case',
        context_id='~2',
    ) == {'_id': '~1', 'data': 'host1'}

    assert json.loads(requests[0].content)['query'][0] == {
        '_name': 'getCase',
        'idOrName': '~2',
    }


def test_get_observable_uses_invocation_context_from_environment(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{'_id': '~1', 'data': 'host1'}])

    monkeypatch.setenv('CEREBRO_CONTEXT_TYPE', 'alert')
    monkeypatch.setenv('CEREBRO_CONTEXT_ID', '~2')
    monkeypatch.setenv('CEREBRO_ORGANISATION', 'blue team')
    client = ThehiveClient(
        base_url='http://thehive',
        key='secret',
        transport=httpx.MockTransport(handler),
    )

    assert client.get_observable('~1') == {'_id': '~1', 'data': 'host1'}
    assert json.loads(requests[0].content)['query'][0] == {
        '_name': 'getAlert',
        'idOrName': '~2',
    }
    assert requests[0].headers['x-organisation'] == 'blue team'


def test_client_uses_thehive_organisation_from_environment(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'_id': '~1', 'data': 'host1'})

    monkeypatch.setenv('TH_ORGANISATION', 'blue team')
    client = ThehiveClient(
        base_url='http://thehive',
        key='secret',
        transport=httpx.MockTransport(handler),
    )

    assert client.get_observable('~1') == {'_id': '~1', 'data': 'host1'}
    assert requests[0].headers['x-organisation'] == 'blue team'


def test_get_observable_uses_global_v1_without_context() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'_id': '~1', 'data': 'host1'})

    client = ThehiveClient(
        base_url='http://thehive',
        key='secret',
        transport=httpx.MockTransport(handler),
    )

    assert client.get_observable('~1') == {'_id': '~1', 'data': 'host1'}
    assert len(requests) == 1
    assert requests[0].method == 'GET'
    assert requests[0].url.path == '/api/v1/observable/~1'


def test_get_observable_falls_back_to_global_v1_when_context_query_is_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/query':
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={'_id': '~1', 'data': 'host1'})

    client = ThehiveClient(
        base_url='http://thehive',
        key='secret',
        transport=httpx.MockTransport(handler),
    )

    assert client.get_observable('~1', context_type='alert', context_id='~2') == {
        '_id': '~1',
        'data': 'host1',
    }
