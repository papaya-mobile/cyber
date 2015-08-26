import logging

from cyber import options
from chat_protocol import ChatProtocol
from chat_server import ChatServer, ChatClient
from cyber import server_logger, client_logger

if __name__ == '__main__':
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    server_logger.setLevel(logging.DEBUG)
    client_logger.setLevel(logging.DEBUG)
    server_logger.addHandler(ch)
    client_logger.addHandler(ch)
    options.load_yaml("chat1.yaml")
    protocol = ChatProtocol(2, ">H")
    chat_server = ChatServer(protocol, ChatClient)
    chat_server.impl(options)
    chat_server.run()
