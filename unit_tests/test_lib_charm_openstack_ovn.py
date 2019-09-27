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
import os

import charms_openstack.test_utils as test_utils

import charm.openstack.ovn as ovn


class TestOVNConfigProperties(test_utils.PatchHelper):

    def test_cluster_local_addr(self):
        self.patch_object(ovn.ch_core.hookenv, 'unit_get')
        cls = mock.MagicMock()
        self.assertEquals(ovn.cluster_local_addr(cls), self.unit_get())

    def test_db_nb_port(self):
        cls = mock.MagicMock()
        self.assertEquals(ovn.db_nb_port(cls), ovn.DB_NB_PORT)

    def test_db_sb_port(self):
        cls = mock.MagicMock()
        self.assertEquals(ovn.db_sb_port(cls), ovn.DB_SB_PORT)


class Helper(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.patch_release(ovn.OVNCharm.release)


class TestOVNCharm(Helper):

    def test_install(self):
        self.patch_object(ovn.charms_openstack.charm.OpenStackCharm,
                          'install')
        self.patch_object(ovn.os.path, 'islink')
        self.islink.return_value = False
        self.patch_object(ovn.os, 'symlink')
        c = ovn.OVNCharm()
        c.install()
        self.islink.assert_called_once_with(
            '/etc/systemd/system/ovn-central.service')
        self.symlink.assert_called_once_with(
            '/dev/null',
            '/etc/systemd/system/ovn-central.service')
        self.install.assert_called_once_with()

    def test__default_port_list(self):
        c = ovn.OVNCharm()
        self.assertEquals(
            c._default_port_list(),
            [ovn.DB_NB_PORT, ovn.DB_SB_PORT])

    def test_ports_to_check(self):
        c = ovn.OVNCharm()
        c._default_port_list = mock.MagicMock()
        c.ports_to_check()
        c._default_port_list.assert_called_once_with()

    def test_enable_services(self):
        self.patch_object(ovn.ch_core.host, 'service_resume')
        c = ovn.OVNCharm()
        c.check_if_paused = mock.MagicMock()
        c.check_if_paused.return_value = ('status', 'message')
        c.enable_services()
        c.check_if_paused.assert_called_once_with()
        self.assertFalse(self.service_resume.called)
        c.check_if_paused.return_value = (None, None)
        c.enable_services()
        self.service_resume.assert_called_once_with('ovn-central')

    def test_ovs_controller_cert(self):
        c = ovn.OVNCharm()
        self.assertEquals(
            c.ovs_controller_cert,
            os.path.join(ovn.OVS_ETCDIR, 'cert_host'))

    def test_ovs_controller_key(self):
        c = ovn.OVNCharm()
        self.assertEquals(
            c.ovs_controller_key,
            os.path.join(ovn.OVS_ETCDIR, 'key_host'))

    def test_run(self):
        self.patch_object(ovn.subprocess, 'run')
        self.patch_object(ovn.ch_core.hookenv, 'log')
        c = ovn.OVNCharm()
        c.run('some', 'args')
        self.run.assert_called_once_with(
            ('some', 'args'),
            stdout=ovn.subprocess.PIPE,
            stderr=ovn.subprocess.STDOUT,
            check=True,
            universal_newlines=True)

    def test_configure_tls(self):
        self.patch_object(ovn.ch_core.hookenv, 'service_name')
        self.service_name.return_value = 'fakeservice'
        self.patch_object(ovn.charms_openstack.charm.OpenStackCharm,
                          'configure_tls')
        self.configure_tls.return_value = [{
            'cert': 'fakecert',
            'key': 'fakekey',
            'cn': 'fakecn',
        }]
        c = ovn.OVNCharm()
        c.configure_cert = mock.MagicMock()
        c.run = mock.MagicMock()
        c.configure_tls()
        self.configure_tls.assert_called_once_with(certificates_interface=None)
        c.configure_cert.assert_called_once_with(
            ovn.OVS_ETCDIR,
            'fakecert',
            'fakekey',
            cn='host')
        c.run.assert_has_calls([
            mock.call('ovs-vsctl',
                      'set-ssl',
                      '/etc/openvswitch/key_host',
                      '/etc/openvswitch/cert_host',
                      '/usr/local/share/ca-certificates/fakeservice.crt'),
            mock.call('ovn-nbctl',
                      'set-ssl',
                      '/etc/openvswitch/key_host',
                      '/etc/openvswitch/cert_host',
                      '/usr/local/share/ca-certificates/fakeservice.crt'),
            mock.call('ovn-sbctl',
                      'set-ssl',
                      '/etc/openvswitch/key_host',
                      '/etc/openvswitch/cert_host',
                      '/usr/local/share/ca-certificates/fakeservice.crt'),
            mock.call('ovn-nbctl',
                      'set-connection',
                      'pssl:6641'),
            mock.call('ovn-sbctl',
                      'set-connection',
                      'role=ovn-controller',
                      'pssl:6642'),
            mock.call('ovs-vsctl',
                      'set',
                      'open',
                      '.',
                      'external-ids:ovn-remote=ssl:127.0.0.1:6642')
        ])
