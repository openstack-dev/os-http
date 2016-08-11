# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from __future__ import print_function

import argparse
import json
import logging
import sys

try:
    import pygments
    import pygments.formatters
    import pygments.lexers
    import pygments.util
except ImportError:
    pygments = None

from keystoneauth1 import exceptions
from keystoneauth1 import session
import os_client_config

from os_http import version

LOG = logging.getLogger(__name__)

_occ_version = os_client_config.__version__

formatter_name = 'console' if sys.stdout.isatty() else 'text'


class ErrorExit(Exception):

    def __init__(self, message, exit_code=1):
        self.message = message
        self.exit_code = exit_code


def format_resp(resp):
    # I can see no way to get the HTTP version
    headers = ["HTTP/1.1 %d %s" % (resp.status_code, resp.reason or '')]
    headers.extend('%s: %s' % k for k in resp.headers.items())
    headers = '\n'.join(headers)

    if 'json' in resp.headers.get('Content-Type', '').lower():
        body = json.dumps(resp.json(), sort_keys=True, indent=4)
    else:
        body = resp.content

    if pygments:
        mime = resp.headers.get('Content-Type')
        http_lexer = pygments.lexers.get_lexer_by_name('http')
        formatter = pygments.formatters.get_formatter_by_name(formatter_name)

        try:
            body_lexer = pygments.lexers.get_lexer_for_mimetype(mime)
        except pygments.util.ClassNotFound:
            body_lexer = pygments.lexers.get_lexer_by_name('text')

        headers = pygments.highlight(headers, http_lexer, formatter)
        body = pygments.highlight(body, body_lexer, formatter)

    return '\n'.join([headers, '', body])


def run(argv):
    parser = argparse.ArgumentParser(
        description='Simple HTTP testing for Openstack')

    parser.add_argument('--debug',
                        action='store_true',
                        help='Enable debug output')

    config = os_client_config.OpenStackConfig()
    config.register_argparse_arguments(parser, argv)

    positional = parser.add_argument_group('Positional Arguments')
    positional.add_argument('method',
                            metavar='METHOD',
                            help='The HTTP method to make the request with')
    positional.add_argument('url',
                            metavar='URL',
                            help='The URL or path to request')
    positional.add_argument('items',
                            metavar='ITEM',
                            nargs='*',
                            help='Additional items')

    opts = parser.parse_args(argv)

    if opts.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARN)

    cloud = config.get_one_cloud(argparse=opts)

    adap = cloud.get_session_client(None)

    # FIXME(jamielennox): These things should be handled by os-client-config
    adap.logger = LOG
    adap.user_agent = 'os-http/%s os-client-config/%s %s' % (
        version.version_string,
        _occ_version,
        session.DEFAULT_USER_AGENT)
    adap.version = opts.os_api_version

    headers = {'Accept': 'application/json'}

    for item in opts.items:
        if ':' in item:
            key, val = item.split(':', 1)
            headers[key] = val
        else:
            raise ErrorExit("Unknown item: %s" % item)

    try:
        resp = adap.request(opts.url,
                            opts.method.upper(),
                            headers=headers,
                            raise_exc=False)

    except exceptions.EmptyCatalog:
        message = ("Failed to find an endpoint because the returned service "
                   "catalog is empty.")

        try:
            get_access = adap.session.auth.get_access
        except AttributeError:
            # not an identity plugin - see if it specifies project_id
            scoped = bool(adap.get_project_id())
        else:
            scoped = get_access(adap.session).scoped

        if not scoped:
            message += (" This seems to be because the credentials provided "
                        "result in an unscoped token. Please check your "
                        "authentication credentials.")

        raise ErrorExit(message)

    except exceptions.EndpointNotFound:
        service_params = ('service_type',
                          'service_name',
                          'interface',
                          'region_name',
                          'version')

        query = ", ".join("%s=%s" % (p, getattr(adap, p))
                          for p in service_params if getattr(adap, p))
        raise ErrorExit("Failed to find an endpoint in the service catalog "
                        "that matches your query: %s" % query)

    return format_resp(resp)


def main(argv=sys.argv[1:]):
    try:
        output = run(argv)
    except ErrorExit as e:
        LOG.error(e.message)
        sys.exit(e.exit_code)
    else:
        print(output)
