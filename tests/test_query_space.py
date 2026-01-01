import requests
from time import sleep
from typing import Any

from databricks.sdk import WorkspaceClient

WORKSPACE_URL = "https://dbc-57e0a25f-9bec.cloud.databricks.com"
M2M_CLIENT_ID = "c3df30ca-0414-446f-9ab6-834747432dcd"
M2M_CLIENT_SECRET = "dose46b091345b727efd7b76361e7b44f614"


query = "What stock had the most traded volume in 2025?"
conversation_id = None
# Function start
if __name__ == "__main__":
    space_id = "01f0d08866f11370b6735facce14e3ff"

    # First, get an OAuth token using M2M credentials
    w = WorkspaceClient(
        host=WORKSPACE_URL,
        client_id=M2M_CLIENT_ID,
        client_secret=M2M_CLIENT_SECRET,
        auth_type="oauth-m2m"
    )

    json_payload = {
        "content": query,
    }
    if conversation_id:
        json_payload["conversation_id"] = conversation_id

    start_conversation = f"/api/2.0/genie/spaces/{space_id}/start-conversation"
    response = requests.post(
        WORKSPACE_URL+start_conversation,
        headers=w.config.authenticate(),
        json=json_payload
    )
    response_dict = dict[Any, Any](response.json())
    conversation_id = response_dict['message']['conversation_id']
    message_id = response_dict['message_id']
    message_status = response_dict['message']['status']
    print(conversation_id, message_id, message_status)
    #print(response_dict)
    sleep(10)
    #message_id = '01f0e35194f213ffad0f1f50e28939b1',
    #conversation_id = '01f0e35194e814ddac18815070128efb',
    get_conversation_message = f"/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}"
    response = requests.get(
        WORKSPACE_URL+get_conversation_message,
        headers=w.config.authenticate()
    )
    response_dict = dict[Any, Any](response.json())
    print(response_dict)
    space_id = response_dict['space_id']
    conversation_id = response_dict['conversation_id']
    message_id = response_dict['message_id']
    status = response_dict['status']
    text = response_dict['attachments'][0]
    attachment_id = response_dict['attachments'][0]['attachment_id']
    print(text, attachment_id)

x = {
    'id': '01f0e35212d513c2a84e0e23b89f63a0',
    'space_id': '01f0d08866f11370b6735facce14e3ff',
    'conversation_id': '01f0e35212c9187298a42e5b45f1418a',
    'user_id': 78631925261941,
    'created_timestamp': 1766860209127,
    'last_updated_timestamp': 1766860214853,
    'status': 'COMPLETED',
    'content': 'What datasets are available in this space?',
    'attachments': [
        {
            'text':{'content': 'There is one dataset available in this space: ai_data_engineer.price_volume.yahoo_finance_price_volume, which contains historical stock market data for various tickers, including daily prices, volume, dividends, and stock splits.'},
            'attachment_id': '01f0e352150416e1b6f99da4e3b1b69d'
        },
        {
            'suggested_questions': {'questions': ['What are the available stock tickers in the dataset?', 'What is the date range covered by the stock market data?', 'What are the average closing prices for each ticker?']}, 'attachment_id': '01f0e35216371d48bc3c6a9d1dc0033d'}
    ],
    'auto_regenerate_count': 0,
    'message_id': '01f0e35212d513c2a84e0e23b89f63a0'
}

{
    'id': '01f0e357610717fdaa79ce36aff55d48',
    'space_id': '01f0d08866f11370b6735facce14e3ff',
    'conversation_id': '01f0e35760fa12a98c253758e632c318',
    'user_id': 78631925261941,
    'created_timestamp': 1766862487802,
    'last_updated_timestamp': 1766862494461,
    'status': 'COMPLETED',
    'content': 'What stock had the most traded volume in 2025?',
    'attachments': 
        [
            {
                'query': {
                    'query': 'SELECT `Ticker`, SUM(`Volume`) AS total_volume\nFROM `ai_data_engineer`.`price_volume`.`yahoo_finance_price_volume`\nWHERE YEAR(`Date`) = 2025 AND `Ticker` IS NOT NULL AND `Volume` IS NOT NULL\nGROUP BY `Ticker`\nORDER BY total_volume DESC\nLIMIT 1',
                    'description': 'You want to find the stock ticker that had the highest total trading volume in the year 2025.',
                    'statement_id': '01f0e357-6311-14c1-8d03-4676a2ddce70',
                    'query_result_metadata': {'row_count': 1}
                },
                'attachment_id': '01f0e35763041059b7102eca6703d021'},
            {
                'suggested_questions': {'questions': ['Which stock had the most traded volume in 2024?', 'What was the total traded volume for AAPL in 2025?', 'What was the average daily trading volume for TSLA in 2025?']},
                'attachment_id': '01f0e35764f41ca2906e0982337d7405'
            }
        ],
        'query_result': {
            'statement_id': '01f0e357-6311-14c1-8d03-4676a2ddce70',
            'row_count': 1
        },
        'auto_regenerate_count': 0,
        'message_id': '01f0e357610717fdaa79ce36aff55d48'
    }


get_sql_query = f"/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result"
response = requests.get(
    WORKSPACE_URL+get_sql_query,
    headers=w.config.authenticate()
)
response_dict = dict[Any, Any](response.json())
print(response_dict)

# No returned sql query, only error message
# {'error_code': 'BAD_REQUEST', 'message': 'Attachment with ID 01f0e356ed5b1ef89243753d490ebd18 is not a valid query attachment.', 'details': [{'@type': 'type.googleapis.com/google.rpc.RequestInfo', 'request_id': '8a8ddc55-3eea-9d22-a6cb-ce4f474273c5', 'serving_data': ''}]}

{
    'statement_response': 
    {
        'statement_id': '01f0e358-b719-16d9-b59d-85cce117e730',
        'status': {'state': 'SUCCEEDED'},
        'manifest': {
            'format': 'JSON_ARRAY',
            'schema': {
                'column_count': 2,
                'columns': [
                    {'name': 'Ticker', 'type_text': 'STRING', 'type_name': 'STRING', 'position': 0},
                    {'name': 'total_volume', 'type_text': 'BIGINT', 'type_name': 'LONG', 'position': 1}
                ]
            },
            'total_chunk_count': 1,
            'chunks': [
                {'chunk_index': 0, 'row_offset': 0, 'row_count': 1, 'byte_count': 472}
            ],
            'total_row_count': 1,
            'total_byte_count': 472,
            'truncated': False
        },
        'result': {
            'chunk_index': 0,
            'row_offset': 0,
            'row_count': 1,
            'data_array': [['NVDA', '51746176100']]
        }
    }
}