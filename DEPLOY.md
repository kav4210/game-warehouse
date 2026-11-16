# Deploy the Lambda (about 30 minutes, you do this part)
1. Create an S3 bucket for the marts.
2. Zip the contents of `src/` and create a Lambda (Python 3.12), handler `lambda_handler.handler`.
3. Attach the AWS-managed "AWSSDKPandas-Python312" layer (gives pandas and numpy).
4. Set env var MART_BUCKET to your bucket; give the role s3:PutObject on it; raise timeout to 60s and memory to 512MB.
5. Add an EventBridge schedule (daily), invoke once manually, confirm 4 files appear under today's date prefix.
Until you complete this the project is NOT deployed. Say "tested with moto" until then.
## dbt
cd dbt_project && export DBT_PROFILES_DIR=$PWD && dbt build   (3 models, 10 tests)
