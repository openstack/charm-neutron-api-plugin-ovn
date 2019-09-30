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

import charmhelpers.core as ch_core

import charms.reactive as reactive

import charms_openstack.bus
import charms_openstack.charm as charm


charms_openstack.bus.discover()

# Use the charms.openstack defaults for common states and hooks
charm.use_defaults(
    'charm.installed',
    'config.changed',
    'update-status',
    'upgrade-charm',
    'certificates.available',
)


@reactive.when_none('neutron-plugin.db_migration',
                    'neutron-plugin.available')
@reactive.when('charm.installed')
def flag_db_migration():
    reactive.set_flag('neutron-plugin.db_migration')


@reactive.when_none('neutron-plugin.available', 'run-default-update-status')
@reactive.when('neutron-plugin.connected')
def request_db_migration():
    neutron = reactive.endpoint_from_flag('neutron-plugin.connected')
    neutron.request_db_migration()


@reactive.when('neutron-plugin.connected', 'ovsdb-cms.available')
def configure_neutron():
    neutron = reactive.endpoint_from_flag(
        'neutron-plugin.connected')
    ovsdb = reactive.endpoint_from_flag(
        'ovsdb-cms.available')
    ch_core.hookenv.log('DEBUG: neutron_config_data="{}"'
                        .format(neutron.neutron_config_data))
    service_plugins = neutron.neutron_config_data.get(
        'service_plugins', '').split(',')
    service_plugins = [svc for svc in service_plugins if svc not in ['router']]
    service_plugins.append('networking_ovn.l3.l3_ovn.OVNL3RouterPlugin')
    tenant_network_types = neutron.neutron_config_data.get(
        'tenant_network_types', '').split(',')
    tenant_network_types.insert(0, 'geneve')
    with charm.provide_charm_instance() as instance:
        neutron.configure_plugin(
            'ovn',
            service_plugins=','.join(service_plugins),
            mechanism_drivers='ovn',
            tenant_network_types=','.join(tenant_network_types),
            subordinate_configuration={
                'neutron-api': {
                    '/etc/neutron/plugins/ml2/ml2_conf.ini': {
                        'sections': {
                            'ovn': [
                                ('ovn_nb_connection',
                                 ','.join(ovsdb.db_nb_connection_strs)),
                                ('ovn_nb_private_key',
                                 instance.adapters_instance.options.ovn_key),
                                ('ovn_nb_certificate',
                                 instance.adapters_instance.options.ovn_cert),
                                ('ovn_nb_ca_cert',
                                 instance.adapters_instance.options.ovn_ca_cert
                                 ),
                                ('ovn_sb_connection',
                                 ','.join(ovsdb.db_sb_connection_strs)),
                                ('ovn_sb_private_key',
                                 instance.adapters_instance.options.ovn_key),
                                ('ovn_sb_certificate',
                                 instance.adapters_instance.options.ovn_cert),
                                ('ovn_sb_ca_cert',
                                 instance.adapters_instance.options.ovn_ca_cert
                                 ),
                                # XXX config
                                ('ovn_l3_scheduler', 'leastloaded'),
                                ('ovn_metadata_enabled', 'true'),  # XXX config
                            ],
                            'ml2_type_geneve': [
                                ('vni_ranges', '1000:2000'),  # XXX config
                                ('max_header_size', '38'),
                            ],
                        },
                    },
                },
            },
        )
        instance.assess_status()


@reactive.when('neutron-plugin.available')
def assess_status():
    with charm.provide_charm_instance() as instance:
        instance.assess_status()


@reactive.when('ovsdb-cms.available')
def poke_ovsdb():
    ovsdb = reactive.endpoint_from_flag('ovsdb-cms.available')
    ch_core.hookenv.log('DEBUG: cluster_remote_addrs="{}"'
                        .format(list(ovsdb.cluster_remote_addrs)))
