#
# KCM responder integration tests
#
# Copyright (c) 2016 Red Hat, Inc.
#
# This is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 only
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import os
import os.path
import stat
import subprocess
import pytest
import socket
import time
import signal

import kdc
import krb5utils
import config
from util import unindent, run_shell

class KcmTestEnv(object):
    def __init__(self, k5kdc, k5util):
        self.k5kdc = k5kdc
        self.k5util = k5util
        self.counter = 0

    def my_uid(self):
        s_myuid = os.environ['NON_WRAPPED_UID']
        return int(s_myuid)

    def ccname(self, my_uid=None):
        if my_uid is None:
            my_uid = self.my_uid()

        return "KCM:%d" % my_uid


@pytest.fixture(scope="module")
def kdc_instance(request):
    """Kerberos server instance fixture"""
    kdc_instance = kdc.KDC(config.PREFIX, "KCMTEST")
    try:
        kdc_instance.set_up()
        kdc_instance.start_kdc()
    except:
        kdc_instance.teardown()
        raise
    request.addfinalizer(kdc_instance.teardown)
    return kdc_instance


def create_conf_fixture(request, contents):
    """Generate sssd.conf and add teardown for removing it"""
    with open(config.CONF_PATH, "w") as conf:
        conf.write(contents)
    os.chmod(config.CONF_PATH, stat.S_IRUSR | stat.S_IWUSR)
    request.addfinalizer(lambda: os.unlink(config.CONF_PATH))


def create_sssd_kcm_fixture(sock_path, request):
    if subprocess.call(['sssd', "--genconf"]) != 0:
        raise Exception("failed to regenerate confdb")

    resp_path = os.path.join(config.LIBEXEC_PATH, "sssd", "sssd_kcm")
    if not os.access(resp_path, os.X_OK):
        # It would be cleaner to use pytest.mark.skipif on the package level
        # but upstream insists on supporting RHEL-6..
        pytest.skip("No KCM responder, skipping")

    kcm_pid = os.fork()
    assert kcm_pid >= 0

    if kcm_pid == 0:
        if subprocess.call([resp_path, "--uid=0", "--gid=0"]) != 0:
            print("sssd_kcm failed to start")
            sys.exit(99)
    else:
        abs_sock_path = os.path.join(config.RUNSTATEDIR, sock_path)
        sck = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        for _ in range(1, 10):
            try:
                sck.connect(abs_sock_path)
            except:
                time.sleep(0.1)
            else:
                break
        sck.close()
        assert os.path.exists(abs_sock_path)

    def kcm_teardown():
        if kcm_pid == 0:
            return
        os.kill(kcm_pid, signal.SIGTERM)

    request.addfinalizer(kcm_teardown)
    return kcm_pid


@pytest.fixture
def setup_for_kcm(request, kdc_instance):
    """
    Just set up the local provider for tests and enable the KCM
    responder
    """
    kcm_path = os.path.join(config.RUNSTATEDIR, "kcm.socket")

    sssd_conf = unindent("""\
        [sssd]
        domains = local
        services = nss

        [domain/local]
        id_provider = local

        [kcm]
        socket_path = {kcm_path}
    """).format(**locals())

    kcm_socket_include = unindent("""
    [libdefaults]
    default_ccache_name = KCM:
    kcm_socket = {kcm_path}
    """).format(**locals())
    kdc_instance.add_config({'kcm_socket': kcm_socket_include})

    create_conf_fixture(request, sssd_conf)
    create_sssd_kcm_fixture(kcm_path, request)

    k5util = krb5utils.Krb5Utils(kdc_instance.krb5_conf_path)

    return KcmTestEnv(kdc_instance, k5util)


def test_kcm_init_list_destroy(setup_for_kcm):
    """
    Test that kinit, kdestroy and klist work with KCM
    """
    testenv = setup_for_kcm
    testenv.k5kdc.add_principal("kcmtest", "Secret123")

    ok = testenv.k5util.has_principal("kcmtest@KCMTEST")
    assert ok is False
    nprincs = testenv.k5util.num_princs()
    assert nprincs == 0

    out, _, _ = testenv.k5util.kinit("kcmtest", "Secret123")
    assert out == 0
    nprincs = testenv.k5util.num_princs()
    assert nprincs == 1

    exp_ccname = testenv.ccname()
    ok = testenv.k5util.has_principal("kcmtest@KCMTEST", exp_ccname)
    assert ok is True

    out = testenv.k5util.kdestroy()
    assert out == 0

    ok = testenv.k5util.has_principal("kcmtest@KCMTEST")
    assert ok is False
    nprincs = testenv.k5util.num_princs()
    assert nprincs == 0


