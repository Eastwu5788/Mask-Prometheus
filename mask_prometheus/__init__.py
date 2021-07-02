# !/usr/local/python/bin/python
# -*- coding: utf-8 -*-
# (C) Wu Dong, 2021
# All rights reserved
# @Author: 'Wu Dong <wudong@eastwu.cn>'
# @Time: '7/2/21 10:22 AM'
# sys
import functools
import time
import typing as t
from inspect import isgenerator
# 3p
import grpc
from grpc.experimental import wrap_server_method_handler
from prometheus_client import (
    Counter,
    Histogram,
    start_http_server,
)
# Check
if t.TYPE_CHECKING:
    from mask import Mask


__version__ = "1.0.0a1"


K_PROMETHEUS_HOST = "PROMETHEUS_HOST"
K_PROMETHEUS_PORT = "PROMETHEUS_PORT"


SERVER_STARTED_COUNTER = Counter(
    "mask_started_total",
    "Total number of RPCs started on the server.",
    ["grpc_type", "grpc_service", "grpc_method"]
)


SERVER_HANDLED_COUNTER = Counter(
    "mask_handled_total",
    "Total numbers of RPCs completed on the server, regardless of success or failure.",
    ["grpc_type", "grpc_service", "grpc_method", "grpc_code"]
)


SERVER_MSG_RECEIVED_TOTAL = Counter(
    "mask_msg_received_total",
    "Total number of RPC stream messages received on the server.",
    ["grpc_type", "grpc_service", "grpc_method"]
)


SERVER_MSG_SENT_TOTAL = Counter(
    "mask_msg_send_total",
    "Total number of RPC stream messages sent by the server.",
    ["grpc_type", "grpc_service", "grpc_method"]
)


SERVER_HANDLED_LATENCY_SECONDS = Histogram(
    "mask_handling_seconds",
    "Histogram of response latency (seconds) of gRPC that had been application-level handled by the server.",
    ["grpc_type", "grpc_service", "grpc_method"]
)


class Reporter:

    @staticmethod
    def _rpc_type(request_stream, response_stream):
        if not request_stream and not response_stream:
            return "unary"

        if request_stream and not response_stream:
            return "client_stream"

        if not request_stream and response_stream:
            return "server_stream"

        return "bidi_stream"

    def __init__(self, handler, details):
        """ Create new reporter
        """
        self.grpc_type = self._rpc_type(handler.request_streaming, handler.response_streaming)

        method = details.method.split("/")
        self.service = method[-2]
        self.method = method[-1]

        self.start_time = time.time()

        SERVER_STARTED_COUNTER.labels(
            grpc_type=self.grpc_type,
            grpc_service=self.service,
            grpc_method=self.method
        ).inc()

    def received_message(self):
        """ Count receive messages
        """
        SERVER_MSG_RECEIVED_TOTAL.labels(
            grpc_type=self.grpc_type,
            grpc_service=self.service,
            grpc_method=self.method
        ).inc()

    def sent_message(self):
        """ Count sent messages
        """
        SERVER_MSG_SENT_TOTAL.labels(
            grpc_type=self.grpc_type,
            grpc_service=self.service,
            grpc_method=self.method
        ).inc()

    def handled(self, code):
        """ Rpc handled count
        """
        SERVER_HANDLED_COUNTER.labels(
            grpc_type=self.grpc_type,
            grpc_service=self.service,
            grpc_method=self.method,
            grpc_code=code,
        ).inc()

        SERVER_HANDLED_LATENCY_SECONDS.labels(
            grpc_type=self.grpc_type,
            grpc_service=self.service,
            grpc_method=self.method,
        ).observe(time.time() - self.start_time)


class _RequestIterator:

    def __init__(self, request, reporter):
        self.reporter = reporter
        self.request = request

    def _next(self):
        resp = self.request.next()
        self.reporter.received_message()
        return resp

    def __iter__(self):
        return self

    def __next__(self):
        return self._next()

    def next(self):
        return self._next()


class _generator:

    def __init__(self, response, reporter):
        self.response = response
        self.reporter = reporter

    def __iter__(self):
        return self

    def __next__(self):
        rst = next(self.response)
        self.reporter.sent_message()
        return rst


class PrometheusInterceptor(grpc.ServerInterceptor):

    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None:
            return handler

        reporter = Reporter(handler, handler_call_details)

        def _wrapper(behavior):
            @functools.wraps(behavior)
            def wrapper(request, context):
                if isinstance(request, grpc._server._RequestIterator):
                    request = _RequestIterator(request, reporter)
                else:
                    reporter.received_message()
                code = grpc.StatusCode.UNKNOWN
                try:
                    resp = behavior(request, context)
                    code = context._state.code or grpc.StatusCode.OK
                    if isgenerator(resp):
                        resp = _generator(resp, reporter)
                    else:
                        reporter.sent_message()
                except Exception as e:
                    code = grpc.StatusCode.INTERNAL
                    raise e
                finally:
                    reporter.handled(code)
                return resp
            return wrapper
        return wrap_server_method_handler(_wrapper, handler)


class Prometheus:

    def __init__(
            self,
            app: t.Optional["Mask"] = None,
            config: t.Optional[t.Dict] = None,
            **kwargs
    ) -> None:
        """ Create prometheus instance for `Mask` instance
        """
        if not (config is None or isinstance(config, dict)):
            raise TypeError("'config' params must be type of dict")

        self.config = dict(config or dict(), **kwargs)
        self.app = app

        if self.app is not None:
            self.init_app(app, self.config)

    def init_app(self, app: "Mask", config: t.Optional[t.Dict] = None) -> None:
        """ Initialize mask instance with prometheus
        """
        # Load mask config
        cfg = app.config.copy()
        if self.config:
            cfg.update(self.config)
        if config:
            cfg.update(config)
        self.config = cfg

        app.register_interceptor(PrometheusInterceptor())
        start_http_server(port=self.config.get(K_PROMETHEUS_PORT, 18080),
                          addr=self.config.get(K_PROMETHEUS_HOST, ""))

        app.extensions["Prometheus"] = self
