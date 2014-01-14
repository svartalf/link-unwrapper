# -*- coding: utf-8 -*-

import time
import datetime
import email.utils
from wsgiref.handlers import format_date_time

import tornado.web
import tornado.httpclient
import tornado.gen
import tornado.ioloop
import tornadoredis
from tornado.options import define, options


class Handler(tornado.web.RequestHandler):

    USER_AGENT = 'link-unwrapper/0.1 (http://github.com/svartalf/link-unwrapper)'

    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self, *args, **kwargs):
        url = self.get_argument('url')

        client = tornado.httpclient.AsyncHTTPClient()

        redirects_count = 0
        cache_age = None

        while True:
            if redirects_count > options.max_redirects:
                self.set_status(500)
                self.finish()
                return

            result = yield tornado.gen.Task(self.application.redis.get, url)
            if result:
                ttl = yield tornado.gen.Task(self.application.redis.ttl, url)
                self.set_header('Cache-Control', 'public, max-age={0}'.format(ttl))
                expires = time.mktime((datetime.datetime.now() + datetime.timedelta(seconds=ttl)).timetuple())
                self.set_header('Expires', format_date_time(expires))

                self.finish(result)
                return

            request = tornado.httpclient.HTTPRequest(url, method='HEAD', follow_redirects=False, headers={
                'User-Agent': self.USER_AGENT,
            })
            response = yield tornado.gen.Task(client.fetch, request)
            current_cache_age = self._get_cache_age(response.headers)
            if current_cache_age:
                cache_age = current_cache_age

            if response.code == 200:
                result_url = url
                self.finish(result_url)
                yield tornado.gen.Task(self.application.redis.setex, url, int(cache_age or options.cache_age), result_url)

                return

            elif response.code in (301, 302):
                result_url = response.headers['Location']
                yield tornado.gen.Task(self.application.redis.setex, url, int(cache_age or options.cache_age), result_url)
                url = result_url
                redirects_count += 1

                continue

            else:
                self.set_status(400, 'Unknown URL {0}'.format(url))
                self.finish()

                return

    def _get_cache_age(self, headers):
        if 'Expires' in headers:
            expires = datetime.datetime(*email.utils.parsedate(headers['Expires'])[:6])
            result = (expires - datetime.datetime.now()).total_seconds()
            if result > 0:
                return result

        if 'Cache-Control' in headers:
            bits = headers['Cache-Control'].split(',')
            for bit in bits:
                try:
                    k, v = bit.split('=')
                except ValueError:
                    continue

                if k == 'max-age':
                    return int(v)


class Application(tornado.web.Application):

    def __init__(self, *args, **kwargs):
        urls = [
            (r'/', Handler),
        ]

        self.redis = tornadoredis.Client(host=options.redis_host, port=options.redis_port,
                                         unix_socket_path=options.redis_unix_socket_path,
                                         password=options.redis_password, selected_db=options.redis_db)

        super(Application, self).__init__(urls, *args, **kwargs)


if __name__ == '__main__':
    define('debug', default=False, type=bool, help='Debug mode')
    define('port', default=8080, type=int, help='TCP port for binding')
    define('max_redirects', default=5, type=int, help='Max redirects count for cycling redirects detection')
    define('cache_age', default=600, type=int, help='Default cache age for URL')

    define('redis_host', default='localhost')
    define('redis_port', default=6379)
    define('redis_unix_socket_path', default=None)
    define('redis_password', default=None)
    define('redis_db', default=None)

    options.parse_command_line()

    application = Application(debug=options.debug)
    application.listen(options.port)

    tornado.ioloop.IOLoop.instance().start()
