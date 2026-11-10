
import httpx

B="http://127.0.0.1:18131"
c=httpx.Client(base_url=B,timeout=300)
c.post("/api/v1/auth/dev-login",params={"email":"admin@dev.local"})
c.headers["x-csrf-token"]=c.cookies.get("ar_csrf")
