import json
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests.auth import HTTPBasicAuth

def lambda_handler(event, context):
    """
    GET /search/{term}
      --> Returns matching events based on search term
    """
    search_term = event["pathParameters"]["term"]
    if not search_term:
        return {"statusCode": 400, "body": json.dumps({"message": "'term' is required."})}

    try:
        match_results = fetch_search_results(search_term)
        return {
            "statusCode": 200,
            "headers": { "Cache-Control": "public, s-maxage=60" },
            "body": json.dumps({"results": match_results})
        }
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Internal server error: {str(e)}"})}

# =============== OpenSearch HELPERS ===============
def get_opensearch_client():
    client = OpenSearch(
        hosts=[{
            # Domain endpoint (IPv4), without `https://` prefix
            "host": "<YOUR_OPENSEARCH_HOSTNAME>",
            "port": 443
        }],
        http_auth=HTTPBasicAuth("admin", "Password100!"),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client

def fetch_search_results(search_term):
    opensearch_client = get_opensearch_client()
    query = {
        "query": {
            "match_phrase": {
                "name": search_term
            }
        }
    }
    response = opensearch_client.search(index="ticketmaster_index", body=query)
    match_results = [{**hit["_source"]} for hit in response["hits"]["hits"]]
    return match_results if match_results else None


if __name__ == "__main__":
    search_request = {
        "pathParameters": {
            "term": "concert"
        }
    }
    res = lambda_handler(search_request, None)
    print("\n----- Search Request -----")
    print(res["statusCode"])
    print(json.dumps(json.loads(res["body"]), indent=2))
