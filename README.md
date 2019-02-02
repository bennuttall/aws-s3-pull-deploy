# S3 Pull deployment

## Running

All files require Python 3

* `pull-deploy.py` runs on a server
* `push-deploy.py` runs on a development machine

Both use the same config, `config.yml`. You can see an example of this at `config.sample.yml`. Some options are server or client-side only and a few are used by both.

It is recommended for a production site to run the pull deployment process once per minute. Please note that in the event of a failure where the files do not exist or the lock is not removed manual intervention may be necessary. It is recommended to have shell access to boxes where this runs. For security the best way to handle this on AWS is using AWS Systems Manager remote sessions. This avoids the need for SSH access to be provisioned on the boxes.
