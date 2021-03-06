import click
import logging

from spinup.cli import shell


@click.command()
@click.option("--license", required=True, help="Path to license file")
@click.option("--username", required=True, help="Username for pullcred secret")
@click.option("--email", required=True, help="Email for pullcred secret")
@click.pass_context
def enterprise(ctx, license, username, email):
    """
    Spin up a deployment of engine. Username and email are required along with the path
    to a valid license

    """
    logging.info("Spinning up enterprise")

    config = shell.create_cluster(
        fresh=ctx.obj["fresh"],
        cluster_name=ctx.obj["cluster_name"],
        agent_count=ctx.obj["agent_count"],
        loadbalancer_port=ctx.obj["loadbalancer_port"],
    )

    shell.create_pullcreds(
        config=config,
        username=username,
        email=email,
        hardened=ctx.obj["hardened"],
    )
    shell.stream_output(
        [
            "kubectl",
            "--kubeconfig",
            config,
            "create",
            "secret",
            "generic",
            "anchore-enterprise-license",
            f"--from-file=license.yaml={license}",
            "--namespace",
            "anchore",
        ]
    )
    shell.helm_upgrade(
        config=config,
        values="values.yaml",
        hardened=ctx.obj["hardened"],
        enterprise=True,
    )
