import socket
from threading import Thread
from os import curdir, sep
from termcolor import colored
import hashlib
import mimetypes
import base64

# https://github.com/enthought/Python-2.7.3/blob/master/Lib/SimpleHTTPServer.py
# https://github.com/enthought/Python-2.7.3/blob/master/Lib/SimpleHTTPServer.py
# https://blog.anvileight.com/posts/simple-python-http-server/
# https://gist.github.com/bradmontgomery/2219997
# https://github.com/enthought/Python-2.7.3/blob/master/Lib/BaseHTTPServer.py
# https://www.afternerd.com/blog/python-http-server/
# https://www.acmesystems.it/python_http

if not mimetypes.inited:
    mimetypes.init()

extensions_map = mimetypes.types_map.copy()


bind_ip = 'localhost'
bind_port = 6524

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((bind_ip, bind_port))
server.listen(5)  # max backlog of connections

print('[SRVR ] listening on ' + bind_ip + ':' + str(bind_port))

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
    def __init__(self, clientsocket, address):
        Thread.__init__(self)
        self.clientsocket = clientsocket
        self.address = address
        self.file = None
        self.mimetype = None
        self.start()
        self.path = None
        self.SecWebSocketKey = None
        self.keep = False
        self.isWebSocket = False

    def parse(self, request):
        command, path, version = None, None, None
        lines = request.decode().split('\r\n')
        firstline = lines[0]
        print('[REQ  ] ' + firstline)
        words = firstline.split()

        if len(words) == 3:
            command, path, version = words
        elif len(words) == 2:
            command, path = words

        if 'Connection: Upgrade' in lines:
            key = [s for s in lines if "Sec-WebSocket-Key" in s]
            if len(key) == 1:
                self.SecWebSocketKey = key[0].split(':')[1].strip()
                self.isWebSocket = True
                self.keep = True

        if (path != None):
            if(path.endswith(".html")):
                self.mimetype = 'text/html'
            elif(path.endswith(".ico")):
                self.mimetype = 'image/x-icon'
            elif(path.endswith(".css")):
                self.mimetype = 'text/css'
            elif(path.endswith(".js")):
                self.mimetype = 'application/javascript'
            if (self.mimetype != None):
                self.path = path

    def WSParse(self, request):
        FIN = request[0] & 0x80 == 128
        Opcode = request[0] & (0xF)
        Mask = request[1] & 0x80 == 128
        Maskbit = None
        payload = request[1] & 0x7F
        payloadlen = 0
        payloadStartbit = 0
        
        if payload < 126:
            payloadlen = payload
        elif payload == 126:
            payloadlen = (request[2] << 8) + request[3]
        elif payload == 127:
            payloadlen = (request[2] << 24) + (request[3] << 16) + (request[4] << 8) + request[5]

        if Mask:
            if payload < 126:
                Maskbit = [request[2] , request[3] , request[4] ,request[5]]
            elif payload == 126:
                Maskbit = [request[4] , request[5] , request[6] ,request[7]]
            elif payload == 127:
                Maskbit = [request[6] , request[7] , request[8] ,request[9]]

        i = 0
        outcome = ""
        for b in request[-payloadlen:]:
            outcome = outcome + (chr(b ^ Maskbit[i % 4]))
            i = i + 1
        return outcome

    def WebSocketHandler(self):
        while 1:
            request = self.clientsocket.recv(4096)
            print(self.WSParse(request))

    def run(self):
        try:
            request = self.clientsocket.recv(4096)

            self.parse(request)

            if self.isWebSocket:
                self.clientsocket.send(b'HTTP/1.1 101 Switching Protocols\r\n')
                self.clientsocket.send(b'Upgrade: websocket\r\n')
                self.clientsocket.send(b'Connection: Upgrade\r\n')
                self.clientsocket.send(b'Sec-WebSocket-Accept: ' +  base64.b64encode(hashlib.sha1((self.SecWebSocketKey + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('utf-8')).digest()) +  b'\r\n')
            else:
                self.clientsocket.send(b'HTTP/1.1 200 OK\r\n')

            if not self.keep:
                self.clientsocket.send(b'Connection: Closed\r\n')

            if (self.mimetype != None):
                self.clientsocket.send(b'Content-Type:')
                self.clientsocket.send(bytes(self.mimetype, "ascii"))
                self.clientsocket.send(b'\r\n')
                    
            self.clientsocket.send(b'\r\n')
                
            # Open the static file requested and send it
            if (self.mimetype != None):
                f = open(curdir + '/contents' + self.path, 'rb')
                self.clientsocket.send(f.read())
                f.close()

            if self.isWebSocket:
                self.WebSocketHandler()

            if not self.keep:
                self.clientsocket.close()

        except Exception as ex:
            print(ex)
            self.clientsocket.close()


while 1:
    try:
        clientsocket, address = server.accept()
        print('[CONN ] accepted connection from ' + ':'.join(str(x) for x in address))
        HTTPHandler(clientsocket, address)
    except Exception as ex:
        print(ex)
        server.close()
        break
