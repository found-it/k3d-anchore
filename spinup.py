#!/usr/bin/env python3

import logging
import os
import shutil
import subprocess
import sys

import click

DEFAULT_FORMAT = "%(levelname)-4s | %(message)s"

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format=DEFAULT_FORMAT)


def stream_output(cmd, redact=None):
    try:
        os.environ["PYTHONUNBUFFERED"] = "1"
        if redact:
            redacted = [r.replace(redact, "<redacted>") for r in cmd]
            logging.info(" ".join(redacted))
        else:
            logging.info(" ".join(cmd))
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )

        while p.poll() is None:
            line = p.stdout.readline().strip()
            if line:
                logging.info(line)
        os.environ["PYTHONUNBUFFERED"] = "0"

    except subprocess.SubprocessError:
        logging.exception(" ".join(cmd))
        sys.exit(1)

    return p


def preflight():
    die = 0
    cmds = ["k3d", "helm", "kubectl"]
    for cmd in cmds:
        if not shutil.which(cmd):
            logging.error(f"Need to install {cmd}")
            die = 1
        else:
            logging.info(f"Found {cmd}")

    if die:
        sys.exit(1)

    logging.info("Preflight checks passed")


def get_kubeconfig(cluster_name):
    cmd = ["k3d", "kubeconfig", "write", cluster_name]
    try:
        logging.info(" ".join(cmd))
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
    except subprocess.SubprocessError:
        logging.exception(" ".join(cmd))
        sys.exit(1)

    if p.returncode != 0:
        logging.error(p.stdout)
        logging.error(p.stderr)
        sys.exit(p.returncode)

    return p.stdout


def get_password(username):
    # TODO: Give option to prompt in cli
    cmd = ["security", "find-internet-password", "-a", username, "-gw"]
    try:
        logging.info(" ".join(cmd))
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
    except subprocess.SubprocessError:
        logging.exception(" ".join(cmd))
        sys.exit(1)

    if p.returncode != 0:
        logging.error(p.stderr)
        sys.exit(p.returncode)

    return p.stdout[:-1]


def create_pullcreds(config, username, email, hardened=False):
    # TODO: Fix ImagePullBackoff for hardened
    if hardened:
        registry = "registry1.dso.mil"
    else:
        registry = "docker.io"

    password = get_password(username)
    stream_output(
        [
            "kubectl",
            "--kubeconfig",
            config,
            "create",
            "secret",
            "docker-registry",
            "anchore-enterprise-pullcreds",
            "--docker-server",
            registry,
            "--docker-username",
            username,
            "--docker-password",
            password,
            "--docker-email",
            email,
            "--namespace",
            "anchore",
        ],
        redact=password,
    )


def helm_upgrade(config, values, hardened=False, enterprise=False):
    cmd = [
        "helm",
        "--kubeconfig",
        config,
        "upgrade",
        "--namespace",
        "anchore",
        "--install",
        "anchore",
        "anchore/anchore-engine",
        "--values",
        values,
    ]

    if enterprise:
        cmd += ["--set", "anchoreEnterpriseGlobal.enabled=true"]

    if hardened:
        cmd += [
            "--set",
            "anchoreEnterpriseGlobal.image=registry1.dso.mil/anchore/enterprise/enterprise:3.0.0",
            "--set",
            "anchoreEnterpriseUi.image=registry1.dso.mil/anchore/enterpriseui/enterpriseui:3.0.0",
            "--set",
            "anchoreGlobal.image=registry1.dso.mil/anchore/engine/engine:0.9.0",
        ]
    stream_output(cmd)


def create_cluster(fresh, cluster_name, agent_count, loadbalancer_port):
    preflight()

    cmd = ["k3d", "cluster", "get", cluster_name]
    exists = stream_output(cmd)
    if exists.returncode == 0:
        if fresh:
            logging.info(f"{cluster_name} cluster exists. Deleting it..")
            cmd = ["k3d", "cluster", "delete", cluster_name]
            stream_output(cmd)
        else:
            logging.warning(f"{cluster_name} already exists.")
            logging.warning("Use --fresh if you want to replace it.")
            sys.exit(0)

    logging.info(f"Creating cluster {cluster_name}")
    cmd = [
        "k3d",
        "cluster",
        "create",
        cluster_name,
        "--agents",
        agent_count,
        "--update-default-kubeconfig=false",
        "--switch-context=false",
        "--port",
        f"{loadbalancer_port}:80@loadbalancer",
        "--wait=true",
    ]
    stream_output(cmd)

    config = get_kubeconfig(cluster_name=cluster_name).strip()
    stream_output(["kubectl", "--kubeconfig", config, "create", "ns", "anchore"])

    logging.info("export KUBECONFIG=(k3d kubeconfig write anchore)")
    return config


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
    ctx.obj["hardened"] = hardened
    ctx.obj["values"] = values
    ctx.obj["fresh"] = fresh
    ctx.obj["cluster_name"] = cluster_name
    ctx.obj["agent_count"] = agent_count
    ctx.obj["loadbalancer_port"] = loadbalancer_port

    logging.debug(ctx.obj)


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

    config = create_cluster(
        fresh=ctx.obj["fresh"],
        cluster_name=ctx.obj["cluster_name"],
        agent_count=ctx.obj["agent_count"],
        loadbalancer_port=ctx.obj["loadbalancer_port"],
    )
    if ctx.obj["hardened"]:
        create_pullcreds(
            config=config,
            username=username,
            email=email,
            hardened=ctx.obj["hardened"],
        )
    helm_upgrade(
        config=config, values="values.yaml", hardened=ctx.obj["hardened"]
    )


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

    config = create_cluster(
        fresh=ctx.obj["fresh"],
        cluster_name=ctx.obj["cluster_name"],
        agent_count=ctx.obj["agent_count"],
        loadbalancer_port=ctx.obj["loadbalancer_port"],
    )

    create_pullcreds(
        config=config,
        username=username,
        email=email,
        hardened=ctx.obj["hardened"],
    )
    stream_output(
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
    helm_upgrade(
        config=config,
        values="values.yaml",
        hardened=ctx.obj["hardened"],
        enterprise=True,
    )


cli.add_command(enterprise)
cli.add_command(engine)


if __name__ == "__main__":
    cli(obj={})
