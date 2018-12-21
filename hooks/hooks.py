#!/usr/bin/env python3

from charmhelpers.core.hookenv import (
    Hooks,
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
    relation_id,
)

from charmhelpers.fetch import (
    apt_install, apt_update,
    filter_installed_packages
)

from charmhelpers.contrib.openstack.ha.utils import (
    generate_ha_relation_data,
)

from jinja2 import Environment, FileSystemLoader

from charmhelpers.core.host import (
    service_pause,
    service_stop,
    service_start,
    service_restart,
)

hooks = Hooks()
package_list=["haproxy"]

@hooks.hook('install')
def install():
    status_set("maintenance", "Installing apt packages...")
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
        status_set("Ready","Now balancing...")
    else:
        status_set("Ready", "Now proxying")


# TODO: build this function, choose a relation like haproxy charm
def config_balancer():
    return

def convert_ports_config():
    ports=config_get("proxy_port").split(",")
    port_ints=[]
    for p in ports:
        if ":" in p:
            port_ints.extend(range(int(p.split(":")[0]),int(p.split(":")[-1])))
        else:
            port_ints.append(int(p))
    return port_ints.sort()


def config_proxy():
    ports=config_get("proxy_port").split(",")
    port_ints=convert_ports_config()

    file_loader = FileSystemLoader("templates")
    env = Environment(loader=file_loader)
    fe_part = env.get_template("fe_part.tmpl")

    with open("/etc/haproxy/haproxy.cfg","w") as f:
        cfg=[]
        for b in config_get("backend_list").split(","):
            cfg.append(fe_part.render(bind_port=port_ints[pcount],
                                      service_name="service_%s".format(pcount),
                                      backend=b))
        f.write("\n\n\n".join(cfg))
        f.close()

    service_restart("haproxy")


@hooks.hook('ha-relation-joined')
def ha_joined(relation_id=None):
    settings = generate_ha_relation_data('hpy')
    relation_set(relation_id=relation_id, **settings)

## TODO: add ha-relation-changed as charm-keystone, for example

