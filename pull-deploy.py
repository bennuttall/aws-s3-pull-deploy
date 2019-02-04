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
import yaml
import argparse

# These seem fair to set as globals; they could be put into the config file
# as new options with a default override for backwards compatibility
LAST_TIMESTAMP_PATH = '/tmp/pull-deploy-last-timestamp'
WEB_DIR = '/var/www'
SYMLINK_NAME = 'active'
EMAIL_LOG = ''
MAX_LOCK_CHECK = 120

def log(msg):
    global EMAIL_LOG

    now = datetime.datetime.now()
    log_date = now.strftime("%Y-%m-%d %H:%M:%S")
    log_line = '['+log_date+'] '+msg
    print(log_line, flush = True)

    EMAIL_LOG += log_line+"\n"


def timestamp_is_newer(latest_timestamp, site):
    latest_timestamp = int(latest_timestamp)
    if (not latest_timestamp):
        raise ValueError('Provided timestamp was empty')

    last_timestamp_path_site = LAST_TIMESTAMP_PATH+'-'+site
    log("Checking last timestamp file: "+last_timestamp_path_site)
    try:
        with open(last_timestamp_path_site, 'r+') as last_timestamp_file:
            last_timestamp = int(last_timestamp_file.read())
    except FileNotFoundError as e:
        last_timestamp = 0

    log("Last timestamp is "+str(last_timestamp))

    if latest_timestamp>last_timestamp:
        log("Needs a reload, returning true")

        return True

    log("New timestamp is not greater than last timestamp")


def send_email_of_log(subject, to_email, from_email):
    ses = boto3.client('ses')
    ses.send_email(Source = from_email, Destination = {'ToAddresses': [to_email]}, Message = {'Subject': {'Data': subject}, 'Body': {'Text': {'Data': EMAIL_LOG}}})


def create_cache_file_php(latest_timestamp, deploy_directory, cfg):
    php_cache_file_content = "<?php\nreturn '"+latest_timestamp+"'; // generated by deploy agent\n"
    php_cache_file_path = deploy_directory+'/_cache.php'
    log('Creating PHP cache file: '+php_cache_file_path);
    with open(php_cache_file_path, 'w') as php_cache_file:
        php_cache_file.write(php_cache_file_content)
    shutil.chown(php_cache_file_path, user = cfg['OWNER'], group = cfg['OWNER'])


def clear_old_dirs(domain_dir, deploy_datetime):
    all_deploys = os.listdir(domain_dir)
    old_dirs = []
    for a_deploy_dir in all_deploys:
        if (a_deploy_dir!=deploy_datetime and a_deploy_dir.startswith('20') and a_deploy_dir!='active' and a_deploy_dir!='content'):
            old_dirs.append(a_deploy_dir)

    if (len(old_dirs)>1):
        log("Got more than 1 extra directory to delete")
        old_dirs.sort()
        for i in range(0, len(old_dirs)-1):
            dir_delete = old_dirs[i]
            log("Deleting directory: "+dir_delete)
            shutil.rmtree(domain_dir+'/'+dir_delete)


def create_temp_directory(deploy_directory, cfg):
    temp_directory=deploy_directory+'/temp'
    log('Creating temp directory: '+temp_directory)
    pathlib.Path(temp_directory+'/temp').mkdir(parents = True, exist_ok = True)
    shutil.chown(temp_directory, user = cfg['OWNER'], group = cfg['OWNER'])


def create_symlink(domain_dir, deploy_directory, cfg):
    symlink = domain_dir+'/'+SYMLINK_NAME
    symlink_temp = symlink+'-tmp'
    log("Creating symlink at "+symlink+' with temporary name '+symlink_temp)
    os.symlink(deploy_directory, symlink_temp)
    shutil.chown(symlink_temp, user = cfg['OWNER'], group = cfg['OWNER'])
    os.rename(symlink_temp, symlink)


def create_deploy_dir(deploy_directory, cfg):
    log("Will deploy latest to "+deploy_directory)
    pathlib.Path(deploy_directory).mkdir(parents = True, exist_ok = True)
    shutil.chown(deploy_directory, user = cfg['OWNER'], group = cfg['OWNER'])


def call_aws(deploy_datetime, deploy_directory, cfg):
    log('Calling aws')
    subprocess.run(['sudo', '-u', cfg['OWNER'], 'aws', 's3', 'sync', 's3://'+cfg['BUCKET']+'/'+cfg['NICKNAME']+'/'+deploy_datetime+'/', deploy_directory+'/', '--only-show-errors'], check = True)


