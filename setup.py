# !/usr/local/python/bin/python
# -*- coding: utf-8 -*-
# (C) Wu Dong, 2021
# All rights reserved
# @Author: 'Wu Dong <wudong@eastwu.cn>'
# @Time: '7/2/21 10:21 AM'
# sys
from setuptools import setup


setup(
    name="Mask-Prometheus",
    install_requires=[
        "Mask>=1.0.0a1",
        "Prometheus-client>=0.11.0"
    ]
)
