import json,logging,os,boto3, string
from botocore.exceptions import ClientError
client_auto_scaling = boto3.client('autoscaling')
client_ec2 = boto3.client('ec2')
logging.basicConfig(format='%(asctime)s [%(levelname)+8s]%(module)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', 'INFO')))


def get_instance_details(ec2_instance_id):
    logger.info('Getting Details of instance id %s ' % (ec2_instance_id))
    try:
        response = client_ec2.describe_instances(
            InstanceIds=[
                ec2_instance_id
            ]
        )
        availability_zone = response['Reservations'][0]['Instances'][0]['Placement']['AvailabilityZone']
        return availability_zone
    except ClientError as e:
        logger.error('Cannot get details from instance %s. The following error was detected %s' % (ec2_instance_id,e))

def get_autoscaling_tag(asg_name):
    try:
        logger.info('Getting tags from %s: ' % asg_name)
        response = client_auto_scaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[
                asg_name
            ]
        )
        for asg in response['AutoScalingGroups']:
            for tags in asg['Tags']:
                 if tags['Key'] == 'ServerName':
                    ServerName = tags['Value']
        logger.info('Returning servername %s' % (ServerName))
        return ServerName
    except ClientError as e:
        logger.error('Failed to get tags %s:' % e) 
        return {
            'Status' : 'NOTOK'
        }


def get_eni(availability_zone, server_name):
    try:
        logger.info('Getting information about the ENI in the AZ %s, using tag key servername %s ' % (availability_zone, server_name))
        response = client_ec2.describe_network_interfaces(
            Filters=[
                {
                    'Name': 'availability-zone',
                    'Values' :  [
                        availability_zone
                    ]
                },
                {
                    'Name': 'tag:ServerName',
                    'Values' :  [
                        server_name
                    ]
                }
            ]                    
        )
        eni_id = response['NetworkInterfaces'][0]['NetworkInterfaceId']
        return eni_id
    except ClientError as e:
        logger.error('Cannot get the ENI ID using %s and tag  %s with error %s' % (availability_zone,server_name,e ))
        return {'Status : NOTOK'}


def attach_eni(ec2_instance_id, eni_id):
    try:
        client_ec2.attach_network_interface(
        DeviceIndex=1,
        InstanceId=ec2_instance_id,
        NetworkInterfaceId=eni_id
        )
        logger.info('Interface %s attached to instance %s' % (eni_id, ec2_instance_id))
        return True
    except ClientError as e:
        logger.error('Could not attach ENI %s in the instance %s , with error %s' % (ec2_instance_id, eni_id,e))
        return False

def return_lifecycle(lifecycle_token, lifecycle_hook_name,asg_name):
    try:
        client_auto_scaling.complete_lifecycle_action(
            LifecycleHookName=lifecycle_hook_name,
            AutoScalingGroupName=asg_name,
            LifecycleActionToken=lifecycle_token,
            LifecycleActionResult='CONTINUE'
        )
        logger.info('%s returned with success for %s' % (asg_name, lifecycle_hook_name))
        return {'Status' : 'OK'}
    except ClientError as e:
        logging.error('Cannot update lifecyclehook %s with error %s' % (lifecycle_hook_name,e))        


def lambda_handler(event, context):
    logger.info('This is the event %s ' % (json.dumps(event)))
    ec2_instance_id = event['detail']['EC2InstanceId']
    lifecycle_token = event['detail']['LifecycleActionToken']
    lifecycle_hook_name = event['detail']['LifecycleHookName']
    asg_name = event['detail']['AutoScalingGroupName']
    availability_zone =  get_instance_details(ec2_instance_id)
    server_name = get_autoscaling_tag(asg_name)
    eni_id = get_eni(availability_zone, server_name)
    if attach_eni(ec2_instance_id,eni_id):
        return_lifecycle(lifecycle_token,lifecycle_hook_name,asg_name)