def get_latest_deploy_info(cfg):
    s3 = boto3.resource('s3')
    latest_deploy_object = s3.Object(cfg['BUCKET'], cfg['NICKNAME']+'/latest-deploy')

    return latest_deploy_object.get()['Body'].read().decode('utf-8')


def make_lock(lock_file):
    log('Locking with file '+lock_file)
    open(lock_file, "w+")


def write_timestamp(cfg):
    with open(LAST_TIMESTAMP_PATH+'-'+cfg['NICKNAME'], 'w') as last_timestamp_file:
        last_timestamp_file.write(str(latest_timestamp))


def run(instance_id, cfg):
    # Give good info for our logs
    log('Running for nickname: '+cfg['NICKNAME']+' and domain: '+cfg['DOMAIN'])

    lock_dir = cfg['LOCK_DIR']+'/'+cfg['NICKNAME']
    lock_file = lock_dir+'/lock-'+cfg['NICKNAME']+'-'+instance_id
    # If this is locked a deploy is in progress; we exit this with a status of 1
    # to indicate nothing has happened but nothing has gone 'wrong' either
    if os.path.isfile(lock_file) :
        log('The lock file '+lock_file+' already existed meaning this instance is deploying now, so exiting')
        return 1

    # We lock to ensure that if the deploy takes longer than the frequency
    # of runs that multiple deploys don't happen at the same time. Other deployment
    # agents on different machines sharing the same distributed lock directory
    # will also watch this lock to determine when they should all deploy
    make_lock(lock_file)

    latest_deploy = get_latest_deploy_info(cfg)

    deploy_datetime, latest_timestamp, expected_object_count = latest_deploy.splitlines()

    log("Latest deploy in folder "+deploy_datetime+" with timestamp "+latest_timestamp)

    # This will be the most common result if the system is run on a regular
    # schedule - no new deploy has been made so we're done. We return 1 to indicate
    # a succesful run but specify that a deploy did not happen
    if not timestamp_is_newer(latest_timestamp, cfg['NICKNAME']):
        os.remove(lock_file)
        return 1

    domain_dir = WEB_DIR+'/'+cfg['DOMAIN']
    deploy_directory = domain_dir+'/'+deploy_datetime

    create_deploy_dir(deploy_director, cfg)

    # This downloads all the files and will take longer depending how many there
    # are - expect it to take a few minutes for a full framework application or similar
    call_aws(deploy_datetime, deploy_directory, cfg)

    write_timestamp(cfg)

    object_count = sum([len(files) for r, d, files in os.walk(deploy_directory+'/objects')])

    log('Checking object count ('+str(object_count)+') matches expected ('+str(expected_object_count)+')')

    # We remove the lock here as we're either about to be done or to error on
    # the basis of an incorrect object count
    os.remove(lock_file)

    # We want to be sure we've got the deployment that the "timestamp" file told
    # us to expect; if not something has gone wrong with the initial upload to S3
    # or with our download to the machine. Maybe the machine is out of disk space
    # or the connection to S3 was interrupted?
    if (int(object_count)==0 or int(object_count)!=int(expected_object_count)):
        log('Counts didn\'t match, exiting')
        return False

    # This system is intended as a distributed deployment system
    # and so we want to have a shared lock with other instances
    log('Checking locks from other instances in '+lock_dir)
    locks = os.listdir(lock_dir)
    count_lock_check = 0
    while True:
        locks = os.listdir(lock_dir)
        if not locks:
            break

        log("Got lock files from other instances, waiting")

        count_lock_check += 1
        # This is somewhat
        if (count_lock_check>MAX_LOCK_CHECK):
            log("Checked lock files "+str(count_lock_check)+" times, still there. Something might have gone wrong, exiting")
            return False

        # Waiting a second between checks means instances should all switch code
        # within roughly one second of one another
        time.sleep(1)

    # We're now setting the deployment live

    # Creating a temp directory inside the newly deployed application might not
    # be needed for every application but will often be useful for local caches or
    # similar which the application wants to discard upon a new version being
    # deployed. In PHP this might be used for twig caches, for example
    create_temp_directory(deploy_directory, cfg)

    # This is specifically focussed around PHP - the system could be extended to
    # generate this in different languages based on the config file. Having a
    # timestamp of the deploy time is useful for cache busting on front end
    # resource requests and likely for other purposes in each application
    create_cache_file_php(latest_timestamp, deploy_directory, cfg)

    # This is the bit that actually causes the new version to become live for
    # users as it repoints the symlink to the active version to our new atomic
    # deployment timestamp
    create_symlink(domain_dir, deploy_directory, cfg)

    # This can be used for various purposes, suggestions would include
    # restarting services which depend on the application version (e.g. PHP FPM)
    # or loading crontab files
    if cfg['CMD']:
        log('Running command: '+cfg['CMD'])
        subprocess.run(cfg['CMD'], check = True, shell = True)

    # This waits for any ongoing requests to complete before removing files
    # which may be in use and therefore get locked by the OS when deleting, or
    # causing errors to users when a required file cannot be found
    time.sleep(5)

    # This removes old directories to save hard disk space. It will leave the
    # previous version which can also help deal with long running requests
    clear_old_dirs(domain_dir, deploy_datetime)

    log("Deploy complete")

    # 2 is the code indicating a succesful deploy
    return 2


