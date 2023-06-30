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

import charms.leadership as leadership
import charms.reactive as reactive

import charms_openstack.bus
import charms_openstack.charm as charm


charms_openstack.bus.discover()

# Use the charms.openstack defaults for common states and hooks
charm.use_defaults(
    'config.changed',
    'charm.default-select-release',
    'update-status',
    'upgrade-charm',
    'certificates.available',
)


@reactive.when_none('charm.installed', 'leadership.set.install_stamp')
@reactive.when('leadership.is_leader')
def stamp_fresh_deployment():
    """Stamp the deployment with leader setting, fresh deployment.
    This is used to determine whether this application is a fresh or upgraded
    deployment which influence the default of the `ovn-source` configuration
    option.
    """
    leadership.leader_set(install_stamp=2203)


@reactive.when_none('is-update-status-hook',
                    'leadership.set.install_stamp',
                    'leadership.set.upgrade_stamp')
@reactive.when('charm.installed', 'leadership.is_leader')
def stamp_upgraded_deployment():
    """Stamp the deployment with leader setting, upgrade.
    This is needed so that the units of this application can safely enable
    the default install hook.
    """
    leadership.leader_set(upgrade_stamp=2203)


@reactive.when_none('charm.installed', 'is-update-status-hook')
@reactive.when_any('leadership.set.install_stamp',
                   'leadership.set.upgrade_stamp')
def enable_install():
    """Enable the default install hook."""
    charm.use_defaults('charm.installed')


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

    def _split_if_str(s):
        _s = s or ''
        return _s.split()

    with charm.provide_charm_instance() as instance:
        mechanism_drivers = instance.mechanism_drivers(
            neutron.neutron_config_data.get('mechanism_drivers'))
        service_plugins = instance.service_plugins(
            neutron.neutron_config_data.get('service_plugins'))
        tenant_network_types = instance.tenant_network_types(
            neutron.neutron_config_data.get('tenant_network_types'))
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
                # NOTE(fnordahl): will be used on chassis with DPDK enabled
                #
                # Neutron will make per chassis decisions based on chassis
                # configuration whether vif_type will be 'ovs' or 'vhostuser'.
                # This allows having a mix of DPDK and non-DPDK nodes in the
                # same deployment.
                ('vhost_sock_dir', '/run/libvirt-vhost-user'),
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
            mechanism_drivers=','.join(mechanism_drivers),
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


@reactive.when('config.changed.ovn-source')
@reactive.when_not('config.default.ovn-source')
def ovn_source_changed():
    with charm.provide_charm_instance() as instance:
        instance.upgrade_ovn()
