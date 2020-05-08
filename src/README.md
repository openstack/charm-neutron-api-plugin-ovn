# Overview

OVN provides open source network virtualization for Open vSwitch (OVS).

The neutron-api-plugin-ovn charm is a subordinate charm that augments Neutron's
configuration for use with the OVN ML2 driver.  On OpenStack Ussuri and onwards
the OVN ML2 driver is maintained as an in-tree driver in Neutron.  On OpenStack
Train it is maintained separately as the ``networking-ovn`` plugin.

# Usage

OVN makes use of Public Key Infrastructure (PKI) to authenticate and authorize
control plane communication.  The charm requires a Certificate Authority to be
present in the model as represented by the `certificates` relation.

The [OpenStack Base bundle][openstack-base-bundle] gives an example of how you
can deploy OpenStack and OVN with [Vault][charm-vault] to automate certificate
lifecycle management.

Please refer to the [OVN Appendix][ovn-cdg] in the
[OpenStack Charms Deployment Guide][cdg] for details.

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

Please report bugs on [Launchpad][lp-neutron-api-plugin-ovn].

For general questions please refer to the OpenStack [Charm Guide][cg].

<!-- LINKS -->

[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/
[ovn-cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-ovn.html
[cg]: https://docs.openstack.org/charm-guide/latest/
[lp-neutron-api-plugin-ovn]: https://bugs.launchpad.net/charm-neutron-api-plugin-ovn/+filebug
[charm-vault]: https://jaas.ai/vault/
[openstack-base-bundle]: https://github.com/openstack-charmers/openstack-bundles/blob/master/development/openstack-base-bionic-ussuri-ovn/bundle.yaml
