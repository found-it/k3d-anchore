import sys
import click
import logging

from . import (engine, enterprise)


@click.group()
@click.option("--hardened", is_flag=True, help="Use Iron Bank containers")
@click.option(
    "--fresh", is_flag=True, help="Overwrite any existing cluster of the same name"
)
@click.option("--cluster-name", default="anchore", help="Cluster name")
@click.option("--agent-count", default="3", help="Number of worker nodes")
@click.option(
    "--loadbalancer-port",
    default="8080",
    help="Local port for accessing the loadbalancer",
)
@click.option("--values", required=True, help="Path to values.yaml")
@click.pass_context
def cli(ctx, hardened, fresh, cluster_name, agent_count, loadbalancer_port, values):
    """
    Main entrypoint for click

    """
    DEFAULT_FORMAT = "%(levelname)-4s | %(message)s"
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format=DEFAULT_FORMAT)

    ctx.obj["hardened"] = hardened
    ctx.obj["values"] = values
    ctx.obj["fresh"] = fresh
    ctx.obj["cluster_name"] = cluster_name
    ctx.obj["agent_count"] = agent_count
    ctx.obj["loadbalancer_port"] = loadbalancer_port

    logging.debug(ctx.obj)


cli.add_command(enterprise.enterprise)
cli.add_command(engine.engine)
