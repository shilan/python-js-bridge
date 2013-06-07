"""
Currently implements zeroMQ sockets server side, which are mapped to javascript
websockets wrapped with SocketIO using tornado.
    * zeroMQ - A wrapper around sockets that handles a lot of messiness
               involved with network connections
    * socketIO - A wrapper around javascript websockets that handles the
                 differences in implementations across browser/OS combinations
    * tornado - A Python-based web framework that allows us to convert easily
                between the zeroMQ and socketIO wrappers.
It sounds complicated to use all of these libraries, but it makes this approach
more robust and surprisingly easier.
"""
import os
import traceback

import zmq
from zmq.eventloop import ioloop, zmqstream
ioloop.install()

import tornado
import tornado.web
import tornadio
import tornadio.router
import tornadio.server

import methods
from config import HTTP_PORT, TCP_PORT

# Subbing the port number into index.html means the config file works on the
# server and the client without additional work
with open("index.html") as index_file:
    index = index_file.read() % {"port": HTTP_PORT}


class IndexHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(index)


class ClientConnection(tornadio.SocketConnection):

    def on_message(self, message):
        """Evaluates the function pointed to by json-rpc."""
        error = None
        try:
            # The only available method is `count`, but I'm generalizing
            # to allow other methods without too much extra code
            result = getattr(methods,
                             message["method"])(**message["params"])
        except:
            # Errors are handled by enabling the `error` flag and returning a
            # stack trace. The client can do with it what it will.
            result = traceback.format_exc()
            error = 1
        self.send({"result": result, "error": error, "id": message["id"]})


WebClientRouter = tornadio.get_router(ClientConnection)

# This enables both websockets and the older flash protocol as a fallback
# for people somehow still not on HTML5. The flash backup will only work with
# root access, but it's not all that important to have it running.
ROOT = os.path.normpath(os.path.dirname(__file__))
handler = [(r"/", IndexHandler), WebClientRouter.route()]
kwargs = {"enabled_protocols": ["websocket", "flashsocket",
                                "xhr-multipart", "xhr-polling"],
          "flash_policy_port": 843,
          "flash_policy_file": os.path.join(ROOT, "flashpolicy.xml"),
          "static_path": os.path.join(ROOT, "static"),
          "socket_io_port": HTTP_PORT}
application = tornado.web.Application(handler, **kwargs)

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://127.0.0.1:%d" % TCP_PORT)
stream = zmqstream.ZMQStream(socket, tornado.ioloop.IOLoop.instance())
stream.on_recv(ClientConnection.on_message)
tornadio.server.SocketServer(application)