def test_kcm_overwrite(setup_for_kcm):
    """
    That that reusing a ccache reinitializes the cache and doesn't
    add the same principal twice
    """
    testenv = setup_for_kcm
    testenv.k5kdc.add_principal("kcmtest", "Secret123")
    exp_ccache = {'kcmtest@KCMTEST': ['krbtgt/KCMTEST@KCMTEST']}

    assert testenv.k5util.num_princs() == 0

    out, _, _ = testenv.k5util.kinit("kcmtest", "Secret123")
    assert out == 0
    assert exp_ccache == testenv.k5util.list_all_princs()

    out, _, _ = testenv.k5util.kinit("kcmtest", "Secret123")
    assert out == 0
    assert exp_ccache == testenv.k5util.list_all_princs()


def test_collection_init_list_destroy(setup_for_kcm):
    """
    Test that multiple principals and service tickets can be stored
    in a collection.
    """
    testenv = setup_for_kcm
    testenv.k5kdc.add_principal("alice", "alicepw")
    testenv.k5kdc.add_principal("bob", "bobpw")
    testenv.k5kdc.add_principal("carol", "carolpw")
    testenv.k5kdc.add_principal("host/somehostname")

    assert testenv.k5util.num_princs() == 0

    out, _, _ = testenv.k5util.kinit("alice", "alicepw")
    assert out == 0
    assert testenv.k5util.default_principal() == 'alice@KCMTEST'
    cc_coll = testenv.k5util.list_all_princs()
    assert len(cc_coll) == 1
    assert cc_coll['alice@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']
    assert 'bob@KCMTEST' not in cc_coll
    assert 'carol@KCMTEST' not in cc_coll

    out, _, _ = testenv.k5util.kinit("bob", "bobpw")
    assert out == 0
    assert testenv.k5util.default_principal() == 'bob@KCMTEST'
    cc_coll = testenv.k5util.list_all_princs()
    assert len(cc_coll) == 2
    assert cc_coll['alice@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']
    assert cc_coll['bob@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']
    assert 'carol@KCMTEST' not in cc_coll

    out, _, _ = testenv.k5util.kinit("carol", "carolpw")
    assert out == 0
    assert testenv.k5util.default_principal() == 'carol@KCMTEST'
    cc_coll = testenv.k5util.list_all_princs()
    assert len(cc_coll) == 3
    assert cc_coll['alice@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']
    assert cc_coll['bob@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']
    assert cc_coll['carol@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']

    out, _, _ = testenv.k5util.kvno('host/somehostname')
    assert out == 0
    cc_coll = testenv.k5util.list_all_princs()
    assert len(cc_coll) == 3
    assert set(cc_coll['carol@KCMTEST']) == set(['krbtgt/KCMTEST@KCMTEST',
                                                 'host/somehostname@KCMTEST'])

    out = testenv.k5util.kdestroy()
    assert out == 0
    assert testenv.k5util.default_principal() == 'bob@KCMTEST'
    cc_coll = testenv.k5util.list_all_princs()
    assert len(cc_coll) == 2
    assert cc_coll['alice@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']
    assert cc_coll['bob@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']
    assert 'carol@KCMTEST' not in cc_coll

    # FIXME - a bug in libkrb5?
    #out = testenv.k5util.kdestroy(all_ccaches=True)
    #assert out == 0
    #cc_coll = testenv.k5util.list_all_princs()
    #assert len(cc_coll) == 0


