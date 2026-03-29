import os
from typing import Any, Dict, Optional
import logging

import snowflake.snowpark as snowpark
from snowflake.core import Root
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)
_debug = os.environ.get("FROSTY_DEBUG", "").lower() in ("1", "true")
logger.setLevel(logging.DEBUG if _debug else logging.WARNING)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.DEBUG if _debug else logging.WARNING)
    _handler.setFormatter(logging.Formatter("[session] %(levelname)s - %(message)s"))
    logger.addHandler(_handler)
logger.propagate = False

# Module-level session cache keyed by (account, user, authenticator, role, warehouse, database).
# Reuses live snowpark sessions across tool calls so MFA is only triggered once per process.
_session_cache: Dict[tuple, Any] = {}


class User:
    def __get__(self,instance,owner):
        return instance._user
    
    def __set__(self,instance,value):
        instance._user = value

    def __delete__(self,instance):
        del instance._user

class Password:
    def __get__(self,instance,owner):
        return instance._password
    
    def __set__(self,instance,value):
        instance._password = value

    def __delete__(self,instance):
        del instance._password

class Account:
    def __get__(self,instance,owner):
        return instance._account
    
    def __set__(self,instance,value):
        instance._account = value

    def __delete__(self,instance):
        del instance._account

class Account:
    def __get__(self,instance,owner):
        return instance._account

    def __set__(self,instance,value):
        instance._account = value

    def __delete__(self,instance):
        del instance._account

class Authenticator:
    def __get__(self,instance,owner):
        return getattr(instance, "_authenticator", None)

    def __set__(self,instance,value):
        instance._authenticator = value

    def __delete__(self,instance):
        del instance._authenticator

class Role:
    def __get__(self,instance,owner):
        return getattr(instance, "_role", None)

    def __set__(self,instance,value):
        instance._role = value

    def __delete__(self,instance):
        del instance._role

class Warehouse:
    def __get__(self,instance,owner):
        return getattr(instance, "_warehouse", None)

    def __set__(self,instance,value):
        instance._warehouse = value

    def __delete__(self,instance):
        del instance._warehouse

class Database:
    def __get__(self,instance,owner):
        return getattr(instance, "_database", None)

    def __set__(self,instance,value):
        instance._database = value

    def __delete__(self,instance):
        del instance._database

class Session:
    def __get__(self,instance,owner):
        return instance._session

    def __set__(self,instance,value):
        instance._session = value

    def __delete__(self,instance):
        del instance._session

class SessionAttr:
    def __init__(self,parent):
        self.parent = parent

    user = User()
    password = Password()
    account = Account()
    authenticator = Authenticator()
    role = Role()
    warehouse = Warehouse()
    database = Database()
    session = Session()

class Session:
    def __init__(self):
        self.attr = SessionAttr(self)

    def set_user(self,value):
        self.attr.user = value

    def set_password(self,value):
        self.attr.password = value

    def set_account(self,value):
        self.attr.account = value

    def set_session(self,value):
        self.attr.session = value

    def set_passcode(self,value):
        self.passcode=value

    def set_authenticator(self,value):
        self.attr.authenticator = value

    def set_role(self,value):
        self.attr.role = value

    def set_warehouse(self,value):
        self.attr.warehouse = value

    def set_database(self,value):
        self.attr.database = value

    def get_session(self):
        if not self.attr.account or not self.attr.user:
            raise ValueError(
                "Snowflake credentials are missing — user and account are required. "
                "Please log in before making any Snowflake requests."
            )
        authenticator = getattr(self.attr, "_authenticator", None)
        if not authenticator and not getattr(self.attr, "_password", None):
            raise ValueError(
                "Snowflake credentials are missing — a password or authenticator is required. "
                "Please log in before making any Snowflake requests."
            )

        connection_params: Dict[str, Any] = {
            "account": self.attr.account,
            "user": self.attr.user,
        }

        authenticator = self.attr.authenticator
        if authenticator:
            connection_params["authenticator"] = authenticator
            # externalbrowser (passkey) does not use a password
            if authenticator != "externalbrowser" and self.attr.password:
                connection_params["password"] = self.attr.password
        else:
            connection_params["password"] = self.attr.password

        for key, attr in (("role", self.attr.role), ("warehouse", self.attr.warehouse), ("database", self.attr.database)):
            if attr:
                connection_params[key] = attr

        cache_key = (
            connection_params.get("account"),
            connection_params.get("user"),
            connection_params.get("authenticator"),
            connection_params.get("role"),
            connection_params.get("warehouse"),
            connection_params.get("database"),
        )

        if cache_key in _session_cache:
            cached = _session_cache[cache_key]
            try:
                cached.sql("SELECT 1").collect()
                logger.debug("Reusing cached Snowflake session for user=%s account=%s", self.attr.user, self.attr.account)
                return cached
            except Exception:
                logger.debug("Cached session expired, creating a new one")
                del _session_cache[cache_key]

        logger.info("━━━ Snowflake connection params ━━━")
        for k, v in connection_params.items():
            display = "***" if k == "password" else v
            logger.info("  %-15s = %s", k, display)
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # --- Inform user what action is required for this authenticator -----
        _auth = connection_params.get("authenticator", "").lower()
        if _auth == "username_password_mfa":
            print("\n\033[1;33m⏳  MFA required — approve the push notification in your Duo/authenticator app,\033[0m")
            print("\033[1;33m   or enter a passcode if prompted below.\033[0m\n")
        elif _auth == "externalbrowser":
            print("\n\033[1;33m🌐  Browser authentication required — a browser window will open shortly.\033[0m\n")

        try:
            session = snowpark.Session.builder.configs(connection_params).create()
        except Exception as e:
            # TOTP MFA requires a current passcode that DUO push does not.
            # Detect this at connection time and prompt the user interactively,
            # then retry once — so DUO push users are never asked for a passcode.
            if "TOTP" in str(e) or ("passcode" in str(e).lower() and "mfa" in str(e).lower()):
                import getpass
                print("\nMFA passcode required (open your authenticator app):")
                passcode = getpass.getpass("TOTP passcode: ").strip()
                connection_params["passcode"] = passcode
                try:
                    session = snowpark.Session.builder.configs(connection_params).create()
                except Exception as retry_e:
                    logger.error("Failed to create Snowflake session after TOTP entry — user=%s account=%s error=%s", self.attr.user, self.attr.account, str(retry_e))
                    raise
            else:
                logger.error("Failed to create Snowflake session — user=%s account=%s error=%s", self.attr.user, self.attr.account, str(e))
                raise

        _session_cache[cache_key] = session
        self.set_session(session)
        logger.debug("Snowflake session created and cached for user=%s account=%s", self.attr.user, self.attr.account)
        return self.attr.session
    
    def get_root_object(self):
        logger.debug("Getting root object from session")
        try:
            root = Root(self.attr.session)
            logger.debug("Root object retrieved successfully")
            return root
        except Exception as e:
            logger.error("Failed to get root object: %s", str(e))
            raise