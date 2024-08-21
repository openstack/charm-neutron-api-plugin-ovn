# Copyright 2020 Canonical Ltd
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
import sys
import unittest.mock as mock

sys.path.append('src')

import charms_openstack.test_utils as test_utils

import actions.actions as actions


class FakeCalledProcess(object):

    returncode = 0
    stdout = 'fake-output-on-stdout'
    stderr = 'fake-output-on-stderr'


class TestActions(test_utils.PatchHelper):

    def test_neutron_credentials(self):
        self.patch_object(actions.cfg, 'ConfigParser')
        parser = mock.MagicMock()
        self.maxDiff = None

        expect = {
            'OS_USER_DOMAIN_NAME': 'fake-user-domain-name',
            'OS_PROJECT_DOMAIN_NAME': 'fake-project-domain-name',
            'OS_AUTH_URL': 'fake-auth-url',
            'OS_PROJECT_NAME': 'fake-project-name',
            'OS_USERNAME': 'fake-username',
            'OS_PASSWORD': 'fake-password',
        }

        def _fakeparser(x, y):
            y.update(
                {
                    'keystone_authtoken': {
                        'user_domain_name': ['fake-user-domain-name'],
                        'project_domain_name': ['fake-project-domain-name'],
                        'auth_url': ['fake-auth-url'],
                        'project_name': ['fake-project-name'],
                        'username': ['fake-username'],
                        'password': ['fake-password'],
                    },
                })
            return parser

        self.ConfigParser.side_effect = _fakeparser
        self.assertDictEqual(actions.get_neutron_credentials(), expect)
        self.ConfigParser.assert_called_once_with(
            '/etc/neutron/neutron.conf', mock.ANY)

    def test_migrate_mtu(self):
        self.patch_object(actions.ch_core.hookenv, 'action_get')
        self.action_get.return_value = False
        self.patch_object(actions.subprocess, 'run')
        fcp = FakeCalledProcess()
        self.run.return_value = fcp
        self.patch_object(actions, 'get_neutron_credentials')
        self.get_neutron_credentials.return_value = {
            'fake-creds': 'from-neutron'}
        self.patch('builtins.print', name='builtin_print')
        self.patch_object(actions.ch_core.hookenv, 'action_fail')

        actions.migrate_mtu(['/some/path/migrate-mtu'])
        self.run.assert_called_once_with(
            (
                'neutron-ovn-migration-mtu',
                'verify',
                'mtu',
            ),
            capture_output=True,
            universal_newlines=True,
            env={
                'PATH': '/usr/bin',
                'fake-creds': 'from-neutron',
            })
        self.builtin_print.assert_has_calls([
            mock.call('migrate-mtu: OUTPUT FROM VERIFY ON STDOUT:\n'
                      'fake-output-on-stdout',
                      file=mock.ANY),
            mock.call('migrate-mtu: OUTPUT FROM VERIFY ON STDERR:\n'
                      'fake-output-on-stderr',
                      file=mock.ANY),
        ])
        self.run.reset_mock()
        self.builtin_print.reset_mock()
        self.action_get.return_value = True
        actions.migrate_mtu(['/some/path/migrate-mtu'])
        self.run.assert_called_once_with(
            (
                'neutron-ovn-migration-mtu',
                'update',
                'mtu',
            ),
            capture_output=True,
            universal_newlines=True,
            env={
                'PATH': '/usr/bin',
                'fake-creds': 'from-neutron',
            })
        self.builtin_print.assert_has_calls([
            mock.call('migrate-mtu: OUTPUT FROM UPDATE ON STDOUT:\n'
                      'fake-output-on-stdout',
                      file=mock.ANY),
            mock.call('migrate-mtu: OUTPUT FROM UPDATE ON STDERR:\n'
                      'fake-output-on-stderr',
                      file=mock.ANY),
        ])
        # check that errors are detected
        fcp.returncode = 1
        actions.migrate_mtu(['/some/path/migrate-mtu'])
        self.action_fail.assert_called_once()
        fcp.returncode = 0
        self.action_fail.reset_mock()
        fcp.stderr = 'Traceback'
        actions.migrate_mtu(['/some/path/migrate-mtu'])
        self.action_fail.assert_called_once()
        self.action_fail.reset_mock()
        fcp.stderr = 'Exception'
        actions.migrate_mtu(['/some/path/migrate-mtu'])
        self.action_fail.assert_called_once()

    def test_migrate_ovn_db(self):
        self.patch_object(actions.ch_core.hookenv, 'action_get')
        self.action_get.return_value = False
        self.patch_object(actions.subprocess, 'run')

        fcp = FakeCalledProcess()
        self.run.return_value = fcp
        self.patch('builtins.print', name='builtin_print')
        self.patch_object(actions.ch_core.hookenv, 'action_fail')
        # NOTE: strictly speaking these really belong to a unit test for the
        # write_filtered_neutron_config_for_sync_util helper but since it
        # exists only to work around a bug let's just mock them here for
        # simplicity and remove it again when the bug is fixed.
        self.patch_object(actions.os, 'umask')
        self.patch_object(actions.os, 'unlink')

        with mock.patch('builtins.open', create=True):
            actions.migrate_ovn_db(['/some/path/migrate-ovn-db'])
            self.run.assert_called_once_with(
                (
                    'neutron-ovn-db-sync-util',
                    '--config-file', '/etc/neutron/neutron-ovn-db-sync.conf',
                    '--config-file', '/etc/neutron/plugins/ml2/ml2_conf.ini',
                    '--ovn-neutron_sync_mode', 'log',
                ),
                capture_output=True,
                universal_newlines=True,
            )
            self.builtin_print.assert_has_calls([
                mock.call('migrate-ovn-db: OUTPUT FROM DRY-RUN ON STDOUT:\n'
                          'fake-output-on-stdout',
                          file=mock.ANY),
                mock.call('migrate-ovn-db: OUTPUT FROM DRY-RUN ON STDERR:\n'
                          'fake-output-on-stderr',
                          file=mock.ANY),
            ])
            self.run.reset_mock()
            self.builtin_print.reset_mock()
            self.action_get.return_value = True
            actions.migrate_ovn_db(['/some/path/migrate-ovn-db'])
            self.run.assert_called_once_with(
                (
                    'neutron-ovn-db-sync-util',
                    '--config-file', '/etc/neutron/neutron-ovn-db-sync.conf',
                    '--config-file', '/etc/neutron/plugins/ml2/ml2_conf.ini',
                    '--ovn-neutron_sync_mode', 'repair',
                ),
                capture_output=True,
                universal_newlines=True,
            )
            self.builtin_print.assert_has_calls([
                mock.call('migrate-ovn-db: OUTPUT FROM SYNC ON STDOUT:\n'
                          'fake-output-on-stdout',
                          file=mock.ANY),
                mock.call('migrate-ovn-db: OUTPUT FROM SYNC ON STDERR:\n'
                          'fake-output-on-stderr',
                          file=mock.ANY),
            ])
            # check that errors are detected
            fcp.returncode = 1
            actions.migrate_ovn_db(['/some/path/migrate-ovn-db'])
            self.action_fail.assert_called_once()
            fcp.returncode = 0
            self.action_fail.reset_mock()
            fcp.stderr = 'ERROR'
            actions.migrate_ovn_db(['/some/path/migrate-ovn-db'])
            self.action_fail.assert_called_once()

    def test_get_neutron_db_connection_string(self):
        self.patch_object(actions.cfg, 'ConfigParser')
        parser = mock.MagicMock()
        self.maxDiff = None

        def _fakeparser(x, y):
            y.update(
                {
                    'database': {
                        'connection': ['fake-connection'],
                    },
                })
            return parser

        self.ConfigParser.side_effect = _fakeparser
        self.assertEqual(
            actions.get_neutron_db_connection_string(), 'fake-connection')

    def test_offline_neutron_morph_db(self):
        self.patch_object(actions.ch_core.hookenv, 'action_get')
        self.action_get.return_value = False
        self.patch_object(actions.subprocess, 'run')
        self.patch_object(actions.ch_core.hookenv, 'charm_dir')
        self.charm_dir.return_value = '/path/to/charm'
        self.patch_object(actions, 'get_neutron_db_connection_string')
        self.get_neutron_db_connection_string.return_value = 'fake-connection'

        fcp = FakeCalledProcess()
        self.run.return_value = fcp
        self.patch('builtins.print', name='builtin_print')
        self.patch_object(actions.ch_core.hookenv, 'action_fail')

        actions.offline_neutron_morph_db(
            ['/some/path/offline-neutron-morph-db'])
        self.run.assert_called_once_with(
            (
                os.path.join(
                    '/path/to/charm/',
                    'files/scripts/neutron_offline_network_type_update.py'),
                'fake-connection',
                'dry',
            ),
            capture_output=True,
            universal_newlines=True,
            env={'PATH': '/usr/bin'},
        )
        self.builtin_print.assert_has_calls([
            mock.call('offline-neutron-morph-db: OUTPUT FROM DRY-RUN ON '
                      'STDOUT:\nfake-output-on-stdout',
                      file=mock.ANY),
            mock.call('offline-neutron-morph-db: OUTPUT FROM DRY-RUN ON '
                      'STDERR:\nfake-output-on-stderr',
                      file=mock.ANY),
        ])
        self.run.reset_mock()
        self.action_get.return_value = True
        actions.offline_neutron_morph_db(
            ['/some/path/offline-neutron-morph-db'])
        self.run.assert_called_once_with(
            (
                os.path.join(
                    '/path/to/charm/',
                    'files/scripts/neutron_offline_network_type_update.py'),
                'fake-connection',
                'morph',
            ),
            capture_output=True,
            universal_newlines=True,
            env={'PATH': '/usr/bin'},
        )
        self.builtin_print.assert_has_calls([
            mock.call('offline-neutron-morph-db: OUTPUT FROM MORPH ON '
                      'STDOUT:\nfake-output-on-stdout',
                      file=mock.ANY),
            mock.call('offline-neutron-morph-db: OUTPUT FROM MORPH ON '
                      'STDERR:\nfake-output-on-stderr',
                      file=mock.ANY),
        ])
        # check that errors are detected
        fcp.returncode = 1
        actions.offline_neutron_morph_db(
            ['/some/path/offline-neutron-morph-db'])
        self.action_fail.assert_called_once()
