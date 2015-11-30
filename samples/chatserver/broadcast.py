import logging
from cyber import broadcast_logger


def run(port):
    from cyber.broadcast import start_broadcast
    from chat_protocol import ChatProtocol
    protocol = ChatProtocol(2, ">H")
    start_broadcast(port, 20, protocol)


if __name__ == '__main__':
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    broadcast_logger.setLevel(logging.DEBUG)
    broadcast_logger.addHandler(ch)
    run(8888)
