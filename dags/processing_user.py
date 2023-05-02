from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
# from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
# from airflow.providers.snowflake.sensors.snowflake import SnowflakeSensor
from airflow.providers.http.sensors.http import HttpSensor
from airflow.operators.python_operator import PythonOperator
from airflow.providers.http.operators.http import SimpleHttpOperator


from airflow.utils.dates import days_ago
from datetime import datetime, timedelta

from pandas import json_normalize
import json


def _process_user(ti):
    user = ti.xcom_pull(task_ids="extract_user")
    user = user['results'][0]
    processed_user = json_normalize({
        'firstname': user['name']['first'],
        'lastname': user['name']['last'],
        'country': user['location']['country'],
        'username': user['login']['username'],
        'password': user['login']['password'],
        'email': user['email'] })
    processed_user.to_csv('/tmp/processed_user.csv', index=None, header=False)

def _store_users():
    hook = PostgresHook(postgres_conn_id = 'postgres')
    hook.copy_expert(
        sql="COPY users FROM stdin WITH DELIMITER as ','",
        filename='/tmp/processed_user.csv'
    )

with DAG(
    'user_processing',
    # default_args=default_args,
    description='A simple test DAG',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2023, 4,1),
    tags=['TEST']
) as dag:
    # Task 1
    create_table = PostgresOperator(
        task_id='create_table',
        postgres_conn_id = 'postgres',
        sql='''
            CREATE TABLE IF NOT EXISTS USERS (
            firstname text not null,
            lastname text not null,
            country text not null,
            username text not null,
            password text not null,
            email text not null
            )
        '''
    )

    is_api_available = HttpSensor(
        task_id = 'is_api_available',
        http_conn_id = 'user_api',
        endpoint = 'api/'
    )

    extract_user = SimpleHttpOperator(
        task_id="extract_user",
        http_conn_id="user_api",
        method='GET',
        endpoint='api/',
        # data={"param1": "value1"},
        # headers={"Content-Type": "application/json"},
        # response_check=lambda response: response.json()['json']['priority'] == 5,
        response_filter=lambda response: json.loads(response.text),
        log_response = True
        # extra_options: Optional[Dict[str, Any]] = None,
        
        # auth_type: Type[AuthBase] = HTTPBasicAuth,
)

    process_users = PythonOperator(
        task_id="process_users",
        python_callable=_process_user
        # op_kwargs: Optional[Dict] = None,
        # op_args: Optional[List] = None,
        # templates_dict: Optional[Dict] = None
        # templates_exts: Optional[List] = None
)

    store_users = PythonOperator(
        task_id = 'store_users',
        python_callable = _store_users    )

create_table >> is_api_available >> extract_user >> process_users >> store_users

