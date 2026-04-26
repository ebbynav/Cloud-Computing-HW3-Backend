import boto3
import json
import os
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

REGION = os.getenv("AWS_REGION", "us-east-1")
ES_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "").replace("https://", "")
ES_INDEX = os.getenv("OPENSEARCH_INDEX", "photos")

LEX_BOT_ID = os.getenv("LEX_BOT_ID", "")
LEX_BOT_ALIAS_ID = os.getenv("LEX_BOT_ALIAS_ID", "")
LEX_LOCALE_ID = os.getenv("LEX_LOCALE_ID", "en_US")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Api-Key,x-api-key",
    "Access-Control-Allow-Methods": "GET,OPTIONS"
}


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body)
    }


def get_es_client():
    if not ES_ENDPOINT:
        raise ValueError("OPENSEARCH_ENDPOINT environment variable is required")

    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, REGION, "es")

    return OpenSearch(
        hosts=[{"host": ES_ENDPOINT, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )


def get_keywords(query):
    lex = boto3.client("lexv2-runtime", region_name=REGION)

    lex_response = lex.recognize_text(
        botId=LEX_BOT_ID,
        botAliasId=LEX_BOT_ALIAS_ID,
        localeId=LEX_LOCALE_ID,
        sessionId="search-session",
        text=query
    )

    print("Lex response:", json.dumps(lex_response, default=str))

    keywords = []
    slots = lex_response.get("sessionState", {}).get("intent", {}).get("slots", {})

    for slot_value in slots.values():
        if slot_value and slot_value.get("value"):
            value = slot_value["value"].get("interpretedValue", "")
            if value:
                keywords.append(value.lower())

    if not keywords:
        stopwords = {
            "show", "me", "find", "photos", "photo", "images", "image",
            "with", "and", "a", "an", "the", "of", "in", "for", "some", "all"
        }
        keywords = [
            word.lower()
            for word in query.split()
            if word.lower() not in stopwords
        ]

    print("Keywords:", keywords)
    return keywords


def search_photos(keywords):
    es = get_es_client()

    query = {
        "query": {
            "bool": {
                "should": [
                    {"match": {"labels": keyword}} for keyword in keywords
                ],
                "minimum_should_match": 1
            }
        }
    }

    print("OpenSearch query:", json.dumps(query))

    os_response = es.search(index=ES_INDEX, body=query)
    print("OpenSearch response:", json.dumps(os_response, default=str))

    results = []

    for hit in os_response.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        object_key = src.get("objectKey")
        bucket = src.get("bucket")
        labels = src.get("labels", [])

        if not object_key or not bucket:
            continue

        results.append({
            "objectKey": object_key,
            "bucket": bucket,
            "url": f"https://{bucket}.s3.amazonaws.com/{object_key}",
            "labels": labels
        })

    return results


def lambda_handler(event, context):
    print("Event:", json.dumps(event))

    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    try:
        params = event.get("queryStringParameters") or {}
        query = params.get("q", "").strip()

        if not query:
            return response(200, {"results": []})

        if LEX_BOT_ID and LEX_BOT_ALIAS_ID:
            keywords = get_keywords(query)
        else:
            stopwords = {
                "show", "me", "find", "photos", "photo", "images", "image",
                "with", "and", "a", "an", "the", "of", "in", "for", "some", "all"
            }
            keywords = [
                word.lower()
                for word in query.split()
                if word.lower() not in stopwords
            ]

        if not keywords:
            return response(200, {"results": []})

        results = search_photos(keywords)
        return response(200, {"results": results})

    except Exception as e:
        print("ERROR:", str(e))
        return response(500, {"message": str(e), "results": []})