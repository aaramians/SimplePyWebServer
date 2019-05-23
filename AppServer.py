import socket
import hashlib
import mimetypes
import base64
import time
import logging

from threading import Thread
from termcolor import colored

# no support for ssl/wss
# no limit on file service

# https://github.com/enthought/Python-2.7.3/blob/master/Lib/SimpleHTTPServer.py
# https://github.com/enthought/Python-2.7.3/blob/master/Lib/SimpleHTTPServer.py
# https://blog.anvileight.com/posts/simple-python-http-server/
# https://gist.github.com/bradmontgomery/2219997
# https://github.com/enthought/Python-2.7.3/blob/master/Lib/BaseHTTPServer.py
# https://www.afternerd.com/blog/python-http-server/
# https://www.acmesystems.it/python_http
# https://github.com/pikhovkin/simple-websocket-server/blob/master/simple_websocket_server/__init__.py


# if not mimetypes.inited:
#     mimetypes.init()
# extensions_map = mimetypes.types_map.copy()



__responses = {
    100: ('Continue', 'Request received, please continue'),
    101: ('Switching Protocols',
          'Switching to new protocol; obey Upgrade header'),

    200: ('OK', 'Request fulfilled, document follows'),
    201: ('Created', 'Document created, URL follows'),
    202: ('Accepted',
          'Request accepted, processing continues off-line'),
    203: ('Non-Authoritative Information', 'Request fulfilled from cache'),
    204: ('No Content', 'Request fulfilled, nothing follows'),
    205: ('Reset Content', 'Clear input form for further input.'),
    206: ('Partial Content', 'Partial content follows.'),

    300: ('Multiple Choices',
          'Object has several resources -- see URI list'),
    301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
    302: ('Found', 'Object moved temporarily -- see URI list'),
    303: ('See Other', 'Object moved -- see Method and URL list'),
    304: ('Not Modified',
          'Document has not changed since given time'),
    305: ('Use Proxy',
          'You must use proxy specified in Location to access this '
          'resource.'),
    307: ('Temporary Redirect',
          'Object moved temporarily -- see URI list'),

    400: ('Bad Request',
          'Bad request syntax or unsupported method'),
    401: ('Unauthorized',
          'No permission -- see authorization schemes'),
    402: ('Payment Required',
          'No payment -- see charging schemes'),
    403: ('Forbidden',
          'Request forbidden -- authorization will not help'),
    404: ('Not Found', 'Nothing matches the given URI'),
    405: ('Method Not Allowed',
          'Specified method is invalid for this resource.'),
    406: ('Not Acceptable', 'URI not available in preferred format.'),
    407: ('Proxy Authentication Required', 'You must authenticate with '
          'this proxy before proceeding.'),
    408: ('Request Timeout', 'Request timed out; try again later.'),
    409: ('Conflict', 'Request conflict.'),
    410: ('Gone',
          'URI no longer exists and has been permanently removed.'),
    411: ('Length Required', 'Client must specify Content-Length.'),
    412: ('Precondition Failed', 'Precondition in headers is false.'),
    413: ('Request Entity Too Large', 'Entity is too large.'),
    414: ('Request-URI Too Long', 'URI is too long.'),
    415: ('Unsupported Media Type', 'Entity body in unsupported format.'),
    416: ('Requested Range Not Satisfiable',
          'Cannot satisfy request range.'),
    417: ('Expectation Failed',
          'Expect condition could not be satisfied.'),

    500: ('Internal Server Error', 'Server got itself in trouble'),
    501: ('Not Implemented',
          'Server does not support this operation'),
    502: ('Bad Gateway', 'Invalid responses from another server/proxy.'),
    503: ('Service Unavailable',
          'The server cannot process the request due to a high load'),
    504: ('Gateway Timeout',
          'The gateway server did not receive a timely response'),
    505: ('HTTP Version Not Supported', 'Cannot fulfill request.'),
}

# class FileTemplate(Template):
#     def __init__(self, file):
#         pass

