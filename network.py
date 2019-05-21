import socket
import hashlib
import mimetypes
import base64
import time

from threading import Thread
from os import curdir, sep
from termcolor import colored

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

MAGICSTRING = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


responses = {
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

class HTTPHandler(Thread):
    def __init__(self, csocket, caddress, endpoints):
        Thread.__init__(self)
        self.csocket = csocket
        self.caddress = caddress
        self.mime = None
        self.path = None
        self.SecWebSocketKey = None
        self.keep = False
        self.isWebSocket = False
        self.filstream = None
        self.SecWebSocketAccept = None
        self.endpoints = endpoints
        self.start()

    def parse(self, request):
        command, path, version = None, None, None
        lines = request.decode().split('\r\n')
        firstline = lines[0]
        print('[reque] ' + firstline)
        words = firstline.split()


        if len(words) == 3:
            command, path, version = words
        elif len(words) == 2:
            command, path = words

        if 'Connection: Upgrade' in lines:
            key = [s for s in lines if "Sec-WebSocket-Key" in s]
            if len(key) == 1:
                self.isWebSocket = True
                self.keep = True
                skey = key[0].split(':')[1].strip()
                stoken = skey + MAGICSTRING
                stokensha1 = hashlib.sha1(stoken.encode('utf-8'))
                self.SecWebSocketAccept = base64.b64encode(stokensha1.digest())
        elif path != None:
            if path in self.endpoints:
                pl = lines[len(lines) -1]
                args = pl.split('$') 
                args2 = dict(item.split("=") for item in pl.split("&"))
                # urlparse.parse_qs("Name1=Value1;Name2=Value2;Name3=Value3")
                method = self.endpoints[path]
                method(**args2)

            elif path.endswith(".html"):
                self.mime = 'text/html'
            elif path.endswith(".ico"):
                self.mime = 'image/x-icon'
            elif path.endswith(".css"):
                self.mime = 'text/css'
            elif path.endswith(".js"):
                self.mime = 'application/javascript'

            if (self.mime != None):
                self.path = path

        if self.mime != None:
            f = open(curdir + '/contents' + self.path, 'rb')
            self.filstream = f.read()
            f.close()


    def WSReceive(self, request):
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

    def WSSend(self, data):
        b1,b2 = 0, 0
        payload = bytearray()
        opcode = 0x1
        fin = 1
        b1 = opcode | fin << 7
        length = len(data)

        if length < 125:
            b2 |= length

        payload.append(b1)
        payload.append(b2)
        payload.extend(bytes(data, "utf-8"))
        self.csocket.send(payload)

    def WebSocketHandler(self):
        while 1:
            r = self.csocket.recv(4096)
            if len(r) > 3:
                print(self.WSReceive(r).decode("ascii") )
            self.WSSend('testing')

    def run(self):
        try:
            request = self.csocket.recv(4096)

            self.parse(request)

            if self.isWebSocket is True:
                self.csocket.send(b'HTTP/1.1 101 Switching Protocols\r\n')
                self.csocket.send(b'Upgrade: websocket\r\n')
                self.csocket.send(b'Connection: Upgrade\r\n')
                self.csocket.send(b'Sec-WebSocket-Accept: ' + self.SecWebSocketAccept +  b'\r\n')
            else:
                self.csocket.send(b'HTTP/1.1 200 OK\r\n')

            if (self.mime != None):
                self.csocket.send(b'Content-Type: ' + bytes(self.mime, "ascii") + b'\r\n')
                    

            if not self.keep:
                self.csocket.send(b'Connection: Closed\r\n')
            self.csocket.send(b'\r\n')
                
            if self.filstream != None:
                self.csocket.send(self.filstream)

            if self.isWebSocket:
                self.WebSocketHandler()

            if not self.keep:
                self.csocket.close()

        except Exception as ex:
            print(ex)
            self.csocket.close()

class GWServer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.endpoints = {}

    def RegisterEndpoint(self, route, callback ):
        self.endpoints[route] = callback
        print('registering endpoint ' + route)

    def run(self):
        ip = 'localhost'
        port = 6545
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((ip, port))
        server.listen(8)  # max backlog of connections

        while 1:
            try:
                print('[serve] listening on ' + ip + ':' + str(port))
                csocket, caddress = server.accept()
                print('[conne] accepted connection from ' + ':'.join(str(x) for x in caddress))
                HTTPHandler(csocket, caddress ,self.endpoints)

            except KeyboardInterrupt:
                print('[conne] closing connection.')
                server.shutdown(socket.SHUT_RD)
                server.close()
                break

            except Exception as ex:
                print(ex)
                server.close()
                break

def Test1(name, time):
    print('test from callback')

srv = GWServer()
srv.RegisterEndpoint('/Test1', Test1)

srv.start()

while 1:
    time.sleep(10)
    print("sleeping ...")

