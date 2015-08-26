import weakref
import time
import threading
import asyncore
import datetime

from .connection import SocketServer, SocketHandler, BroadcastClient
from .pool import HandleThreadsPool
from .log import server_logger, client_logger
from .protocol import Protocol

class Client(object):
    def __init__(self, handler, protocol, server):
        '''
        :param connecter: The connection object of the client.
        :param server: The potp server object.
        '''
        handler.client = self
        self.addr = handler.addr
        self.handler = handler
        self.server = server
        self._id = None
        self._closing = False
        self._protocol = protocol

        self.inittime = self._last_action_time = time.time()
        self._lock = threading.Lock()

        self._recvbuffer = ''
        self._sent_bytes = 0
        
        self.sid = None
        self.uid = None

    def _id_get(self):
        return self._id or id(self)

    def _id_set(self, value):
        self._id = value

    id = property(_id_get, _id_set)

    def handle_data(self, data):
        self._recvbuffer += data
        while self._recvbuffer:
            ret = self._protocol.parse_data(self._recvbuffer)
            if ret is None:
                break
            req, offset = ret
            self._recvbuffer = self._recvbuffer[offset:]
            self.add_request(req)

    def add_request(self, req):
        client_logger.debug("[Client %s] Add new request %s." % (self.id, req))
        try:
            if req is '':
                # send it immediately
                self.send_command('')
            else:
                # handler request in thread
                self.server.pool.put_nowait((0, self, req), cid=self.id)
        except Exception, e:
            client_logger.exception(e)
        self._last_action_time = time.time()

    def send_command(self, cmd):
        client_logger.debug("[Client %s] Send command %s." % (self.id, cmd))
        self.send_response(cmd)

    def send_response(self, response):
        data = self._protocol.pack_data(response)
        if data is not None and self.handler:
            self.handler.send_data(data)

    def handle_close(self, msg=''):
        with self._lock:
            if not self._closing:
                self._closing = True
            else:
                return
        client_logger.debug("[Client %s] Closing '%s'" % (self.id, msg))
        self.server.pool.put_nowait((1, self.close, [], {}), cid=self.id)

    def close(self):
        '''
        Close the connector, remove itself
        from the server.
        '''
        try:
            self.on_close()
        except Exception, e:
            client_logger.exception(e)
        try:
            handler = self.handler
            self.handler = None
            if handler:
                handler.client = None
                handler.close()
        except Exception, e:
            client_logger.exception(e)
        self.server.remove_client(self)
        self.server = None

    def on_close(self):
        raise NotImplementedError("Client.on_close")

    def check_timeout(self):
        idle = time.time() - self._last_action_time

        if idle > self.server.idle_time:
            client_logger.debug("[Client %s] Idled over %s seconds, kicked." %(self.id, idle))
            self.handle_close()
            return True

        return False

class Server(object):
    server = None

    def __init__(self, protocol, client_cls=None, **kw):
        ''''''
        self.clients = []
        self.keyed_clients = weakref.WeakValueDictionary()
        self.client_lock = threading.Lock()
        self.dead = False
        self.broadcast_client = None
        self.socket_server = None
        self.pool = None
        self.request_handler = None
        self.bc_host = None
        self.bc_port = None
        assert(isinstance(protocol, Protocol))
        self.protocol = protocol
        if client_cls is None:
            self.client_cls = Client
        else:
            assert(issubclass(client_cls, Client))
            self.client_cls = client_cls

    def impl(self, *sub, **kw):
        # configable
        raise NotImplementedError("Server.impl")

    def initialize(self):
        assert(self.server_id>0 and self.server_id<65536)
        assert(callable(self.request_handler))
        self.socket_server = SocketServer(self.port, self.backlog, self)
        self.pool = HandleThreadsPool(self.request_handler, self.pool_size)
        if self.bc_host and self.bc_port:
            self.broadcast_client = BroadcastClient(self.bc_host, self.bc_port, self.server_id, self.protocol, self)

    def on_stop(self):
        raise NotImplementedError("Server.on_stop")

    def run(self):
        self._start_time = time.time()

        # Init server
        self.initialize()

        # Begin loop
        self.start_loop()

        # Stop server
        self.on_stop()
        self.close_server()

    def info(self):
        server_logger.info("Listening port %s" % self.port)
        server_logger.info("Server server_id: %s" % self.server_id)

    def process_broadcast_events(self):
        # By default, event is packed as [cid, cmd]
        # you may overload this method to other protocol
        for cid, cmd in self.broadcast_client.recv_events():
            server_logger.debug("[Key %s]Process cmd %s" % (cid, cmd))
            try:
                if cid in self.keyed_clients:
                    self.keyed_clients[cid].send_command(cmd)
            except Exception, e:
                server_logger.exception(e)

    def start_loop(self):
        self.info()
        err_cnt = 0
        lastt = time.time()
        while (not self.dead) or self.clients:
            # 1. Handle broadcast msg
            if self.broadcast_client:
                self.process_broadcast_events()

            # 2. checkout zombie clients
            for u in self.clients[:]:
                u.check_timeout()

            # 3. main asyncore loop
            try:
                asyncore.loop(0.025, True, None, 2)
                err_cnt = 0
            except AttributeError, e:
                server_logger.exception(e)
                err_cnt += 1
                if err_cnt > 10:
                    break
            except KeyboardInterrupt, e:
                server_logger.exception(e)
                if self.dead_mode():
                    break
            except Exception, e:
                # normally, this shouldn't happen
                server_logger.exception(e)

    def close_server(self):
        for c in self.clients:
            c.handle_close()
        if self.broadcast_client:
            self.broadcast_client.close()

    def dead_mode(self):
        server_logger.info("Enter Dead Server Mode...")
        old_state = self.dead
        self.dead = True
        self.socket_server.handle_close()
        return old_state

    def new_client(self, handler):
        self.clients.append(self.client_cls(handler, self.protocol, self))

    def remove_client(self, client):
        with self.client_lock:
            if client in self.clients:
                self.clients.remove(client)
