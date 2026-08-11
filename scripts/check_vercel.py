import urllib.request, json

VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'
deployment_id = 'dpl_AFXNAT2AVWx2kWdWx7xt28NacwAX'

req = urllib.request.Request(
    f'https://api.vercel.com/v13/deployments/{deployment_id}',
    headers={'Authorization': f'Bearer {VERCEL_TOKEN}'}
)
r = urllib.request.urlopen(req, timeout=10)
data = json.loads(r.read())
print('State:', data.get('state'))
print('URL:', data.get('url'))
print('Name:', data.get('name'))
