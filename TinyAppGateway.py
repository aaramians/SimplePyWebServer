import socket
import hashlib
import mimetypes
import base64
import time
import logging
import sys
from threading import Thread


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


if sys.version_info[0] < 3:
    raise Exception("Must be using Python 3")

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


class TinyAppGateway(Thread):
    class ServiceHandlerThread(Thread):
        def __init__(self, csocket, caddress, server):
            Thread.__init__(self)
            self.csocket = csocket
            self.caddress = caddress
            self.path = None
            self.server = server
            self.__MAGICSTRING = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
            self.daemon = True

        def ResolveEndpoint(self):
            # this may have a problem of patrtial recv ?
            self.request = self.csocket.recv(4 * 1024)

            if len(self.request) > 4 * 1024:
                raise NotImplementedError

            self.command, self.route, self.version = None, None, None

            self.lines = self.request.decode().split('\r\n')
            logging.info(self.lines[0])
            words = self.lines[0].split()
            
            # todo move the logic to run and to Endpoints
            if len(words) == 3:
                self.command, self.route, self.version = words
            elif len(words) == 2:
                self.command, self.route = words

            endpoint = None
            endpointtype = None
            if self.route != None:
                endpoint = self.server.endpoints['*']
                endpointtype = TinyAppGateway.WebStaticEndpoint
                if  self.route in self.server.endpoints:
                    endpoint = self.server.endpoints[self.route]
                    endpointtype = type(endpoint)

            return endpoint, endpointtype

        def run(self):
            try:
                self.endpoint, self.endpointtype = self.ResolveEndpoint()

                if self.endpointtype == TinyAppGateway.WebSocketEndpoint:
                    key = [s for s in self.lines if "Sec-WebSocket-Key" in s]
                    if len(key) == 1:
                        skey = key[0].split(':')[1].strip()
                        stoken = skey + self.__MAGICSTRING
                        stokensha1 = hashlib.sha1(stoken.encode('utf-8'))
                        secWebSocketAccept = base64.b64encode(stokensha1.digest())
                        self.csocket.send(b'HTTP/1.1 101 Switching Protocols\r\n')
                        self.csocket.send(b'Upgrade: websocket\r\n')
                        self.csocket.send(b'Connection: Upgrade\r\n')
                        self.csocket.send(b'Sec-WebSocket-Accept: ' + secWebSocketAccept +  b'\r\n')
                        self.csocket.send(b'\r\n')
                    self.endpoint.OnReady(self.endpoint, self.csocket)

                if self.endpointtype == TinyAppGateway.WebServiceEndpoint:
                    pl = self.lines[len(self.lines) -1]
                    args2 = dict(item.split("=") for item in pl.split("&"))
                    # urlparse.parse_qs("Name1=Value1;Name2=Value2;Name3=Value3")
                    method = self.endpoint.callback
                    content = method(**args2)
                    contentlen = len(content)
                    self.csocket.send(b'HTTP/1.1 200 OK\r\n')
                    self.csocket.send(b'Content-Length: ' + bytes(str(contentlen), "ascii") + b'\r\n')
                    self.csocket.send(b'Connection: Closed\r\n')
                    self.csocket.send(b'\r\n')
                    if content != None:
                        self.csocket.send(content)

                # we can use mimetypes.init if this gets more complicated
                if self.endpointtype == TinyAppGateway.WebStaticEndpoint:
                    f = open(self.endpoint.path + self.route, 'rb')
                    content = f.read(16*1024*1024)
                    contentlen = len(content)
                    f.close()
                    
                    mime = 'application/octet-stream'
                    
                    if self.route.endswith(".html"):
                        mime = 'text/html'
                    elif self.route.endswith(".ico"):
                        mime = 'image/x-icon'  
                    elif self.route.endswith(".css"):
                        mime = 'text/css'
                    elif self.route.endswith(".jpg"):
                        mime = 'image/jpeg'                    
                    elif self.route.endswith(".js"):
                        mime = 'application/javascript'
                    elif self.route.endswith(".mp4"):
                        mime = 'video/mp4'

                    self.csocket.send(b'HTTP/1.1 200 OK\r\n')
                    self.csocket.send(b'Content-Type: ' + bytes(mime, "ascii") + b'\r\n')
                    self.csocket.send(b'Content-Length: ' + bytes(str(contentlen), "ascii") + b'\r\n')
                    self.csocket.send(b'Connection: Closed\r\n')
                    self.csocket.send(b'\r\n')
                    self.csocket.send(content)

                self.csocket.close()

            except Exception as ex:
                logging.critical(ex)
                self.csocket.close()

    class Endpoint(object):
        def __init__(self, route, callback):
            self.route = route
            self.callback = callback

    class WebStaticEndpoint(Endpoint):
        def __init__(self, path):
            self.route = '*'
            self.path = path
            logging.info('content path : ' + self.path)

    class ServerSentEventEndpoint(Endpoint):
        def __init__(self, route, callback):
            raise NotImplementedError

    class WebServiceEndpoint(Endpoint):
        def __init__(self, route, callback):
            self.route = route
            self.callback = callback

        def OnReady(self):
            pass

    class WebSocketEndpoint(Endpoint):
        def __init__(self, route, callback):
            self.route = route
            self.callback = callback

        def Receive(self,socket):
            # partial recv looks like wont happen, how ever multiple packets may need to be received and combined
            request = socket.recv(4096)
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

        def Send(self, payload, socket = None):
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
            plbytes.extend(payload)
            socket.send(plbytes)
      
        def OnReady(self, socket):
            while 1:
                response = self.callback(self.Receive(socket))
                if response != None:
                    self.Send(response, socket)

    def __init__(self, hostname, port):
        Thread.__init__(self)
        self.endpoints = {}
        self.hostname = hostname
        self.port = port
        self.daemon = True
        self.running = False

    def RegisterEndpoint(self, endpoint):
        logging.debug('registering endpoint ' + endpoint.route)
        self.endpoints[endpoint.route] = endpoint

    def stop(self):
        """
        properly kills the process: https://stackoverflow.com/a/16736227/4225229
        """
        self.running = False
        time.sleep(1)
        t = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        t.connect((self.hostname, self.port))
        t.close()

    def run(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.hostname, self.port))
        self.server.listen(5)  # max backlog of connections
        logging.info('listening on ' + self.hostname + ':' + str(self.port))
        self.running = True
        while self.running:
            try:
                csocket, caddress = self.server.accept()
                logging.debug('connect ' + ':'.join(str(x) for x in caddress))
                TinyAppGateway.ServiceHandlerThread(csocket, caddress, self).start()
            except Exception as ex:
                logging.critical(ex)
                self.server.close()
                break

