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
import subprocess

import charms.reactive as reactive

import charmhelpers.core as ch_core

import charms_openstack.adapters
import charms_openstack.charm


class NeutronAPIPluginOvn(charms_openstack.charm.OpenStackCharm):
    release = 'train'
    name = 'ovn'
    packages = ['python3-networking-ovn']
    required_relations = ['neutron-plugin', 'ovsdb-cms']
    python_version = 3
