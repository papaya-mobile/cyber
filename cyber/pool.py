# -*- coding: utf-8 -*-
import threading
import time
import logging
import random
import collections

from .log import server_logger
from .config import DEFAULT_POOL_SIZE

class HandleThread(threading.Thread):
    total = 0

    def __init__(self, request_handler):
        super(HandleThread, self).__init__()
        self.setDaemon(True)
        HandleThread.total += 1
        self.cnt = self.total
        self.act = 0  # timmstamp of start of request
        self.client = self.req = None

        self.request_handler = request_handler

        self.queue = collections.deque()
        self.a = threading.Lock()
        self.b = threading.Lock()
        self.w = False  # whether the queue is empty

    def qsize(self):
        with self.a:
            return len(self.queue)

    def put_nowait(self, item):
        '''
        Put a request into the queue.
        '''
        with self.a:
            self.queue.append(item)
            if self.w:
                self.w = False
                self.b.release()

    def get(self):
        '''
        Get a task from queue.
        Note that if the two locks self.a and self.b
        prevent the queue from empty queue exception.
        If queue is empty, the .get() method will stay
        in the locked state of acquiring self.b.
        '''
        with self.a:
            if not self.queue:
                self.w = True
                with self.b:
                    self.a.release()
                    self.b.acquire()
                    self.a.acquire()
            ret = self.queue.popleft()
        return ret

    def run(self):
        try:
            while True:
                request = self.get()
                request_type = request[0]

                self.act = time.time()
                self.client = self.req = None
                try:
                    if request_type == 0:
                        client, req = request[1:]
                        self.client, self.req = client, req
                        self.request_handler(client, req)
                    elif request_type == 1:
                        func, args, kwargs = request[1:]
                        func(*args, **kwargs)
                    else:
                        raise Exception("Unknown request_type %s." % request_type)
                except Exception, e:
                    server_logger.exception(e)
                finally:
                    self.act = 0
                    pass
        except Exception, e:
            server_logger.exception(e)


class HandleThreadsPool(object):
    def __init__(self, request_handler, pool_size=DEFAULT_POOL_SIZE):
        self.request_handler = request_handler
        self.pool_size = pool_size
        self.handle_threads = []
        for i in range(self.pool_size):
            ht = HandleThread(self.request_handler)
            ht.start()
            self.handle_threads.append(ht)

    def get_handle_thread(self, cid=None):
        if cid:
            ti = (cid / 3) % self.pool_size
            return self.handle_threads[ti]
        else:
            return random.choice(self.handle_threads)

    def put_nowait(self, req, cid=None):
        ht = self.get_handle_thread(cid)
        ht.put_nowait(req)
