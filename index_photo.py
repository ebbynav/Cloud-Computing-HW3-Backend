import json
import os
from datetime import datetime

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection

REGION = os.getenv("AWS_REGION", "us-east-1")
ES_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "").replace("https://", "")
ES_USER = os.getenv("OPENSEARCH_USER", "")
ES_PASS = os.getenv("OPENSEARCH_PASS", "")
ES_INDEX = os.getenv("OPENSEARCH_INDEX", "photos")

def get_es_client():
    if not ES_ENDPOINT:
        raise ValueError("OPENSEARCH_ENDPOINT environment variable is required")

    http_auth = (ES_USER, ES_PASS) if ES_USER and ES_PASS else None
    return OpenSearch(
        hosts=[{'host': ES_ENDPOINT, 'port': 443}],
        http_auth=http_auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )

def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")
    s3 = boto3.client('s3')
    rekognition = boto3.client('rekognition', region_name=REGION)

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    print(f"Processing: {bucket}/{key}")

    rek_response = rekognition.detect_labels(
        Image={'S3Object': {'Bucket': bucket, 'Name': key}},
        MaxLabels=10,
        MinConfidence=70
    )
    labels = [l['Name'].lower() for l in rek_response['Labels']]
    print(f"Labels: {labels}")

    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        custom = head.get('Metadata', {}).get('customlabels', '')
        if custom:
            labels += [l.strip().lower() for l in custom.split(',')]
            print(f"Custom labels: {custom}")
    except Exception as e:
        print(f"Metadata error: {e}")

    doc = {
        "objectKey": key,
        "bucket": bucket,
        "createdTimestamp": datetime.now().isoformat(),
        "labels": labels
    }
    es = get_es_client()
    resp = es.index(index=ES_INDEX, body=doc, id=key)
    print(f"Indexed: {resp}")
    return {'statusCode': 200, 'body': json.dumps(f"Indexed {key}")}