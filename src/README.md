# Overview

OVN provides open source network virtualization for Open vSwitch (OVS).

Subordinate charm that deploys the ``networking-ovn`` component on
``neutron-api`` units and augments Neutron's configuration for use with
the OVN ML2 plugin.

> **Note**: The OVN charms are considered preview charms.

# Usage

OVN makes use of Public Key Infrastructure (PKI) to authenticate and authorize
control plane communication.  The charm requires a Certificate Authority to be
present in the model as represented by the `certificates` relation.

There is an [OVN overlay bundle](https://github.com/openstack-charmers/openstack-bundles/blob/master/development/overlays/openstack-base-ovn.yaml)
for use in conjunction with the [OpenStack Base bundle](https://github.com/openstack-charmers/openstack-bundles/blob/master/development/openstack-base-bionic-train/bundle.yaml)
which give an example of how you can automate certificate lifecycle management
with the help from [Vault](https://jaas.ai/vault/).

To deploy (partial deployment of linked charms only):

    juju config neutron-api manage-neutron-plugin-legacy-mode=false

    juju deploy neutron-api-plugin-ovn
    juju deploy ovn-central -n 3 --config source=cloud:bionic-train
    juju deploy ovn-chassis

    juju add-relation neutron-api-plugin-ovn:certificates vault:certificates
    juju add-relation neutron-api-plugin-ovn:neutron-plugin \
        neutron-api:neutron-plugin-api-subordinate
    juju add-relation ovn-central:certificates vault:certificates
    juju add-relation ovn-chassis:ovsdb ovn-central:ovsdb
    juju add-relation ovn-chassis:certificates vault:certificates
    juju add-relation ovn-chassis:nova-compute nova-compute:neutron-plugin

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-neutron-api-plugin-ovn/+filebug).

For general questions please refer to the OpenStack [Charm Guide](https://docs.openstack.org/charm-guide/latest/).
