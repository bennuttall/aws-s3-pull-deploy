import yaml

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
