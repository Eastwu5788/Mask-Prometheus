# !/usr/local/python/bin/python
# -*- coding: utf-8 -*-
# (C) Wu Dong, 2021
# All rights reserved
# @Author: 'Wu Dong <wudong@eastwu.cn>'
# @Time: '7/2/21 3:09 PM'
# 3p
from mask import Mask
from mask_prometheus import Prometheus
# project
from examples.protos.hello_pb2 import HelloResponse


app = Mask(__name__)
app.config["REFLECTION"] = True
app.config["DEBUG"] = True

app.config["PROMETHEUS_PORT"] = 18080

prometheus = Prometheus()
prometheus.init_app(app)


@app.route(method="SayHello", service="Hello")
def say_hello_handler(request, context):
    """ Handler SayHello request
    """
    return HelloResponse(message="Hello Reply: %s" % request.name)


@app.route(method="SayHelloStream", service="Hello")
def say_hello_stream_handler(request, context):
    """ Handler stream SayHello request
    """
    message = ""
    for item in request:
        message += item.name
        yield HelloResponse(message="Hello Reply: %s" % item.name)
    # return HelloResponse(message="Hello Reply: %s" % message)


if __name__ == "__main__":
    app.run(port=1020)
