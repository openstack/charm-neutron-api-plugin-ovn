#!/usr/local/sbin/charm-env python3
#
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

import contextlib
import os
import subprocess
import sys
import traceback

from oslo_config import cfg

# Load modules from $CHARM_DIR/lib
sys.path.append('lib')
sys.path.append('reactive')

from charms.layer import basic
basic.bootstrap_charm_deps()
basic.init_config_states()

import charms_openstack.bus

import charmhelpers.core as ch_core

charms_openstack.bus.discover()


NEUTRON_CONF = '/etc/neutron/neutron.conf'
NEUTRON_OVN_DB_SYNC_CONF = '/etc/neutron/neutron-ovn-db-sync.conf'


def get_neutron_credentials():
    """Retrieve service credentials from Neutron's configuration file.

    Since we are a subordinate of the neutron-api charm and have no direct
    relationship with Keystone ourselves we rely on gleaning Neutron's
    credentials from its config file.

    :returns: Map of environment variable name and appropriate value for auth.
    :rtype: Dict[str,str]
    """
    sections = {}
    parser = cfg.ConfigParser(NEUTRON_CONF, sections)
    parser.parse()
    auth_section = 'keystone_authtoken'
    return {
        'OS_USER_DOMAIN_NAME': sections[auth_section]['user_domain_name'][0],
        'OS_PROJECT_DOMAIN_NAME': sections[auth_section][
            'project_domain_name'][0],
        'OS_AUTH_URL': sections[auth_section]['auth_url'][0],
        'OS_PROJECT_NAME': sections[auth_section]['project_name'][0],
        'OS_USERNAME': sections[auth_section]['username'][0],
        'OS_PASSWORD': sections[auth_section]['password'][0],
    }


def get_neutron_db_connection_string():
    """Retrieve db connection string from Neutron's configuration file.

    Since we are a subordinate of the neutron-api charm and have no direct
    relationship with the database ourselves we rely on gleaning Neutron's
    credentials from its config file.

    :returns: SQLAlchemy consumable DB connection string.
    :rtype: str
    """
    sections = {}
    parser = cfg.ConfigParser(NEUTRON_CONF, sections)
    parser.parse()
    return sections['database']['connection'][0]


@contextlib.contextmanager
def write_filtered_neutron_config_for_sync_util():
    """This helper exists to work around LP: #1894048.

    Load neutron config and write out a copy with any sections or options
    offending the `neutron-ovn-db-sync-util` removed.

    The helper should be used as a context manager to have the temporary config
    file removed when done. Example:

        with write_filtered_neutron_config_for_sync_util():
            do_something()
    """
    # Make sure the file we create has safe permissions
    stored_mask = os.umask(0o0027)
    try:
        with open(NEUTRON_CONF, 'r') as fin:
            with open(NEUTRON_OVN_DB_SYNC_CONF, 'w') as fout:
                for line in fin.readlines():
                    # The ovn-db-sync-util chokes on this. LP: #1894048
                    if line.startswith('auth_section'):
                        continue
                    fout.write(line)
    finally:
        # Restore umask for further execution regardless of any exception
        # occurring above.
        os.umask(stored_mask)

    yield

    # remove the temporary config file
    os.unlink(NEUTRON_OVN_DB_SYNC_CONF)


def migrate_mtu(args):
    """Reduce MTU on overlay networks prior to migration to Geneve.

    :param args: Argument list
    :type args: List[str]
    """
    action_name = os.path.basename(args[0])
    dry_run = not ch_core.hookenv.action_get('i-really-mean-it')
    mode = 'verify' if dry_run else 'update'
    cp = subprocess.run(
        (
            'neutron-ovn-migration-mtu',
            mode,
            'mtu',
        ),
        capture_output=True,
        universal_newlines=True,
        env={
            'PATH': '/usr/bin',
            **get_neutron_credentials(),
        })
    if dry_run:
        banner_msg = '{}: OUTPUT FROM VERIFY'.format(action_name)
    else:
        banner_msg = '{}: OUTPUT FROM UPDATE'.format(action_name)

    # we pass the output through and it will be captured both in log and
    # action output
    output_indicates_failure = False
    for output_name in ('stdout', 'stderr'):
        fh = getattr(sys, output_name)
        data = getattr(cp, output_name)
        print('{} ON {}:\n'.format(banner_msg, output_name.upper()) + data,
              file=fh)
        for fail_word in ('Exception', 'Traceback'):
            if fail_word in data:
                # the `neutron-ovn-migration-mtu` tool does not set an error
                # code on failure, look for errors in the output and set action
                # status accordingly.
                output_indicates_failure = True

    if cp.returncode != 0 or output_indicates_failure:
        ch_core.hookenv.action_fail(
            'Execution failed, please investigate output.')


