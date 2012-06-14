import logging
import socket
import tornado
import tornado.gen
import tornado.httpserver
import tornado.httpclient
import tornado.ioloop
import tornado.web
import sys
import urlparse

class RequestHandler(tornado.web.RequestHandler):

    def initialize(self, proxy_to, ca_file, request_timeout):
        self.proxy_to = urlparse.urlparse(proxy_to)
        self.ca_file = ca_file
        self.request_timeout = request_timeout

    @tornado.web.asynchronous
    @tornado.gen.engine
    def handle_request(self):
        try:
            logging.info("proxying request %s to %s" % (self.request.path, self.proxy_to.netloc))

            request = self._build_request()

            http_client = tornado.httpclient.AsyncHTTPClient(io_loop=tornado.ioloop.IOLoop.instance())
            response = yield tornado.gen.Task(http_client.fetch, request)
            if response.code == 599:
                logging.error("request failed with %s" % response.error)
                self._send_error_response()
            else:
                self._send_response(response)
        except Exception as e:
            logging.exception("Unexpected error: %s" % str(e))
            self._send_error_response()

    def _build_request(self):
        uri = urlparse.urlunparse([self.proxy_to.scheme, self.proxy_to.netloc, self.request.path, None, self.request.query, None])

        headers = self.request.headers.copy()
        del headers['Host']

        if self.request.method in ["DELETE", "GET", "HEAD"]:
            body = None
        else:
            body = self.request.body

        request = tornado.httpclient.HTTPRequest(
            uri,
            request_timeout = self.request_timeout,
            ca_certs = self.ca_file,
            method = self.request.method,
            headers = headers,
            body = body
        )
        return request

    def _send_error_response(self):
        self.set_status(502)
        self.set_header("X-Proxy-Server", socket.gethostname())
        self.finish()

    def _send_response(self, response):
        message = response.body
        self.set_status(response.code)
        headers = response.headers.copy()
        if 'Transfer-Encoding' in headers:
            del headers['Transfer-Encoding']

        for header, value in headers.iteritems():
            self.set_header(header, value)
        self.set_header("X-Proxy-Server", socket.gethostname())
        self.write(message)
        self.finish()

    get = post = put = delete = head = handle_request
