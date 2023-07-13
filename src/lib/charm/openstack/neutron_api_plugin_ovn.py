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

import charmhelpers.core as ch_core
import charmhelpers.fetch as ch_fetch
import charms_openstack.adapters
import charms_openstack.charm
import charms.reactive as reactive

import charmhelpers.core.hookenv as hookenv

CERT_RELATION = 'certificates'
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
    required_relations = [CERT_RELATION, 'neutron-plugin', 'ovsdb-cms']
    python_version = 3
    release_pkg = version_package = 'neutron-common'
    # make sure we can write secrets readable by the ``neutron-server`` process
    group = 'neutron'
    db_migration_needed = False
    # Neutron service plugins to add
    svc_plugins = []
    # Neutron service plugins to remove
    svc_plugin_blacklist = [
        # FWaaS is not supported and also deprecated
        'firewall',
        'firewall_v2',
        # Security groups logging not supported at this time
        'log',
        # Port forwarding is not supported at this time
        'port_forwarding',
        # OVN has its own service driver for that replaces Neutron ``router``
        'router',
        # VPNaaS is not supported
        'vpnaas',
    ]
    # Neutron mechanism driers to prepend
    mech_drivers = ['ovn']
    # Neutron mechanism drivers to allow
    mech_driver_whitelist = ['sriovnicswitch']
    # Neutron tenant network types to prepend
    network_types = ['geneve']

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

    def states_to_check(self, required_relations=None):
        """Override parent method to add custom messaging.

        Note that this method will only override the messaging for certain
        relations, any relations we don't know about will get the default
        treatment from the parent method.

        :param required_relations: Override `required_relations` class instance
                                   variable.
        :type required_relations: Optional[List[str]]
        :returns: Map of relation name to flags to check presence of
                  accompanied by status and message.
        :rtype: collections.OrderedDict[str, List[Tuple[str, str, str]]]
        """
        # Retrieve default state map
        states_to_check = super().states_to_check(
            required_relations=required_relations)

        # The parent method will always return a OrderedDict
        if CERT_RELATION in states_to_check:
            # for the certificates relation we want to replace all messaging
            states_to_check[CERT_RELATION] = [
                # the certificates relation has no connected state
                ('{}.available'.format(CERT_RELATION),
                 'blocked',
                 "'{}' missing".format(CERT_RELATION)),
                # we cannot proceed until Vault have provided server
                # certificates
                ('{}.server.certs.available'.format(CERT_RELATION),
                 'waiting',
                 "'{}' awaiting server certificate data"
                 .format(CERT_RELATION)),
            ]

        return states_to_check

    @property
    def db_migration_needed(self):
        """Determine whether DB migration is needed.

        The returned variable must be set in the release specifc charm classes.

        :returns: Whether DB migration is needed.
        :rtype: bool
        """
        return self.db_migration_needed

    def service_plugins(self, neutron_svc_plugins=None):
        """Provide list of service plugins for current OpenStack release.

        The ``svc_plugins`` class variable must be set in the release
        specifc charm classes.

        The ``svc_plugin_blacklist`` class variable defines which
        service plugins to not use together with OVN.

        :param neutron_svc_plugins: Comma separated list of service plugins
                                    from Neutron.
        :type neutron_svc_plugins: Optional[str]
        :returns: List of service plugins
        :rtype: List[str]
        """
        neutron_svc_plugins = neutron_svc_plugins or ''
        return [
            service_plugin
            for service_plugin in neutron_svc_plugins.split(',')
            if service_plugin not in self.svc_plugin_blacklist
        ] + self.svc_plugins

    def mechanism_drivers(self, neutron_mech_drivers=None):
        """Provide list of mechanism drivers for current OpenStack release.

        The ``mech_drivers`` class variable defines which drivers to add
        and must be set in the release specific charm classes.

        The ``mech_driver_whitelist`` class variable defines which
        mechanism drivers are allowed to use together with OVN.

        :param neutron_mech_drivers: Comma separated list of mechanism drivers
                                     from Neutron.
        :type neutron_mech_drivers: Optional[str]
        :returns: List of mechanism drivers
        :rtype: List[str]
        """
        neutron_mech_drivers = neutron_mech_drivers or ''
        return self.mech_drivers + [
            mech_driver
            for mech_driver in neutron_mech_drivers.split(',')
            if mech_driver in self.mech_driver_whitelist
        ]

    def tenant_network_types(self, neutron_tenant_network_types=None):
        """Provide list of tenant network types for current OpenStack release.

        The ``network_types`` class variable dfines which types to
        prepend and must be set in the release specific charm classes.

        :param neutron_tenant_network_types: Comma separated list of tenant
                                             network types from Neutron.
        :type neutron_tenant_network_types: Optional[str]
        :returns: List of tenant network types
        :rtype: List[str]
        """
        neutron_tenant_network_types = neutron_tenant_network_types or ''
        return self.network_types + [
            network_type
            for network_type in neutron_tenant_network_types.split(',')
        ]

    def upgrade_charm(self):
        """ It rises 'restart-needed' flag as a part of "upgrade-charm" hook.

        Flag is risen to trigger corresponding handler invocation.
        :param None
        :returns: None
        """
        super().upgrade_charm()
        reactive.set_flag('restart-needed')


