"""
backend/scripts/init_floci.py

Self-healing initialization script for Floci (local AWS emulator).
Ensures required Secrets Manager secrets, S3 buckets, and SQS queues exist,
and writes the PostgreSQL database password to /run/secrets/pg_password for Docker.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_floci")

ENDPOINT_URL = (
    os.environ.get("AWS_ENDPOINT_URL")
    or os.environ.get("SECRETS_MANAGER_ENDPOINT_URL")
    or "http://localhost:4566"
)
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID") or "test"
SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY") or "test"

DB_SECRET_NAME = os.environ.get("DATABASE_SECRET_NAME") or "day4/film-review/database"
JWT_SECRET_NAME = os.environ.get("JWT_SECRET_NAME") or "day4/film-review/jwt"
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME") or "film-review-assets"
SQS_QUEUE_NAME = os.environ.get("SQS_QUEUE_NAME") or "review-events-queue"
SQS_DLQ_NAME = os.environ.get("SQS_DLQ_NAME") or "review-events-dlq"
SQS_MAX_RECEIVE_COUNT = int(os.environ.get("SQS_MAX_RECEIVE_COUNT", "3"))
SQS_VISIBILITY_TIMEOUT = int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "30"))

MAX_RETRIES = 10
RETRY_DELAY = 2


def wait_for_floci(sm_client) -> bool:
    """Wait until Floci is ready to accept requests."""
    logger.info("Connecting to Floci at %s...", ENDPOINT_URL)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            sm_client.list_secrets(MaxResults=1)
            logger.info("[OK] Connected to Floci successfully.")
            return True
        except (EndpointConnectionError, Exception) as err:
            logger.warning("Floci not ready yet (attempt %d/%d): %s", attempt, MAX_RETRIES, err)
            time.sleep(RETRY_DELAY)
    logger.error("Could not reach Floci after %d attempts.", MAX_RETRIES)
    return False


def ensure_secrets(sm_client) -> str:
    """Ensure database and JWT secrets exist in Secrets Manager. Returns DB password."""
    # 1. Database Secret
    db_password = os.environ.get("POSTGRES_PASSWORD", "password")
    db_payload = {
        "username": os.environ.get("POSTGRES_USER", "postgres"),
        "password": db_password,
        "database": os.environ.get("POSTGRES_DB", "film_review_db"),
        "host": os.environ.get("POSTGRES_HOST", "db"),
        "port": int(os.environ.get("DB_PORT", "5432")),
    }

    try:
        resp = sm_client.get_secret_value(SecretId=DB_SECRET_NAME)
        existing = json.loads(resp.get("SecretString", "{}"))
        db_password = existing.get("password", db_password)
        logger.info("[OK] Secret '%s' already exists.", DB_SECRET_NAME)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ResourceNotFoundException":
            logger.info("Creating missing secret '%s'...", DB_SECRET_NAME)
            sm_client.create_secret(Name=DB_SECRET_NAME, SecretString=json.dumps(db_payload))
            logger.info("[OK] Created secret '%s'.", DB_SECRET_NAME)
        else:
            raise

    # 2. JWT Secret
    jwt_payload = {
        "secret_key": "supersecretjwtkeyforlocaldevelopment1234567890"
    }
    try:
        sm_client.get_secret_value(SecretId=JWT_SECRET_NAME)
        logger.info("[OK] Secret '%s' already exists.", JWT_SECRET_NAME)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ResourceNotFoundException":
            logger.info("Creating missing secret '%s'...", JWT_SECRET_NAME)
            sm_client.create_secret(Name=JWT_SECRET_NAME, SecretString=json.dumps(jwt_payload))
            logger.info("[OK] Created secret '%s'.", JWT_SECRET_NAME)
        else:
            raise

    return db_password


def ensure_s3(s3_client) -> None:
    """Ensure the assets S3 bucket exists."""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        logger.info("[OK] S3 bucket '%s' already exists.", S3_BUCKET_NAME)
    except ClientError:
        try:
            s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
            logger.info("[OK] Created S3 bucket '%s'.", S3_BUCKET_NAME)
        except Exception as exc:
            logger.warning("Could not create S3 bucket '%s': %s", S3_BUCKET_NAME, exc)


def ensure_sqs(sqs_client) -> None:
    """Ensure the review events SQS queue and DLQ exist, and configure RedrivePolicy."""
    # 1. Ensure DLQ exists
    try:
        resp = sqs_client.get_queue_url(QueueName=SQS_DLQ_NAME)
        dlq_url = resp["QueueUrl"]
        logger.info("[OK] SQS DLQ '%s' already exists at %s.", SQS_DLQ_NAME, dlq_url)
    except ClientError:
        try:
            resp = sqs_client.create_queue(QueueName=SQS_DLQ_NAME)
            dlq_url = resp["QueueUrl"]
            logger.info("[OK] Created SQS DLQ '%s' at %s.", SQS_DLQ_NAME, dlq_url)
        except Exception as exc:
            logger.warning("Could not create SQS DLQ '%s': %s", SQS_DLQ_NAME, exc)
            return

    # 2. Retrieve DLQ ARN
    try:
        attrs = sqs_client.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])
        dlq_arn = attrs["Attributes"]["QueueArn"]
        logger.info("[OK] SQS DLQ ARN: %s", dlq_arn)
    except Exception as exc:
        logger.warning("Could not retrieve DLQ ARN for '%s': %s", SQS_DLQ_NAME, exc)
        return

    # 3. Ensure Main Queue exists
    try:
        resp = sqs_client.get_queue_url(QueueName=SQS_QUEUE_NAME)
        main_url = resp["QueueUrl"]
        logger.info("[OK] SQS main queue '%s' already exists at %s.", SQS_QUEUE_NAME, main_url)
    except ClientError:
        try:
            resp = sqs_client.create_queue(QueueName=SQS_QUEUE_NAME)
            main_url = resp["QueueUrl"]
            logger.info("[OK] Created SQS main queue '%s' at %s.", SQS_QUEUE_NAME, main_url)
        except Exception as exc:
            logger.warning("Could not create SQS main queue '%s': %s", SQS_QUEUE_NAME, exc)
            return

    # 4. Configure RedrivePolicy and VisibilityTimeout on Main Queue
    try:
        redrive_policy = {
            "deadLetterTargetArn": dlq_arn,
            "maxReceiveCount": str(SQS_MAX_RECEIVE_COUNT),
        }
        sqs_client.set_queue_attributes(
            QueueUrl=main_url,
            Attributes={
                "RedrivePolicy": json.dumps(redrive_policy),
                "VisibilityTimeout": str(SQS_VISIBILITY_TIMEOUT),
            },
        )
        logger.info(
            "[OK] Configured RedrivePolicy on '%s' -> '%s' (maxReceiveCount=%d, visibilityTimeout=%d).",
            SQS_QUEUE_NAME,
            SQS_DLQ_NAME,
            SQS_MAX_RECEIVE_COUNT,
            SQS_VISIBILITY_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("Could not configure RedrivePolicy on queue '%s': %s", SQS_QUEUE_NAME, exc)


def write_pg_password_file(password: str) -> None:
    """Write database password to /run/secrets/pg_password for PostgreSQL container."""
    secrets_dir = Path("/run/secrets")
    if secrets_dir.exists() or os.name != "nt":
        try:
            secrets_dir.mkdir(parents=True, exist_ok=True)
            pass_file = secrets_dir / "pg_password"
            pass_file.write_text(password)
            try:
                os.chmod(pass_file, 0o400)
            except Exception:
                pass
            logger.info("[OK] Wrote database password to %s.", pass_file)
        except Exception as exc:
            logger.error("Failed to write password file: %s", exc)


def main() -> None:
    boto_kwargs = {
        "endpoint_url": ENDPOINT_URL,
        "region_name": REGION,
        "aws_access_key_id": ACCESS_KEY,
        "aws_secret_access_key": SECRET_KEY,
    }

    sm_client = boto3.client("secretsmanager", **boto_kwargs)
    s3_client = boto3.client("s3", **boto_kwargs)
    sqs_client = boto3.client("sqs", **boto_kwargs)

    if not wait_for_floci(sm_client):
        sys.exit(1)

    db_password = ensure_secrets(sm_client)
    ensure_s3(s3_client)
    ensure_sqs(sqs_client)
    write_pg_password_file(db_password)

    logger.info("=========================================================")
    logger.info("   [SUCCESS] Floci initialization completed successfully  ")
    logger.info("=========================================================")


if __name__ == "__main__":
    main()
