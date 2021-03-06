# Cyber - A distributed asynchronous socket framework of Python

Cyber is a distributed async socket framework based on Python asyncore.dispatcher.

### Installation

Install Kiwi from source:

    $ git clone https://github.com/papaya-mobile/cyber.git
    $ cd cyber
    $ python setup.py install

### Basic usage

To use this framework, you need to inherit Server, Client. And define your own protocol for communication.

### Samples

#### EchoServer

First let's define the echo protocol:

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

The socket read_buffer will be pass to method `parse_data`, which will unpack one package from buffer. The method is suppose to return a tuple (package, offset), in which `package` is the unpacked package and `offset` identify the offset of unparsed buffer. `pack_data` is used to pack source to protocol package.

Then we need to define our own `EchoClient`:

    class EchoClient(Client):
        def on_close(self):
            pass

Since nothing need to be handled before close a connection, so we can just pass it. `echo_handler` is the main handler of server.

    def echo_handler(client, request):
        client.send_command(request)

The `echo_handler` have two parameters. `client` is the connection client, who have a method `send_command` to send data to remote client.

At last we need to implement an `EchoServer`:

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

To init a Cyber server need two arguments, first is the protocol instance, second is the client class. And the `impl` method is for setup server env. `server_id` id the unique id of server. `port` is the server listen port. `backlog` it the parameter of socket backlog. The Cyber is using multi threading handle request, so `pool_size` is the size of threading pool. `idel_time` identify how many seconds a client will be kicked. And `request_handler` is the function handle request from client.

After all, we can start echo server very easily:

    options.server_id = random.randint(1, 100)
    options.sock_port = 1234
    options.pool_size = 20
    options.idle_time = 60
    options.backlog = 5
    echo_server = EchoServer(EchoProtocol(), EchoClient)
    echo_server.impl(options)
    echo_server.run()

#### ChatServer

ChatServer is a distribute chat server. The source is under ./samples/chatserver/.

As this ChatServer support multi server, to handle communication between servers, we need a broadcast server, which defined in broadcast.py. We also write to server listen separate port defined in chat1.yaml and chat2.yaml. To start the ChatServer first we need to start broadcast server:

    $ python broadcast.py 
    start broadcast server listen 8888

Then starting to server:

    $ python server1.py 
    SocketServer listen on port 1234 (backlog: 20)
    Listening port 1234
    Server server_id: 1

    $ python server2.py 
    SocketServer listen on port 1235 (backlog: 20)
    Listening port 1235
    Server server_id: 2

After these step we can test it:

In `screen 1` , we telnet chat server1:

    $ telnet 127.0.0.1 1234
    Trying 127.0.0.1...
    Connected to 127.0.0.1.
    Escape character is '^]'.

First, user need to login server with a user name, then user can send message to himself:

    login,Calvin
    You have login to Server(1), bind a Session(1109166156cb4463b3ad950dec045e7c)
    send,Calvin,hello calvin
    User (Calvin) says to you: "hello calvin"

In `Screen 2`, user yan connect - login to server1 and say 'hi' to Calvin:

    $ telnet 127.0.0.1 1234
    Trying 127.0.0.1...
    Connected to 127.0.0.1.
    Escape character is '^]'.
    login,Yan
    You have login to Server(1), bind a Session(7e39cacb576a44be949d6d2fa19277c2)
    send,Calvin,hi

In `Screen 1` Calvin will receive the message from Yan:

    User (Yan) says to you: "hi"

In `Screen 3`, user rocky connect - login to server2, and say 'hello' to Calvinand Yan:

    $ telnet 127.0.0.1 1235
    Trying 127.0.0.1...
    Connected to 127.0.0.1.
    Escape character is '^]'.
    login,Rocky
    You have login to Server(2), bind a Session(c17a3671c9d54a67894787480f281622)
    send,Yan,hello Yan
    send,Calvin,hello Calvin

Then user Calvin and Yan will receive hello from Rocky in their own screen:

    User (Rocky) says to you: "hello Calvin"

    User (Rocky) says to you: "hello Yan"

