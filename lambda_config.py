# Author : Pavani Boga ( pavanianapala@gmail.com )
# Date: 12/17/2017
# Purpose : this is a centralized lambda function which checks for compliance type which is ensuring
# the tags given in the config rule are present for all the AWS resources in that account and send an
# HTML email on periodic basis which are non-compliant
# More info : https://aws.amazon.com/blogs/devops/how-to-centrally-manage-aws-config-rules-across-multiple-aws-accounts/
import json
import boto3


# Iterate through required tags ensureing each required tag is present, 
# and value is one of the given valid values
def find_violation(current_tags, required_tags):
    value_match = False
    for rtag in required_tags:
        tag_present = False
        for tag in current_tags:
            if tag == rtag:
                tag_present = True
                rvaluesplit = required_tags[rtag].split(",")
                for rvalue in rvaluesplit:
                    if current_tags[tag] == required_tags[rtag]:
                        value_match = True
                        break
                    if current_tags[tag] != "":
                        if rvalue == "*":
                            value_match = True
                            break
    if value_match == False:
        return 'NON_COMPLIANT'
    else:
        return 'COMPLIANT'

def lambda_handler(event, context):
    
    print(json.dumps(event,indent=4))
    params = json.loads(event["ruleParameters"])
    invoking_event = json.loads(event["invokingEvent"])
    acct_id = event['accountId']

    result_token = "No token found."
    if "resultToken" in event:
        result_token = event["resultToken"]
        
    rule_parameters = { k:v for k,v in params.items() if k not in ['executionRole','email'] }
    
    
    sts_client = boto3.client('sts')
    temp_creds = sts_client.assume_role(RoleArn=params['executionRole'],RoleSessionName='awsconfig-requiredtags')
    
    session = boto3.session.Session(aws_access_key_id=temp_creds['Credentials']['AccessKeyId'],aws_secret_access_key=temp_creds['Credentials']['SecretAccessKey'],aws_session_token=temp_creds['Credentials']['SessionToken'])
    iam_client = session.client('iam')
    acct_alias = iam_client.list_account_aliases()['AccountAliases'][0]
    config = session.client('config')
    config_rules = config.describe_config_rules(ConfigRuleNames=[event['configRuleName']])['ConfigRules'][0]
    
    
    compliance_resourceTypes = [ 'AWS::EC2::Instance', 'AWS::S3::Bucket','AWS::EC2::Volume','AWS::RDS::DBInstance']
    
    
    evaluation_results = list()
    
    for resource_type in compliance_resourceTypes:
        for resource in config.list_discovered_resources(resourceType=resource_type)['resourceIdentifiers']:
            current_tags = ''
            if resource_type in ['AWS::EC2::Instance','AWS::EC2::Volume']:
                ec2_client = session.client('ec2')
                instance_tags = ec2_client.describe_tags(Filters = [{ 'Name': 'resource-id', 'Values':[ resource['resourceId'] ]}])['Tags']
                current_tags = { each['Key']:each['Value'] for each in instance_tags }
            if resource_type == 'AWS::S3::Bucket':
                s3_client = session.client('s3')
                try:
                    bucket_tags = s3_client.get_bucket_tagging(Bucket=resource['resourceId'])['TagSet']
                    current_tags = { each['Key']:each['Value'] for each in bucket_tags }
                except:
                    current_tags = {}
                
            if resource_type == 'AWS::RDS::DBInstance':
                rds_client = session.client('rds')
                rds_metadata = rds_client.describe_db_instances(DBInstanceIdentifier=resource['resourceName'])
                rds_tags = rds_client.list_tags_for_resource(ResourceName=rds_metadata['DBInstances'][0]['DBInstanceArn'])['TagList']
                current_tags = { each['Key']:each['Value'] for each in rds_tags }
                resource['resourceId'] = resource['resourceName']
                
            if resource_type == 'AWS::Redshift::Cluster':
                redshift_client = session.client('redshift')
                redshift_tags = redshift_client.describe_clusters(ClusterIdentifier=resource['resourceName'])['Tags']
                current_tags = { each['Key']:each['Value'] for each in redshift_tags }
                resource['resourceId'] = resource['resourceName']
                
                
            result = find_violation(current_tags,rule_parameters)
            
            if result == 'NON_COMPLIANT':
                config.put_evaluations(
                Evaluations=[
                   {
                    "ComplianceResourceType":resource_type,
                    "ComplianceResourceId":resource['resourceId'],
                    "ComplianceType":result,
                    "OrderingTimestamp": invoking_event['notificationCreationTime']
                    },
                  ],
                ResultToken=result_token
                )
                evaluation_results.append({ 'resource_type':resource_type, 'resource_id': resource['resourceId'], 'Compliance': result })
            
    
    #Email the compliance report
    ses_client = session.client('ses')
    sender_email = '<<fill in the email here>>'
    receiver_email = params['email'].split(',')
    
    html_body = """<html><head></head><body><h1>The AWS Config Violation Report</h1>
                        <h2> Account Id - %s </h2>
                        <h2> Account Alias - %s</h2>
                       <table border='1'><tr><th>Resource Type</th><th>Resource</th><th>Compliance</th></tr>""" %(acct_id,acct_alias)
    
    for result in evaluation_results:
        html_body += "<tr><td>"+result['resource_type']
        if result['resource_type'] == 'AWS::EC2::Instance':
            html_body += "</td><td><a href='https://console.aws.amazon.com/ec2/v2/home?region=us-east-1#Instances:search=%s'>%s</a>" %(result['resource_id'],result['resource_id'])
        
        if result['resource_type'] == 'AWS::EC2::Volume':
            html_body += "</td><td><a href='https://console.aws.amazon.com/ec2/v2/home?region=us-east-1#Volumes:search=%s'>%s</a>" %(result['resource_id'],result['resource_id'])


        if result['resource_type'] == 'AWS::S3::Bucket':
            html_body += "</td><td><a href='https://console.aws.amazon.com/s3/buckets/%s/?region=us-east-1'>%s</a>" %(result['resource_id'],result['resource_id'])
        
        if result['resource_type'] == 'AWS::RDS::DBInstance':
            html_body += "</td><td><a href='https://console.aws.amazon.com/rds/home?region=us-east-1#dbinstance:id=%s'>%s</a>" %(result['resource_id'],result['resource_id'])

        if result['Compliance'] == 'COMPLIANT':    
            html_body += "</td><td><span style = 'color:green;font-weight:bold'>" + result['Compliance'] + "</span></td></tr>"
        else:
            html_body += "</td><td><span style = 'color:red;font-weight:bold'>" + result['Compliance'] + "</span></td></tr>"
            
        
    html_body += "</table><h2>Config Rule Report : <a href='https://console.aws.amazon.com/config/home?region=us-east-1#/rules/rule-details/%s'>%s</a></db></body></html>" %(event['configRuleName'],event['configRuleName'])

    for email in receiver_email:
        ses_client.send_email(Destination={ 'ToAddresses': [ email ] },Message={'Subject': { 'Data': 'AWS Config Violation' }, 'Body': { 'Html': { 'Data': html_body } } },Source=sender_email)

    
	
