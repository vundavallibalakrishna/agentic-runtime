# ruff: noqa
import asyncio
import http.client
import importlib
import smtplib
import socket
import urllib.request

import boto3
import httpx
import requests
from httpx import Client as C

Raw = httpx.Client


def a():
    return httpx.put("http://x")


def b():
    return httpx.patch("http://x")


def c():
    return requests.put("http://x")


def d():
    return requests.request("GET", "http://x")


def e():
    return urllib.request.urlopen("http://x")


def f():
    return http.client.HTTPConnection("x")


def g():
    return socket.create_connection(("x", 80))


async def h():
    return await asyncio.open_connection("x", 80)


def i():
    return importlib.import_module("httpx").Client()


def j():
    return httpx.Client()


def k():
    return Raw()


def l():
    return boto3.Session().client("s3")


def m():
    return boto3.resource("s3")


def n():
    return httpx.HTTPTransport()


def o():
    guard = None  # mention of a companion name only
    return httpx.Client()


def p():
    return smtplib.SMTP("x")


def q():
    return C()