def TestSocket(payload):
    p = payload.decode("ascii")
    logging.debug(p)
    return bytes(p, "utf-8")

def TestCustomOnReady(endpoint, socket):
    q = endpoint.Receive(socket)
    logging.debug(q)
    endpoint.Send(bytes('Echoing', "utf-8"), socket)

def TestAjax(param1, param2, param3):
    logging.debug('%s %s %s ', param1, param2, param3)
    return b'Ajax Response'

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format = '%(asctime)s - %(name)s - [%(levelname)-5.5s] - %(message)s')
    from os import path as ospath
    tag = TinyAppGateway('', 65150)
    tag.RegisterEndpoint(TinyAppGateway.WebServiceEndpoint('/TestAjax', TestAjax))
    # tag.RegisterEndpoint(TinyAppGateway.WebSocketEndpoint('/Socket', TestSocket))
    X = TinyAppGateway.WebSocketEndpoint('/Socket', TestSocket)
    X.OnReady = TestCustomOnReady
    tag.RegisterEndpoint(X)
    tag.RegisterEndpoint(TinyAppGateway.WebStaticEndpoint(ospath.dirname(ospath.abspath( __file__ )) + '/contents'))
    tag.start()
    logging.debug('http://localhost:' + str(tag.port) + '/TinyAppGatwayIndex.html')
    try:
        logging.info('Press Ctrl+C to terminate.')
        tag.join()
    except KeyboardInterrupt:
        logging.debug('closing connection')
        tag.stop()
        tag.join()
