#!/usr/bin/env python3
import json, os, subprocess, traceback, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET

E = "arn:aws:iam::125746528491:role/metricforge-entry-b8358a07fc"
B = "arn:aws:iam::125746528491:role/metricforge-broker-9d7a0ac7cc"
F = "arn:aws:iam::125746528491:role/metricforge-final-329005447e"
R = "ap-northeast-2"
AMI = "ami-0efca712577c4c937"
ATT = "bdeeb30544829362"
SI = "git-30b28c539ebd"
BE = "mf-broker-bdeeb30544829362"
FE = "01c4cc693cad98d62dbba067"
P = "/metricforge/recovery/final-seed"


def mint():
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=sts.amazonaws.com"
    req = urllib.request.Request(
        url,
        headers={"Authorization": "bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)["value"]


def decode_claims(token):
    import base64
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))
    keys = ("iss", "sub", "aud", "job_workflow_ref", "repository", "workflow_ref", "actor")
    return {k: claims.get(k) for k in keys}


def assume_oidc_http(role, token, sess):
    body = urllib.parse.urlencode(
        {
            "Action": "AssumeRoleWithWebIdentity",
            "Version": "2011-06-15",
            "RoleArn": role,
            "RoleSessionName": sess,
            "WebIdentityToken": token,
            "DurationSeconds": "3600",
        }
    ).encode()
    req = urllib.request.Request("https://sts.amazonaws.com/", data=body)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")
        raise RuntimeError(f"sts_http_{err.code}: {detail[:1500]}") from err
    root = ET.fromstring(raw)
    ns = {"s": "https://sts.amazonaws.com/doc/2011-06-15/"}
    c = root.find(".//s:Credentials", ns)
    if c is None:
        raise RuntimeError("credentials_missing: " + raw[:500].decode())
    return {
        "AccessKeyId": c.findtext("s:AccessKeyId", namespaces=ns),
        "SecretAccessKey": c.findtext("s:SecretAccessKey", namespaces=ns),
        "SessionToken": c.findtext("s:SessionToken", namespaces=ns),
    }


def assume_oidc_cli(token, sess):
    proc = subprocess.run(
        [
            "aws",
            "sts",
            "assume-role-with-web-identity",
            "--role-arn",
            E,
            "--role-session-name",
            sess,
            "--web-identity-token",
            token,
            "--duration-seconds",
            "3600",
            "--output",
            "json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
        env={**os.environ, "AWS_EC2_METADATA_DISABLED": "true", "AWS_PAGER": ""},
    )
    if proc.returncode:
        raise RuntimeError(f"cli_fail: {proc.stderr[-1500:]}")
    creds = json.loads(proc.stdout)["Credentials"]
    return {
        "AccessKeyId": creds["AccessKeyId"],
        "SecretAccessKey": creds["SecretAccessKey"],
        "SessionToken": creds["SessionToken"],
    }


def env(c):
    e = os.environ.copy()
    e.update(
        {
            "AWS_ACCESS_KEY_ID": c["AccessKeyId"],
            "AWS_SECRET_ACCESS_KEY": c["SecretAccessKey"],
            "AWS_SESSION_TOKEN": c["SessionToken"],
            "AWS_DEFAULT_REGION": R,
            "AWS_REGION": R,
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_PAGER": "",
        }
    )
    return e


def aws(e, a):
    p = subprocess.run(
        ["aws", *a],
        env=e,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    if p.returncode:
        return {"ok": False, "error": p.stderr[-1500:]}
    try:
        return {"ok": True, "value": json.loads(p.stdout) if p.stdout.strip() else None}
    except Exception:
        return {"ok": True, "value": p.stdout.strip()}


def main():
    rep = {"stage": "final"}
    try:
        tok = mint()
        rep["claims"] = decode_claims(tok)
    except Exception as ex:
        rep["mint_error"] = f"{type(ex).__name__}: {ex}"
        print(json.dumps(rep, indent=2, sort_keys=True))
        return

    try:
        entry = assume_oidc_cli(tok, "oidc-30b28c53")
        rep["entry_via"] = "cli"
    except Exception as ex1:
        rep["cli_error"] = str(ex1)[:1500]
        try:
            entry = assume_oidc_http(E, tok, "oidc-30b28c53")
            rep["entry_via"] = "http"
        except Exception as ex2:
            rep["http_error"] = str(ex2)[:1500]
            print(json.dumps(rep, indent=2, sort_keys=True))
            return

    rep["entry_ok"] = True
    ee = env(entry)
    br = aws(
        ee,
        [
            "sts",
            "assume-role",
            "--role-arn",
            B,
            "--role-session-name",
            "recover-30b28c53",
            "--external-id",
            BE,
            "--source-identity",
            SI,
            "--tags",
            f"Key=AmiId,Value={AMI}",
            f"Key=Attestation,Value={ATT}",
            "--transitive-tag-keys",
            "AmiId",
            "Attestation",
            "--output",
            "json",
        ],
    )
    if not br.get("ok"):
        rep["broker_err"] = br.get("error")
        print(json.dumps(rep, indent=2, sort_keys=True))
        return
    rep["broker_ok"] = True
    be = env(br["value"]["Credentials"])
    fr = aws(
        be,
        [
            "sts",
            "assume-role",
            "--role-arn",
            F,
            "--role-session-name",
            "final-77c4c937",
            "--external-id",
            FE,
            "--source-identity",
            SI,
            "--output",
            "json",
        ],
    )
    if not fr.get("ok"):
        rep["final_err"] = fr.get("error")
        print(json.dumps(rep, indent=2, sort_keys=True))
        return
    rep["final_ok"] = True
    fe = env(fr["value"]["Credentials"])
    sd = aws(
        fe,
        ["ssm", "get-parameter", "--name", P, "--with-decryption", "--output", "json"],
    )
    if sd.get("ok"):
        rep["seed"] = sd["value"]["Parameter"]["Value"]
    else:
        rep["seed_err"] = sd.get("error")
    print(json.dumps(rep, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