def test_kswitch(setup_for_kcm):
    """
    Test switching between principals
    """
    testenv = setup_for_kcm
    testenv.k5kdc.add_principal("alice", "alicepw")
    testenv.k5kdc.add_principal("bob", "bobpw")
    testenv.k5kdc.add_principal("host/somehostname")
    testenv.k5kdc.add_principal("host/differenthostname")

    out, _, _ = testenv.k5util.kinit("alice", "alicepw")
    assert out == 0
    assert testenv.k5util.default_principal() == 'alice@KCMTEST'

    out, _, _ = testenv.k5util.kinit("bob", "bobpw")
    assert out == 0
    assert testenv.k5util.default_principal() == 'bob@KCMTEST'

    cc_coll = testenv.k5util.list_all_princs()
    assert len(cc_coll) == 2
    assert cc_coll['alice@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']
    assert cc_coll['bob@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']

    out = testenv.k5util.kswitch("alice@KCMTEST")
    assert testenv.k5util.default_principal() == 'alice@KCMTEST'
    out, _, _ = testenv.k5util.kvno('host/somehostname')
    assert out == 0
    cc_coll = testenv.k5util.list_all_princs()
    assert len(cc_coll) == 2
    assert set(cc_coll['alice@KCMTEST']) == set(['krbtgt/KCMTEST@KCMTEST',
                                                 'host/somehostname@KCMTEST'])
    assert cc_coll['bob@KCMTEST'] == ['krbtgt/KCMTEST@KCMTEST']

    out = testenv.k5util.kswitch("bob@KCMTEST")
    assert testenv.k5util.default_principal() == 'bob@KCMTEST'
    out, _, _ = testenv.k5util.kvno('host/differenthostname')
    assert out == 0
    cc_coll = testenv.k5util.list_all_princs()
    assert len(cc_coll) == 2
    assert set(cc_coll['alice@KCMTEST']) == set(['krbtgt/KCMTEST@KCMTEST',
                                                 'host/somehostname@KCMTEST'])
    assert set(cc_coll['bob@KCMTEST']) == set([
                                    'krbtgt/KCMTEST@KCMTEST',
                                    'host/differenthostname@KCMTEST'])


def test_subsidiaries(setup_for_kcm):
    """
    Test that subsidiary caches are usable and KCM: without specifying UID
    can be used to identify the collection
    """
    testenv = setup_for_kcm
    testenv.k5kdc.add_principal("alice", "alicepw")
    testenv.k5kdc.add_principal("bob", "bobpw")
    testenv.k5kdc.add_principal("host/somehostname")
    testenv.k5kdc.add_principal("host/differenthostname")

    out, _, _ = testenv.k5util.kinit("alice", "alicepw")
    assert out == 0
    out, _, _ = testenv.k5util.kvno('host/somehostname')

    out, _, _ = testenv.k5util.kinit("bob", "bobpw")
    assert out == 0
    out, _, _ = testenv.k5util.kvno('host/differenthostname')

    exp_cc_coll = dict()
    exp_cc_coll['alice@KCMTEST'] = 'host/somehostname@KCMTEST'
    exp_cc_coll['bob@KCMTEST'] = 'host/differenthostname@KCMTEST'

    klist_l = testenv.k5util.list_princs()
    princ_ccache = dict()
    for line in klist_l:
        princ, subsidiary = line.split()
        princ_ccache[princ] = subsidiary

    for princ, subsidiary in princ_ccache.items():
        env = {'KRB5CCNAME': subsidiary}
        cc_coll = testenv.k5util.list_all_princs(env=env)
        assert len(cc_coll) == 1
        assert princ in cc_coll
        assert exp_cc_coll[princ] in cc_coll[princ]

    cc_coll = testenv.k5util.list_all_princs(env={'KRB5CCNAME': 'KCM:'})
    assert len(cc_coll) == 2
    assert set(cc_coll['alice@KCMTEST']) == set(['krbtgt/KCMTEST@KCMTEST',
                                                 'host/somehostname@KCMTEST'])
    assert set(cc_coll['bob@KCMTEST']) == set([
                                            'krbtgt/KCMTEST@KCMTEST',
                                            'host/differenthostname@KCMTEST'])


def test_kdestroy_nocache(setup_for_kcm):
    """
    Destroying a non-existing ccache should not throw an error
    """
    testenv = setup_for_kcm
    testenv.k5kdc.add_principal("alice", "alicepw")
    out, _, _ = testenv.k5util.kinit("alice", "alicepw")
    assert out == 0

    testenv.k5util.kdestroy()
    assert out == 0
    out = testenv.k5util.kdestroy()
    assert out == 0