def migrate_ovn_db(args):
    """Migrate the Neutron DB into OVN with the `neutron-ovn-db-sync-util`.

    :param args: Argument list
    :type args: List[str]
    """
    action_name = os.path.basename(args[0])
    dry_run = not ch_core.hookenv.action_get('i-really-mean-it')
    sync_mode = 'log' if dry_run else 'repair'
    with write_filtered_neutron_config_for_sync_util():
        cp = subprocess.run(
            (
                'neutron-ovn-db-sync-util',
                '--config-file', NEUTRON_OVN_DB_SYNC_CONF,
                '--config-file', '/etc/neutron/plugins/ml2/ml2_conf.ini',
                '--ovn-neutron_sync_mode', sync_mode,
            ),
            capture_output=True,
            universal_newlines=True,
        )
    if dry_run:
        banner_msg = '{}: OUTPUT FROM DRY-RUN'.format(action_name)
    else:
        banner_msg = '{}: OUTPUT FROM SYNC'.format(action_name)

    # we pass the output through and it will be captured both in log and
    # action output
    output_indicates_failure = False
    for output_name in ('stdout', 'stderr'):
        fh = getattr(sys, output_name)
        data = getattr(cp, output_name)
        print('{} ON {}:\n'.format(banner_msg, output_name.upper()) + data,
              file=fh)
        if 'ERROR' in data:
            # the `neutron-ovn-db-sync-util` tool does not set an error code on
            # failure, look for errors in the output and set action status
            # accordingly.
            output_indicates_failure = True

    if cp.returncode != 0 or output_indicates_failure:
        ch_core.hookenv.action_fail(
            'Execution failed, please investigate output.')


def offline_neutron_morph_db(args):
    """Perform offline moprhing of tunnel networks in the Neutron DB.

    :param args: Argument list
    :type args: List[str]
    """
    action_name = os.path.basename(args[0])
    dry_run = not ch_core.hookenv.action_get('i-really-mean-it')
    mode = 'dry' if dry_run else 'morph'
    cp = subprocess.run(
        (
            '{}'.format(
                os.path.join(
                    ch_core.hookenv.charm_dir(),
                    'files/scripts/neutron_offline_network_type_update.py')),
            get_neutron_db_connection_string(),
            mode,
        ),
        capture_output=True,
        universal_newlines=True,
        # We want this tool to run outside of the charm venv to let it consume
        # system Python packages.
        env={'PATH': '/usr/bin'},
    )
    if dry_run:
        banner_msg = '{}: OUTPUT FROM DRY-RUN'.format(action_name)
    else:
        banner_msg = '{}: OUTPUT FROM MORPH'.format(action_name)

    # we pass the output through and it will be captured both in log and
    # action output
    for output_name in ('stdout', 'stderr'):
        fh = getattr(sys, output_name)
        data = getattr(cp, output_name)
        print('{} ON {}:\n'.format(banner_msg, output_name.upper()) + data,
              file=fh)

    if cp.returncode != 0:
        ch_core.hookenv.action_fail(
            'Execution failed, please investigate output.')


ACTIONS = {
    'migrate-mtu': migrate_mtu,
    'migrate-ovn-db': migrate_ovn_db,
    'offline-neutron-morph-db': offline_neutron_morph_db,
}


def main(args):
    action_name = os.path.basename(args[0])
    try:
        action = ACTIONS[action_name]
    except KeyError:
        return 'Action {} undefined'.format(action_name)
    else:
        try:
            action(args)
        except Exception as e:
            ch_core.hookenv.log('action "{}" failed: "{}" "{}"'
                                .format(action_name, str(e),
                                        traceback.format_exc()),
                                level=ch_core.hookenv.ERROR)
            ch_core.hookenv.action_fail(str(e))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
