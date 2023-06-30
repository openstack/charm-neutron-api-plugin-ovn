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

import collections
import io
import os
import unittest.mock as mock

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

    def test_states_to_check(self):
        self.maxDiff = None
        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        expect = collections.OrderedDict([
            ('certificates', [
                ('certificates.available', 'blocked',
                 "'certificates' missing"),
                ('certificates.server.certs.available',
                 'waiting',
                 "'certificates' awaiting server certificate data")]),
            ('neutron-plugin', [
                ('neutron-plugin.connected',
                 'blocked',
                 "'neutron-plugin' missing"),
                ('neutron-plugin.available',
                 'waiting',
                 "'neutron-plugin' incomplete")]),
            ('ovsdb-cms', [
                ('ovsdb-cms.connected', 'blocked', "'ovsdb-cms' missing"),
                ('ovsdb-cms.available', 'waiting', "'ovsdb-cms' incomplete")]),

        ])
        self.assertDictEqual(c.states_to_check(), expect)

    def test_service_plugins(self):
        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        svc_plugins = (
            'router,firewall,firewall_v2,metering,segments,log,'
            'neutron_dynamic_routing.services.bgp.bgp_plugin.BgpPlugin,'
            'lbaasv2,port_forwarding,vpnaas')
        expect = [
            'metering',
            'segments',
            'lbaasv2',
            'ovn-router',
        ]
        self.assertEquals(c.service_plugins(svc_plugins), expect)

    def test_mechanism_drivers(self):
        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        mech_drivers = 'openvswitch,hyperv,l2population,sriovnicswitch'
        expect = [
            'ovn',
            'sriovnicswitch',
        ]
        self.assertEquals(c.mechanism_drivers(mech_drivers), expect)

    def test_tenant_network_types(self):
        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        network_types = 'gre,vlan,flat,local'
        expect = ['geneve', 'gre', 'vlan', 'flat', 'local']
        self.assertEquals(c.tenant_network_types(network_types), expect)

    @mock.patch.object(neutron_api_plugin_ovn.ch_core.host, "lsb_release")
    def test_series_caching(self, mock_lsb_release):
        """Test caching property that returns host's series."""
        series = 'focal'
        mock_lsb_release.return_value = {'DISTRIB_CODENAME': series}
        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()

        # Assert that getter returns correct value
        self.assertEquals(c.series, series)
        mock_lsb_release.assert_called_once_with()

        # Assert that getter does not call underlying functions multiple times
        _ = c.series
        mock_lsb_release.assert_called_once_with()

    def test_ovn_source_focal_default(self):
        """Test that 'ovn_source' property returns default UCA pocket.

        If value of 'ovn-source' is empty string we should return default
        pocket for the series.
        """
        series = 'focal'

        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        c.options.ovn_source = ''
        c._series = series

        default_pocket = c.ovn_default_pockets[series]

        self.assertEquals(c.ovn_source, default_pocket)

    def test_ovn_source_distro(self):
        """Test that 'ovn_source' property returns no UCA pocket.

        If value of 'ovn-source' is 'distro' charm should not perform any
        upgrades and therefore this property should not return any UCA pocket.
        """
        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        c.options.ovn_source = 'distro'

        self.assertEquals(c.ovn_source, '')

    def test_ovn_source_manual(self):
        """Test that 'ovn_source' property returns manually configured ppa.

        If value of 'ovn-source' isn't any of the special values, this property
        should return the config value directly, assuming that it's explicitly
        configured PPA URL.
        """
        ppa = 'cloud:focal-ovn-22.03'

        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        c.options.ovn_source = ppa

        self.assertIs(c.ovn_source, ppa)

    def test_is_fresh_deployment(self):
        """Test property that returns True if 'install_stamp' flag is set."""
        self.patch_object(neutron_api_plugin_ovn.reactive, 'is_flag_set')
        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()

        self.is_flag_set.return_value = False
        self.assertFalse(c.fresh_deployment)

        self.is_flag_set.return_value = True
        self.assertTrue(c.fresh_deployment)

    def test_charm_install_ovn_upgrade(self):
        """Test that on fresh install, UCA pocket is used to upgrade OVN.

        Fresh installations of this charm should used default UCA
        pocket to install OVN packages.
        """
        charm_class = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm
        fresh_deployment_mock = mock.PropertyMock(return_value=True)
        self.patch_object(charm_class, 'upgrade_ovn')
        self.patch_object(
            charm_class,
            'fresh_deployment',
            new_callable=fresh_deployment_mock
        )

        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        c.install()

        self.upgrade_ovn.assert_called_once_with()

    def test_charm_install_ovn_dont_upgrade(self):
        """Test that handler triggered by upgrade, won't install new OVN.

        Installation handlers that are triggered during charm upgrade should
        not automatically upgrade OVN packages from new UCA pocket
        """
        charm_class = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm
        fresh_deployment_mock = mock.PropertyMock(return_value=False)
        self.patch_object(charm_class, 'upgrade_ovn')
        self.patch_object(
            charm_class,
            'fresh_deployment',
            new_callable=fresh_deployment_mock
        )

        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        c.install()

        self.upgrade_ovn.assert_not_called()

    def test_upgrade_ovn_from_uca(self):
        """Upgrade OVN packages if there's an OVN UCA pocket configured."""
        charm_class = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm
        ovn_source_data = 'focal-ovn-22.03'
        ovn_source_mock = mock.PropertyMock(return_value=ovn_source_data)
        self.patch_object(
            charm_class,
            'ovn_source',
            new_callable=ovn_source_mock
        )
        self.patch_object(charm_class, '_upgrade_packages')
        self.patch_object(neutron_api_plugin_ovn.ch_fetch, 'add_source')
        neutron_principal_mock = mock.MagicMock()
        self.patch_object(neutron_api_plugin_ovn.reactive,
                          'endpoint_from_flag',
                          return_value=neutron_principal_mock)
        c = neutron_api_plugin_ovn.UssuriNeutronAPIPluginCharm()
        c.upgrade_ovn()

        self.add_source.assert_called_once_with(ovn_source_data)
        self._upgrade_packages.assert_called_once_with()
        neutron_principal_mock.request_restart.assert_called_once_with()
