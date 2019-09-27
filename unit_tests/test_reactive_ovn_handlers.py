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

import reactive.ovn_handlers as handlers

import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        defaults = [
            'charm.installed',
            'config.changed',
            'update-status',
            'upgrade-charm',
        ]
        hook_set = {
            'when': {
                'render': ('charm.installed',),
                'certificates_in_config_tls': ('config.rendered',
                                               'config.changed',),
            },
            'when_not_all': {
                'certificates_in_config_tls': ('config.default.ssl_ca',
                                               'config.default.ssl_cert',
                                               'config.default.ssl_key',),
            },
        }
        # test that the hooks were registered via the
        # reactive.ovn_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestOvnHandlers(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        # self.patch_release(octavia.OctaviaCharm.release)
        self.charm = mock.MagicMock()
        self.patch_object(handlers.charm, 'provide_charm_instance',
                          new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = \
            self.charm
        self.provide_charm_instance().__exit__.return_value = None

    def test_render(self):
        self.patch_object(handlers.charm, 'use_defaults')
        self.patch_object(handlers.reactive, 'set_flag')
        self.charm.enable_services.return_value = False
        handlers.render()
        self.charm.render_with_interfaces.assert_called_once_with([])
        self.charm.enable_services.assert_called_once_with()
        self.assertFalse(self.use_defaults.called)
        self.assertFalse(self.set_flag.called)
        self.charm.assess_status.assert_called_once_with()
        self.charm.enable_services.return_value = True
        handlers.render()
        self.use_defaults.assert_called_once_with('certificates.available')
        self.set_flag.assert_called_once_with('config.rendered')
