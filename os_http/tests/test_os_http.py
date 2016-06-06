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

"""
test_os_http
----------------------------------

Tests for `os_http` module.
"""

import re
import uuid

import fixtures
from keystoneauth1 import fixture
import requests_mock
from testtools import matchers

from os_http import shell
from os_http.tests import base

AUTH_URL = 'http://openstack.example.com:5000'

PUBLIC_SERVICE_URL = 'http://public.example.com:9292'
ADMIN_SERVICE_URL = 'http://admin.example.com:9292'
INTERNAL_SERVICE_URL = 'http://internal.example.com:9292'
SERVICE_REGION = uuid.uuid4().hex


class TestInputs(base.TestCase):

    def setUp(self):
        super(TestInputs, self).setUp()

        disc = fixture.DiscoveryList(href=AUTH_URL, v2=False)

        self.service_type = uuid.uuid4().hex
        self.service_id = uuid.uuid4().hex
        self.service_name = uuid.uuid4().hex

        self.user_id = uuid.uuid4().hex
        self.username = uuid.uuid4().hex
        self.project_id = uuid.uuid4().hex
        self.project_name = uuid.uuid4().hex

        self.token = fixture.V3Token(user_id=self.user_id,
                                     user_name=self.username,
                                     project_id=self.project_id,
                                     project_name=self.project_name)

        self.token.add_role()
        self.token.add_role()
        self.token_id = uuid.uuid4().hex

        service = self.token.add_service(self.service_type,
                                         id=self.service_id,
                                         name=self.service_name)

        service.add_standard_endpoints(public=PUBLIC_SERVICE_URL,
                                       admin=ADMIN_SERVICE_URL,
                                       internal=INTERNAL_SERVICE_URL,
                                       region=SERVICE_REGION)

        self.requests_mock.get(AUTH_URL, json=disc, status_code=300)
        self.auth_mock = self.requests_mock.post(
            AUTH_URL + '/v3/auth/tokens',
            json=self.token,
            headers={'X-Subject-Token': self.token_id})

        # don't do any console formatting markup
        m = fixtures.MockPatchObject(shell, 'formatter_name',  'text')
        self.useFixture(m)

    def shell(self, *args, **kwargs):
        for k, v in kwargs.items():
            args.append('--os-%s' % k.replace('_', '-'))
            args.append(v)

        return shell.run(args)

    def test_simple_get(self):
        path = '/%s' % uuid.uuid4().hex
        public_url = '%s%s' % (PUBLIC_SERVICE_URL, path)

        json_a = uuid.uuid4().hex
        json_b = uuid.uuid4().hex

        service_mock = self.requests_mock.get(
            public_url,
            json={json_a: json_b},
            status_code=200,
            reason='OK',
            headers={'Content-Type': 'application/json'})

        resp = self.shell('get', path,
                          '--os-service-type', self.service_type,
                          '--os-auth-type', 'password',
                          '--os-auth-url', AUTH_URL,
                          '--os-project-id', self.project_id,
                          '--os-user-id', self.user_id)

        self.assertEqual('GET', self.requests_mock.last_request.method)
        self.assertEqual(public_url, self.requests_mock.last_request.url)

        self.assertTrue(service_mock.called)

        self.assertThat(resp, matchers.StartsWith('HTTP/1.1 200 OK'))
        self.assertIn('Content-Type: application/json', resp)

        r = '.*{\s*"%s":\s*"%s"\s*}$' % (json_a, json_b)
        self.assertThat(resp, matchers.MatchesRegex(r, re.M | re.S))

    def test_endpoint_not_found(self):
        path = '/%s' % uuid.uuid4().hex
        public_url = '%s%s' % (PUBLIC_SERVICE_URL, path)
        service_mock = self.requests_mock.get(public_url)

        e = self.assertRaises(shell.ErrorExit,
                              self.shell,
                              'get', path,
                              '--os-service-type', uuid.uuid4().hex,
                              '--os-auth-type', 'password',
                              '--os-auth-url', AUTH_URL,
                              '--os-project-id', self.project_id,
                              '--os-user-id', self.user_id)
        self.assertIn('Failed to find an endpoint in the service ', e.message)

    def test_headers(self):
        path = '/%s' % uuid.uuid4().hex
        public_url = '%s%s' % (PUBLIC_SERVICE_URL, path)

        json_a = uuid.uuid4().hex
        json_b = uuid.uuid4().hex

        service_mock = self.requests_mock.get(public_url)

        header_key = uuid.uuid4().hex
        header_val = uuid.uuid4().hex

        self.shell('get', path,
                   '%s:%s' % (header_key, header_val),
                   '--os-service-type', self.service_type,
                   '--os-auth-type', 'password',
                   '--os-auth-url', AUTH_URL,
                   '--os-project-id', self.project_id,
                   '--os-user-id', self.user_id)

        self.assertEqual(header_val,
                         self.requests_mock.last_request.headers[header_key])
