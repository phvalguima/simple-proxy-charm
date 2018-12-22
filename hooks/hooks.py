#!/usr/bin/env python3

import hashlib
import json
import os
import sys

_path = os.path.dirname(os.path.realpath(__file__))
_root = os.path.abspath(os.path.join(_path, '..'))


def _add_path(path):
    if path not in sys.path:
        sys.path.insert(1, path)


_add_path(_root)

from subprocess import check_call

from charmhelpers.core import unitdata

from charmhelpers.core.hookenv import (
    config as config_get,
    Hooks,
    UnregisteredHookError,
    config,
    log,
    DEBUG,
    INFO,
    WARNING,
    relation_get,
    relation_ids,
    relation_set,
    related_units,
    status_set,
    open_port,
    is_leader,
    relation_id,
)

from charmhelpers.core.host import (
    service_pause,
    service_stop,
    service_start,
    service_restart,
)

from charmhelpers.payload.execd import execd_preinstall

from charmhelpers.fetch import (
    apt_install, apt_update,
    filter_installed_packages
)

from charmhelpers.contrib.openstack.ha.utils import (
    generate_ha_relation_data,
)

from jinja2 import Environment, FileSystemLoader


hooks = Hooks()
package_list=["haproxy"]

@hooks.hook('install.real')
def install():
    status_set("maintenance", "Installing apt packages...")
    execd_preinstall()
    apt_update()
    apt_install(package_list, fatal=True)
    config_changed()


@hooks.hook('config-changed')
def config_changed():
    status_set("maintenance", "Resetting configs...")

    if config_get("mode") is "balancer":
        config_balancer()
    else:
        config_proxy()
    
    for r_id in relation_ids('ha'):
        ha_joined(relation_id=r_id)
    if config_get("mode") is "balancer":
        status_set("active","Now balancing...")
    else:
        status_set("active", "Now proxying")


# TODO: build this function, choose a relation like haproxy charm
def config_balancer():
    return

def convert_ports_config():
    ports=config_get("proxy_port").split(",")
    port_ints=[]
    for p in ports:
        if ":" in p:
            port_ints.extend(range(int(p.split(":")[0]),int(p.split(":")[-1])+1))
        else:
            port_ints.append(int(p))
    port_ints.sort()
    return port_ints


def block_service(msg):
    status_set("blocked",msg)
    service_stop("haproxy")


def config_proxy():
    ports=config_get("proxy_port").split(",")
    port_ints=convert_ports_config()

    file_loader = FileSystemLoader("templates")
    env = Environment(loader=file_loader)
    fe_part = env.get_template("fe_part.tmpl")

    with open("/etc/haproxy/haproxy.cfg","w") as f:
        cfg=[]
        pcount=0
        if not port_ints:
            log("ports not defined, stopping...")
            block_service("proxy_port undefined, please define this config")
            return
        for b in config_get("backend_list").split(","):
            if pcount >= len(port_ints):
                log("WARNING: not enough port supplied")
                block_service("Not enough ports supplied")
                f.close()
                return
            cfg.append(fe_part.render(bind_port=port_ints[pcount],
                                      service_name="service_{}".format(pcount),
                                      backend=b))
            pcount+=1
        f.write("\n\n\n".join(cfg))
        f.close()
    service_restart("haproxy")


@hooks.hook('ha-relation-joined')
def ha_joined(relation_id=None):
    settings = generate_ha_relation_data('hpy')
    log("ha_joined: generated ha relation data is {}".format(settings))
    relation_set(relation_id=relation_id, **settings)

## TODO: add ha-relation-changed as charm-keystone, for example

def main():
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))


if __name__ == '__main__':
    main()