def pull(cfg_file):
    cfg = get_config(cfg_file)

    response = requests.get('http://169.254.169.254/latest/meta-data/instance-id')
    instance_id = response.text
    log('Starting deploy agent on instance '+instance_id)

    try:
        result = run(instance_id, cfg)
    except BaseException as e:
        log('Error: '+str(e))
        result = False

    if not result:
        send_email_of_log('Deploy ERROR for "'+cfg['NICKNAME']+'" to "'+cfg['DOMAIN']+'": instance '+instance_id, cfg['EMAIL_NOTIFY'], cfg['EMAIL_FROM'])

    if result==2:
        send_email_of_log('Deploy COMPLETE for "'+cfg['NICKNAME']+'" to "'+cfg['DOMAIN']+'": instance '+instance_id, cfg['EMAIL_NOTIFY'], cfg['EMAIL_FROM'])


def get_config(cfg_file):
    try:
        with open(cfg_file, 'r') as ymlfile:
            cfg = yaml.load(ymlfile)
    except FileNotFoundError as e:
        raise FileNotFoundError("Config file not found, expected name was '{}'".format(cfg_file))

    if (not cfg):
        raise ReferenceError("Config file at '{}' failed to parse".format(cfg_file))

    cfg_errors = []
    if (not cfg.get('LOCK_DIR')):
        cfg_errors.append("The 'LOCK_DIR' config item must be set to a directory to store distributed lock files")

    if (not cfg.get('BUCKET')):
        cfg_errors.append("The 'BUCKET' config item must be set to the name of the S3 bucket you intend to deploy from")

    if (not cfg.get('NICKNAME')):
        cfg_errors.append("The 'NICKAME' config item must be set to a string naming this deployment which matches the prefix given to it in S3")

    if (not cfg.get('DOMAIN')):
        cfg_errors.append("The 'DOMAIN' config item must be set to the domain name this site will be hosted at")

    if (not cfg.get('EMAIL_NOTIFY')):
        cfg_errors.append("The 'EMAIL_NOTIFY' config item must be set to an email address to notify on success or failed deployment")

    if (not cfg.get('EMAIL_FROM')):
        cfg_errors.append("The 'EMAIL_FROM' config item must be set to an email address you are authorised to send from via SES")

    if (not cfg.get('OWNER')):
        cfg_errors.append("The 'OWNER' config item must be set to the name of the user/group to own created files")

    if 'CMD' not in cfg.keys():
        cfg_errors.append("The 'CMD' config item must be set to either an empty string or a valid shell command to run after deployment")

    if (cfg_errors):
        raise ReferenceError("The config file at '{}' had errors: \n".format(cfg_file)+"\n".join(cfg_errors))

    return cfg

def show(cfg_file):
    cfg = get_config(cfg_file)

    print(cfg)

def main():
    parser = argparse.ArgumentParser(description='Pull new releases from an S3 bucket')
    parser.add_argument('--show', dest='action', action='store_const', const='show',
                       help='Prints the config')
    parser.add_argument('--pull', dest='action', action='store_const', const='pull',
                       help='Runs a pull deployment')
    parser.add_argument('--config', dest='cfg_file', action='store', default='config.yml',
                       help="Path to a config YAML file (default is 'config.yml')")
    args = parser.parse_args()

    if (args.action=='show'):
        show(args.cfg_file)
    elif (args.action=='pull'):
        pull(args.cfg_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
