import asyncore
import socket
import threading
import resource

from .log import server_logger

try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (50000, 50000))
except Exception, e:
    pass

MAX_PACKAGE_LENGTH = 256 * 1024  # 256 KB


class SocketHandler(asyncore.dispatcher):
    def __init__(self, sock, addr):
        asyncore.dispatcher.__init__(self, sock=sock)
        self.addr = addr
        self.writelock = threading.Lock()
        self._buffer = ''
        self._recvbuffer = ''
        self.client = None

    def send_data(self, data):
        with self.writelock:
            self._buffer += data

    def read_data(self):
        # read available datas
        try:
            data = self.recv(128 * 1024)
            self._recvbuffer += data
        except Exception, e:
            if str(e).find('Resource temporarily unavailable') != -1:
                pass
            else:
                self.handle_close('Read Error')

    def handle_read(self):
        self.read_data()
        if self.client:
            self.client.handle_data(self._recvbuffer)
        self._recvbuffer = ''

    def writable(self):
        return len(self._buffer) > 0

    def handle_write(self):
        with self.writelock:
            if self._buffer:
                try:
                    sent = self.send(self._buffer)
                    self._buffer = self._buffer[sent:]
                except socket.error, e:
                    self.handle_close('Error send data')

    def handle_expt(self):
        self.handle_close()

    def handle_close(self, msg='connection closed'):
        try:
            if self.client:
                self.client.handle_close(msg)
            self.close()
        except Exception, e:
            server_logger.exception(e)


class SocketServer(asyncore.dispatcher):
    def __init__(self, port, backlog, server):
        asyncore.dispatcher.__init__(self)
        self._port, self._server = port, server
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', port))
        self.listen(backlog)
        server_logger.info("SocketServer listen on port %s (backlog: %s)" %
                           (port, backlog))

    def handle_accept(self):
        try:
            accept = self.accept()
            if accept:
                conn, addr = accept
                handler = SocketHandler(conn, addr)
                self._server.new_client(handler)
        except Exception, e:
            server_logger.exception(e)

    def handle_close(self):
        try:
            server_logger.info('Close Socket Server')
            self.close()
        except Exception, e:
            server_logger.exception(e)


class BroadcastClient(asyncore.dispatcher):
    def __init__(self, host, port, server_id, protocol, server=None):
        self._read_buffer = ''
        self._write_buffer = ''
        self._length = None
        self._protocol = protocol
        self._server = server
        self._server_id = server_id
        self._writelock = threading.Lock()
        self._closelock = threading.Lock()
        self._recved_msgs = []
        # send server_id to broadcast server first
        self._write_buffer = self._protocol.pack_serverid(server_id)
        self.opened = True

        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host, self.port = host, port
        self.connect((host, port))

    def send_event(self, data):
        with self._writelock:
            self._write_buffer += data

    def recv_events(self):
        ret = self._recved_msgs
        self._recved_msgs = []
        return ret

    def handle_connect(self):
        pass

    def handle_expt(self):
        self.handle_close()

    def handle_close(self):
        with self._closelock:
            if self.opened:
                self.opened = False
                threading.Timer(2,
                                _delayreconnect,
                                args=(self.host, self.port, self._server_id,
                                      self._protocol),
                                kwargs={'server': self._server}).start()
                self.close()

    def writable(self):
        return self._write_buffer

    def readable(self):
        return True

    def handle_write(self):
        with self._writelock:
            if self._write_buffer:
                try:
                    sent = self.send(self._write_buffer)
                    self._write_buffer = self._write_buffer[sent:]
                except:
                    self.handle_close()

    def handle_read(self):
        '''
        Get potp decoded event.
        (sid, req) is format of received event.
        '''
        try:
            data = self.recv(8192)
            self._read_buffer += data
        except Exception, e:
            if str(e).find('Resource temporarily unavailable') != -1:
                pass
            else:
                self.handle_close()
                return
        self.parse_data()

    def parse_data(self):
        while self._read_buffer:
            ret = self._protocol.parse_data(self._read_buffer)
            if ret is None:
                break
            data, offset = ret
            self._read_buffer = self._read_buffer[offset:]
            self._recved_msgs.append(data)


def _delayreconnect(host, port, server_id, protocol, server):
    client = BroadcastClient(host, port, server_id, protocol)
    # replace the "broadcast_client" of server with new BroadcastClient
    server.broadcast_client = client


def broadcast_cmd(broadcast_client, protocol, server_id, msg):
    packed_serverid = protocol.pack_serverid(server_id)
    packed_data = protocol.pack_data(msg)
    broadcast_client.send_event(packed_serverid + packed_data)
