# S3 Pull deployment

## Running

All files require Python 3 and the `boto3` library which can be installed from pip

* `pull-deploy.py` runs on a server
* `push-deploy.py` runs on a development machine

Both use the same config, `config.yml`. You can see an example of this at `config.sample.yml`. Some options are server or client-side only and a few are used by both.

Start using the sample config with `cp config.sample.yml config.yml`

It is recommended for a production site to run the pull deployment process once per minute. Please note that in the event of a failure where the files do not exist or the lock is not removed manual intervention may be necessary. It is recommended to have shell access to boxes where this runs. For security the best way to handle this on AWS is using AWS Systems Manager remote sessions. This avoids the need for SSH access to be provisioned on the boxes.

### Example code for user data

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
