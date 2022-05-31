#!/usr/bin/env python3

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

"""neutron_offline_network_type_update

The purpose of this module is to provide a tool that allow the user to perform
Neutron database surgery to change the type of tunnel networks from 'gre' and
'vxlan' to 'geneve'.

It is an optional part of a migration from a legacy Neutron ML2+OVS to ML2+OVN
deployment.

At the time of this writing the Neutron OVN ML2 driver will assume that all
chassis participating in a network to use the 'geneve' tunnel protocol and it
will ignore the value of the `network_type` field in any non-physical network
in the Neutron database. It will also ignore the `segmentation_id` field and
let OVN assign the VNIs [0].

The Neutron API currently does not support changing the type of a network, so
when doing a migration the above described behaviour is actually a welcomed
one.

However, after the migration is done and all the primary functions are working,
the end user of the cloud will be left with the false impression of their
existing 'gre' or 'vxlan' typed networks still being operational on said tunnel
protocols. In reality 'geneve' is used under the hood.

The end user will also run into issues with modifying any existing networks
with `openstack network set` throwing error messages about networks of type
'gre' or 'vxlan' not being supported.

After running this script said networks will have their `network_type` field
changed to 'geneve' which will fix the above described problems.

NOTE: Use this script with caution, it is of absolute importance that the
      `neutron-server` process is stopped while the script is running.

NOTE: While we regularly exercise the script as part of our functional testing
      of the charmed migration path and the script is touching fundamental data
      structures that are not likely to have their definition changed much in
      the Neutron database, we would still advise you to take a fresh backup of
      the Neutron database and keep it for a while just in case.

0: https://github.com/ovn-org/ovn/blob/1e07781310d8155997672bdce01a2ff4f5a93e83/northd/ovn-northd.c#L1188-L1268
"""  # noqa

import os
import sys

from oslo_db.sqlalchemy import session

import sqlalchemy


class NotFound(Exception):
    pass


def main(argv):
    """Main function.

    :param argv: Argument list
    :type argv: List[str]
    :returns: POSIX exit code
    :rtype: int
    """
    program = os.path.basename(argv[0])
    if len(argv) < 2:
        usage(program)
        return os.EX_USAGE
    elif len(argv) < 3 or argv[2] != 'morph':
        print('DRY-RUN, WILL NOT COMMIT TRANSACTION')

    db_engine = session.create_engine(argv[1])
    db_maker = session.get_maker(db_engine, autocommit=False)
    db_session = db_maker(bind=db_engine)

    to_network_type = 'geneve'
    for network_type in ('gre', 'vxlan'):
        n_morphed = morph_networks(db_session, network_type, to_network_type)
        print('Morphed {} networks of type {} to {}.'
              .format(n_morphed, network_type, to_network_type))

    if len(argv) < 3 or argv[2] != 'morph':
        print('DRY-RUN, WILL NOT COMMIT TRANSACTION')
        return os.EX_USAGE

    db_session.commit()
    db_session.close()
    db_engine.dispose()
    return os.EX_OK


def usage(program):
    """Print information about how to use program.

    :param program: Name of program
    :type program: str
    """
    print('usage {} db-connection-string [morph]\n'
          '\n'
          'Morph non-physical networks of type "gre" and "vxlan" into '
          'geneve networks.\n'
          '\n'
          'The Neutron database must already have enough free "geneve" VNIs\n'
          'before running this tool. If the process stops because there are\n'
          'no more VNIs, increase the VNI range with the `vni_ranges`\n'
          'configuration option on the `ml2_type_geneve` section and then\n'
          'start and stop the neutron-server before trying again.\n'
          '\n'
          'The second argument must be the literal string "morph" for the\n'
          'tool to perform an action, otherwise it will not commit the\n'
          'transaction to the database, effectively performing a dry run.\n'
          ''.format(program),
          file=sys.stderr)


def vni_row_name(network_type):
    """Determine name of row for VNI in allocations table.

    :param network_type: Network type to determine row name for.
    :type network_type: str
    :returns: Row name
    :rtype: str
    :raises: ValueError
    """
    if network_type in ('gre',):
        return '{}_id'.format(network_type)
    elif network_type in ('geneve', 'vxlan'):
        return '{}_vni'.format(network_type)
    raise ValueError('Unsupported network_type: {}'.format(network_type))


