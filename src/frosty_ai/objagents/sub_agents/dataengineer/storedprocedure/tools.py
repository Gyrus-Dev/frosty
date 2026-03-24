import logging

from google.adk.tools import ToolContext


def _get_session(tool_context: ToolContext):
    """Build a Snowpark session from credentials stored in tool context state."""
    from src.session import Session as SnowflakeSession

    username = tool_context.state.get("user:SNOWFLAKE_USER_NAME")
    account = tool_context.state.get("app:ACCOUNT_IDENTIFIER")

    if not username or not account:
        missing = [k for k, v in {"username": username, "account": account}.items() if not v]
        raise ValueError(f"Missing Snowflake credentials in session state: {', '.join(missing)}")

    session_inst = SnowflakeSession()
    session_inst.set_user(username)
    session_inst.set_account(account)
    session_inst.set_password(tool_context.state.get("user:USER_PASSWORD"))
    if tool_context.state.get("user:AUTHENTICATOR"):
        session_inst.set_authenticator(tool_context.state.get("user:AUTHENTICATOR"))
    if tool_context.state.get("user:ROLE"):
        session_inst.set_role(tool_context.state.get("user:ROLE"))
    if tool_context.state.get("app:WAREHOUSE"):
        session_inst.set_warehouse(tool_context.state.get("app:WAREHOUSE"))
    if tool_context.state.get("app:DATABASE"):
        session_inst.set_database(tool_context.state.get("app:DATABASE"))
    return session_inst.get_session()


def create_and_validate_procedure(
    create_sql: str,
    database_name: str,
    schema_name: str,
    procedure_name: str,
    sample_args: list[str],
    tool_context: ToolContext,
) -> dict:
    """
    Validate a stored procedure's syntax and logic using a temporary name —
    WITHOUT persisting anything to Snowflake.

    The tool rewrites the CREATE statement to use a unique temporary procedure
    name (``<procedure_name>_FROSTY_VAL_<8-char-hex>``), runs the CREATE and a
    dry-run CALL inside a transaction, then **always ROLLBACKs** — so nothing is
    left in Snowflake regardless of whether the validation passes or fails.

    On success the agent must follow up with ``execute_query`` using the original
    ``create_sql`` (with the real procedure name) to actually create the procedure.

    Args:
        create_sql: The complete CREATE PROCEDURE statement (any variant —
            ``CREATE OR REPLACE``, ``CREATE IF NOT EXISTS``, or plain
            ``CREATE PROCEDURE``).  The tool rewrites the name internally.
        database_name: Database that owns the procedure.
        schema_name: Schema that owns the procedure.
        procedure_name: Procedure name without qualification.
        sample_args: List of argument value strings for the dry-run CALL,
            e.g. ``["'dry_run_test'", "0", "NULL"]``.  Pass ``[]`` for
            procedures that take no arguments.
        tool_context: ADK tool context carrying session credentials and state.

    Returns:
        On success: ``{ success: True, validated_sql, dry_run_result, message }``
            ``validated_sql`` is the original ``create_sql`` unchanged — pass it
            directly to ``execute_query`` to create the real procedure.
        On failure: ``{ success: False, failed_step, error, message }``
            where ``failed_step`` is ``"CREATE"`` or ``"DRY_RUN"``.
    """
    import re as _re
    import uuid as _uuid

    logger_name = tool_context.state.get("app:LOGGER")
    logger = (
        logging.getLogger(logger_name).getChild(__name__)
        if logger_name
        else logging.getLogger(__name__)
    )

    # Safety gate — DROP is never allowed even in validation
    if "DROP " in create_sql.upper():
        logger.warning("Safety gate blocked create_and_validate_procedure: DROP")
        return {
            "success": False,
            "failed_step": "SAFETY_GATE",
            "error": "'DROP' is not permitted.",
            "message": "Query blocked: 'DROP' is not permitted.",
        }

    # Build a unique temporary procedure name so validation never collides with
    # an existing procedure and nothing meaningful is left after rollback.
    temp_suffix = f"_FROSTY_VAL_{_uuid.uuid4().hex[:8].upper()}"
    temp_procedure_name = f"{procedure_name.upper()}{temp_suffix}"

    # Rewrite the procedure name in the CREATE statement.
    # Replace only the first occurrence of the bare procedure name after the
    # object-type keyword so we don't touch the body.
    temp_sql = _re.sub(
        rf"(?i)(CREATE\s+(?:OR\s+REPLACE\s+)?(?:IF\s+NOT\s+EXISTS\s+)?PROCEDURE\s+"
        rf"(?:{_re.escape(database_name.upper())}\.{_re.escape(schema_name.upper())}\.)?"
        rf"){_re.escape(procedure_name)}",
        rf"\g<1>{temp_procedure_name}",
        create_sql,
        count=1,
        flags=_re.IGNORECASE,
    )

    args_csv = ", ".join(str(a) for a in sample_args)
    temp_call_stmt = (
        f"CALL {database_name.upper()}.{schema_name.upper()}"
        f".{temp_procedure_name}({args_csv})"
    )

    failed_step = None
    session = None
    try:
        session = _get_session(tool_context)

        logger.info(
            "create_and_validate_procedure: BEGIN transaction (temp name: %s)",
            temp_procedure_name,
        )
        session.sql("BEGIN").collect()

        # Step 1: CREATE with temp name
        failed_step = "CREATE"
        logger.info("create_and_validate_procedure: executing CREATE with temp name")
        session.sql(temp_sql).collect()

        # Step 2: DRY RUN CALL against temp procedure
        failed_step = "DRY_RUN"
        logger.info("create_and_validate_procedure: dry-run CALL: %s", temp_call_stmt)
        dry_run_rows = session.sql(temp_call_stmt).collect()
        dry_run_result = [
            row.as_dict() if hasattr(row, "as_dict") else str(row)
            for row in dry_run_rows
        ]

        # Always rollback — validation only, nothing persists
        session.sql("ROLLBACK").collect()
        logger.info(
            "create_and_validate_procedure: ROLLBACK — validation passed, "
            "no procedure persisted. Agent must now call execute_query with original SQL."
        )

        return {
            "success": True,
            "validated_sql": create_sql,
            "dry_run_result": dry_run_result,
            "message": (
                f"Validation passed for '{database_name.upper()}.{schema_name.upper()}"
                f".{procedure_name.upper()}' (tested under temp name '{temp_procedure_name}'). "
                "Transaction rolled back — nothing was persisted. "
                "Now call execute_query with the original SQL to create the real procedure."
            ),
        }

    except Exception as e:
        logger.error(
            "create_and_validate_procedure: %s failed — rolling back. Error: %s",
            failed_step,
            str(e),
        )
        try:
            if session is not None:
                session.sql("ROLLBACK").collect()
                logger.info("create_and_validate_procedure: ROLLBACK completed")
        except Exception as rb_err:
            logger.warning("create_and_validate_procedure: ROLLBACK failed: %s", str(rb_err))

        return {
            "success": False,
            "failed_step": failed_step,
            "error": str(e),
            "message": (
                f"Validation failed at step '{failed_step}': {str(e)}. "
                "Fix the SQL and retry create_and_validate_procedure."
            ),
        }
