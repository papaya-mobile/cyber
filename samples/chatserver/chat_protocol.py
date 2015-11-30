import struct
import json

from cyber.protocol import Protocol


class ChatProtocol(Protocol):
    def __init__(self, sidlen, sidhead_format):
        super(ChatProtocol, self).__init__()
        self.sidhead = struct.Struct(sidhead_format)
        self.sidlen = sidlen

    def parse_serverid(self, data):
        if len(data) >= self.sidlen:
            server_id, = self.sidhead.unpack_from(data, 0)
            return server_id, self.sidlen
        else:
            return None

    def pack_serverid(self, server_id):
        return self.sidhead.pack(server_id)

    def parse_data(self, data):
        offset = data.find('\n')
        if offset == -1:
            return None
        request = data[:offset]
        return request.strip(), offset + 1

    def pack_data(self, msg):
        data = "%s\n" % msg
        return data