def allocate_segment(db_session, network_type):
    """Allocate VNI for network_type.

    :param db_session: SQLAlchemy DB Session object.
    :type db_session: SQLAlchemy DB Session object.
    :param network_type: Network type to allocate vni for.
    :type network_type: str
    :returns: Allocated VNI
    :rtype: int
    """
    alloc_table = 'ml2_{}_allocations'.format(network_type)
    vni_row = vni_row_name(network_type)

    # Get next available VNI
    vni = None
    stmt = sqlalchemy.text(
        'SELECT MIN({}) FROM {}  WHERE allocated=0'
        .format(vni_row, alloc_table))
    rs = db_session.execute(stmt)
    for row in rs:
        if hasattr(row, 'itervalues'):
            vni = next(row.itervalues())
        else:
            vni = next(iter(row))
        # A aggregated query will always provide a result, check for NULL
        if vni is None:
            raise NotFound(
                'unable to allocate "{}" segment.'.format(network_type))
        break

    # Allocate VNI
    stmt = sqlalchemy.text(
        'UPDATE {} SET allocated=1 WHERE {}=:vni'.format(alloc_table, vni_row))
    db_session.execute(stmt, {'vni': vni})
    return vni


def deallocate_segment(db_session, network_type, vni):
    """Deallocate VNI for network_type.

    :param db_session: SQLAlchemy DB Session object.
    :type db_session: SQLAlchemy DB Session object.
    :param network_type: Network type to de-allocate vni for.
    :type network_type: str
    :param vni: VNI
    :type vni: int
    """
    alloc_table = 'ml2_{}_allocations'.format(network_type)
    vni_row = vni_row_name(network_type)

    # De-allocate VNI
    stmt = sqlalchemy.text(
        'UPDATE {} SET allocated=0 WHERE {}=:vni'.format(alloc_table, vni_row))
    db_session.execute(stmt, {'vni': vni})


def get_network_segments(db_session, network_type):
    """Get tunnel networks of certain type.

    :param db_session: SQLAlchemy DB Session object.
    :type db_session: SQLAlchemy DB Session object.
    :param network_type: Network type to iterate over.
    :type network_type: str
    :returns: Iterator for data
    :rtype: Iterator[str,str,str,int]
    """
    # Get networks
    stmt = sqlalchemy.text(
        'SELECT id,network_id,network_type,segmentation_id '
        'FROM networksegments '
        'WHERE physical_network IS NULL AND '
        '      network_type=:network_type')
    rs = db_session.execute(stmt, {'network_type': network_type})
    for row in rs:
        if hasattr(row, 'values'):
            yield row.values()
        else:
            yield row


def morph_networks(db_session, from_network_type, to_network_type):
    """Morph all networks of one network type to another.

    :param db_session: SQLAlchemy DB Session object.
    :type db_session: SQLAlchemy DB Session object.
    :param from_network_type: Network type to morph from.
    :type from_network_type: str
    :param to_network_type: Network type to morph to.
    :type to_network_type: str
    :returns: Number of networks morphed
    :rtype: int
    """
    stmt = sqlalchemy.text(
        'UPDATE networksegments '
        'SET network_type=:new_network_type,segmentation_id=:new_vni '
        'WHERE id=:id')
    n_morphed = 0
    for segment_id, network_id, network_type, vni in get_network_segments(
            db_session, from_network_type):
        new_vni = allocate_segment(db_session, to_network_type)
        db_session.execute(stmt, {
            'new_network_type': to_network_type,
            'new_vni': new_vni,
            'id': segment_id,
        })
        print('segment {} for network {} changed from {}:{} to {}:{}'
              .format(segment_id, network_id, network_type, vni,
                      to_network_type, new_vni))
        deallocate_segment(db_session, from_network_type, vni)
        n_morphed += 1
    return n_morphed


if __name__ == '__main__':
    sys.exit(main(sys.argv))
