from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request

def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") in ["admin", "manager"]:
                return fn(*args, **kwargs)
            else:
                return jsonify(msg="Accès refusé : Droits administrateur ou gestionnaire requis"), 403
        return decorator
    return wrapper
