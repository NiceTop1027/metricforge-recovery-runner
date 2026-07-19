#!/usr/bin/env python3
import json,os,subprocess,urllib.parse,urllib.request,xml.etree.ElementTree as ET
E="arn:aws:iam::125746528491:role/metricforge-entry-b8358a07fc"
B="arn:aws:iam::125746528491:role/metricforge-broker-9d7a0ac7cc"
F="arn:aws:iam::125746528491:role/metricforge-final-329005447e"
R="ap-northeast-2";AMI="ami-0efca712577c4c937";ATT="bdeeb30544829362";SI="git-30b28c539ebd"
BE="mf-broker-bdeeb30544829362";FE="01c4cc693cad98d62dbba067";P="/metricforge/recovery/final-seed"
def mint():
 r=urllib.request.Request(os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]+"&audience=sts.amazonaws.com",headers={"Authorization":"bearer "+os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
 return json.load(urllib.request.urlopen(r,timeout=20))["value"]
def assume_oidc(role,token,sess):
 body=urllib.parse.urlencode({"Action":"AssumeRoleWithWebIdentity","Version":"2011-06-15","RoleArn":role,"RoleSessionName":sess,"WebIdentityToken":token,"DurationSeconds":"3600"}).encode()
 root=ET.fromstring(urllib.request.urlopen(urllib.request.Request("https://sts.amazonaws.com/",data=body),timeout=30).read());ns={"s":"https://sts.amazonaws.com/doc/2011-06-15/"};c=root.find(".//s:Credentials",ns)
 return {"AccessKeyId":c.findtext("s:AccessKeyId",namespaces=ns),"SecretAccessKey":c.findtext("s:SecretAccessKey",namespaces=ns),"SessionToken":c.findtext("s:SessionToken",namespaces=ns)}
def env(c):
 e=os.environ.copy();e.update({"AWS_ACCESS_KEY_ID":c["AccessKeyId"],"AWS_SECRET_ACCESS_KEY":c["SecretAccessKey"],"AWS_SESSION_TOKEN":c["SessionToken"],"AWS_DEFAULT_REGION":R,"AWS_REGION":R,"AWS_EC2_METADATA_DISABLED":"true","AWS_PAGER":""});return e
def aws(e,a):
 p=subprocess.run(["aws",*a],env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
 if p.returncode:return {"ok":False,"error":p.stderr[-1500:]}
 try:return {"ok":True,"value":json.loads(p.stdout) if p.stdout.strip() else None}
 except:return {"ok":True,"value":p.stdout.strip()}
rep={"stage":"final"}
try:
 tok=mint();entry=assume_oidc(E,tok,"oidc-30b28c53");rep["entry_ok"]=True
except Exception as ex:
 rep["entry_error"]=str(ex);print(json.dumps(rep));raise SystemExit
ee=env(entry)
br=aws(ee,["sts","assume-role","--role-arn",B,"--role-session-name","recover-30b28c53","--external-id",BE,"--source-identity",SI,"--tags",f"Key=AmiId,Value={AMI}",f"Key=Attestation,Value={ATT}","--transitive-tag-keys","AmiId","Attestation","--output","json"])
rep["broker"]=br.get("ok");
if not br.get("ok"):rep["broker_err"]=br.get("error");print(json.dumps(rep));raise SystemExit
be=env(br["value"]["Credentials"])
fr=aws(be,["sts","assume-role","--role-arn",F,"--role-session-name","final-77c4c937","--external-id",FE,"--source-identity",SI,"--output","json"])
rep["final"]=fr.get("ok")
if not fr.get("ok"):rep["final_err"]=fr.get("error");print(json.dumps(rep));raise SystemExit
fe=env(fr["value"]["Credentials"])
sd=aws(fe,["ssm","get-parameter","--name",P,"--with-decryption","--output","json"])
if sd.get("ok"):rep["seed"]=sd["value"]["Parameter"]["Value"]
else:rep["seed_err"]=sd.get("error")
print(json.dumps(rep,indent=2,sort_keys=True))
