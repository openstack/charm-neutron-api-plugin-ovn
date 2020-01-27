# Copyright 2019 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import mock
import os

import charms_openstack.test_utils as test_utils

import charm.openstack.neutron_api_plugin_ovn as neutron_api_plugin_ovn


class TestNeutronAPIPluginOvnConfigProperties(test_utils.PatchHelper):

    def test_ovn_key(self):
        cls = mock.MagicMock()
        self.assertEquals(
            neutron_api_plugin_ovn.ovn_key(cls),
            os.path.join(neutron_api_plugin_ovn.NEUTRON_PLUGIN_ML2_DIR,
                         'key_host'))

    def test_ovn_cert(self):
        cls = mock.MagicMock()
        self.assertEquals(
            neutron_api_plugin_ovn.ovn_cert(cls),
            os.path.join(neutron_api_plugin_ovn.NEUTRON_PLUGIN_ML2_DIR,
                         'cert_host'))

    def test_ovn_ca_cert(self):
        cls = mock.MagicMock()
        cls.charm_instance.name = 'neutron-api-plugin-ovn'
        self.assertEquals(
            neutron_api_plugin_ovn.ovn_ca_cert(cls),
            os.path.join(neutron_api_plugin_ovn.NEUTRON_PLUGIN_ML2_DIR,
                         'neutron-api-plugin-ovn.crt'))


class Helper(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.patch_release(
            neutron_api_plugin_ovn.TrainNeutronAPIPluginCharm.release)
        self.patch_release(
            neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm.release)


class TestNeutronAPIPluginOvnCharm(Helper):

    def test_configure_tls(self):
        self.patch('charmhelpers.core.hookenv', 'service_name')
        self.service_name.return_value = 'fakeservice'
        self.patch_object(
            neutron_api_plugin_ovn.charms_openstack.charm.OpenStackCharm,
            'get_certs_and_keys')
        self.get_certs_and_keys.return_value = [{
            'cert': 'fakecert',
            'key': 'fakekey',
            'cn': 'fakecn',
            'ca': 'fakeca',
            'chain': 'fakechain',
        }]
        with mock.patch('builtins.open', create=True) as mocked_open:
            mocked_file = mock.MagicMock(spec=io.FileIO)
            mocked_open.return_value = mocked_file
            c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
            c.configure_cert = mock.MagicMock()
            c.configure_tls()
            mocked_open.assert_called_once_with(
                '/etc/neutron/plugins/ml2/neutron-api-plugin-ovn.crt', 'w')
            mocked_file.__enter__().write.assert_called_once_with(
                'fakeca\nfakechain')
            c.configure_cert.assert_called_once_with(
                neutron_api_plugin_ovn.NEUTRON_PLUGIN_ML2_DIR,
                'fakecert',
                'fakekey',
                cn='host',
            )
