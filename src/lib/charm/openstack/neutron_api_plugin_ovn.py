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

import os

import charms_openstack.adapters
import charms_openstack.charm


NEUTRON_PLUGIN_ML2_DIR = '/etc/neutron/plugins/ml2'


@charms_openstack.adapters.config_property
def ovn_key(cls):
    return os.path.join(NEUTRON_PLUGIN_ML2_DIR, 'key_host')


@charms_openstack.adapters.config_property
def ovn_cert(cls):
    return os.path.join(NEUTRON_PLUGIN_ML2_DIR, 'cert_host')


@charms_openstack.adapters.config_property
def ovn_ca_cert(cls):
    return os.path.join(NEUTRON_PLUGIN_ML2_DIR,
                        '{}.crt'.format(cls.charm_instance.name))


class NeutronAPIPluginCharm(charms_openstack.charm.OpenStackCharm):
    release = 'stein'
    name = 'neutron-api-plugin-ovn'
    packages = ['python3-networking-ovn']
    required_relations = ['neutron-plugin', 'ovsdb-cms']
    python_version = 3
    # make sure we can write secrets readable by the ``neutron-server`` process
    group = 'neutron'

    def configure_tls(self, certificates_interface=None):
        tls_objects = self.get_certs_and_keys(
            certificates_interface=certificates_interface)

        for tls_object in tls_objects:
            with open(ovn_ca_cert(self.adapters_instance), 'w') as crt:
                crt.write(
                    tls_object['ca'] +
                    os.linesep +
                    tls_object.get('chain', ''))
            self.configure_cert(NEUTRON_PLUGIN_ML2_DIR,
                                tls_object['cert'],
                                tls_object['key'],
                                cn='host')
