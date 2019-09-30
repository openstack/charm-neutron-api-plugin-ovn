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

import mock

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
                'flag_db_migration': (
                    'neutron-plugin.db_migration',
                    'neutron-plugin.available',),
                'request_db_migration': (
                    'neutron-plugin.available',
                    'run-default-update-status',),
            },
            'when': {
                'flag_db_migration': ('charm.installed',),
                'request_db_migration': ('neutron-plugin.connected',),
                'configure_neutron': (
                    'neutron-plugin.connected',
                    'ovsdb-cms.available',),
                'assess_status': ('neutron-plugin.available',),
                'poke_ovsdb': ('ovsdb-cms.available',),
            },
        }
        # test that the hooks were registered via the
        # reactive.ovn_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestOvnHandlers(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        # self.patch_release(octavia.OctaviaCharm.release)
        self.charm = mock.MagicMock()
        self.patch_object(handlers.charm, 'provide_charm_instance',
                          new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = \
            self.charm
        self.provide_charm_instance().__exit__.return_value = None

    def test_flag_db_migration(self):
        self.patch_object(handlers.reactive, 'set_flag')
        handlers.flag_db_migration()
        self.set_flag.assert_called_once_with('neutron-plugin.db_migration')

    def test_request_db_migration(self):
        self.patch_object(handlers.reactive, 'endpoint_from_flag')
        neutron = mock.MagicMock()
        ovsdb = mock.MagicMock()
        self.endpoint_from_flag.side_effect = [neutron, ovsdb]
        neutron.neutron_config_data.get.side_effect = [
            'router,firewall_v2,metering,segments,'
            'neutron_dynamic_routing.services.bgp.bgp_plugin.BgpPlugin,'
            'lbaasv2',
            'gre,vlan,flat,local',
        ]
        handlers.configure_neutron()
        neutron.configure_plugin.assert_called_once_with(
            'ovn',
            service_plugins=(
                'firewall_v2,metering,segments,'
                'neutron_dynamic_routing.services.bgp.bgp_plugin.BgpPlugin,'
                'lbaasv2,networking_ovn.l3.l3_ovn.OVNL3RouterPlugin'),
            mechanism_drivers='ovn',
            tenant_network_types='geneve,gre,vlan,flat,local',
            subordinate_configuration={
                'neutron-api': {
                    '/etc/neutron/plugins/ml2/ml2_conf.ini': {
                        'sections': {
                            'ovn': [
                                ('ovn_nb_connection',
                                 ''),  # FIXME
                                ('ovn_nb_private_key', mock.ANY),
                                ('ovn_nb_certificate', mock.ANY),
                                ('ovn_nb_ca_cert', mock.ANY),
                                ('ovn_sb_connection',
                                 ''),  # FIXME
                                ('ovn_sb_private_key', mock.ANY),
                                ('ovn_sb_certificate', mock.ANY),
                                ('ovn_sb_ca_cert', mock.ANY),
                                ('ovn_l3_scheduler', 'leastloaded'),
                                ('ovn_metadata_enabled', 'true'),
                            ],
                            'ml2_type_geneve': [
                                ('vni_ranges', '1000:2000'),
                                ('max_header_size', '38'),
                            ],
                        },
                    },
                },
            },
        )

    # def test_render(self):
    #     self.patch_object(handlers.charm, 'use_defaults')
    #     self.patch_object(handlers.reactive, 'set_flag')
    #     self.charm.enable_services.return_value = False
    #     handlers.render()
    #     self.charm.render_with_interfaces.assert_called_once_with([])
    #     self.charm.enable_services.assert_called_once_with()
    #     self.assertFalse(self.use_defaults.called)
    #     self.assertFalse(self.set_flag.called)
    #     self.charm.assess_status.assert_called_once_with()
    #     self.charm.enable_services.return_value = True
    #     handlers.render()
    #     self.use_defaults.assert_called_once_with('certificates.available')
    #     self.set_flag.assert_called_once_with('config.rendered')
