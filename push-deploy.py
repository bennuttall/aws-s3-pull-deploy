import boto3
import subprocess
import pathlib
import random
import time
import os
import requests
import datetime
import shutil
import sys
import argparse

import load_config

def log(msg):
    now = datetime.datetime.now()
    log_date = now.strftime("%Y-%m-%d %H:%M:%S")
    log_line = '['+log_date+'] '+msg
    print(log_line, flush = True)


def deploy(deploy, cfg_file):
    cfg = load_config.get_config(cfg_file)

    date_string = datetime.datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    timestamp = int(time.time())
    file_count = sum([len(files) for r, d, files in os.walk(deploy)])

    latest_deploy=str(date_string)+"\n"+str(timestamp)+"\n"+str(file_count)

    cmd='aws s3 sync '+deploy+'/ s3://'+cfg['BUCKET']+'/'+cfg['NICKNAME']+'/ --only-show-errors'

    log("Running the following shell command to sync files: '"+cmd+"'")
    subprocess.run(cmd, check = True, shell = True)

    log("Writing the following file to S3 to trigger deploy on instances:\n"+latest_deploy)
    client = boto3.client('s3')
    client.put_object(Bucket=cfg['BUCKET'], Key=cfg['NICKNAME']+'/latest_deploy', Body=latest_deploy)

    log("Complete, instances will deploy next time pull-deploy.py is run with the --pull flag")


def show(cfg_file):
    cfg = load_config.get_config(cfg_file)

    print(cfg)

def main():
    parser = argparse.ArgumentParser(description='Push releases to an S3 bucket')
    parser.add_argument('--show', dest='action', action='store_const', const='show',
                       help='Prints the config')
    parser.add_argument('--deploy', dest='deploy', action='store',
                       help='Runs a push deployment')
    parser.add_argument('--config', dest='cfg_file', action='store', default='config.yml',
                       help="Path to a config YAML file (default is 'config.yml')")
    args = parser.parse_args()

    if (args.action=='show'):
        show(args.cfg_file)
    elif (args.deploy):
        deploy(args.deploy, args.cfg_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
