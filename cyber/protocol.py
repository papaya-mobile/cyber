# -*- coding: utf-8 -*-


class Protocol(object):
    def __init__(self, *sub, **kw):
        pass

    def pack_data(self, data):
        raise NotImplementedError("Protocol.pack_data")

    def parse_data(self, data):
        raise NotImplementedError("Protocol.parse_data")

    def parse_serverid(self, data):
        raise NotImplementedError("Protocol.parse_serverid")

    def pack_serverid(self, server_id):
        raise NotImplementedError("Protocol.pack_serverid")