class TrainNeutronAPIPluginCharm(BaseNeutronAPIPluginCharm):
    """The Train incarnation of the charm."""
    release = 'train'
    packages = ['python3-networking-ovn']
    db_migration_needed = True
    svc_plugins = ['networking_ovn.l3.l3_ovn.OVNL3RouterPlugin']


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
    svc_plugins = ['ovn-router']
    ovn_default_pockets = {
        'focal': 'cloud:focal-ovn-22.03',
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._series = None

    @property
    def series(self):
        """Caching property of host's distribution release codename."""
        if self._series is None:
            self._series = ch_core.host.lsb_release()['DISTRIB_CODENAME']

        return self._series

    @property
    def ovn_source(self):
        """Return OVN UCA pocket that should be installed based on the config.

        Based on the configuration value in charm's 'ovn-source':

            * "distro" - Don't configure any UCA pocket, use distro's default
            * "" (empty string) - Configure default UCA pocket for the series.
            * Any other value - return config value as-is, assuming that user
                                configured UCA pocket explicitly.

        :return: UCA pocket string or empty string if no eligible pocket was
                 defined/configured.
        """
        config_value = self.options.ovn_source
        if config_value == 'distro':
            return ''
        elif config_value == '':
            return self.ovn_default_pockets.get(self.series, '')

        return config_value

    @property
    def fresh_deployment(self):
        """Return True if charm-upgrade handler is in progress."""
        return reactive.is_flag_set('leadership.set.install_stamp')

    def _upgrade_packages(self):
        """Trigger upgrade of openstack packages.

        This function mimics behavior of
        'BaseOpenstackCharmActions.do_openstack_pkg_upgrade(False)' that was
        added in Yoga release.
        """
        ch_fetch.apt_update()

        dpkg_opts = [
            '--option', 'Dpkg::Options::=--force-confnew',
            '--option', 'Dpkg::Options::=--force-confdef',
        ]
        ch_fetch.apt_upgrade(
            options=dpkg_opts,
            fatal=True,
            dist=True)
        ch_fetch.apt_install(
            packages=self.all_packages,
            options=dpkg_opts,
            fatal=True)
        self.remove_obsolete_packages()

    def install(self):
        """Install or upgrade OVN packages from dedicated pocket.

        On new installs (e.g. not charm-upgrades), trigger ovn package upgrade.
        """
        if self.fresh_deployment:
            self.upgrade_ovn()

    def upgrade_ovn(self):
        """Upgrade ovn packages based configured UCA pocket."""
        if self.ovn_source:
            hookenv.log('Adding "{}" pocket and upgrading '
                        'packages.'.format(self.ovn_source))
            ch_fetch.add_source(self.ovn_source)
            self._upgrade_packages()
            neutron_api = reactive.endpoint_from_flag(
                'neutron-plugin.connected'
            )
            if neutron_api is not None:
                neutron_api.request_restart()
