import json,logging,os,boto3
from botocore.exceptions import ClientError
logging.basicConfig(format='%(asctime)s [%(levelname)+8s]%(module)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', 'INFO')))
action = os.getenv('ACTION')
client_auto_scaling = boto3.client('autoscaling')


def update_auto_scaling(asg_list,action):
    if action == 'down':
        MinSize=0
        MaxSize=1
        DesiredCapacity=0
    elif action == 'up':
        MinSize=1
        MaxSize=1
        DesiredCapacity=1
    else:
        logger.error('Invalid action')
        return  {
            'Status': 'NOTOK'
        }
    if len(asg_list) > 0:
        for i in asg_list:
            try:
                logger.info('updating autoscaling %s' % i)
                client_auto_scaling.update_auto_scaling_group(
                    AutoScalingGroupName=i,
                    MinSize=MinSize,
                    MaxSize=MaxSize,
                    DesiredCapacity=DesiredCapacity
                    )
                return {
                    'Status' : 'OK'
                }
            except ClientError as e:
                logger.error('Cannot update autoscaling group %s with the error: %s ' % (i,e))
                return  {
                    'Status': 'NOTOK'
                }
    else:
        logger.info('The list of ASG is null, nothing to do')                 
        return {'Status' : 'OK'}
def create_autoscaling_group_list():
    asg_list = []
    try:
        paginator = client_auto_scaling.get_paginator('describe_auto_scaling_groups')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for asg in page['AutoScalingGroups']:
                 if asg.get('Tags'):
                     for tags in asg['Tags']:
                          if tags['Key'] == 'Stop' and tags['Value'] == 'Yes':
                              asg_list.append(asg['AutoScalingGroupName'])
        logger.info('This is the list of ASGs %s ' % str(asg_list))
        return asg_list 
    except ClientError as e:
        logger.error('Failed to get tags %s ' % (e))
        return {
            'Status' : 'NOTOK'
        }
        
def lambda_handler(event, context):
    asg_list = create_autoscaling_group_list()
    update_auto_scaling(asg_list,action)
 