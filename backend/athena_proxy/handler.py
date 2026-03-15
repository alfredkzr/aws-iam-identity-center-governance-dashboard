"""
Athena Proxy Lambda — Query Lifecycle + Fast-Load Cache

Handles frontend requests for assignment data:
  1. Checks S3 cache for pre-rendered summary.json (fast path)
  2. Falls back to running an Athena SQL query (slow path)
  3. Caches the results for subsequent requests
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import fnmatch
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from default_risk_policies import DEFAULT_RISK_POLICIES, RISK_LEVELS

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
INVENTORY_BUCKET = os.environ.get("INVENTORY_BUCKET", "")
ATHENA_RESULTS_BUCKET = os.environ.get("ATHENA_RESULTS_BUCKET", "")
CACHE_BUCKET = os.environ.get("CACHE_BUCKET", "")
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "")
ATHENA_DATABASE = os.environ.get("ATHENA_DATABASE", "")
ATHENA_TABLE = os.environ.get("ATHENA_TABLE", "assignments")
ATHENA_PERMISSION_SETS_TABLE = os.environ.get("ATHENA_PERMISSION_SETS_TABLE", "permission_sets")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
OKTA_DOMAIN = os.environ.get("OKTA_DOMAIN", "")
LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY", "")

RISK_POLICIES_KEY = "risk-policies.json"

CACHE_KEY = "summary.json"
CACHE_MAX_AGE_SECONDS = 3600  # 1 hour

# Valid query types — allowlist to prevent abuse
VALID_QUERY_TYPES = {"all", "summary", "dates", "permission_sets", "permission_sets_dates", "risk_policies", "save_risk_policies"}

# Validate table names at cold-start to prevent SQL injection
_TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
for _tbl_name in (ATHENA_TABLE, ATHENA_PERMISSION_SETS_TABLE):
    if not _TABLE_NAME_PATTERN.match(_tbl_name):
        raise ValueError(
            f"Invalid table name '{_tbl_name}'. "
            "Must match pattern: ^[a-zA-Z_][a-zA-Z0-9_]*$"
        )

# Boto3 clients
boto_config = Config(retries={"max_attempts": 5, "mode": "adaptive"})
athena = boto3.client("athena", config=boto_config)
s3 = boto3.client("s3", config=boto_config)


# Module-level cache for validated tokens: {token_hash: expiry_timestamp}
_token_cache = {}
_TOKEN_CACHE_MAX = 200


def _validate_token(event):
    """Validate the Okta access token by calling Okta's /userinfo endpoint.

    This delegates cryptographic signature verification to Okta's server,
    requiring no external Python dependencies (uses only urllib from stdlib).

    Validated tokens are cached in-memory (keyed by SHA-256 hash) until their
    exp claim, so repeated requests with the same token avoid network calls.

    Returns (True, payload) on success or (False, error_message) on failure.
    Skips validation entirely when OKTA_DOMAIN is not configured (local dev).
    """
    if not OKTA_DOMAIN:
        if not LOCAL_API_KEY:
            logger.warning("No auth mechanism configured (no OKTA_DOMAIN, no LOCAL_API_KEY)")
            return False, "Server authentication not configured"
        headers = event.get("headers") or {}
        provided_key = headers.get("x-api-key", "")
        if not provided_key:
            return False, "Missing X-Api-Key header"
        if not hmac.compare_digest(provided_key, LOCAL_API_KEY):
            return False, "Invalid API key"
        return True, {"auth": "api_key"}

    headers = event.get("headers") or {}
    token = headers.get("x-auth-token", "")
    if not token:
        return False, "Missing X-Auth-Token header"

    # Check in-memory cache first (avoids network call for repeat requests)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cached_exp = _token_cache.get(token_hash)
    if cached_exp and time.time() < cached_exp:
        return True, {"cached": True}

    # Validate token via Okta's userinfo endpoint (Okta verifies the signature)
    try:
        userinfo_url = f"https://{OKTA_DOMAIN}/oauth2/default/v1/userinfo"
        req = urllib.request.Request(
            userinfo_url,
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            userinfo = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        logger.warning(f"Okta userinfo returned {e.code}")
        return False, "Invalid or expired token"
    except Exception as e:
        logger.warning(f"Okta userinfo call failed: {e}")
        return False, "Token validation failed"

    # Extract expiry from the token for caching (best-effort decode)
    cache_ttl = 300  # default 5-minute cache if we can't read exp
    try:
        parts = token.split(".")
        if len(parts) == 3:
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get("exp", 0)
            if exp > time.time():
                cache_ttl = exp - time.time()
    except Exception:
        pass

    # Evict oldest entries if cache is full
    if len(_token_cache) >= _TOKEN_CACHE_MAX:
        _token_cache.clear()

    _token_cache[token_hash] = time.time() + min(cache_ttl, 3600)

    return True, userinfo


def lambda_handler(event, context):
    """Main entry point — returns assignment data as JSON with CORS headers."""
    try:
        # Validate authentication when Okta is configured
        valid, token_result = _validate_token(event)
        if not valid:
            logger.warning(f"Auth rejected: {token_result}")
            return _response(401, {"error": "Unauthorized"})

        # Determine the query type from the request
        query_type = _get_query_type(event)
        logger.info(f"Request query_type={query_type}")

        # Validate query type against allowlist
        if query_type not in VALID_QUERY_TYPES:
            logger.warning(f"Invalid query_type received: {query_type}")
            return _response(400, {"error": f"Invalid query type. Must be one of: {', '.join(VALID_QUERY_TYPES)}"})

        # Fast path: list available dates quickly directly from S3
        if query_type == "dates":
            dates = _get_available_dates()
            return _response(200, {"dates": dates})

        # Fast path: list available permission sets dates from S3
        if query_type == "permission_sets_dates":
            dates = _get_available_dates(prefix="permission_sets/snapshot_date=")
            return _response(200, {"dates": dates})

        # Risk policies: read or save
        if query_type == "risk_policies":
            return _handle_get_risk_policies()

        if query_type == "save_risk_policies":
            return _handle_save_risk_policies(event)

        # Permission sets: read directly from S3 JSON (fast path, no Athena needed)
        if query_type == "permission_sets":
            snapshot_date = _get_snapshot_date(event)
            force_refresh = _is_force_refresh(event)
            return _handle_permission_sets(snapshot_date, force_refresh)

        # Extract snapshot date (if provided)
        snapshot_date = _get_snapshot_date(event)
        logger.info(f"Target snapshot_date={snapshot_date}")

        # Check for force refresh parameter
        force_refresh = _is_force_refresh(event)
        logger.info(f"force_refresh={force_refresh}")

        # Fast path: check cache first (skip if force_refresh is True)
        if not force_refresh:
            cached = _get_cached_summary(snapshot_date)
            if cached is not None:
                logger.info("Cache hit — returning cached summary")
                return _response(200, cached)
        else:
            logger.info("Force refresh requested — bypassing cache")

        # Slow path: run Athena query
        logger.info("Cache miss or force refresh — running Athena query")
        results = _run_athena_query(query_type, snapshot_date)

        # Build summary and cache it
        summary = _build_summary(results, snapshot_date)
        _put_cached_summary(summary, snapshot_date)

        return _response(200, summary)

    except Exception as exc:
        logger.exception(f"Error processing request: {exc}")
        return _response(500, {"error": "Internal server error"})


# ---------------------------------------------------------------------------
# Cache Layer
# ---------------------------------------------------------------------------
def _get_cache_key(snapshot_date):
    if snapshot_date:
        return f"summary_{snapshot_date}.json"
    return CACHE_KEY

def _get_cached_summary(snapshot_date=None):
    """Try to load summary.json from cache bucket. Returns None if stale or missing."""
    key = _get_cache_key(snapshot_date)
    try:
        response = s3.get_object(Bucket=CACHE_BUCKET, Key=key)
        last_modified = response["LastModified"]
        age = (datetime.now(timezone.utc) - last_modified).total_seconds()

        if age > CACHE_MAX_AGE_SECONDS:
            logger.info(f"Cache is stale ({age:.0f}s old)")
            return None

        body = response["Body"].read().decode("utf-8")
        return json.loads(body)

    except s3.exceptions.NoSuchKey:
        logger.info("No cache file found")
        return None
    except Exception as exc:
        logger.warning(f"Cache read failed: {exc}")
        return None


def _put_cached_summary(summary, snapshot_date=None):
    """Write summary.json to cache bucket."""
    key = _get_cache_key(snapshot_date)
    try:
        s3.put_object(
            Bucket=CACHE_BUCKET,
            Key=key,
            Body=json.dumps(summary, default=str).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Summary cached successfully")
    except Exception as exc:
        logger.warning(f"Cache write failed: {exc}")


# ---------------------------------------------------------------------------
# Athena Query Lifecycle
# ---------------------------------------------------------------------------
def _run_athena_query(query_type="all", snapshot_date=None):
    """Execute an Athena query and return the results."""
    sql = _get_query_sql(query_type, snapshot_date)

    # Start query execution
    start_response = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        WorkGroup=ATHENA_WORKGROUP,
    )
    query_execution_id = start_response["QueryExecutionId"]
    logger.info(f"Started Athena query: {query_execution_id}")

    # Poll for completion
    result = _wait_for_query(query_execution_id)

    if result["QueryExecution"]["Status"]["State"] != "SUCCEEDED":
        reason = result["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
        raise RuntimeError(f"Athena query failed: {reason}")

    # Fetch results
    return _fetch_results(query_execution_id)


def _wait_for_query(query_execution_id, max_wait=55):
    """Poll Athena for query completion. Max wait ~55s to stay within Lambda timeout."""
    start = time.time()
    delay = 0.5

    while True:
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = response["QueryExecution"]["Status"]["State"]

        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return response

        elapsed = time.time() - start
        if elapsed > max_wait:
            athena.stop_query_execution(QueryExecutionId=query_execution_id)
            raise TimeoutError(f"Athena query timed out after {max_wait}s")

        time.sleep(min(delay, max_wait - elapsed))
        delay = min(delay * 1.5, 5)  # Exponential backoff, max 5s


def _fetch_results(query_execution_id):
    """Fetch all result rows from a completed Athena query."""
    rows = []
    kwargs = {"QueryExecutionId": query_execution_id, "MaxResults": 1000}
    headers = None

    while True:
        response = athena.get_query_results(**kwargs)
        result_rows = response["ResultSet"]["Rows"]

        for row in result_rows:
            values = [col.get("VarCharValue", "") for col in row["Data"]]
            if headers is None:
                headers = values  # First row is column headers
            else:
                rows.append(dict(zip(headers, values)))

        next_token = response.get("NextToken")
        if not next_token:
            break
        kwargs["NextToken"] = next_token

    logger.info(f"Fetched {len(rows)} rows from Athena")
    return rows


# ---------------------------------------------------------------------------
# Query Builder
# ---------------------------------------------------------------------------
def _get_query_sql(query_type, snapshot_date):
    """Return the SQL query for the given type. Table name is validated at cold-start."""
    date_filter = f"WHERE snapshot_date = '{snapshot_date}'" if snapshot_date else ""

    if query_type == "summary":
        return f"""
            SELECT
                account_id,
                account_name,
                COUNT(*) as total_assignments,
                COUNT(DISTINCT principal_name) as unique_principals,
                COUNT(DISTINCT permission_set_name) as unique_permission_sets
            FROM {ATHENA_TABLE}
            {date_filter}
            GROUP BY account_id, account_name
            ORDER BY total_assignments DESC
        """
    else:
        return f"""
            SELECT
                account_id,
                account_name,
                principal_type,
                principal_name,
                principal_email,
                permission_set_name,
                permission_set_arn,
                group_name
            FROM {ATHENA_TABLE}
            {date_filter}
            ORDER BY account_name, principal_name
        """


# ---------------------------------------------------------------------------
# Summary Builder
# ---------------------------------------------------------------------------
def _build_summary(rows, snapshot_date=None):
    """Build a summary object from query results."""
    accounts = set()
    principals = set()
    permission_sets = set()

    for row in rows:
        accounts.add(row.get("account_id", ""))
        principals.add(row.get("principal_name", ""))
        permission_sets.add(row.get("permission_set_name", ""))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_date": snapshot_date,
        "stats": {
            "total_assignments": len(rows),
            "total_accounts": len(accounts),
            "total_principals": len(principals),
            "total_permission_sets": len(permission_sets),
        },
        "assignments": rows,
    }


# ---------------------------------------------------------------------------
# HTTP Response Helper
# ---------------------------------------------------------------------------
def _get_query_type(event):
    """Extract query type from Lambda Function URL event."""
    params = event.get("queryStringParameters") or {}
    return params.get("type", "all")

def _get_snapshot_date(event):
    """Extract requested snapshot date, sanitize it to YYYY-MM-DD."""
    params = event.get("queryStringParameters") or {}
    date_str = params.get("date")
    if date_str and re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    return None

def _is_force_refresh(event):
    """Check if force refresh is requested via query parameter."""
    params = event.get("queryStringParameters") or {}
    return params.get("force", "").lower() == "true"

def _get_available_dates(prefix="assignments/snapshot_date="):
    """List out snapshot dates directly from S3 by finding common prefixes."""
    try:
        response = s3.list_objects_v2(
            Bucket=INVENTORY_BUCKET,
            Prefix=prefix,
            Delimiter="/"
        )
        prefixes = response.get("CommonPrefixes", [])
        
        dates = []
        for p in prefixes:
            match = re.search(r"snapshot_date=(\d{4}-\d{2}-\d{2})", p["Prefix"])
            if match:
                dates.append(match.group(1))
        
        # Return sorted descending (newest first)
        return sorted(dates, reverse=True)
    except Exception as exc:
        logger.error(f"Failed to fetch dates from S3: {exc}")
        return []


# ---------------------------------------------------------------------------
# Risk Evaluation Helpers (re-evaluate at query time)
# ---------------------------------------------------------------------------
def _load_risk_policies():
    """Load risk policies from S3 or fall back to defaults.

    Unlike the worker, this does NOT use a module-level cache so that
    every request picks up the latest saved rules.
    """
    try:
        resp = s3.get_object(Bucket=INVENTORY_BUCKET, Key=RISK_POLICIES_KEY)
        body = resp["Body"].read().decode("utf-8")
        policies = json.loads(body)
        logger.info("Loaded custom risk policies from S3 for re-evaluation")
        return policies
    except Exception:
        logger.info("No custom risk policies in S3 — using defaults for re-evaluation")
        return DEFAULT_RISK_POLICIES


def _match_pattern(value, pattern):
    """Check if a value matches a pattern. Auto-detects wildcard patterns.

    Special case: a bare '*' or '*:*' pattern is treated as an exact match
    (catches literal IAM Action: '*'), not as a glob that matches everything.
    """
    if pattern in ('*', '*:*'):
        return value == pattern
    if any(c in pattern for c in ('*', '?', '[', ']')):
        return fnmatch.fnmatch(value, pattern)
    return value == pattern


def _evaluate_risk(record, risk_rules):
    """Evaluate a permission set record against risk rules.

    Returns (risk_level, risk_reasons) where risk_level is the highest
    matched level and risk_reasons is a list of matched rule descriptions.
    """
    highest_level = "low"
    reasons = []

    rules = risk_rules.get("rules", [])

    # Collect all policy names for managed_policy_name rules
    policy_names = []
    for p in record.get("aws_managed_policies", []):
        policy_names.append(p.get("name", ""))
    for p in record.get("customer_managed_policies", []):
        policy_names.append(p.get("name", ""))

    # Collect all inline policy actions
    inline_actions = []
    inline_policy_str = record.get("inline_policy", "")
    if inline_policy_str:
        try:
            policy_doc = json.loads(inline_policy_str) if isinstance(inline_policy_str, str) else inline_policy_str
            statements = policy_doc.get("Statement", [])
            if isinstance(statements, dict):
                statements = [statements]
            for stmt in statements:
                if stmt.get("Effect", "").lower() != "allow":
                    continue
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                inline_actions.extend(actions)
        except (json.JSONDecodeError, AttributeError):
            pass

    for rule in rules:
        rule_type = rule.get("type", "")
        pattern = rule.get("pattern", "")
        risk = rule.get("risk", "low")
        reason = rule.get("reason", "")

        matched = False

        if rule_type == "managed_policy_name":
            for name in policy_names:
                if _match_pattern(name, pattern):
                    matched = True
                    break
        elif rule_type == "inline_policy_action":
            for action in inline_actions:
                if _match_pattern(action, pattern):
                    matched = True
                    break

        if matched:
            reasons.append({
                "rule": pattern,
                "risk": risk,
                "reason": reason,
            })
            if RISK_LEVELS.get(risk, 0) > RISK_LEVELS.get(highest_level, 0):
                highest_level = risk

    return highest_level, reasons


def _reeval_risk_scores(records):
    """Re-evaluate risk scores on a list of permission set records in place."""
    risk_policies = _load_risk_policies()
    for record in records:
        risk_level, risk_reasons = _evaluate_risk(record, risk_policies)
        record["risk_level"] = risk_level
        record["risk_reasons"] = risk_reasons


def _handle_permission_sets(snapshot_date, force_refresh):
    """Handle permission sets request — reads JSON directly from S3."""
    cache_key = f"ps_summary_{snapshot_date}.json" if snapshot_date else "ps_summary.json"

    # Check cache first
    if not force_refresh:
        try:
            cached_resp = s3.get_object(Bucket=CACHE_BUCKET, Key=cache_key)
            last_modified = cached_resp["LastModified"]
            age = (datetime.now(timezone.utc) - last_modified).total_seconds()
            if age <= CACHE_MAX_AGE_SECONDS:
                logger.info("Permission sets cache hit")
                body = cached_resp["Body"].read().decode("utf-8")
                cached_data = json.loads(body)
                # Re-evaluate risk at query time (always uses latest rules)
                _reeval_risk_scores(cached_data.get("permission_sets", []))
                return _response(200, cached_data)
        except Exception:
            pass

    # Determine target date
    if not snapshot_date:
        dates = _get_available_dates(prefix="permission_sets/snapshot_date=")
        snapshot_date = dates[0] if dates else None

    if not snapshot_date:
        return _response(200, {"permission_sets": [], "snapshot_date": None})

    # Read JSON Lines from S3
    s3_key = f"permission_sets/snapshot_date={snapshot_date}/permission_sets.json"
    try:
        obj = s3.get_object(Bucket=INVENTORY_BUCKET, Key=s3_key)
        raw = obj["Body"].read().decode("utf-8")
        records = [json.loads(line) for line in raw.strip().split("\n") if line.strip()]
    except s3.exceptions.NoSuchKey:
        logger.info(f"No permission sets data for {snapshot_date}")
        records = []
    except Exception as exc:
        logger.error(f"Failed to read permission sets from S3: {exc}")
        records = []

    # Re-evaluate risk at query time (always uses latest rules)
    _reeval_risk_scores(records)

    result = {
        "snapshot_date": snapshot_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "permission_sets": records,
        "stats": {
            "total_permission_sets": len(records),
        },
    }

    # Cache result
    try:
        s3.put_object(
            Bucket=CACHE_BUCKET,
            Key=cache_key,
            Body=json.dumps(result, default=str).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as exc:
        logger.warning(f"Failed to cache permission sets: {exc}")

    return _response(200, result)

# ---------------------------------------------------------------------------
# Risk Policies Handlers
# ---------------------------------------------------------------------------
def _handle_get_risk_policies():
    """Read risk-policies.json from S3 or return defaults."""
    try:
        resp = s3.get_object(Bucket=INVENTORY_BUCKET, Key=RISK_POLICIES_KEY)
        body = resp["Body"].read().decode("utf-8")
        policies = json.loads(body)
        logger.info("Loaded custom risk policies from S3")
        return _response(200, {"source": "custom", "policies": policies})
    except Exception:
        logger.info("No custom risk policies — returning defaults")
        return _response(200, {"source": "default", "policies": DEFAULT_RISK_POLICIES})


def _handle_save_risk_policies(event):
    """Save risk-policies.json to S3."""
    try:
        # Parse request body
        body = event.get("body", "")
        if isinstance(body, str):
            policies = json.loads(body)
        else:
            policies = body

        # Validate schema
        if not isinstance(policies, dict):
            return _response(400, {"error": "Request body must be a JSON object"})
        if "rules" not in policies:
            return _response(400, {"error": "Missing 'rules' array in request body"})
        if not isinstance(policies["rules"], list):
            return _response(400, {"error": "'rules' must be an array"})

        # Validate each rule
        required_fields = {"type", "pattern", "risk", "reason"}
        valid_types = {"managed_policy_name", "inline_policy_action"}
        valid_risk = {"critical", "high", "medium", "low"}

        for i, rule in enumerate(policies["rules"]):
            missing = required_fields - set(rule.keys())
            if missing:
                return _response(400, {"error": f"Rule {i}: missing fields: {', '.join(missing)}"})
            if rule["type"] not in valid_types:
                return _response(400, {"error": f"Rule {i}: invalid type '{rule['type']}'. Must be one of: {', '.join(valid_types)}"})
            if rule["risk"] not in valid_risk:
                return _response(400, {"error": f"Rule {i}: invalid risk '{rule['risk']}'. Must be one of: {', '.join(valid_risk)}"})

        # Ensure version field
        policies.setdefault("version", 1)

        # Write to S3
        s3.put_object(
            Bucket=INVENTORY_BUCKET,
            Key=RISK_POLICIES_KEY,
            Body=json.dumps(policies, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

        logger.info(f"Saved {len(policies['rules'])} risk rules to S3")
        return _response(200, {
            "status": "success",
            "message": f"Saved {len(policies['rules'])} risk rules",
            "policies": policies,
        })

    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON in request body"})
    except Exception as exc:
        logger.exception(f"Failed to save risk policies: {exc}")
        return _response(500, {"error": "Failed to save risk policies"})


def _response(status_code, body, event=None):
    """Build a Lambda Function URL response with JSON body.
    Note: CORS headers are handled automatically by the Lambda Function URL configuration.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, default=str),
    }
