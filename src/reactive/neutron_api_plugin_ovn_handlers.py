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
import charms.leadership as leadership

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


@reactive.when('neutron-plugin.connected')
def configure_neutron():
    neutron = reactive.endpoint_from_flag(
        'neutron-plugin.connected')
    ch_core.hookenv.log('DEBUG: neutron_config_data="{}"'
                        .format(neutron.neutron_config_data))
    neutron.configure_plugin(
        'ovn',
        subordinate_configuration={
            'neutron-api': {
                '/etc/neutron/neutron.conf': {
                    'sections': {
                        'blablabla': [
                            ('neutron_conf_key1', 'val1'),
                        ],
                    },
                },
                '/etc/neutron/plugins/ml2/ml2_conf.ini': {
                    'sections': {
                        'ovn': [
                            ('ml2_conf_key1', 'val1'),
                        ],
                    },
                },
            },
        },
    )


@reactive.when('neutron-plugin.available')
def assess_status():
    with charm.provide_charm_instance() as instance:
        instance.assess_status()


@reactive.when('ovsdb-cms.available')
def poke_ovsdb():
    ovsdb = reactive.endpoint_from_flag('ovsdb-cms.available')
    ch_core.hookenv.log('DEBUG: cluster_remote_addrs="{}"'
                        .format(list(ovsdb.cluster_remote_addrs)))