class ServiceHandlerThread(Thread):

    def __init__(self, csocket, caddress, server):
        Thread.__init__(self)
        self.csocket = csocket
        self.caddress = caddress
        self.mime = None
        self.path = None
        self.SecWebSocketKey = None
        self.content = None
        self.server = server
        self.__MAGICSTRING = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

    def parse(self):
        self.command, self.route, self.version = None, None, None

        self.lines = self.request.decode().split('\r\n')
        logging.debug(self.lines[0])
        words = self.lines[0].split()
        
        # todo move the logic to run and to Endpoints
        if len(words) == 3:
            self.command, self.route, self.version = words
        elif len(words) == 2:
            self.command, self.route = words

        self.endpoint = self.server.endpoints['*']
        self.endpointtype = AppServer.WebStaticEndpoint

        if self.route != None and self.route in self.server.endpoints:
            self.endpoint = self.server.endpoints[self.route]
            self.endpointtype = type(self.endpoint)


    def run(self):
        try:
            self.request = self.csocket.recv(4096)

            if len(self.request) > 4000:
                raise NotImplementedError

            self.parse()

            if self.endpointtype == AppServer.WebSocketEndpoint:
                key = [s for s in self.lines if "Sec-WebSocket-Key" in s]
                if len(key) == 1:
                    skey = key[0].split(':')[1].strip()
                    stoken = skey + self.__MAGICSTRING
                    stokensha1 = hashlib.sha1(stoken.encode('utf-8'))
                    self.SecWebSocketAccept = base64.b64encode(stokensha1.digest())
                    self.csocket.send(b'HTTP/1.1 101 Switching Protocols\r\n')
                    self.csocket.send(b'Upgrade: websocket\r\n')
                    self.csocket.send(b'Connection: Upgrade\r\n')
                    self.csocket.send(b'Sec-WebSocket-Accept: ' + self.SecWebSocketAccept +  b'\r\n')
            else:
                self.csocket.send(b'HTTP/1.1 200 OK\r\n')

            if (self.mime != None):
                self.csocket.send(b'Content-Type: ' + bytes(self.mime, "ascii") + b'\r\n')
                    
            if self.endpointtype != AppServer.WebSocketEndpoint:
                self.csocket.send(b'Connection: Closed\r\n')

            self.csocket.send(b'\r\n')

            if self.endpointtype == AppServer.WebServiceEndpoint:
                pl = self.lines[len(self.lines) -1]
                args2 = dict(item.split("=") for item in pl.split("&"))
                # urlparse.parse_qs("Name1=Value1;Name2=Value2;Name3=Value3")
                method = self.endpoint.callback
                self.content = method(**args2)

            if self.endpointtype == AppServer.WebStaticEndpoint:
                if self.endpoint.route == None:
                    pass
                elif self.route.endswith(".html"):
                    self.mime = 'text/html'
                elif self.route.endswith(".ico"):
                    self.mime = 'image/x-icon'
                elif self.route.endswith(".css"):
                    self.mime = 'text/css'
                elif self.route.endswith(".js"):
                    self.mime = 'application/javascript'
                elif self.route.endswith(".mp4"):
                    self.mime = 'video/mp4'

                if self.mime != None:
                    f = open(self.endpoint.path + self.route, 'rb')
                    self.content = f.read()
                    f.close()
                                    
            if self.content != None:
                self.csocket.send(self.content)

            if self.endpointtype == AppServer.WebSocketEndpoint:
                self.endpoint.WebSocketReady(self.csocket)

            self.csocket.close()

        except Exception as ex:
            logging.critical(ex)
            self.csocket.close()


