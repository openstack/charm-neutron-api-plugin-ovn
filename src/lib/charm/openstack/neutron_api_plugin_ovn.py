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
    """Get path of TLS key file.

    :param cls: charms_openstack.adapters.ConfigurationAdapter derived class
                instance.  Charm class instance is at cls.charm_instance.
    :type: cls: charms_openstack.adapters.ConfiguartionAdapter
    :returns: Path to OVN TLS key file
    :rtype: str
    """
    return os.path.join(NEUTRON_PLUGIN_ML2_DIR, 'key_host')


@charms_openstack.adapters.config_property
def ovn_cert(cls):
    """Get path of TLS certificate file.

    :param cls: charms_openstack.adapters.ConfigurationAdapter derived class
                instance.  Charm class instance is at cls.charm_instance.
    :type: cls: charms_openstack.adapters.ConfiguartionAdapter
    :returns: Path to OVN TLS certificate file
    :rtype: str
    """
    return os.path.join(NEUTRON_PLUGIN_ML2_DIR, 'cert_host')


@charms_openstack.adapters.config_property
def ovn_ca_cert(cls):
    """Get path of TLS key file.

    :param cls: charms_openstack.adapters.ConfigurationAdapter derived class
                instance.  Charm class instance is at cls.charm_instance.
    :type: cls: charms_openstack.adapters.ConfiguartionAdapter
    :returns: Path to OVN TLS CA certificate file
    :rtype: str
    """
    return os.path.join(NEUTRON_PLUGIN_ML2_DIR,
                        '{}.crt'.format(cls.charm_instance.name))


class BaseNeutronAPIPluginCharm(charms_openstack.charm.OpenStackCharm):
    abstract_class = True
    name = 'neutron-api-plugin-ovn'
    required_relations = ['neutron-plugin', 'ovsdb-cms']
    python_version = 3
    release_pkg = version_package = 'neutron-common'
    # make sure we can write secrets readable by the ``neutron-server`` process
    group = 'neutron'
    db_migration_needed = False
    service_plugins = []

    def configure_tls(self, certificates_interface=None):
        """Override configure_tls method for neutron-api-plugin-ovn.

        See parent method for parameter documentation.

        The charm inherits from ``OpenStackCharm`` class which only writes
        the CA to disk.  We need to implement a handler for the layout of certs
        suitable for this charms payload.
        """
        tls_objects = self.get_certs_and_keys(
            certificates_interface=certificates_interface)

        for tls_object in tls_objects:
            with open(ovn_ca_cert(self.adapters_instance), 'w') as crt:
                chain = tls_object.get('chain')
                if chain:
                    crt.write(tls_object['ca'] + os.linesep + chain)
                else:
                    crt.write(tls_object['ca'])

            self.configure_cert(NEUTRON_PLUGIN_ML2_DIR,
                                tls_object['cert'],
                                tls_object['key'],
                                cn='host')

    @property
    def db_migration_needed(self):
        """Determine whether DB migration is needed.

        The returned variable must be set in the release specifc charm classes.

        :returns: Whether DB migration is needed.
        :rtype: bool
        """
        return self.db_migration_needed

    @property
    def service_plugins(self):
        """Provide list of service plugins for current OpenStack release.

        The returned variable must be set in the release specifc charm classes.

        :returns: List of service plugins
        :rtype: List
        """
        return self.service_plugins


class TrainNeutronAPIPluginCharm(BaseNeutronAPIPluginCharm):
    """The Train incarnation of the charm."""
    release = 'train'
    packages = ['python3-networking-ovn']
    db_migration_needed = True
    service_plugins = ['networking_ovn.l3.l3_ovn.OVNL3RouterPlugin']


class UssuriNeutronAPIPluginCharm(BaseNeutronAPIPluginCharm):
    """The Ussuri incarnation of the charm.

    The separate ``networking-ovn`` package has been removed and has been
    merged into Neutron upstream.

    It is still useful to handle the configuration and relations specific to
    OVN in a subordinate charm.
    """
    release = 'ussuri'
    packages = []
    db_migration_needed = False
    service_plugins = ['ovn-router']

    def install(self):
        """We no longer need to install anything."""
        pass
