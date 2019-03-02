import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="s3pd",
    version="0.1.0",
    author="Mike Lehan",
    description="Tool to syncronise deployments from S3 onto multiple EC2 instances",
    license="MIT",
    keywords=[],
    url="",
    packages=find_packages(),
    requires=[
        'boto3',
        'requests',
        'PyYAML',
    ],
    long_description=read('README.md'),
    entry_points={
        'console_scripts': [
            'pull-deploy = as3pd.pull_deploy:main',
            'push-deploy = as3pd.push_deploy:main',
        ]
    },
)