class AppServer(Thread):
    class Endpoint():
        def __init__(self, route, callback):
            self.route = route
            self.callback = callback

    class WebStaticEndpoint(Endpoint):
        def __init__(self, path):
            self.route = '*'
            self.path = path

    class ServerSentEventEndpoint(Endpoint):
        def __init__(self, route, callback):
            raise NotImplementedError

    class WebServiceEndpoint(Endpoint):
        def __init__(self, route, callback):
            self.route = route
            self.callback = callback

    class WebSocketEndpoint(Endpoint):
        def __init__(self, route, callback):
            self.route = route
            self.callback = callback
            self.lastwebsocket = None #todo session

        def Receive(self, request):
            fin = request[0] & 0x80 == 128
            opcode = request[0] & (0xF)
            Mask = request[1] & 0x80 == 128
            
            payload = bytearray()
            plMask = None
            plFlag = request[1] & 0x7F
            plLen = 0
            plStart = 0

            if plFlag < 126:
                plLen = plFlag
                plStart = 2
                if Mask:
                    plMask = [request[2] , request[3] , request[4] ,request[5]]
                    plStart = 2 + 4

            elif plFlag == 126:
                plLen = (request[2] << 8) + request[3]
                plStart = 4
                if Mask:
                    plMask = [request[4] , request[5] , request[6] ,request[7]]
                    plStart = 4 + 4

            elif plFlag == 127:
                plLen = (request[2] << 24) + (request[3] << 16) + (request[4] << 8) + request[5]
                plStart = 6
                if Mask:
                    plMask = [request[6] , request[7] , request[8] ,request[9]]
                    plStart = 6 + 4

            i = 0
            for b in request[plStart:]:
                if Mask:
                    payload.append(b ^ plMask[i % 4])
                else:
                    payload.append(b)
                i = i + 1
                plLen = plLen - 1
            return payload

        def Send(self, socket, payload):
            pllen = len(payload)
            plbytes = bytearray()
            b1,b2 = 0, 0
            opcode = 0x1
            fin = 1
            b1 = opcode | fin << 7

            if pllen < 125:
                b2 |= pllen
            elif pllen > 124:
                raise NotImplementedError

            plbytes.append(b1)
            plbytes.append(b2)
            plbytes.extend(bytes(payload, "utf-8"))
            socket.send(plbytes)
      
        def WebSocketReady(self, socket):
            self.lastwebsocket = socket
            while 1:
                r = socket.recv(4096)
                if len(r) > 3:
                    self.callback(self.Receive(r))

    def __init__(self, ip, port):
        Thread.__init__(self)
        self.endpoints = {}
        self.ip = ip
        self.port = port

    def RegisterEndpoint(self, endpoint):
        logging.debug('registering endpoint ' + endpoint.route)
        self.endpoints[endpoint.route] = endpoint

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.ip, self.port))
        server.listen(5)  # max backlog of connections
        logging.info('listening on ' + self.ip + ':' + str(self.port))
        while 1:
            try:
                csocket, caddress = server.accept()
                logging.debug('connect ' + ':'.join(str(x) for x in caddress))
                ServiceHandlerThread(csocket, caddress, self).start()

            except KeyboardInterrupt:
                logging.debug('closing connection')
                server.shutdown(socket.SHUT_RD)
                server.close()
                break

            except Exception as ex:
                logging.critical(ex)
                server.close()
                break

def TestSocket(payload):
    logging.debug('socket test ' + payload.decode("ascii") )

def TestAjax(path):
    logging.debug('ajax test ' + path)
    return b'response'

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - [%(levelname)-5.5s] - %(message)s')
    from os import path as ospath
    contentspath = ospath.dirname(ospath.abspath( __file__ )) + '/contents'
    logging.debug('contents path' + contentspath)
    app = AppServer('localhost', 65130)

    wse = AppServer.WebSocketEndpoint('/Socket', TestSocket)

    app.RegisterEndpoint(AppServer.WebServiceEndpoint('/TestAjax', TestAjax))
    app.RegisterEndpoint(wse)

    app.RegisterEndpoint(AppServer.WebStaticEndpoint(contentspath))
    app.start()
    time.sleep(1)
    logging.debug('http://' + app.ip + ':' + str(app.port) + '/index.html')
    while 1:
        time.sleep(1)
        if wse.lastwebsocket != None:
            wse.Send(wse.lastwebsocket, 'testX')