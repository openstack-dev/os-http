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

from keystoneauth1 import adapter
from keystoneauth1 import exceptions
from keystoneauth1 import loading

LOG = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Simple HTTP testing for Openstack')

    loading.register_session_argparse_arguments(parser)
    loading.register_auth_argparse_arguments(parser, sys.argv[1:])

    parser.add_argument('--debug',
                        action='store_true',
                        help='Enable debug output')

    service_group = parser.add_argument_group('Service Options')
    service_group.add_argument('--os-service-type',
                               help='The service type to find in a catalog')
    service_group.add_argument('--os-service-name',
                               help='The service name to find in a catalog')
    service_group.add_argument('--os-interface',
                               help='The interface to contact')
    service_group.add_argument('--os-region-name',
                               help='The region name to find the service in')
    service_group.add_argument('--os-api-version',
                               help='The version of the api to request')

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

    opts = parser.parse_args()

    if opts.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARN)

    auth = loading.load_auth_from_argparse_arguments(opts)
    session = loading.load_session_from_argparse_arguments(
        opts,
        auth=auth,
        user_agent='os-http')

    service_params = {'service_type': opts.os_service_type,
                      'service_name': opts.os_service_name,
                      'interface': opts.os_interface,
                      'region_name': opts.os_region_name,
                      'version': opts.os_api_version}

    adap = adapter.Adapter(session=session, logger=LOG, **service_params)

    headers = {'Accept': 'application/json'}

    for item in opts.items:
        if ':' in item:
            key, val = item.split(':', 1)
            headers[key] = val
        else:
            LOG.error("Unknown item: %s", item)
            sys.exit(1)

    try:
        resp = adap.request(opts.url,
                            opts.method.upper(),
                            headers=headers,
                            raise_exc=False)

    except exceptions.EmptyCatalog:
        message = ("Failed to find an endpoint because the returned service "
                   "catalog is empty.")

        try:
            get_access = auth.get_access
        except AttributeError:
            # not an identity plugin - see if it specifies project_id
            scoped = bool(adap.get_project_id())
        else:
            scoped = get_access(session).scoped

        if not scoped:
            message += (" This seems to be because the credentials provided "
                        "result in an unscoped token. Please check your "
                        "authentication credentials.")

        LOG.error(message)
        sys.exit(1)

    except exceptions.EndpointNotFound:
        query = ", ".join("%s=%s" % p for p in service_params.items() if p[1])
        LOG.error("Failed to find an endpoint in the service catalog that "
                  "matches your query: %s", query)
        sys.exit(1)

    # I can see no way to get the HTTP version
    headers = ["HTTP/1.1 %d %s" % (resp.status_code, resp.reason)]
    headers.extend('%s: %s' % k for k in resp.headers.items())
    headers = '\r\n'.join(headers)

    if 'json' in resp.headers.get('Content-Type', '').lower():
        body = json.dumps(resp.json(), sort_keys=True, indent=4)
    else:
        body = resp.content

    if pygments:
        mime = resp.headers.get('Content-Type')
        http_lexer = pygments.lexers.get_lexer_by_name('http')
        formatter = pygments.formatters.get_formatter_by_name('console')

        try:
            body_lexer = pygments.lexers.get_lexer_for_mimetype(mime)
        except pygments.util.ClassNotFound:
            body_lexer = pygments.lexers.get_lexer_by_name('text')

        headers = pygments.highlight(headers, http_lexer, formatter)
        body = pygments.highlight(body, body_lexer, formatter)

    print(headers)
    print(body)
