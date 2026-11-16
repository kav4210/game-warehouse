"""AWS Lambda entry point. Triggered on a schedule (EventBridge). Builds the warehouse in /tmp,
uploads the three mart CSVs and alerts.json to S3 under a dated prefix."""
import os, shutil, datetime, boto3
HERE=os.path.dirname(os.path.abspath(__file__))
def handler(event, context):
    bucket=os.environ['MART_BUCKET']; work='/tmp/gamewh'
    shutil.rmtree(work, ignore_errors=True); os.makedirs(f'{work}/data'); os.makedirs(f'{work}/src')
    shutil.copy(f'{HERE}/marts.sql', f'{work}/src/marts.sql')
    cwd=os.getcwd(); os.chdir(work)
    try:
        import sys; sys.path.insert(0, HERE)
        import generate_raw, pipeline
        generate_raw.generate(out='data'); pipeline.run()
    finally:
        os.chdir(cwd)
    s3=boto3.client('s3'); prefix=datetime.date.today().isoformat()
    keys=[]
    for f in ['mart_game_quarterly.csv','mart_region_channel.csv','mart_engagement.csv','alerts.json']:
        k=f'{prefix}/{f}'; s3.upload_file(f'{work}/data/{f}', bucket, k); keys.append(k)
    return {'bucket':bucket,'uploaded':keys}
