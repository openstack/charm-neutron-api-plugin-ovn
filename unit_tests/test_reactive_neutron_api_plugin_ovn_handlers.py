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

from unittest import mock

import reactive.neutron_api_plugin_ovn_handlers as handlers

import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        defaults = [
            'charm.installed',
            'config.changed',
            'update-status',
            'upgrade-charm',
            'certificates.available',
        ]
        hook_set = {
            'when_none': {
                'maybe_flag_db_migration': (
                    'neutron-plugin.db_migration',
                    'neutron-plugin.available',),
                'maybe_request_db_migration': (
                    'neutron-plugin.available',
                    'run-default-update-status',),
            },
            'when': {
                'maybe_flag_db_migration': ('charm.installed',),
                'maybe_request_db_migration': ('neutron-plugin.connected',),
                'configure_neutron': (
                    'neutron-plugin.connected',
                    'ovsdb-cms.available',),
                'assess_status': ('neutron-plugin.available',),
                'poke_ovsdb': ('ovsdb-cms.available',),
                'restart_neutron': ('restart-needed',),
            },
        }
        # test that the hooks were registered via the
        # reactive.ovn_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestOvnHandlers(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.charm = mock.MagicMock()
        self.patch_object(handlers.charm, 'provide_charm_instance',
                          new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = \
            self.charm
        self.provide_charm_instance().__exit__.return_value = None

    def patch_charm(self, attr, return_value=None):
        mocked = mock.patch.object(self.charm, attr)
        self._patches[attr] = mocked
        started = mocked.start()
        started.return_value = return_value
        self._patches_start[attr] = started
        setattr(self, attr, started)

    def pmock(self, return_value=None):
        p = mock.PropertyMock().return_value = return_value
        return p

    def test_maybe_flag_db_migration(self):
        self.patch_object(handlers.reactive, 'set_flag')
        self.charm.db_migration_needed = self.pmock(False)
        handlers.maybe_flag_db_migration()
        self.assertFalse(self.set_flag.called)
        self.charm.db_migration_needed = self.pmock(True)
        handlers.maybe_flag_db_migration()
        self.set_flag.assert_called_once_with('neutron-plugin.db_migration')

    def test_maybe_request_db_migration(self):
        self.patch_object(handlers.reactive, 'endpoint_from_flag')
        neutron_plugin = mock.MagicMock()
        self.endpoint_from_flag.return_value = neutron_plugin
        self.charm.db_migration_needed = self.pmock(False)
        handlers.maybe_request_db_migration()
        self.assertFalse(neutron_plugin.request_db_migration.called)
        self.charm.db_migration_needed = self.pmock(True)
        handlers.maybe_request_db_migration()
        neutron_plugin.request_db_migration.assert_called_once_with()

    def test_render(self):
        self.patch_object(handlers.reactive, 'endpoint_from_flag')
        neutron = mock.MagicMock()
        ovsdb = mock.MagicMock()
        self.endpoint_from_flag.side_effect = [neutron, ovsdb]
        neutron.neutron_config_data.get.side_effect = lambda x: {
            'mechanism_drivers': (
                'openvswitch,hyperv,l2population,sriovnicswitch'),
            'service_plugins': (
                'router,firewall_v2,metering,segments,'
                'lbaasv2'),
            'tenant_network_types': 'gre,vlan,flat,local',
        }.get(x)
        options = self.charm.adapters_instance.options
        options.ovn_key = self.pmock('aKey')
        options.ovn_cert = self.pmock('aCert')
        options.ovn_ca_cert = self.pmock('aCaCert')
        options.ovn_l3_scheduler = self.pmock('aSched')
        options.ovn_metadata_enabled = self.pmock('aMetaData')
        options.enable_distributed_floating_ip = self.pmock('dont')
        options.dns_servers = self.pmock('dns1 dns2')
        options.geneve_vni_ranges = self.pmock('vnia:vniA vnib:vniB')
        options.dhcp_default_lease_time = self.pmock(42)
        options.ovn_dhcp4_global_options = self.pmock('a:A4 b:B4')
        options.ovn_dhcp6_global_options = self.pmock('a:A6 b:B6')
        self.patch_charm('mechanism_drivers')
        self.mechanism_drivers.return_value = ['ovn', 'sriovnicswitch']
        self.patch_charm('service_plugins')
        self.service_plugins.return_value = [
            'metering', 'segments', 'lbaasv2', 'ovn-router']
        self.patch_charm('tenant_network_types')
        self.tenant_network_types.return_value = [
            'geneve', 'gre', 'vlan', 'flat', 'local']
        handlers.configure_neutron()
        neutron.configure_plugin.assert_called_once_with(
            'ovn',
            service_plugins='metering,segments,lbaasv2,ovn-router',
            mechanism_drivers='ovn,sriovnicswitch',
            tenant_network_types='geneve,gre,vlan,flat,local',
            subordinate_configuration={
                'neutron-api': {
                    '/etc/neutron/plugins/ml2/ml2_conf.ini': {
                        'sections': {
                            'ovn': [
                                ('ovn_nb_connection',
                                 ''),  # FIXME
                                ('ovn_nb_private_key', 'aKey'),
                                ('ovn_nb_certificate', 'aCert'),
                                ('ovn_nb_ca_cert', 'aCaCert'),
                                ('ovn_sb_connection',
                                 ''),  # FIXME
                                ('ovn_sb_private_key', 'aKey'),
                                ('ovn_sb_certificate', 'aCert'),
                                ('ovn_sb_ca_cert', 'aCaCert'),
                                ('ovn_l3_scheduler', 'aSched'),
                                ('ovn_metadata_enabled', 'aMetaData'),
                                ('enable_distributed_floating_ip', 'dont'),
                                ('dns_servers', 'dns1,dns2'),
                                ('dhcp_default_lease_time', 42),
                                ('ovn_dhcp4_global_options', 'a:A4,b:B4'),
                                ('ovn_dhcp6_global_options', 'a:A6,b:B6'),
                                ('vhost_sock_dir', '/run/libvirt-vhost-user')
                            ],
                            'ml2_type_geneve': [
                                ('vni_ranges', 'vnia:vniA,vnib:vniB'),
                                ('max_header_size', '38'),
                            ],
                        },
                    },
                },
            },
        )

    @mock.patch.object(handlers.reactive, 'endpoint_from_flag')
    @mock.patch.object(handlers.reactive, 'clear_flag')
    def test_restart_neutron(self, clear_flag, endpoint_from_flag):
        neutron_plugin = mock.MagicMock()
        endpoint_from_flag.return_value = neutron_plugin
        handlers.restart_neutron()
        neutron_plugin.request_restart.assert_called_once()
        neutron_plugin.request_restart.assert_called_once_with()
        clear_flag.assert_called_once()
        clear_flag.assert_called_once_with('restart-needed')
