import requests
from rethinkdb import ReqlTimeoutError, r

r.connect("isard-db", 28015).repl()


def activate_shares():
    try:
        r.db("isard").table("config").get(1).update(
            {"shares": {"templates": True, "isos": True}}
        ).run()
        print("Shares between categories activated")
    except Exception as e:
        print("Error activating shares.\n" + str(e))


activate_shares()
print(
    "Webapp docker服务需要重新启动才能应用更改：docker restart isard-webapp"
)
