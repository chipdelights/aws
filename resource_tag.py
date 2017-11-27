#Author: Pavani Boga ( pavanianapala@gmail.com )
#Date: 11/25/2017
#Job: https://www.upwork.com/jobs/~013e03239b4f6eb5e4
#This script tags various AWS resources
#Run : python resource_tag.py --type <<ec2|ebs|s3|rds|redshift --file <<csv file which has the resources to tag
 
import csv
import boto3
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-t','--type',help="Type: ec2|ebs|s3|rds|redshift")
parser.add_argument('-f','--file',help="csv file")
parser.add_argument('-r','--region',help="AWS Region")
args = parser.parse_args()

sts_client = boto3.client('sts')
acct_id = sts_client.get_caller_identity()['Account']

arn_prefix = { 'ec2': 'arn:aws:ec2:%s:%s:instance/' %(args.region,acct_id), 
               'ebs': 'arn:aws:ec2:%s:%s:volume/' %(args.region,acct_id),
               's3': 'arn:aws:s3:::',
               'rds': 'arn:aws:rds:%s:%s:db:' %(args.region,acct_id),
               'redshift': 'arn:aws:redshift:%s:%s:dbname:' %(args.region,acct_id),
            }

resource_prefix = { 'ec2' : 'InstanceId', 'ebs': 'Volume', 'rds': 'InstanceId', 's3': 'Bucket', 'redshift': 'InstanceId' }

tag_resources = list()

with open(args.file) as f:
    reader = csv.DictReader(f)
    for row in reader:
        tag_resources.append(row)

tag_client = boto3.client('resourcegroupstaggingapi',region_name=args.region)

for resource in tag_resources:
    # Building tag_list assuming from second column are tags
    tags_list = [ { key:resource[key] } for key in list(resource.keys())[1:] ]
    try:
        tag_resource = resource[resource_prefix[args.type]]
    except Exception as e:
        print('Mismatch between type and csv file passed, please check it')
        sys.exit(1)
    
    resource_arn = arn_prefix[args.type] + tag_resource

    for tag in tags_list:
        tag_client.tag_resources(ResourceARNList=[resource_arn],Tags=tag)
