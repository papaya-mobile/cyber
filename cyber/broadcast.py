import asyncore
import socket
import resource

from .protocol import Protocol
from .log import broadcast_logger

try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (50000, 50000))
except Exception, e:
    pass

MAX_PACKAGE_LENGTH = 1024 * 1024  # 1 Mb


class ListenClient(asyncore.dispatcher):
    def __init__(self, sock, addr, protocol, server):
        broadcast_logger.info("Got connection")

        asyncore.dispatcher.__init__(self, sock=sock)
        self._addr = addr
        self._sock_server = server
        self._protocol = protocol
        self._buffer = ''
        self._recvbuffer = ''
        self._target = None
        self._length = None
        self._myid = None
        self._init = False

    def get_myid(self):
        if not self._init and self._recvbuffer:
            server_id = self._protocol.parse_serverid(self._recvbuffer)
            if server_id is None:
                return
            self._myid, offset = server_id
            self._recvbuffer = self._recvbuffer[offset:]
            if self._myid > 0:
                # server_id == 0 is only a client
                self._sock_server.clients[self._myid] = self
            broadcast_logger.debug("ACPT new conn from %s, SERVER(%s)" %
                                   (self._myid, self._sock_server.clients))
            self._init = True

    def handle_read(self):
        try:
            data = self.recv(128 * 1024)
            self._recvbuffer += data
        except Exception, e:
            if str(e).find('Resource temporarily unavailable') != -1:
                pass
            else:
                broadcast_logger.exception(e)
                self.handle_close()
                return

        # init server_it first
        self.get_myid()
        if not self._init:
            return

        self.transfer()

    def transfer(self):
        while self._recvbuffer:
            if self._target is None:
                server_id = self._protocol.parse_serverid(self._recvbuffer)
                if server_id is None:
                    break
                self._target, offset = server_id
                self._recvbuffer = self._recvbuffer[offset:]
                if self._target <= 0:
                    # Close connection gently
                    broadcast_logger.debug("wrong target(%s)" % (self._target))
                    self._target = None
                    self.handle_close()
                    return
            else:
                ret = self._protocol.parse_data(self._recvbuffer)
                if ret is None:
                    break
                data, offset = ret
                self._recvbuffer = self._recvbuffer[offset:]
                packed_data = self._protocol.pack_data(data)
                self._sock_server.send_to(self._target, packed_data)
                self._target = None

    def send_data(self, data):
        self._buffer += data

    def readable(self):
        return True

    def writable(self):
        return len(self._buffer) > 0

    def handle_write(self):
        if self._buffer:
            try:
                sent = self.send(self._buffer)
                self._buffer = self._buffer[sent:]
            except Exception:
                broadcast_logger.exception('ListenClient.handle_write')
                self.handle_close()

    def handle_expt(self):
        self.handle_close()

    def handle_close(self):
        try:
            if self._myid in self._sock_server.clients:
                self._sock_server.clients.pop(self._myid)
        except Exception:
            broadcast_logger.exception('ListenClient.handle_close')

        try:
            self.close()
        except Exception:
            broadcast_logger.exception('ListenClient.handle_close')


class ListenServer(asyncore.dispatcher):
    def __init__(self, port, backlog, protocol):
        asyncore.dispatcher.__init__(self)
        self._port, self._backlog = port, backlog
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(("", port))
        self.listen(backlog)
        self.clients = {}
        assert (isinstance(protocol, Protocol))
        self.protocol = protocol

    def send_to(self, server_id, data):
        broadcast_logger.debug("Send %s to %s" % (data, server_id))
        if server_id in self.clients:
            self.clients[server_id].send_data(data)

    def handle_accept(self):
        try:
            conn, addr = self.accept()
            ListenClient(conn, addr, self.protocol, self)
        except Exception, e:
            broadcast_logger.exception(e)

    def handle_close(self):
        broadcast_logger.debug("SERVER CLOSE")
        try:
            self.close()
        except Exception, e:
            broadcast_logger.exception(e)


def start_broadcast(port, backlog, protocol):
    broadcast_logger.inof("start broadcast server listen %s" % port)
    ListenServer(port, backlog, protocol)
    asyncore.loop(use_poll=True)
