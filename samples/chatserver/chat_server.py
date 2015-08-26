import random
import logging
import uuid
import os

from cyber import options
from cyber.server import Server, Client
from cyber.connection import broadcast_cmd
from cyber import server_logger, client_logger

def save_session(user_id, session_id, server_id):
    fn = "./session_%s"%user_id
    content = "\n".join([str(user_id), str(session_id), str(server_id)])
    with open(fn, "w") as f:
        f.write(content)

def read_session(user_id):
    fn = "./session_%s"%user_id
    if not os.path.isfile(fn):
        return None
    content = open(fn).read()
    return content.split("\n")

def delete_session(user_id):
    fn = "./session_%s"%user_id
    os.remove(fn)

def request_handler(client, request):
    request = request.split(',')
    cmd = request[0]
    if cmd == "login":
        login_handler(client, request)
    elif cmd == "send":
        chat_handler(client, request)
    else:
        client.send_command("DO NOT SUPPORT: %s"%cmd)

def login_handler(client, request):
    user_id = request[1]
    server = client.server
    server_id = server.server_id
    session_id = uuid.uuid4().hex
    print "user %s login to server %s bind session %s" %(user_id, server_id, session_id)

    # Assign client -> (session, user)
    client.sid = session_id
    client.uid = user_id
    server.keyed_clients[session_id] = client
    save_session(user_id, session_id, server_id)

    resp = "You have login to Server(%s), bind a Session(%s)" %(server_id, session_id)
    client.send_command(resp)

def chat_handler(client, request):
    fid = client.uid
    tid = request[1]
    msg = request[2]
    session = read_session(tid)
    if session is None:
        resp = "%s user does not exist"%tid
        print resp
        client.send_command(resp)
    else:
        resp =  'User (%s) says to you: "%s"'%(fid, msg)
        print 'User (%s) says "%s" to (%s)'%(fid, msg, tid)
        to_uid, to_sid, to_serverid = session
        server = client.server
        to_serverid = int(to_serverid)
        if to_serverid == server.server_id and to_sid in server.keyed_clients:
            server.keyed_clients[to_sid].send_command(resp)
        else:
            send_to_user(server, to_sid, to_serverid, resp)

def send_to_user(server, session_id, server_id, msg):
    broadcast_client = server.broadcast_client
    protocol = server.protocol
    if broadcast_client:
        msg = "%s,%s"%(session_id, msg)
        broadcast_cmd(broadcast_client, protocol, server_id, msg)

class ChatClient(Client):
    def on_close(self):
        delete_session(self.uid)

class ChatServer(Server):
    def __init__(self, protocol, client_cls):
        super(ChatServer, self).__init__(protocol=protocol, client_cls=client_cls)

    def impl(self, conf):
        self.server_id = conf.server_id
        self.port = conf.sock_port
        self.pool_size = conf.pool_size
        self.dead = False
        self.idle_time = conf.idle_time
        self.backlog = conf.backlog
        self.bc_host = conf.bc_host
        self.bc_port = conf.bc_port
        self.request_handler = request_handler

    def process_broadcast_events(self):
        # using "cid,cmd" format intead of default pack format [cid, cmd]
        for msg in self.broadcast_client.recv_events():
            cid, msg = msg.split(',', 1)
            server_logger.debug("[Key %s]Process cmd %s" % (cid, msg))
            try:
                if cid in self.keyed_clients:
                    self.keyed_clients[cid].send_command(msg)
            except Exception, e:
                server_logger.exception(e)

    def on_stop(self):
        pass
