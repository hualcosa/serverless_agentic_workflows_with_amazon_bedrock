import boto3
import cfnresponse
import os
import logging
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    try:
        logger.info(f"Received event: {event}")
        
        if event['RequestType'] in ['Create', 'Update']:
            source_bucket = event['ResourceProperties']['SourceBucket']
            source_prefix = event['ResourceProperties'].get('SourcePrefix', '')
            destination_bucket = event['ResourceProperties']['DestinationBucket']
            destination_prefix = event['ResourceProperties'].get('DestinationPrefix', '')
            
            copy_objects(source_bucket, source_prefix, destination_bucket, destination_prefix)
            
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                'Message': f'Successfully copied objects from {source_bucket}/{source_prefix} to {destination_bucket}/{destination_prefix}'
            })
        elif event['RequestType'] == 'Delete':
            destination_bucket = event['ResourceProperties']['DestinationBucket']
            destination_prefix = event['ResourceProperties'].get('DestinationPrefix', '')
            
            delete_objects(destination_bucket, destination_prefix)
            
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                'Message': f'Successfully deleted objects from {destination_bucket}/{destination_prefix}'
            })
        else:
            cfnresponse.send(event, context, cfnresponse.FAILED, {
                'Message': f'Unsupported request type: {event["RequestType"]}'
            })
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {
            'Message': f'Error: {str(e)}'
        })

def copy_objects(source_bucket, source_prefix, destination_bucket, destination_prefix):
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=source_bucket, Prefix=source_prefix):
        for obj in page.get('Contents', []):
            source_key = obj['Key']
            # Filter for PDF files only
            if not source_key.lower().endswith('.pdf'):
                continue
            destination_key = os.path.join(destination_prefix, os.path.relpath(source_key, source_prefix))
            
            logger.info(f"Copying {source_bucket}/{source_key} to {destination_bucket}/{destination_key}")
            
            s3_client.copy_object(
                CopySource={'Bucket': source_bucket, 'Key': source_key},
                Bucket=destination_bucket,
                Key=destination_key
            )

def delete_objects(bucket, prefix):
    paginator = s3_client.get_paginator('list_objects_v2')
    delete_us = dict(Objects=[])
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            delete_us['Objects'].append(dict(Key=obj['Key']))
            
            # AWS limits to deleting 1000 objects at a time
            if len(delete_us['Objects']) >= 1000:
                logger.info(f"Deleting {len(delete_us['Objects'])} objects from {bucket}")
                response = s3_client.delete_objects(Bucket=bucket, Delete=delete_us)
                handle_delete_response(response)
                delete_us = dict(Objects=[])

    # Delete any remaining objects
    if delete_us['Objects']:
        logger.info(f"Deleting {len(delete_us['Objects'])} objects from {bucket}")
        response = s3_client.delete_objects(Bucket=bucket, Delete=delete_us)
        handle_delete_response(response)

def handle_delete_response(response):
    if 'Errors' in response:
        for error in response['Errors']:
            logger.error(f"Error deleting object {error['Key']}: {error['Code']} - {error['Message']}")
        raise Exception("Failed to delete some objects")