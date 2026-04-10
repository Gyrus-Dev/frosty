from src.session import Session
from google.adk.tools import ToolContext
from snowflake.snowpark.exceptions import SnowparkSQLException
import logging


def _get_session(tool_context: ToolContext):
    """Helper function to get Snowflake session from tool context."""
    session_inst = Session()
    username = tool_context.state.get("user:SNOWFLAKE_USER_NAME")
    account = tool_context.state.get("app:ACCOUNT_IDENTIFIER")
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


def list_all_warehouses(tool_context: ToolContext) -> dict:
    """List all warehouses accessible to the user."""
    logger = logging.getLogger(tool_context.state.get("app:LOGGER")).getChild(__name__)
    logger.debug("list_all_warehouses called")
    try:
        session = _get_session(tool_context)
        rows = session.sql("SHOW WAREHOUSES").collect()
        records = [row.as_dict() if hasattr(row, "as_dict") else dict(row) for row in rows]
        return {
            "warehouses": records,
            "count": len(records),
            "message": f"Found {len(records)} warehouse(s)",
        }
    except SnowparkSQLException as e:
        logger.error("Snowflake SQL error listing warehouses: %s", str(e))
        return {
            "warehouses": [],
            "count": 0,
            "error": str(e),
            "message": f"Snowflake SQL error listing warehouses: {str(e)}",
        }
    except Exception as e:
        logger.error("Error listing warehouses: %s", str(e))
        return {
            "warehouses": [],
            "count": 0,
            "error": str(e),
            "message": f"Error listing warehouses: {str(e)}",
        }


def check_warehouse_exists(warehouse_name: str, tool_context: ToolContext) -> dict:
    """Check if a warehouse exists in Snowflake."""
    logger = logging.getLogger(tool_context.state.get("app:LOGGER")).getChild(__name__)
    logger.debug("check_warehouse_exists called for warehouse '%s'", warehouse_name)
    warehouse_name_upper = warehouse_name.upper()
    try:
        session = _get_session(tool_context)
        rows = session.sql(f"SHOW WAREHOUSES LIKE '{warehouse_name_upper}'").collect()
        exists = len(rows) > 0
        return {
            "exists": exists,
            "warehouse_name": warehouse_name_upper,
            "message": f"Warehouse '{warehouse_name_upper}' {'exists' if exists else 'does not exist'}",
        }
    except SnowparkSQLException as e:
        logger.error("Snowflake SQL error checking warehouse '%s': %s", warehouse_name, str(e))
        return {
            "exists": False,
            "warehouse_name": warehouse_name_upper,
            "error": str(e),
            "message": f"Snowflake SQL error checking warehouse '{warehouse_name_upper}': {str(e)}",
        }
    except Exception as e:
        logger.error("Error checking warehouse '%s': %s", warehouse_name, str(e))
        return {
            "exists": False,
            "warehouse_name": warehouse_name_upper,
            "error": str(e),
            "message": f"Error checking warehouse '{warehouse_name_upper}': {str(e)}",
        }
