# S3 Pull deployment

## Installing

If you didn't install awscli via pip you may need the `botocore` or `boto3` python libraries installed locally.

Run `pip3 list | grep boto` - if you don't see `botocore` and `boto3` in the list run `sudo pip3 install boto3`. In some cases running this install after installing awscli via pip could break awscli.

## Running

All files require Python 3 and the `boto3` library which can be installed from pip

* `pull-deploy.py` runs on a server
* `push-deploy.py` runs on a development machine

Both use the same config, `config.yml`. You can see an example of this at `config.sample.yml`. Some options are server or client-side only and a few are used by both.

Start using the sample config with `cp config.sample.yml config.yml` and then fill in your own variables:

* LOCK_DIR: This directory will be used to lock deployments. An obvious location would be `/efs/deploy`
* BUCKET: The name of the bucket you will deploy to
* DOMAIN: The domain that will be created on web servers. E.g. `your.domain.com` would be created at `/var/www/your.domain.com`
* NICKNAME: A short name for your site to allow multiple sites to deploy from one bucket
* SNS_SUCCESS: The "arn" of the SNS topic you will use to inform about successful deployments
* SNS_ERROR: The "arn" of the SNS topic you will use to inform about errors with deployments
* OWNER: The owning user/group of all deployed files. On an apache setup this would often be 'www-data'
* CMD: An optional line of script to eval at the end of the deploy process, e.g. create files, load crontab

Run `python3 push-deploy.py --show` to check the config.

To deploy a directory run:

```
python3 push-deploy.py --deploy=/path/to/directory
```

NB: this will ignore the `.git` directory in whatever you target but copy all other dotfiles. It will also copy the config file. This project contains two examples at `examples/html` and `examples/php`. When using your own application: AWS load balancers carry out health checks, so whatever load balancer config you use will need a path that can return a 200 response when the load balancer makes a request to it.

### Example code for user data

It is recommended for a production site to run the pull deployment process once per minute. Please note that in the event of a failure where the files do not exist or the lock is not removed manual intervention may be necessary. It is recommended to have shell access to boxes where this runs. For security the best way to handle this on AWS is using AWS Systems Manager remote sessions. This avoids the need for SSH access to be provisioned on the boxes.

Place this in the user data of an EC2 instance or launch configuration to install the pull deploy system on instance creation.

It will also set up a 1 minute crontab as root to check for new deployments, and log to a file. Note this example will overwrite existing root crontab.

```
deploy_tool_dir="/opt/pull-deploy"
echo "Downloading deployment tool to $deploy_tool_dir"
cd /tmp
rm -f *.tar.gz
wget "<Desired release GitHub tar gz URL>"
mkdir -p "$deploy_tool_dir"
echo "Extracting deployment tool"
tar -C "$deploy_tool_dir" -xzf *.tar.gz
mv /opt/pull-deploy/*/* /opt/pull-deploy/

# Download the config
echo "Download deploy config"
aws s3 cp s3://<Your deploy bucket>/config.yml "$deploy_tool_dir/"

mkdir -p /var/log/cron/root
crontab <<EOF
# m h  dom mon dow   command
* * * * * python3 "$deploy_tool_dir/pull-deploy.py" --pull >> /var/log/cron/root/deploy
EOF
```
