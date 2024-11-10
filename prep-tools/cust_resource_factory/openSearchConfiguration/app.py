import boto3
import cfnresponse
from opensearchpy import OpenSearch, RequestsHttpConnection, OpenSearchException, AuthorizationException
from requests_aws4auth import AWS4Auth
import json
import logging
import time

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    try:
        request_type = event['RequestType']
        properties = event['ResourceProperties']
        
        if request_type in ['Create', 'Update']:
            collection_name = properties['CollectionName']
            region = properties['Region']
            collection_endpoint = properties['CollectionEndpoint']
            
            client = create_opensearch_client(collection_endpoint, region)
            configure_collection_with_retry(client, collection_name)
            
            response_data = {"Message": f"Collection {collection_name} configured successfully"}
            cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data)
        elif request_type == 'Delete':
            # Optionally handle deletion
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {"Message": "Nothing to delete"})
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)})

def create_opensearch_client(collection_endpoint, region):
    """
    Create an OpenSearch client with SigV4 authentication.
    """
    try:
        # Create a session and get credentials
        session = boto3.Session()
        credentials = session.get_credentials()

        # Parse the host from the endpoint
        collection_host = collection_endpoint.replace("https://", "")

        # Create the OpenSearch client with SigV4 auth
        client = OpenSearch(
            hosts = [{'host': collection_host, 'port': 443}],
            http_auth = AWS4Auth(credentials.access_key, 
                                credentials.secret_key,
                                region, 
                                'aoss',
                                session_token=credentials.token),
            use_ssl = True,
            verify_certs = True,
            connection_class = RequestsHttpConnection
        )
        return client
    except Exception as e:
        print(f"Error creating OpenSearch client: {str(e)}")

def configure_collection_with_retry(client, collection_name, max_retries=10, initial_backoff=1):
    retries = 0
    while retries < max_retries:
        try:
            configure_collection(client, collection_name)
            logger.info(f"Collection {collection_name} configured successfully after {retries} retries")
            # Add a short delay before returning
            time.sleep(30)
            return
        except AuthorizationException as e:
            retries += 1
            if retries >= max_retries:
                logger.error(f"Max retries reached. Failed to configure collection: {str(e)}")
                raise
            backoff = 10
            logger.warning(f"Authorization error. Retrying in 10 seconds. Retry {retries}/{max_retries}")
            time.sleep(backoff)
        except Exception as e:
            logger.error(f"Unexpected error configuring collection: {str(e)}")
            raise

def configure_collection(client, collection_name):
    """
    Configure the collection with the given client and region.
    """
    index_name = f"{collection_name}-index"
    index_body = {
        'settings': {
            'index': {
                'number_of_shards': 2,
                'number_of_replicas': 0,
                'knn': True,
            }
        }
    }

    try:
        # Check if index already exists
        if not client.indices.exists(index=index_name):
            response = client.indices.create(index=index_name, body=index_body)
            logger.info(f'Index created: {response}')
        else:
            logger.info(f'Index {index_name} already exists')

        mappings = {
            "properties": {
                "AMAZON_BEDROCK_METADATA": {
                    "type": "text",
                    "index": False
                },
                "AMAZON_BEDROCK_TEXT_CHUNK": {
                    "type": "text"
                },
                "bedrock-knowledge-base-default-vector": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "engine": "faiss",
                        "space_type": "l2",
                        "name": "hnsw",
                        "parameters": {}
                    }
                },
                "id": {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                }
            }
        }

        # Update the mappings
        response = client.indices.put_mapping(index=index_name, body=mappings)
        logger.info(f'Mappings updated: {response}')

        # Verify the updated mappings
        updated_mappings = client.indices.get_mapping(index=index_name)
        logger.info(f"Updated mappings: {json.dumps(updated_mappings, indent=2)}")
    except AuthorizationException:
        logger.warning("Authorization error. Will retry.")
        raise
    except OpenSearchException as e:
        logger.error(f"OpenSearch error configuring collection: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error configuring collection: {str(e)}")
        raise
