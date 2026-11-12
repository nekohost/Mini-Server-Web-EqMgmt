"""Anonymous production HTTPS smoke test: no credentials and no writes."""
import json
from urllib import request, error

BASE = "https://nekohost.org"
class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
opener = request.build_opener(NoRedirect())
cases = [
    ("/login", "GET", {200}),
    ("/register", "GET", {200}),
    ("/admin_center", "GET", {302, 303, 401, 403}),
    ("/audit_logs", "GET", {302, 303, 401, 403}),
    ("/api/audit_logs", "GET", {302, 303, 401, 403}),
    ("/access_logs", "GET", {302, 303, 401, 403}),
    ("/users_management", "GET", {302, 303, 401, 403}),
    ("/admin/ai/logs", "GET", {302, 303, 401, 403}),
    ("/api/admin/ai/logs", "GET", {302, 303, 401, 403}),
    ("/api/users/create", "POST", {302, 303, 400, 401, 403, 405}),
]
out = []
for path, method, allowed in cases:
    req = request.Request(BASE+path,method=method,headers={
        "Accept": "text/html,application/json", "User-Agent": "Admin-Release-QA/1.0",
        **({"Content-Type": "application/json"} if method == "POST" else {}),
    },data=(b"{}" if method=="POST" else None))
    try:
        with opener.open(req,timeout=12) as response:
            status = response.status
            body = response.read(65536) if path == "/register" else b""
    except error.HTTPError as e:
        status = e.code
        body = b""
    valid = status in allowed and (path != "/register" or "이름 (선택)".encode() in body)
    out.append({"path":path,"method":method,"http":status,"pass":valid})
print(json.dumps({"tests":len(out),"passed":sum(row["pass"] for row in out),
                  "failed":[row for row in out if not row["pass"]],
                  "results":out},ensure_ascii=True))
if not all(row["pass"] for row in out):
    raise SystemExit(1)
