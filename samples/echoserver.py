import random
import logging

from cyber import options
from cyber.server import Server, Client
from cyber.protocol import Protocol
from cyber import server_logger, client_logger

def echo_handler(client, request):
    client.send_command(request)

class EchoProtocol(Protocol):
    def __init__(self, *sub, **kw):
        super(EchoProtocol, self).__init__(*sub, **kw)
    def pack_data(self, msg):
        data = "%s\n"%msg
        return data
    def parse_data(self, readbuffer):
        offset = readbuffer.find('\n')
        if offset == -1:
            return None
        request = readbuffer[:offset]
        return request.strip(), offset+1

class EchoClient(Client):
    def on_close(self):
        pass

class EchoServer(Server):
    def __init__(self, protocol, client_cls):
        super(EchoServer, self).__init__(protocol=protocol, client_cls=client_cls)

    def impl(self, conf):
        self.server_id = conf.server_id
        self.port = conf.sock_port
        self.pool_size = conf.pool_size
        self.dead = False
        self.idle_time = conf.idle_time
        self.backlog = conf.backlog
        self.request_handler = echo_handler

    def on_stop(self):
        pass

if __name__ == "__main__":
    options.server_id = random.randint(1, 100)
    options.sock_port = 1234
    options.pool_size = 20
    options.idle_time = 60
    options.backlog = 5

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    server_logger.setLevel(logging.INFO)
    client_logger.setLevel(logging.INFO)
    server_logger.addHandler(ch)
    client_logger.addHandler(ch)

    echo_server = EchoServer(EchoProtocol(), EchoClient)
    echo_server.impl(options)
    echo_server.run()
