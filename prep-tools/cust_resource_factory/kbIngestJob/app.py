import boto3
import cfnresponse
import time
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_agent = boto3.client('bedrock-agent')

def lambda_handler(event, context):
    try:
        logger.info(f"Received event: {event}")
        
        if event['RequestType'] in ['Create', 'Update']:
            knowledge_base_id = event['ResourceProperties']['KnowledgeBaseId']
            data_source_id = event['ResourceProperties']['DataSourceId']
            
            start_and_wait_for_ingestion_job(knowledge_base_id, data_source_id)
            
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                'Message': f'Successfully completed ingestion job for knowledge base {knowledge_base_id}'
            })
        elif event['RequestType'] == 'Delete':
            # No action needed for delete
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                'Message': 'No action required for delete'
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

def start_and_wait_for_ingestion_job(knowledge_base_id, data_source_id):
    response = bedrock_agent.start_ingestion_job(
        dataSourceId=data_source_id,
        knowledgeBaseId=knowledge_base_id
    )
    logger.info(f"Started ingestion job: {response}")
    
    ingestion_job_id = response['ingestionJob']['ingestionJobId']
    
    while True:
        response = bedrock_agent.get_ingestion_job(
            dataSourceId=data_source_id,
            knowledgeBaseId=knowledge_base_id, 
            ingestionJobId=ingestion_job_id
        )
        status = response['ingestionJob']['status']
        logger.info(f'Ingestion job status: {status}')
        if status not in ['IN_PROGRESS', 'STARTING']:
            break
        time.sleep(5)
    
    if status != 'COMPLETE':
        raise Exception(f"Ingestion job failed with status: {status}")
    
    logger.info("Ingestion job completed successfully.")
