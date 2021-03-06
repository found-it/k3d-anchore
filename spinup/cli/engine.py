import click
import logging
import sys

from spinup.cli import shell

@click.command()
@click.option("--username", required=False, help="Username for pullcred secret")
@click.option("--email", required=False, help="Email for pullcred secret")
@click.pass_context
def engine(ctx, username, email):
    """
    Spin up a deployment of engine. Username and email are required if the hardened
    flag is used

    """
    if ctx.obj["hardened"]:
        if not username or not email:
            logging.error("Username and password are required for a hardened image")
            # TODO: Print help menu for subcommand
            sys.exit(1)

    logging.info("Spinning up engine")

    config = shell.create_cluster(
        fresh=ctx.obj["fresh"],
        cluster_name=ctx.obj["cluster_name"],
        agent_count=ctx.obj["agent_count"],
        loadbalancer_port=ctx.obj["loadbalancer_port"],
    )
    if ctx.obj["hardened"]:
        shell.create_pullcreds(
            config=config,
            username=username,
            email=email,
            hardened=ctx.obj["hardened"],
        )
    shell.helm_upgrade(
        config=config, values="values.yaml", hardened=ctx.obj["hardened"]
    )

