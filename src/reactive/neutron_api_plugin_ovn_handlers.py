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
    'charm.default-select-release',
    'update-status',
    'upgrade-charm',
    'certificates.available',
)


@reactive.when_none('neutron-plugin.db_migration',
                    'neutron-plugin.available')
@reactive.when('charm.installed')
def maybe_flag_db_migration():
    with charm.provide_charm_instance() as instance:
        if instance.db_migration_needed:
            reactive.set_flag('neutron-plugin.db_migration')


@reactive.when_none('neutron-plugin.available', 'run-default-update-status')
@reactive.when('neutron-plugin.connected')
def maybe_request_db_migration():
    neutron = reactive.endpoint_from_flag('neutron-plugin.connected')
    with charm.provide_charm_instance() as instance:
        if instance.db_migration_needed:
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
    tenant_network_types = neutron.neutron_config_data.get(
        'tenant_network_types', '').split(',')
    tenant_network_types.insert(0, 'geneve')

    def _split_if_str(s):
        _s = s or ''
        return _s.split()

    with charm.provide_charm_instance() as instance:
        service_plugins.extend(instance.service_plugins)
        options = instance.adapters_instance.options
        sections = {
            'ovn': [
                ('ovn_nb_connection', ','.join(ovsdb.db_nb_connection_strs)),
                ('ovn_nb_private_key', options.ovn_key),
                ('ovn_nb_certificate', options.ovn_cert),
                ('ovn_nb_ca_cert', options.ovn_ca_cert),
                # NOTE(fnordahl): Tactical workaround for LP: #1864640
                ('ovn_sb_connection', ','.join(
                    ovsdb.db_connection_strs(
                        ovsdb.cluster_remote_addrs,
                        ovsdb.db_sb_port + 10000))),
                ('ovn_sb_private_key', options.ovn_key),
                ('ovn_sb_certificate', options.ovn_cert),
                ('ovn_sb_ca_cert', options.ovn_ca_cert),
                ('ovn_l3_scheduler', options.ovn_l3_scheduler),
                ('ovn_metadata_enabled', options.ovn_metadata_enabled),
                ('enable_distributed_floating_ip',
                    options.enable_distributed_floating_ip),
                ('dns_servers', ','.join(_split_if_str(options.dns_servers))),
                ('dhcp_default_lease_time', options.dhcp_default_lease_time),
                ('ovn_dhcp4_global_options',
                    ','.join(_split_if_str(
                        options.ovn_dhcp4_global_options))),
                ('ovn_dhcp6_global_options',
                    ','.join(
                        _split_if_str(options.ovn_dhcp6_global_options))),
            ],
            'ml2_type_geneve': [
                ('vni_ranges', ','.join(
                    _split_if_str(options.geneve_vni_ranges))),
                ('max_header_size', '38'),
            ],
        }
        neutron.configure_plugin(
            'ovn',
            service_plugins=','.join(service_plugins),
            mechanism_drivers='ovn',
            tenant_network_types=','.join(tenant_network_types),
            subordinate_configuration={
                'neutron-api': {
                    '/etc/neutron/plugins/ml2/ml2_conf.ini': {
                        'sections': sections,
                    },
                },
            },
        )
        instance.assess_status()
